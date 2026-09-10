# hdmap-watch

**Automated triage for HD map QA**

HD map QA is expensive because mapping specialists may need to inspect large
numbers of lane-level features against sensor observations. HDMap Watch
automatically compares HD-map geometry and topology against LiDAR-derived
observations, identifies suspicious features, and ranks them for human review.

---

## The business problem

An HD map for a single urban district contains tens of thousands of
lane-level features: lane boundaries, centerlines, stop lines, crosswalks,
connectivity between lanes. Every one of them can be wrong — surveyed
incorrectly, invalidated by construction, or degraded by a localization error
during capture.

Validating them is manual. A specialist opens each feature alongside the
sensor data and decides whether the map matches reality. At scale this is the
dominant cost in map maintenance, and it does not parallelize cheaply because
the scarce resource is trained attention.

Most features are fine. The problem is not inspection — it is *deciding what
to inspect*. HDMap Watch is a triage layer: it scores every feature, and
returns a ranked queue short enough for a specialist to work through in an
afternoon while still containing nearly all the genuine defects.

The metric that matters is therefore not accuracy in the abstract. It is:

> **What fraction of features must a human review to catch a given fraction
> of real defects?**

---

## How it works

```
   HD map                              LiDAR sweeps
   lane boundaries, centerlines,       point clouds + ego pose
   stop lines, crosswalks, topology
              │                                │
              └────────────┬───────────────────┘
                           ▼
              Stage 1  —  alignment
              rigid-align the map to the
              accumulated point cloud, so
              localization error is not
              mistaken for map error
                           ▼
              Stage 2  —  observability gate
              per-feature point density and
              range; features with too little
              support are marked
              unobservable, not suspicious
                           ▼
              Stage 3  —  geometric residual
              distance from each map feature
              to the nearest supporting
              LiDAR evidence
                           ▼
              Stage 4  —  topology checks
              dangling lane connections,
              unreachable segments, stop
              lines with no lane, geometry
              that violates its own graph
                           ▼
              Stage 5  —  rank and threshold
              combine residual, topology
              violations and observability
              into one suspicion score
                           ▼
              Stage 6  —  review queue
              ranked GeoJSON + per-feature
              crop, exported for QA tooling
                           ▼
              Stage 7  —  verdicts back in
              reviewer labels feed the
              evaluation set and recalibrate
              the threshold
```

Stages 1 and 2 exist because of what the naive version gets wrong.

**Alignment first.** Without it, a small pose error shifts every feature in
the log and the detector flags the entire map. Misalignment is a
sensor problem masquerading as a map problem, and separating the two is most
of the work.

**Observability before suspicion.** A lane boundary 60m out with nine points
on it is not evidence of anything. Scoring it as if it were produces
false positives that destroy reviewer trust faster than any other failure
mode. Unobservable features are excluded from the queue rather than ranked
low in it.

---

## Results

| Metric | Value |
|---|---|
| Features evaluated | — |
| Scenarios / logs | — |
| Review queue as % of features | — |
| Recall of injected defects | — |
| Precision at operating threshold | — |

Recall is measured against injected perturbations with known ground truth;
precision against reviewer verdicts. *Placeholders until there is enough
labelled data to report honestly.*

---

## Evaluation method

Real HD map versions with documented drift are not publicly available, so
defects are injected into a known-good map and the detector is scored on
whether it finds them.

| Perturbation | Represents |
|---|---|
| Lateral shift of a lane boundary, 20–100cm | survey error, resurfacing |
| Deleted crosswalk or stop line | removed marking |
| Rotated stop line | intersection redesign |
| Severed lane connection | construction closure |
| Whole-tile pose offset | localization failure during capture |

The last one is a control: a good detector should attribute it to
misalignment in Stage 1 rather than reporting every feature in the tile as
defective.

---

## Getting started

### Requirements

- Python 3.10+
- Argoverse 2 sensor dataset (a single log is enough to start)

### Install

```bash
git clone https://github.com/<you>/hdmap-watch.git
cd hdmap-watch
pip install -e .
```

### Run

```bash
# score one log against its shipped map
python -m hdmap_watch scan --log <log_id>

# inject known defects and report recall
python -m hdmap_watch eval --log <log_id> --perturb lane_shift,stopline_delete
```

Outputs `out/queue.geojson`, ranked by suspicion score, plus a per-feature
crop for review.

---

## Two-week build plan

| Days | Deliverable |
|---|---|
| 1–2 | Load one Argoverse 2 log: map features, LiDAR sweeps, ego pose. Render both together. |
| 3–4 | Accumulate sweeps into a single cloud in map frame. Ground/non-ground split. |
| 5–6 | Geometric residual for lane boundaries. First ranked queue, however crude. |
| 7 | Perturbation harness — inject defects, measure recall. Baseline number. |
| 8–9 | Rigid alignment stage. Re-measure; expect the largest single precision gain. |
| 10 | Observability gating on point density and range. Re-measure. |
| 11 | Topology checks. |
| 12 | Scale to 10+ logs. Record the headline numbers. |
| 13 | Review export, README results table, short write-up of failure modes. |
| 14 | Buffer. Something will take twice as long as planned. |

Days 7, 9 and 10 are the ones that matter. Each produces a before/after
number, and those numbers are the substance of the project.

---

## Limitations

- Argoverse 2 maps are treated as ground truth; where they are themselves
  wrong, the detector will appear to produce false positives
- Injected perturbations are not a substitute for real map drift, and may not
  reproduce its distribution
- Vertical geometry is largely unhandled; the current scoring is planar
- Dense urban occlusion suppresses observability and causes misses
- No handling of features absent from the map entirely — this compares
  existing geometry rather than discovering new features

---

## Data

| Source | Role |
|---|---|
| [Argoverse 2](https://www.argoverse.org/av2.html) | Lane-level HD maps, LiDAR sweeps, ego pose |
| [nuScenes](https://www.nuscenes.org/) | Alternative, smaller, HD maps included |

---

## Project layout

```
hdmap_watch/
  io.py           load map features, sweeps, poses
  align.py        rigid alignment, map frame to point cloud
  observe.py      per-feature point density and range gating
  residual.py     geometric distance scoring
  topology.py     graph consistency checks
  rank.py         score combination and thresholding
  perturb.py      defect injection for evaluation
  export.py       ranked review queue
tests/
  fixtures/       one trimmed log, known perturbations
```

---

## Status

Under active development. See the two-week plan above for what exists and
what does not.

## License

MIT
