import boto3
import pytest
from moto import mock_aws

from hdmap_watch.etl import load

BUCKET = "test-bucket"


@pytest.fixture
def s3_bucket():
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        client.create_bucket(Bucket=BUCKET)
        yield client


def test_upload_raw_log_splits_lidar_and_maps(tmp_path, s3_bucket):
    log_dir = tmp_path / "log"
    (log_dir / "map").mkdir(parents=True)
    (log_dir / "sensors/lidar").mkdir(parents=True)
    (log_dir / "sensors/cameras/ring_front_center").mkdir(parents=True)
    (log_dir / "map" / "log_map_archive.json").write_text("{}")
    (log_dir / "city_SE3_egovehicle.feather").write_bytes(b"pose")
    (log_dir / "sensors/lidar/000.feather").write_bytes(b"sweep")
    (log_dir / "sensors/cameras/ring_front_center" / "000.jpg").write_bytes(b"img")

    n_uploaded = load.upload_raw_log(log_dir, BUCKET, "log123")

    keys = {obj["Key"] for obj in s3_bucket.list_objects_v2(Bucket=BUCKET)["Contents"]}
    assert keys == {
        "raw/maps/log123/map/log_map_archive.json",
        "raw/maps/log123/city_SE3_egovehicle.feather",
        "raw/lidar/log123/000.feather",
    }
    assert n_uploaded == 3  # camera file excluded


def test_upload_review_queue(tmp_path, s3_bucket):
    csv_path = tmp_path / "queue.csv"
    csv_path.write_text("segment_id,risk,status\n1,2,REVIEW\n")

    uri = load.upload_review_queue(csv_path, BUCKET, "log123")

    assert uri == f"s3://{BUCKET}/processed/review_queue/log123.csv"
    body = s3_bucket.get_object(Bucket=BUCKET, Key="processed/review_queue/log123.csv")["Body"].read()
    assert b"REVIEW" in body
