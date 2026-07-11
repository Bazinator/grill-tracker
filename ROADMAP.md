# Steak Tracker v1 Roadmap

## v1 outcome

Given a live camera stream, the home computer must detect steaks, maintain useful stable IDs through short misses and duplicate boxes, save detection history, and send overlay metadata to a restaurant display. The display combines that metadata with the live video.

The Pi camera software is outside this repository. For v1, this repository owns the home inference/state service, evaluation tools, persistence, and the browser-facing metadata contract.

## Target architecture

```text
Pi Zero 2 camera
       |
       | live video stream
       v
home media input -> Python inference -> C++ state engine -> SQLite
       |                                      |
       | video to restaurant display          | overlay events
       +---------------------> browser UI <----+
```

Keep the three channels separate:

1. **Video:** the camera stream reaches inference and the display through a replaceable media adapter. Start with a file or OpenCV-compatible URL; choose the production transport after measuring the restaurant connection.
2. **State:** one event per processed frame contains frame/time, stable IDs, boxes or centroids, confidence, and active/missing state. The browser consumes this lightweight stream for overlays.
3. **History:** SQLite on the home computer stores runs and state transitions. Do not store every video frame in the database.

Do not add a message broker, microservices, or a remote database for v1. A single home process and SQLite cover one camera and one display.

## Tracking rules to define and measure

The current implementation is a baseline, not a final policy.

| Rule | Current baseline | v1 decision method |
| --- | ---: | --- |
| Detection confidence | `0.40` | Sweep on labeled validation clips; optimize recall while bounding false steaks. |
| YOLO IoU/NMS | `0.40` | Sweep with confidence; measure duplicate and missed detections. |
| Same-frame dedupe | centroid distance `40 px` | Prefer box IoU once boxes cross the C++ boundary; validate crowded-grill merges. |
| Frame association | nearest centroid within `90 px` | Measure ID switches; add motion/IoU only if nearest-centroid misses the gate. |
| Missing grace period | `25 frames` | Express as time, then convert using processed FPS; test short occlusion versus removed steaks. |
| New steak confirmation | immediate | Require consecutive observations only if false-positive births remain material. |
| Removal | after grace period | Emit one removal event and persist the completed lifetime. |

Every rule change must be evaluated on the same versioned clip manifest. Do not tune on the final holdout clips.

## Evaluation contract

Each useful test clip needs a small sidecar annotation containing:

- clip name and scene conditions;
- time ranges with expected visible steak count;
- important add, remove, occlusion, and duplicate events;
- optional stable identity annotations for a smaller tracking subset.

Report at least:

- detection precision and recall on labeled frames;
- count error over time;
- duplicate rate;
- ID switches and track fragmentation;
- add/remove latency in seconds;
- inference FPS and end-to-end latency.

The existing `packets_total`, `dedupes_total`, `max_grill_size`, and `cumulative_steaks` remain useful diagnostics, but they are not accuracy metrics without ground truth.

## Work plan

### Phase 0 — reproducible repository

- [x] Build and run the C++ tests in the devcontainer.
- [x] Exclude local data, videos, weights, environments, binaries, and run output from Git.
- [x] Document the current pipeline and v1 boundary.
- [x] Add a proprietary license.
- [x] Make model and clip paths explicit everywhere; remove machine-specific defaults.
- [ ] Make the initial Git commit and push it to the private remote.

Exit gate: a new checkout plus private weights/data can run both synthetic tests and one real clip using documented commands.

### Phase 1 — trustworthy offline benchmark

- [ ] Create a versioned clip manifest with train/validation/holdout groups.
- [ ] Add sidecar ground truth for steak counts and key events.
- [ ] Make the real-video runner produce one comparable JSON report per model/configuration.
- [ ] Record model hash, thresholds, tracker rules, FPS, and clip manifest version in every report.
- [ ] Add a review mode that renders model boxes and state-engine stable IDs onto saved clips.

Exit gate: one command compares two model/configuration runs and the overlay makes failures visually inspectable.

### Phase 2 — calibrate detection and state rules

- [ ] Sweep confidence and NMS thresholds on validation clips.
- [ ] Pass bounding boxes into the state engine so dedupe can use IoU, not centroid distance alone.
- [ ] Sweep association distance and missing duration using labeled add/remove/occlusion cases.
- [ ] Add confirmation frames only if measured false births require it.
- [ ] Freeze v1 defaults and acceptance thresholds in the benchmark config.

Exit gate: holdout metrics meet agreed count accuracy, add/remove latency, ID stability, and inference speed targets.

### Phase 3 — live home service

- [ ] Replace the file-only input with an OpenCV-compatible stream URL while retaining file input for regression tests.
- [ ] Emit newline-delimited JSON state events from the C++ engine or its supervising process.
- [ ] Persist runs, tracks, and state transitions in SQLite.
- [ ] Reconnect after stream loss and mark the run unhealthy rather than inventing state.
- [ ] Add a health endpoint with stream age, inference FPS, and last successful frame.

Exit gate: the home computer runs unattended for a full restaurant shift and recovers from a camera disconnect.

### Phase 4 — restaurant overlay

- [ ] Build a minimal browser page that plays the live stream and draws stable IDs/count from state events.
- [ ] Include connection and stale-data indicators.
- [ ] Measure video/metadata alignment and carry a shared timestamp through the pipeline.
- [ ] Package the display for kiosk use on the restaurant tablet.

Exit gate: the tablet stays synchronized and clearly shows when detections or connectivity are stale.

## Model improvement loop

1. Run the frozen benchmark and rank false negatives, false positives, duplicate boxes, and ID failures.
2. Sample new training frames from the worst scene categories: glare, smoke, occlusion, crowding, partial steaks, hands, and tools.
3. Deduplicate near-identical frames and keep clips from the same shift in only one dataset split.
4. Correct labels before changing augmentation or architecture.
5. Train from a recorded dataset version and save parameters, metrics, and model hash.
6. Promote a model only when it improves the holdout gates and remains fast enough for live inference.

More data is not automatically better; targeted, correctly labeled, leakage-free data is the priority.
