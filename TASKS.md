# Tasks

## Ready for implementation

- [ ] Add a versioned clip-manifest format with train, validation, and holdout groups.
- [ ] Record model hash, thresholds, tracker rules, FPS, and manifest version in evaluation reports.
- [ ] Add a saved-video review mode showing raw detections and state-engine IDs together.
- [ ] Make the C++ state engine emit one overlay/state event per frame.
- [ ] Pass bounding boxes to the state engine and benchmark IoU-based deduplication.
- [ ] Add an OpenCV-compatible stream URL input while keeping file input for tests.
- [ ] Store runs and state transitions in SQLite.

## Owner input required

- [ ] Label expected steak counts and add/remove/occlusion events in validation clips.
- [ ] Choose which clips belong to train, validation, and untouched holdout sets.
- [ ] Define acceptable count error, add/remove latency, ID-switch rate, and minimum FPS.
- [ ] Review rendered failures and identify cases where the ground truth or model is wrong.
- [ ] Confirm the production camera transport after testing the restaurant network.

Work from the first unchecked item whose prerequisites are complete. Do not block implementation work on labeling tasks that can be developed against a small example manifest.
