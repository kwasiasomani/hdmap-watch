# HDMap Watch — LiDAR-Based HD Map Change Detection & Validation Pipeline

**Detects potentially stale or incorrect lane-level HD-map features by
comparing map geometry and topology against LiDAR observations, then
ranks suspicious features for human review.**

An HD map for a single urban district contains tens of thousands of
lane-level features: lane boundaries, centerlines, connectivity between
lanes, neighbor relationships. Every one of them can be wrong — surveyed
incorrectly, invalidated by construction, or degraded by a localization
error during capture. Checking them by hand doesn't scale, but *most
features are fine* — so the job isn't inspection, it's triage: score
every feature, and return a queue short enough for a specialist to work
through in an afternoon while still containing nearly all the genuine
defects.

The metric that matters is therefore not accuracy in the abstract. It is:

> **What fraction of features must a human review to catch a given
> fraction of real defects?**

---

## Architecture

```
                    HD Map + LiDAR Point Cloud
                              |
                              v
                        AWS S3 (real)
              raw/maps/<log_id>/, raw/lidar/<log_id>/
                              |
                              v
                   Point Cloud Processor
        target: Open3D — accumulate, downsample, align
        today:  NumPy accumulation + map-raster ground filter
                              |
                              v
                Map / Sensor Alignment
              NOT YET IMPLEMENTED — see Limitations
                              |
                              v
                    HD Map QA Engine
                /             |              \
         Geometry QA     Topology QA     Semantic QA
        LiDAR residual   dangling lane   declared-neighbor
        vs. lane paint    references     plausibility
                \             |              /
                 \            |             /
                        Risk Scoring
              unweighted vote across the 3 checks
                              |
                              v
                       Priority Queue
                              |
                  +-----------+-----------+
                  |                       |
                  v                       v
                PASS                  REVIEW
                                          |
                                          v
                        AWS S3 (real): processed/review_queue/
                                          |
                                          v
                                  Discord Alert
                              real payload, dry-run today
                                          |
                                          v
                               Mapping Specialist
```

Boxes marked **(real)** are actual, running AWS infrastructure — an S3
bucket this pipeline extracts from, transforms, and loads into on every
run, not a diagram of intent. Everything else is described honestly in
[Status](#status).

---

## ETL

The pipeline is a straightforward Extract → Transform → Load, in
`hdmap_watch/etl/`:

| Stage | Module | What it does |
|---|---|---|
| **Extract** | `extract.py` | Pulls one log's map, LiDAR, and pose from the public Argoverse 2 bucket (unsigned, no credentials needed). Idempotent — re-running skips files already downloaded at the right size. |
| **Transform** | `transform.py` | The HD Map QA Engine: accumulates LiDAR into the city frame, ground-filters it, then runs Geometry QA, Topology QA, and Semantic QA, and combines them into a per-segment Risk Score and a PASS/REVIEW Priority Queue. Promoted from `notebooks/01_pipeline_walkthrough.ipynb`, where every threshold here was derived by looking at real data first. |
| **Load** | `load.py` | Uploads the raw log to `s3://<bucket>/raw/{maps,lidar}/<log_id>/` and the scored queue to `s3://<bucket>/processed/review_queue/<log_id>.csv`. |

Run the whole thing end to end:

```bash
python -m hdmap_watch.etl.run_etl \
  --log-id 02678d04-cc9f-3148-9f95-1ba66347dff9 \
  --bucket <your-bucket>
```

Or extract + transform only, with no AWS credentials at all:

```bash
python -m hdmap_watch.etl.run_etl \
  --log-id 02678d04-cc9f-3148-9f95-1ba66347dff9 \
  --no-upload
```

This has been run for real against `s3://hdmap-watch-455515343653` in
`us-west-2` (private, public access blocked, SSE-AES256 default
encryption) — 92 lane segments scored, 42 flagged REVIEW, 164 raw files
plus the review queue landing in S3.

---

## Notebook: `notebooks/01_pipeline_walkthrough.ipynb`

This is where the QA logic was designed and is still the place to read
the reasoning, including — worth reading even if you skip the code —
**two places where the first implementation failed, and one place where
a fix that looked obviously correct wasn't**, documented rather than
edited out:

- **Geometry QA, attempt 1, fails.** A synthetic 0.6m lateral shift of a
  real lane boundary went undetected, because matching against *any*
  nearby ground-level LiDAR point can't tell painted lane markings apart
  from ordinary pavement. Fixed by filtering to the brightest ground
  returns (LiDAR intensity, a proxy for retroreflective paint) before
  matching.
- **Topology QA, naive version over-fires.** Flagging every dangling
  `successor`/`predecessor` reference produced 17 hits on a 92-segment
  map; 15–16 of them were just where this log's map tile happened to be
  cropped, not real defects. Filtering by distance to the tile edge
  fixes most of it — one case landed close enough to the margin that
  calling it resolved rather than a judgment call would oversell it.
- **Risk Scoring's aggregation rule is an open problem, not a solved
  one.** Flagging a segment if *any* boundary vertex exceeds the
  residual threshold catches 58% of observed segments — too many for a
  usable queue. Switching to the *median* vertex per segment cuts that
  to 9%, but also misses the injected defect used to prove Geometry QA
  works at all. The pipeline keeps the noisier rule and says so, rather
  than picking whichever one makes the demo look cleaner.

It also has a cheat-sheet section at the end for explaining the
project's reasoning out loud.

---

## CI/CD

Two GitHub Actions workflows, in `.github/workflows/`:

- **`ci.yml`** — every push/PR: install, `ruff check`, `pytest`. Fast,
  no AWS, no data download. `tests/test_etl_load.py` mocks S3 with
  `moto`, so the Load stage is tested without touching real AWS.
- **`etl-smoke.yml`** — manual dispatch (pick a log id/split) plus a
  weekly schedule. Always runs Extract + Transform against a real
  public log (no credentials needed) and uploads the resulting queue as
  a workflow artifact. If the repo has `AWS_ACCESS_KEY_ID`,
  `AWS_SECRET_ACCESS_KEY`, and `HDMAP_WATCH_BUCKET` configured under
  *Settings → Secrets and variables → Actions*, it also loads the
  result into S3; otherwise it's a credential-free smoke test.

These are committed but not pushed — review them before pushing so
`etl-smoke.yml`'s schedule doesn't start firing on a fork or repo you
don't intend it to.

---

## Status

| Stage | Target | Today |
|---|---|---|
| Ingestion / Load | S3, fleet of jobs | **Real S3 bucket**, `hdmap_watch/etl/extract.py` + `load.py`, one log at a time |
| Point Cloud Processor | Open3D | NumPy accumulation + AV2's map-raster ground filter, in `transform.py` |
| Map/Sensor Alignment | Rigid (ICP) alignment | **Not implemented** — the single biggest gap; see Limitations |
| Geometry QA | Calibrated, multi-log | Working, single-log, intensity-based lane-marking proxy |
| Topology QA | Full city graph | Working, single-tile, edge-cropping caveat documented |
| Semantic QA | Multiple semantic invariants | One check: declared-neighbor geometric plausibility |
| Risk Scoring | Calibrated weights | Unweighted vote; aggregation problem open (see notebook) |
| Priority Queue / PASS-REVIEW | — | Working |
| Discord Alert | Live webhook | Real payload code, dry-run (no webhook configured) |
| Mapping Specialist hand-off | Review UI | CSV in S3 (`processed/review_queue/<log_id>.csv`) |
| CI/CD | Automated eval on push | **Implemented** — `ci.yml` + `etl-smoke.yml` |

---

## Data

Argoverse 2's sensor dataset ships exactly the three things this needs
per log: an HD map, LiDAR sweeps, and ego pose.

```bash
scripts/fetch_log.sh val 02678d04-cc9f-3148-9f95-1ba66347dff9
```

or equivalently `python -m hdmap_watch.etl.extract`, called by the ETL
CLI above. Skips camera images (~90% of a log's size, unused here). No
AWS credentials needed for this step — it's a public, unsigned bucket.
~150MB per log.

| Source | Role |
|---|---|
| [Argoverse 2](https://www.argoverse.org/av2.html) | Lane-level HD maps, LiDAR sweeps, ego pose |
| [nuScenes](https://www.nuscenes.org/) | Alternative, smaller, HD maps included |

---

## Getting started

```bash
git clone <this repo>
cd hdmap-watch
pip install -e ".[dev]"
pip install --no-deps av2==0.3.6  # see "A note on av2's dependencies" below

# whole ETL, real AWS bucket you control:
python -m hdmap_watch.etl.run_etl --log-id 02678d04-cc9f-3148-9f95-1ba66347dff9 --bucket <your-bucket>

# or no AWS at all:
python -m hdmap_watch.etl.run_etl --log-id 02678d04-cc9f-3148-9f95-1ba66347dff9 --no-upload

# tests + lint
pytest -q
ruff check .

# the full walkthrough with the design reasoning
jupyter lab notebooks/01_pipeline_walkthrough.ipynb
```

### A note on av2's dependencies

`av2` (the Argoverse 2 devkit) declares `torch`, the full NVIDIA CUDA
toolkit, `kornia`, `numba`, and `polars` as required dependencies —
~7GB installed, and enough to run a GitHub Actions runner out of disk
mid-install (this happened; see `git log`). None of it is touched by
the two av2 modules this project actually imports
(`av2.geometry.geometry`, `av2.map.map_api`). Their real,
verified-by-import-error import-time dependencies are `matplotlib`,
`opencv-python-headless`, `pillow`, and `universal-pathlib` — all
listed directly in `pyproject.toml`. Installing `av2` itself with
`--no-deps` skips the rest. Both CI workflows do this in a separate
step after the main install. Total environment: ~900MB instead of ~7GB.

---

## Why alignment and observability come before scoring

**Alignment (target, not yet built).** Without it, a small pose error
shifts every feature in the log and the detector flags the entire map.
Misalignment is a sensor problem masquerading as a map problem, and
separating the two is most of the work — which is exactly why its
absence is the headline limitation right now rather than a footnote.

**Observability (implemented).** A lane boundary 60m out with a handful
of points on it is not evidence of anything. In the one log this has
been run against, ~55% of lane-boundary vertices were never near any
LiDAR return at all — the vehicle simply never drove past that part of
the map in a ~15 second log. Scoring those as "far from evidence" would
be indistinguishable from a real defect, so they're excluded from the
queue rather than ranked low in it. The same reasoning applies one
layer up in Topology QA: a dangling reference at the edge of a cropped
map tile isn't a broken lane, it's just where the map stops.

---

## Results

| Metric | Value |
|---|---|
| Features evaluated | — |
| Scenarios / logs | — |
| Review queue as % of features | — |
| Recall of injected defects | — |
| Precision at operating threshold | — |

Recall is measured against injected perturbations with known ground
truth; precision against reviewer verdicts. *Placeholders until there
is enough labelled data to report honestly* — the notebook's aggregation
finding above is exactly why: on one log, the natural noise floor of an
intensity-based lane-marking proxy is close in magnitude to a 1m defect,
so no threshold tried separates them cleanly without labeled data across
many logs.

---

## Limitations

- **No alignment stage.** Every QA check downstream currently can't tell
  "the map is wrong" apart from "the pose was wrong." Argoverse 2's
  poses are accurate enough that this doesn't break the demo, but it's
  a load-bearing assumption, not a guarantee.
- **Geometry QA's lane-marking proxy is a percentile picked by eye**
  (brightest 10% of ground returns), not calibrated per sensor or road
  surface.
- **Risk Scoring's aggregation rule is unresolved** — see the notebook
  and Status table.
- **Single log, single tile.** Topology QA can't distinguish a real
  dangling reference from a map-crop boundary without the full city
  graph.
- **CI has no AWS credentials by default** — `etl-smoke.yml` exercises
  Extract + Transform only unless secrets are added, so Load is only
  covered by the mocked `moto` unit tests in CI, not a real upload.
- Argoverse 2 maps are treated as ground truth; where they are
  themselves wrong, checks will appear to produce false positives.
- Vertical geometry is unhandled; all scoring is planar (x, y).
- No handling of features absent from the map entirely — this compares
  existing geometry rather than discovering new features.

---

## Project layout

```
hdmap_watch/
  etl/
    extract.py            pull one log from the public AV2 bucket
    transform.py           HD Map QA Engine + Risk Scoring
    load.py                 push raw log + review queue to S3
    run_etl.py               CLI: extract -> transform -> load
notebooks/
  01_pipeline_walkthrough.ipynb   design + reasoning + failure narrative
scripts/
  fetch_log.sh             shell alternative to extract.py
.github/workflows/
  ci.yml                   lint + unit tests (mocked S3) on push/PR
  etl-smoke.yml             real-data smoke test, manual + weekly
data/                       downloaded logs (gitignored)
out/                         review_queue_<log_id>.csv
tests/
  test_transform.py
  test_etl_load.py           mocked-S3 (moto) tests for load.py
  fixtures/
```

---

## License

MIT
