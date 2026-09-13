"""Build the JSON bundle behind site/index.html's map + queue view.

    python scripts/build_viz_data.py <log_id> [--split val] [--out site/_data.json]

Prints the bundle to stdout by default; useful once more logs are added
(one bundle per log, swapped in via the page's log selector).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from hdmap_watch.etl import transform

CITY_NAMES = {
    "ATX": "Austin",
    "DTW": "Detroit",
    "MIA": "Miami",
    "PAO": "Palo Alto",
    "PIT": "Pittsburgh",
    "WDC": "Washington DC",
}


def _city_code(log_dir: Path) -> str:
    for path in (log_dir / "map").glob("log_map_archive_*.json"):
        parts = path.stem.split("____")
        if len(parts) == 2:
            return parts[1].split("_city")[0]
    return "UNKNOWN"


def build(log_dir: Path) -> dict:
    city_code = _city_code(log_dir)
    log = transform.load_log(log_dir)
    ground_pts, ground_intensity = transform.accumulate_ground_points(log)
    geometry = transform.geometry_qa(log, ground_pts, ground_intensity)
    topology = transform.topology_qa(log)
    semantic = transform.semantic_qa(log)
    queue = transform.risk_score(log, geometry, topology, semantic)

    risk_by_id = dict(zip(queue["segment_id"], queue["risk"]))
    status_by_id = dict(zip(queue["segment_id"], queue["status"]))

    segments = []
    for ls in log.lane_segments:
        checks = [
            name
            for name, result in [("geometry", geometry), ("topology", topology), ("semantic", semantic)]
            if ls.id in result["flagged_segments"]
        ]
        segments.append(
            {
                "id": int(ls.id),
                "risk": int(risk_by_id[ls.id]),
                "status": status_by_id[ls.id],
                "checks": checks,
                "is_intersection": bool(ls.is_intersection),
                "left": np.round(ls.left_lane_boundary.xyz[:, :2], 2).tolist(),
                "right": np.round(ls.right_lane_boundary.xyz[:, :2], 2).tolist(),
            }
        )

    all_x = np.concatenate([np.array(s["left"] + s["right"])[:, 0] for s in segments])
    all_y = np.concatenate([np.array(s["left"] + s["right"])[:, 1] for s in segments])

    return {
        "log_id": log_dir.name,
        "city": city_code,
        "city_name": CITY_NAMES.get(city_code, city_code),
        "bounds": {
            "xmin": float(all_x.min()),
            "xmax": float(all_x.max()),
            "ymin": float(all_y.min()),
            "ymax": float(all_y.max()),
        },
        "summary": {
            "total": len(segments),
            "pass": int((queue["status"] == "PASS").sum()),
            "review": int((queue["status"] == "REVIEW").sum()),
            "geometry_flagged": len(geometry["flagged_segments"]),
            "topology_flagged": len(topology["flagged_segments"]),
            "semantic_flagged": len(semantic["flagged_segments"]),
        },
        "segments": segments,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("log_id")
    parser.add_argument("--split", default="val")
    parser.add_argument("--data-root", default="data/av2_sensor")
    parser.add_argument("--out", help="write here instead of stdout")
    args = parser.parse_args()

    bundle = build(Path(args.data_root) / args.split / args.log_id)
    text = json.dumps(bundle)
    if args.out:
        Path(args.out).write_text(text)
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
