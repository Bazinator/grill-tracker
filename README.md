# Steak Tracker

Steak Tracker is an early-stage computer-vision pipeline for detecting steaks on a restaurant grill and maintaining stable identities when detections overlap or briefly disappear.

The repository currently contains a working offline prototype:

```text
video file -> YOLO/ByteTrack (Python) -> binary frame stream -> state engine (C++) -> run statistics
```

The synthetic state-engine tests pass. The current model does not yet have reliable recall or stable IDs on the real test clips, so this is not production-ready.

## Repository layout

- `perception/`: video decoding, YOLO inference, packet serialization, and video evaluation.
- `core-engine/`: C++ deduplication, association, expiry rules, and synthetic tests.
- `train/`: training entry points. Model weights, datasets, virtual environments, and run output are intentionally excluded from Git.
- `.devcontainer/`: Ubuntu development environment with the C++ and Python dependencies.
- `ROADMAP.md`: v1 architecture, acceptance gates, and ordered work.
- `TASKS.md`: implementation queue separated from owner-required labeling and product decisions.
- `MANUAL_REVIEW.md`: owner workflow for splits, labels, review videos, and parameter sweeps.

The private dataset, test videos, trained weights, and previous run artifacts are not part of the repository. Pass their paths explicitly when running inference or training.

## Quick start

Open the repository in its devcontainer, then run:

```bash
make -C core-engine test
make -C core-engine test-scenarios
```

Run a real clip through inference and the state engine:

```bash
python3 -u perception/testModel.py \
  --pipe \
  --video /path/to/clip.mp4 \
  --model /path/to/best.pt \
  2>/dev/null | ./core-engine/steak_consumer
```

Evaluate the standard local clips and save a report:

```bash
python3 perception/run_video_tests.py \
  --manifest evaluation/manifest.json \
  --video-dir /path/to/clips \
  --model /path/to/best.pt \
  --output runs/evaluation.json \
  --reviews-dir runs/reviews
```

The report records hashes for the model and manifest, inference/tracker settings, source-video metadata, processing FPS, and state-engine statistics. Review videos draw raw model boxes in green and stable state-engine IDs at their centroids. Clips remain `unassigned` in the committed manifest until an owner chooses leakage-safe train, validation, and holdout groups.

See [`core-engine/TESTING.md`](core-engine/TESTING.md) for the scenario definitions and metric interpretation.

Start a training run with explicit private data:

```bash
python3 train/train.py --data /path/to/dataset/data.yaml --model yolov12n.pt
```

## Current state rules

The C++ state engine currently:

1. Merges same-frame boxes whose IoU is at least `0.20`, keeping the higher-confidence detection.
2. Greedily associates each remaining detection with the nearest unmatched steak within `90 px`.
3. Keeps an unmatched steak for `25` missed frames, then removes it.
4. Assigns a new stable ID to every unmatched detection.

These are configurable baselines. They must be calibrated against labeled clips before v1; see [`ROADMAP.md`](ROADMAP.md).

## GitHub readiness

Before the first push:

1. Confirm `git status --ignored` excludes datasets, videos, weights, environments, binaries, and run output.
2. Run both `make` test targets in the devcontainer.
3. Make one clean initial commit; do not add private restaurant footage or generated model artifacts.
