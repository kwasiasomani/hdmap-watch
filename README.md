# HDMap Watch

HDMap Watch compares lane-level HD maps with LiDAR observations to flag
potential map errors for human review. It uses Argoverse 2 data and saves
a CSV review queue, with optional uploads to AWS S3.

## What it does

- Checks lane geometry against bright ground-level LiDAR returns.
- Checks lane connections and neighboring-lane relationships.
- Scores lane segments and labels them PASS or REVIEW.

## Getting started

Requires Python 3.10 or later. From the project directory, install:

```bash
pip install -e ".[dev]"
pip install --no-deps av2==0.3.6
```

Install `av2` separately with `--no-deps` to skip unused heavyweight
dependencies. The dependencies used by this project are in `pyproject.toml`.

Run on a public Argoverse 2 log without AWS credentials:

```bash
python -m hdmap_watch.etl.run_etl \
  --log-id 02678d04-cc9f-3148-9f95-1ba66347dff9 \
  --no-upload
```

The command downloads the log, runs the checks, and writes
`out/review_queue_<log_id>.csv`.

To also upload the raw data and review queue to S3, configure AWS
credentials and replace `--no-upload` with `--bucket <your-bucket>`.

## Development

Run tests and lint:

```bash
pytest -q
ruff check .
```

See [the walkthrough notebook](notebooks/01_pipeline_walkthrough.ipynb)
for the QA logic, experiments, and known tradeoffs.

## Limitations

- Map/sensor alignment is not implemented, so pose errors can look like map errors.
- Geometry thresholds and risk scoring need calibration across more logs.
- Cropped map edges can produce false topology flags.
- Checks use existing map features in 2D; they do not discover missing features.
- Precision and recall have not yet been established with enough labeled data.

## License

MIT
