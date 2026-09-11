"""CLI: extract one log, run the QA transform, load raw + results to S3.

    python -m hdmap_watch.etl.run_etl --log-id <id> --bucket <bucket>
"""

from __future__ import annotations

import argparse
from pathlib import Path

from . import extract, load, transform


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hdmap-watch-etl")
    parser.add_argument("--split", default="val")
    parser.add_argument("--log-id", required=True)
    parser.add_argument("--bucket", help="required unless --no-upload is set")
    parser.add_argument("--data-root", default="data/av2_sensor")
    parser.add_argument("--out", default="out")
    parser.add_argument("--skip-upload-raw", action="store_true", help="skip re-uploading raw log data")
    parser.add_argument(
        "--no-upload", action="store_true", help="extract + transform only, no S3 access at all (no credentials needed)"
    )
    return parser


def run(args: argparse.Namespace) -> Path:
    log_dir = Path(args.data_root) / args.split / args.log_id

    print(f"[extract] {args.split}/{args.log_id} -> {log_dir}")
    extract.download_log(args.split, args.log_id, log_dir)

    print("[transform] running HD Map QA Engine + Risk Scoring")
    queue = transform.run_qa_pipeline(log_dir)
    n_review = int((queue["status"] == "REVIEW").sum())
    print(f"[transform] {len(queue)} segments scored, {n_review} flagged REVIEW")

    out_path = Path(args.out) / f"review_queue_{args.log_id}.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    queue.to_csv(out_path, index=False)

    if args.no_upload:
        print(f"[load] --no-upload set, skipping S3 entirely. Queue written to {out_path}")
        return out_path

    if not args.bucket:
        raise SystemExit("--bucket is required unless --no-upload is set")

    if not args.skip_upload_raw:
        print(f"[load] uploading raw log to s3://{args.bucket}/raw/{{maps,lidar}}/{args.log_id}/")
        n_uploaded = load.upload_raw_log(log_dir, args.bucket, args.log_id)
        print(f"[load] {n_uploaded} raw files uploaded")

    uri = load.upload_review_queue(out_path, args.bucket, args.log_id)
    print(f"[load] review queue uploaded to {uri}")
    return out_path


def main() -> None:
    args = build_parser().parse_args()
    run(args)


if __name__ == "__main__":
    main()
