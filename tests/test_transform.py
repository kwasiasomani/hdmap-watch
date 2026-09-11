import numpy as np
import pandas as pd
import pytest

from hdmap_watch.etl.transform import (
    combine_risk_scores,
    find_dangling_references,
    flag_by_threshold,
    mean_boundary_distance,
    pose_at,
    score_geometry,
)


def _xyz(points_2d: list[tuple[float, float]]) -> np.ndarray:
    return np.array([[x, y, 0.0] for x, y in points_2d])


# --- pose_at (transformation) --------------------------------------------


def test_pose_at_returns_nearest_pose_as_rotation_and_translation():
    pose = pd.DataFrame(
        {
            "timestamp_ns": [100, 200, 300],
            "qw": [1.0, 1.0, 1.0],
            "qx": [0.0, 0.0, 0.0],
            "qy": [0.0, 0.0, 0.0],
            "qz": [0.0, 0.0, 0.0],
            "tx_m": [0.0, 10.0, 20.0],
            "ty_m": [0.0, 0.0, 0.0],
            "tz_m": [0.0, 0.0, 0.0],
        }
    )

    R, t = pose_at(pose, timestamp_ns=190)

    np.testing.assert_allclose(R, np.eye(3), atol=1e-9)
    np.testing.assert_allclose(t, [10.0, 0.0, 0.0])


def test_pose_at_clamps_to_last_pose_past_the_end():
    pose = pd.DataFrame(
        {
            "timestamp_ns": [100, 200],
            "qw": [1.0, 1.0],
            "qx": [0.0, 0.0],
            "qy": [0.0, 0.0],
            "qz": [0.0, 0.0],
            "tx_m": [0.0, 5.0],
            "ty_m": [0.0, 0.0],
            "tz_m": [0.0, 0.0],
        }
    )

    _, t = pose_at(pose, timestamp_ns=999)

    np.testing.assert_allclose(t, [5.0, 0.0, 0.0])


def test_pose_at_applies_a_90_degree_yaw_rotation():
    # qw,qz = cos(45deg), sin(45deg) -> 90 degree rotation about z
    c = np.cos(np.pi / 4)
    pose = pd.DataFrame(
        {
            "timestamp_ns": [0],
            "qw": [c],
            "qx": [0.0],
            "qy": [0.0],
            "qz": [c],
            "tx_m": [0.0],
            "ty_m": [0.0],
            "tz_m": [0.0],
        }
    )

    R, t = pose_at(pose, timestamp_ns=0)
    rotated = np.array([1.0, 0.0, 0.0]) @ R.T + t

    np.testing.assert_allclose(rotated, [0.0, 1.0, 0.0], atol=1e-9)


# --- score_geometry (Geometry QA) -----------------------------------------


def test_score_geometry_flags_an_observed_boundary_whose_evidence_is_offset():
    # segment 1's vertices sit right on top of their own evidence cluster
    # (residual ~0, not flagged). segment 2's vertices are each 1.5m from
    # their nearest evidence -- close enough to be "observed" (within the
    # 2.0m radius) but far enough to exceed the 1.0m suspicion threshold.
    verts = _xyz([(0, 0), (1, 0), (5, 5), (6, 5)])
    seg_ids = np.array([1, 1, 2, 2])

    def small_cluster(center: tuple[float, float]) -> np.ndarray:
        cx, cy = center
        return _xyz([(cx, cy), (cx + 0.1, cy), (cx - 0.1, cy), (cx, cy + 0.1), (cx, cy - 0.1)])

    seg1_evidence = np.concatenate([small_cluster((0, 0)), small_cluster((1, 0))])
    seg2_evidence = np.concatenate([small_cluster((6.5, 5)), small_cluster((7.5, 5))])  # +1.5m offset
    ground_pts = np.concatenate([seg1_evidence, seg2_evidence])
    ground_intensity = np.full(len(ground_pts), 200.0)  # all "bright" -> percentile filter keeps everything

    result = score_geometry(
        verts,
        seg_ids,
        ground_pts,
        ground_intensity,
        bright_percentile=0,
        observability_radius_m=2.0,
        observability_min_points=3,
        suspicion_threshold_m=1.0,
    )

    assert result["flagged_segments"] == {2}
    assert result["n_observed"] == 4  # all four vertices have enough nearby evidence to be scored


def test_score_geometry_does_not_flag_unobserved_vertices():
    verts = _xyz([(100, 100)])  # far from any ground point
    seg_ids = np.array([1])
    ground_pts = _xyz([(0, 0)] * 10)
    ground_intensity = np.full(10, 200.0)

    result = score_geometry(verts, seg_ids, ground_pts, ground_intensity, bright_percentile=0)

    assert result["flagged_segments"] == set()
    assert result["n_observed"] == 0


def test_score_geometry_handles_empty_ground_points():
    verts = _xyz([(0, 0)])
    seg_ids = np.array([1])

    result = score_geometry(verts, seg_ids, np.empty((0, 3)), np.empty(0))

    assert result["flagged_segments"] == set()
    assert result["n_observed"] == 0


# --- find_dangling_references (Topology QA) -------------------------------


def test_find_dangling_references_ignores_refs_near_the_tile_edge():
    segments = [
        {"id": 1, "successors": [999], "predecessors": [], "start_xy": (0, 0), "end_xy": (0.5, 0.5)},
    ]
    # tile spans (0,0) to (100,100); segment 1's dangling successor endpoint
    # (0.5, 0.5) is right at the corner -> within any reasonable margin
    result = find_dangling_references(segments, tile_bounds=(0, 100, 0, 100), tile_edge_margin_m=15.0)

    assert result["n_dangling_total"] == 1
    assert result["flagged_segments"] == set()  # near-edge, not a real defect


def test_find_dangling_references_flags_interior_dangling_refs():
    segments = [
        {"id": 1, "successors": [999], "predecessors": [], "start_xy": (0, 0), "end_xy": (50, 50)},
    ]
    # endpoint (50,50) is dead center of a (0,100)x(0,100) tile -> not an edge artifact
    result = find_dangling_references(segments, tile_bounds=(0, 100, 0, 100), tile_edge_margin_m=15.0)

    assert result["n_dangling_total"] == 1
    assert result["flagged_segments"] == {1}


def test_find_dangling_references_ignores_valid_references():
    segments = [
        {"id": 1, "successors": [2], "predecessors": [], "start_xy": (0, 0), "end_xy": (50, 50)},
        {"id": 2, "successors": [], "predecessors": [1], "start_xy": (50, 50), "end_xy": (60, 60)},
    ]
    result = find_dangling_references(segments, tile_bounds=(0, 100, 0, 100))

    assert result["n_dangling_total"] == 0
    assert result["flagged_segments"] == set()


# --- mean_boundary_distance / flag_by_threshold (Semantic QA) -------------


def test_mean_boundary_distance_is_nearest_point_not_index_matched():
    # two parallel lines, offset by 4m, sampled in OPPOSITE directions and
    # at different densities -- index-matching these would give a huge
    # distance; nearest-point matching should give ~4m regardless
    a = _xyz([(0, 0), (5, 0), (10, 0)])
    b = _xyz([(10, 4), (5, 4), (0, 4), (2.5, 4), (7.5, 4)])  # reversed order, denser

    d = mean_boundary_distance(a, b)

    assert d == pytest.approx(4.0, abs=1e-6)


def test_flag_by_threshold():
    values = {1: 1.0, 2: 9.0, 3: 8.1, 4: 8.0}

    flagged = flag_by_threshold(values, threshold=8.0)

    assert flagged == {2, 3}  # strictly greater than; 8.0 itself is not flagged


# --- combine_risk_scores (Risk Scoring) -----------------------------------


def test_combine_risk_scores_counts_votes_and_sorts_descending():
    queue = combine_risk_scores(
        segment_ids=[1, 2, 3],
        geometry_flagged={1, 2},
        topology_flagged={2},
        semantic_flagged={2, 3},
    )

    by_id = queue.set_index("segment_id")
    assert by_id.loc[1, "risk"] == 1
    assert by_id.loc[2, "risk"] == 3
    assert by_id.loc[3, "risk"] == 1
    assert list(queue["segment_id"]) == [2, 1, 3] or list(queue["segment_id"]) == [2, 3, 1]
    assert by_id.loc[2, "status"] == "REVIEW"


def test_combine_risk_scores_pass_when_no_check_fires():
    queue = combine_risk_scores([1], geometry_flagged=set(), topology_flagged=set(), semantic_flagged=set())

    assert queue.iloc[0]["risk"] == 0
    assert queue.iloc[0]["status"] == "PASS"
