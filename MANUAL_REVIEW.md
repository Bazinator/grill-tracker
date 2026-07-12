# Manual Review Guide

Human review supplies the truth the benchmark cannot infer from its own predictions. Do not tune thresholds from unlabeled statistics alone.

## 1. Prepare private inputs

Inside the devcontainer, confirm the model and clips are available:

```bash
test -f /path/to/best.pt
ls /path/to/clips
make -C core-engine
```

## 2. Assign dataset splits (owner decision)

Edit `evaluation/manifest.json` and replace each `unassigned` split with `train`, `validation`, or `holdout`.

- Keep every clip from the same recording shift in one split.
- Use `validation` for threshold tuning.
- Never inspect or tune against `holdout` until defaults are frozen.
- Keep training clips out of accuracy reports.

List the result without running inference:

```bash
python3 perception/run_video_tests.py \
  --manifest evaluation/manifest.json \
  --video-dir /path/to/clips \
  --model /path/to/best.pt \
  --output runs/list-only.json \
  --list-only
```

## 3. Generate one review video

Start with the shortest or most familiar clip:

```bash
python3 perception/run_video_tests.py \
  --manifest evaluation/manifest.json \
  --video-dir /path/to/clips \
  --model /path/to/best.pt \
  --clip remove_steaks1.mp4 \
  --output runs/manual-review.json \
  --reviews-dir runs/reviews
```

Open `runs/reviews/remove_steaks1.review.mp4` outside the container.

- Green box: raw model detection.
- Cyan point and `ID`: active state-engine steak.
- Red point and `mN`: retained steak missed for `N` frames.

Record timestamps for missed steaks, false steaks, merged neighboring steaks, duplicate boxes, ID changes, late additions, and late removals.

## 4. Add ground truth (owner inspection)

Copy `evaluation/ground_truth.example.json` into private evaluation storage. Fill in visible-count time ranges, add/remove/occlusion events, `visible_steaks_after` for each event, and scene conditions, then set that file in the clip's `ground_truth` manifest field relative to `--video-dir`.

Ground truth should describe what is visibly on the grill, not what the model predicted. Commit only annotations that contain no private media or identifying information.

The current sidecar supports count and event scoring. Per-box precision/recall requires frame-level box annotation and is postponed until count/event results show that the extra labeling cost is necessary.

## 5. Run the validation baseline

```bash
python3 perception/run_video_tests.py \
  --manifest evaluation/manifest.json \
  --split validation \
  --video-dir /path/to/clips \
  --model /path/to/best.pt \
  --output runs/validation-baseline.json \
  --reviews-dir runs/reviews/baseline
```

Do not promote settings from `packets_total`, `max_grill_size`, or ID turnover alone. Compare them with the labeled counts and events.

## 6. Run a bounded parameter sweep

After validation labels exist:

```bash
python3 perception/sweep_configs.py \
  --manifest evaluation/manifest.json \
  --video-dir /path/to/clips \
  --model /path/to/best.pt \
  --output-dir runs/sweep \
  --confidence 0.25 0.40 \
  --nms-iou 0.35 0.40 \
  --match-distance 75 90 110 \
  --dedupe-iou 0.20 \
  --max-age 15 25 40 \
  --max-runs 36
```

Use fewer values for the first pass. Freeze the best validation candidate, run it once on `holdout`, and do not retune from holdout failures.
The sweep writes `runs/sweep/index.json`, ranked by labeled count mean absolute error. Visual review and event latency still decide between close candidates.

## Owner decisions still required

- Leakage-safe split assignment
- Ground-truth labels and event timestamps
- Acceptable count error, add/remove latency, ID-switch rate, and minimum FPS
- Visual confirmation that IoU dedupe does not merge adjacent physical steaks
- Whether measured false births justify confirmation frames
- Final v1 defaults and model promotion
- Whether count/event metrics are insufficient and box-level labels are worth adding
