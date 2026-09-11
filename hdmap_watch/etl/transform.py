"""Transform: HD Map QA Engine.

Promoted from notebooks/01_pipeline_walkthrough.ipynb, where every
threshold below was chosen by looking at its effect on real data before
being hardcoded here — see the notebook for that derivation and for the
two cases (Geometry QA, Topology QA) where a first attempt was wrong.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from av2.geometry.geometry import quat_to_mat
from av2.map.map_api import ArgoverseStaticMap
from scipy.spatial import cKDTree

OBSERVABILITY_RADIUS_M = 2.0
OBSERVABILITY_MIN_POINTS = 5
SUSPICION_THRESHOLD_M = 1.0
BRIGHT_PERCENTILE = 90
TILE_EDGE_MARGIN_M = 15.0
NEIGHBOR_DISTANCE_THRESHOLD_M = 8.0


@dataclass
class MapLog:
    log_dir: Path
    avm: ArgoverseStaticMap
    lane_segments: list
    by_id: dict
    pose: pd.DataFrame
    lidar_files: list[Path]


def load_log(log_dir: Path) -> MapLog:
    avm = ArgoverseStaticMap.from_map_dir(log_dir / "map", build_raster=True)
    lane_segments = avm.get_scenario_lane_segments()
    pose = (
        pd.read_feather(log_dir / "city_SE3_egovehicle.feather")
        .sort_values("timestamp_ns")
        .reset_index(drop=True)
    )
    lidar_files = sorted((log_dir / "sensors/lidar").glob("*.feather"))
    return MapLog(
        log_dir=log_dir,
        avm=avm,
        lane_segments=lane_segments,
        by_id={ls.id: ls for ls in lane_segments},
        pose=pose,
        lidar_files=lidar_files,
    )


def pose_at(pose: pd.DataFrame, timestamp_ns: int) -> tuple[np.ndarray, np.ndarray]:
    """Nearest city_SE3_egovehicle pose to a given timestamp: (R, t)."""
    pose_ts = pose["timestamp_ns"].to_numpy()
    idx = min(np.searchsorted(pose_ts, timestamp_ns), len(pose) - 1)
    row = pose.iloc[idx]
    R = quat_to_mat(row[["qw", "qx", "qy", "qz"]].to_numpy(dtype=float))
    t = row[["tx_m", "ty_m", "tz_m"]].to_numpy(dtype=float)
    return R, t


def sweep_to_city(path: Path, pose: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    df = pd.read_feather(path)
    xyz_ego = df[["x", "y", "z"]].to_numpy()
    R, t = pose_at(pose, int(path.stem))
    return xyz_ego @ R.T + t, df["intensity"].to_numpy()


def accumulate_ground_points(log: MapLog) -> tuple[np.ndarray, np.ndarray]:
    """Every sweep, in the city frame, filtered to ground-level points."""
    city_parts, intensity_parts = zip(*(sweep_to_city(f, log.pose) for f in log.lidar_files))
    all_pts = np.concatenate(city_parts, axis=0)
    all_intensity = np.concatenate(intensity_parts, axis=0)
    ground_mask = log.avm.get_ground_points_boolean(all_pts)
    return all_pts[ground_mask], all_intensity[ground_mask]


def _boundary_vertices(log: MapLog) -> tuple[np.ndarray, np.ndarray]:
    verts, seg_ids = [], []
    for ls in log.lane_segments:
        for boundary in (ls.left_lane_boundary, ls.right_lane_boundary):
            verts.append(boundary.xyz)
            seg_ids += [ls.id] * len(boundary.xyz)
    return np.concatenate(verts, axis=0), np.array(seg_ids)


def score_geometry(
    verts: np.ndarray,
    seg_ids: np.ndarray,
    ground_pts: np.ndarray,
    ground_intensity: np.ndarray,
    bright_percentile: float = BRIGHT_PERCENTILE,
    observability_radius_m: float = OBSERVABILITY_RADIUS_M,
    observability_min_points: int = OBSERVABILITY_MIN_POINTS,
    suspicion_threshold_m: float = SUSPICION_THRESHOLD_M,
) -> dict:
    """LiDAR residual vs. candidate lane-marking points (brightest ground returns).

    Pure numpy — no av2 map object needed, so this is unit-testable with
    synthetic points. A raw ground-point tree can't tell lane paint from
    bare pavement; see the notebook's Geometry QA section for the failed
    first attempt this intensity filter replaced.
    """
    if len(ground_pts) == 0:
        return {
            "flagged_segments": set(),
            "n_vertices": len(verts),
            "n_observed": 0,
            "median_residual_observed": None,
        }

    bright_threshold = np.percentile(ground_intensity, bright_percentile)
    bright_pts = ground_pts[ground_intensity >= bright_threshold]
    tree = cKDTree(bright_pts[:, :2])

    residual, _ = tree.query(verts[:, :2], k=1)
    neighbor_count = tree.query_ball_point(verts[:, :2], r=observability_radius_m, return_length=True)
    observed = neighbor_count >= observability_min_points
    flagged_segments = set(seg_ids[observed & (residual > suspicion_threshold_m)])

    return {
        "flagged_segments": flagged_segments,
        "n_vertices": len(verts),
        "n_observed": int(observed.sum()),
        "median_residual_observed": float(np.median(residual[observed])) if observed.any() else None,
    }


def geometry_qa(
    log: MapLog,
    ground_pts: np.ndarray,
    ground_intensity: np.ndarray,
    **kwargs,
) -> dict:
    verts, seg_ids = _boundary_vertices(log)
    return score_geometry(verts, seg_ids, ground_pts, ground_intensity, **kwargs)


def find_dangling_references(
    segments: list[dict],
    tile_bounds: tuple[float, float, float, float],
    tile_edge_margin_m: float = TILE_EDGE_MARGIN_M,
) -> dict:
    """Dangling successor/predecessor references, away from the tile edge.

    Pure — takes plain dicts, not av2 LaneSegment objects, so this is
    unit-testable without a real map. Each segment dict needs: id,
    successors, predecessors, start_xy, end_xy. `tile_bounds` is
    (xmin, xmax, ymin, ymax) over the whole map, used to tell "this
    reference points outside the map because the tile was cropped here"
    apart from "this reference points at an id that just doesn't exist" —
    see the notebook's Topology QA section for why that distinction
    matters (17 raw hits, 15-16 of them tile-crop artifacts).
    """
    ids = {s["id"] for s in segments}
    xmin, xmax, ymin, ymax = tile_bounds

    def near_tile_edge(xy: tuple[float, float]) -> bool:
        x, y = xy
        return (
            x - xmin < tile_edge_margin_m
            or xmax - x < tile_edge_margin_m
            or y - ymin < tile_edge_margin_m
            or ymax - y < tile_edge_margin_m
        )

    dangling, interior = [], []
    for seg in segments:
        for kind, refs, endpoint in [
            ("successor", seg["successors"], seg["end_xy"]),
            ("predecessor", seg["predecessors"], seg["start_xy"]),
        ]:
            for ref in refs:
                if ref not in ids:
                    dangling.append((seg["id"], kind, ref))
                    if not near_tile_edge(endpoint):
                        interior.append(seg["id"])

    return {
        "flagged_segments": set(interior),
        "n_dangling_total": len(dangling),
        "n_dangling_interior": len(interior),
    }


def topology_qa(log: MapLog, tile_edge_margin_m: float = TILE_EDGE_MARGIN_M) -> dict:
    all_x = np.concatenate([ls.left_lane_boundary.xyz[:, 0] for ls in log.lane_segments])
    all_y = np.concatenate([ls.left_lane_boundary.xyz[:, 1] for ls in log.lane_segments])
    tile_bounds = (all_x.min(), all_x.max(), all_y.min(), all_y.max())

    segments = [
        {
            "id": ls.id,
            "successors": ls.successors,
            "predecessors": ls.predecessors,
            "start_xy": tuple(ls.left_lane_boundary.xyz[0, :2]),
            "end_xy": tuple(ls.left_lane_boundary.xyz[-1, :2]),
        }
        for ls in log.lane_segments
    ]
    return find_dangling_references(segments, tile_bounds, tile_edge_margin_m)


def mean_boundary_distance(a_xyz: np.ndarray, b_xyz: np.ndarray) -> float:
    """Mean nearest-point distance from every point of `a_xyz` to `b_xyz`.

    Deliberately nearest-point (KD-tree), not index-matched — two lanes'
    boundary polylines aren't guaranteed to be sampled in the same
    direction or density. See the notebook for the index-matching bug
    (up to 130m on real, correct neighbor pairs) this replaced.
    """
    tree = cKDTree(b_xyz[:, :2])
    d, _ = tree.query(a_xyz[:, :2], k=1)
    return float(d.mean())


def flag_by_threshold(values: dict[int, float], threshold: float) -> set[int]:
    return {key for key, value in values.items() if value > threshold}


def semantic_qa(log: MapLog, neighbor_distance_threshold_m: float = NEIGHBOR_DISTANCE_THRESHOLD_M) -> dict:
    """Declared left-neighbor plausibility: should be ~1 lane-width away."""
    distances = {}
    for ls in log.lane_segments:
        if ls.left_neighbor_id is not None and ls.left_neighbor_id in log.by_id:
            nb = log.by_id[ls.left_neighbor_id]
            distances[ls.id] = mean_boundary_distance(ls.left_lane_boundary.xyz, nb.right_lane_boundary.xyz)

    return {
        "flagged_segments": flag_by_threshold(distances, neighbor_distance_threshold_m),
        "n_checked": len(distances),
        "median_distance": float(np.median(list(distances.values()))) if distances else None,
    }


def combine_risk_scores(
    segment_ids: list[int],
    geometry_flagged: set[int],
    topology_flagged: set[int],
    semantic_flagged: set[int],
) -> pd.DataFrame:
    """Unweighted vote across the three QA checks. See the notebook's Risk
    Scoring section for the known, unresolved aggregation tension this
    simple rule doesn't solve."""
    rows = [
        {
            "segment_id": seg_id,
            "risk": int(seg_id in geometry_flagged) + int(seg_id in topology_flagged) + int(seg_id in semantic_flagged),
        }
        for seg_id in segment_ids
    ]
    queue = pd.DataFrame(rows).sort_values("risk", ascending=False).reset_index(drop=True)
    queue["status"] = np.where(queue["risk"] >= 1, "REVIEW", "PASS")
    return queue


def risk_score(log: MapLog, geometry: dict, topology: dict, semantic: dict) -> pd.DataFrame:
    segment_ids = [ls.id for ls in log.lane_segments]
    return combine_risk_scores(
        segment_ids, geometry["flagged_segments"], topology["flagged_segments"], semantic["flagged_segments"]
    )


def run_qa_pipeline(log_dir: Path) -> pd.DataFrame:
    """The whole HD Map QA Engine + Risk Scoring, for one log."""
    log = load_log(log_dir)
    ground_pts, ground_intensity = accumulate_ground_points(log)
    geometry = geometry_qa(log, ground_pts, ground_intensity)
    topology = topology_qa(log)
    semantic = semantic_qa(log)
    return risk_score(log, geometry, topology, semantic)
