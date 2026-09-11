"""Load: push raw log data and QA results into our private S3 bucket.

Layout, matching the target architecture:
  s3://<bucket>/raw/maps/<log_id>/...              map, pose, calibration
  s3://<bucket>/raw/lidar/<log_id>/...              LiDAR sweeps
  s3://<bucket>/processed/review_queue/<log_id>.csv the Priority Queue
"""

from __future__ import annotations

from pathlib import Path

import boto3

LIDAR_REL_PREFIX = Path("sensors/lidar")
CAMERA_REL_PREFIX = Path("sensors/cameras")


def upload_raw_log(local_log_dir: Path, bucket: str, log_id: str) -> int:
    """Upload a downloaded log's map/pose/calibration/LiDAR files. Returns
    the number of files uploaded."""
    client = boto3.client("s3")
    n_uploaded = 0
    for path in local_log_dir.rglob("*"):
        if path.is_dir():
            continue
        rel = path.relative_to(local_log_dir)
        if str(rel).startswith(str(CAMERA_REL_PREFIX)):
            continue
        if str(rel).startswith(str(LIDAR_REL_PREFIX)):
            key = f"raw/lidar/{log_id}/{rel.relative_to(LIDAR_REL_PREFIX)}"
        else:
            key = f"raw/maps/{log_id}/{rel}"
        client.upload_file(str(path), bucket, key)
        n_uploaded += 1
    return n_uploaded


def upload_review_queue(local_csv: Path, bucket: str, log_id: str) -> str:
    client = boto3.client("s3")
    key = f"processed/review_queue/{log_id}.csv"
    client.upload_file(str(local_csv), bucket, key)
    return f"s3://{bucket}/{key}"
