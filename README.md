# HDMap Watch

Compare Argoverse 2 lane maps with LiDAR observations and rank potential errors for human review. The dashboard shows lane geometry, risk scores, and a filterable review queue.

## Run the dashboard

Requires Node.js and npm (CI uses Node 20).

```bash
cd site
npm ci
npm run dev
```

Open the local URL printed by Vite. Pittsburgh and Miami data are included; AWS is not required. Run `npm run build` to create `site/dist/`.

## Run the data pipeline

Use Python 3.11 or 3.12 (CI uses 3.12); the pinned AV2 package has no Python 3.14 wheel.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pip install --no-deps av2==0.3.6
python -m hdmap_watch.etl.run_etl \
  --log-id 02678d04-cc9f-3148-9f95-1ba66347dff9 --no-upload
```

AV2 is installed separately to avoid its unused heavyweight dependencies. The pipeline downloads public map, LiDAR, and pose data and writes `out/review_queue_<log_id>.csv`.

For S3, configure AWS credentials locally and replace `--no-upload` with `--bucket YOUR_BUCKET`. This uploads raw data under `raw/maps/` and `raw/lidar/`, and results under `processed/review_queue/`. Add `--skip-upload-raw` to upload only the results. Uploading does not refresh the dashboard's bundled JSON.

## Checks and limitations

Run `pytest -q` and `ruff check .` from the project root; run `npm run build` inside `site/`.

Geometry, topology, and neighbor checks contribute one risk vote each. A score of 1–3 means REVIEW; PASS means no check fired, not proof of correctness. Alignment errors, limited observations, and heuristic thresholds can affect results; precision and recall are not yet established.

The [executed notebook](notebooks/01_pipeline_walkthrough.ipynb) shows real LiDAR, coordinate transforms, and QA results. Its [PNG figures](notebooks/images/) are ready to view or share. On this Mac, select `.venv/notebook/bin/python` as its kernel.

[Interview and learning guide](reamd_lear.md) · [Walkthrough notebook](notebooks/01_pipeline_walkthrough.ipynb) · [MIT license](LICENSE)
