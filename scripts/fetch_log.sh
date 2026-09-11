#!/usr/bin/env bash
# Download one Argoverse 2 sensor log: HD map, LiDAR sweeps, ego pose,
# and calibration. Skips the camera images (~90% of a log's size) since
# this project only needs the map and LiDAR.
#
# Usage: scripts/fetch_log.sh [split] [log_id]
#   split  train | val | test   (default: val)
#   log_id an AV2 sensor log id (default: a known-good Pittsburgh log)
set -euo pipefail

SPLIT="${1:-val}"
LOG_ID="${2:-02678d04-cc9f-3148-9f95-1ba66347dff9}"
DEST="data/av2_sensor/${SPLIT}/${LOG_ID}"

mkdir -p "$DEST"

aws s3 sync \
  "s3://argoverse/datasets/av2/sensor/${SPLIT}/${LOG_ID}/" \
  "$DEST" \
  --exclude "sensors/cameras/*" \
  --no-sign-request \
  --region us-east-1

echo "Downloaded to $DEST"
du -sh "$DEST"
