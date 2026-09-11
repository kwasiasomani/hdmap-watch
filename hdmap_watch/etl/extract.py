"""Extract: pull one Argoverse 2 sensor log from the public AV2 bucket.

No AWS credentials needed — it's a public, unsigned bucket. Camera
images (~90% of a log's size) are skipped; this pipeline only uses the
map, LiDAR, and pose.
"""

from __future__ import annotations

from pathlib import Path

import boto3
from botocore import UNSIGNED
from botocore.config import Config

PUBLIC_BUCKET = "argoverse"
PUBLIC_REGION = "us-east-1"


def _public_client():
    return boto3.client("s3", region_name=PUBLIC_REGION, config=Config(signature_version=UNSIGNED))


def download_log(split: str, log_id: str, dest_dir: Path, skip_cameras: bool = True) -> Path:
    """Download one log's map/LiDAR/pose/calibration files. Idempotent:
    a file already present at its expected size is not re-downloaded."""
    client = _public_client()
    prefix = f"datasets/av2/sensor/{split}/{log_id}/"
    dest_dir.mkdir(parents=True, exist_ok=True)

    paginator = client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=PUBLIC_BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            rel = obj["Key"][len(prefix) :]
            if skip_cameras and rel.startswith("sensors/cameras/"):
                continue
            local_path = dest_dir / rel
            if local_path.exists() and local_path.stat().st_size == obj["Size"]:
                continue
            local_path.parent.mkdir(parents=True, exist_ok=True)
            client.download_file(PUBLIC_BUCKET, obj["Key"], str(local_path))

    return dest_dir
