# Testing Guide: Pipeline, Stats, and Diagnostics

This document explains how to test the steak tracking pipeline and interpret run statistics to determine whether issues are caused by the **model (YOLO)** or the **backend state logic (Grill/SteakTracker)**.

---

## 1. Quick Start: Running the Pipeline

### With a real video

```bash
cd /workspaces/steakTracker
python3 -u perception/testModel.py --video /workspaces/steakTracker/data/test/vettedClips/add_steaks1.mp4 2>/dev/null | ./core-engine/steak_consumer
```

At EOF, `steak_consumer` emits JSON stats to stderr:

```json
{"frames_processed":1200,"packets_total":3500,"dedupes_total":150,"max_grill_size":8,"cumulative_steaks":12}
```

### With synthetic test streams

```bash
python3 perception/generate_test_stream.py <scenario> <output.bin> --frames 100
./core-engine/steak_consumer < <output.bin>
```

Scenarios:
- **stable**: One steak, fixed position. Expected: cumulative_steaks=1, dedupes=0.
- **flicker**: One steak, drops every 5 frames. Tests miss/prune recovery. Expected: cumulative_steaks=1 if max_age > drop interval.
- **dual**: Two overlapping detections per frame. Tests deduplication. Expected: dedupes_total = packets_total / 2, cumulative_steaks=1.
- **drift**: One steak drifting across frames. Tests association by distance. Expected: cumulative_steaks=1 if speed < match_distance/frame.
- **multi**: Multiple steaks appearing/disappearing. Tests multi-track behavior.

---

## 2. Understanding Run Statistics

| Metric | What it measures | Healthy range |
|--------|------------------|---------------|
| **frames_processed** | Total frames ingested | Should match video frame count |
| **packets_total** | Total raw detections from YOLO | Depends on video content |
| **dedupes_total** | Packets merged (same-frame duplicates) | Low unless model produces many overlaps |
| **max_grill_size** | Peak simultaneous steaks on grill | Matches physical steak count |
| **cumulative_steaks** | Total distinct stable_ids created | Close to physical steak count if tracking is stable |

---

## 3. Diagnosing Issues: Model vs Backend

### Symptoms and likely causes

| Symptom | Likely cause | Metric clues |
|---------|--------------|--------------|
| **Too many cumulative_steaks** (much higher than physical count) | ID flicker: steaks are being lost and re-created as new | Check if flicker scenario shows cumulative>1; may need to tune `max_age` or `match_distance` in backend |
| **dedupes_total very high** | Model produces many overlapping boxes per steak | Model issue: retrain or adjust NMS/conf threshold |
| **packets_total very low** (steaks not detected) | Model not detecting steaks | Model issue: check training data, conf threshold |
| **max_grill_size too high** (phantom steaks) | False positives from model OR backend not deduping | If dedupes_total is low, model issue (false positives); if high, backend may need tuning |
| **max_grill_size too low** (missing steaks) | Model not detecting some steaks | Model issue: review detection recall |
| **Stable scenario fails** (cumulative>1) | Backend association too strict | Tune `match_distance` up |
| **Drift scenario fails** (cumulative>1) | match_distance too small for steak speed | Tune `match_distance` up |

### Decision tree

```
                    Is packets_total appropriate for the video?
                              |
           +------------------+------------------+
           |                                     |
          YES                                   NO (too low or too high)
           |                                     |
   Is cumulative_steaks                   Model issue:
   close to physical count?               - Too low: model not detecting (train more, lower conf)
           |                              - Too high: false positives (train more, raise conf)
   +-------+-------+
   |               |
  YES             NO (too many IDs)
   |               |
Tracking is       Is dedupes_total high?
stable.           |
                  +--------+--------+
                  |                 |
                 YES               NO
                  |                 |
         Model produces      Backend issue:
         many duplicates     - Tune match distance, dedupe IoU, and max age
         (retrain or NMS)
```

---

## 4. Tuning Backend Parameters

The evaluator passes these environment-backed settings to the C++ engine:

| Parameter | Default | Effect |
|-----------|---------|--------|
| **STEAK_MATCH_DISTANCE** | 90 px | Max centroid distance to associate a packet with an existing steak. Increase if steaks move fast between frames. |
| **STEAK_DEDUPE_IOU** | 0.20 | Same-frame boxes at or above this IoU are merged. Raise to merge fewer boxes; lower to merge more. |
| **STEAK_MAX_AGE** | 25 frames | Frames without a match before a steak is pruned. Increase if detections flicker often; decrease to drop phantoms faster. |

### How to tune

1. Label validation clips and run the bounded sweep in `MANUAL_REVIEW.md`.
2. If cumulative_steaks >> physical count: try increasing max age (detection flicker) or match distance (fast movement).
3. If dedupes_total is very high: model is producing many overlapping boxes; consider retraining or adjusting YOLO NMS threshold in `testModel.py`.
4. Re-run and compare stats.

---

## 5. Verbose Mode for Debugging

```bash
STEAK_VERBOSE=1 ./core-engine/steak_consumer < test.bin 2>&1 | head -50
```

Output shows per-frame:
- Raw packets (steak_id, centroid, conf, timestamp)
- Grill steaks (stable_id, centroid, conf, last_seen, miss_count)
- Deduped and new counts

Use this to trace why a steak ID was lost or created.

---

## 6. Saving Stats to a File

```bash
STEAK_STATS_PATH=stats.json ./core-engine/steak_consumer < video_stream.bin 2>/dev/null
cat stats.json
```

Useful for automated testing or comparing runs.

---

## 7. Test Scenarios Checklist

| Scenario | Expected outcome | Pass criteria |
|----------|------------------|---------------|
| stable (50 frames) | cumulative_steaks=1, dedupes=0 | One stable ID throughout |
| flicker (50 frames, drop every 5) | cumulative_steaks=1 (if max_age > 5) | ID survives drops |
| dual (50 frames, distance=20) | cumulative_steaks=1, dedupes=50 | Deduplication works |
| drift (50 frames, speed=2) | cumulative_steaks=1 | Association across movement |
| multi (50 frames, 3 steaks) | cumulative_steaks=3 | Correct multi-track |

Run all scenarios:

```bash
cd /workspaces/steakTracker
for s in stable flicker dual drift multi; do
  python3 perception/generate_test_stream.py $s /tmp/test_$s.bin --frames 50
  echo "=== $s ===" && ./core-engine/steak_consumer < /tmp/test_$s.bin
done
```

---

## 8. Summary: Model vs Backend

- **Model issues** (YOLO training, conf, NMS):
  - packets_total too low (not detecting) or too high (false positives)
  - dedupes_total very high (many overlapping boxes)
  - Fix: retrain model, adjust `conf` or `iou` in `testModel.py`

- **Backend issues** (Grill/SteakTracker):
  - cumulative_steaks much higher than physical count (ID flicker)
  - max_grill_size wrong (phantom or missing steaks)
  - Fix: sweep `STEAK_MATCH_DISTANCE`, `STEAK_DEDUPE_IOU`, and `STEAK_MAX_AGE` on labeled validation clips.

Use synthetic scenarios to isolate: if `stable` and `drift` fail, it's backend; if real video fails but synthetics pass, it's model.

---

## 9. Testing with Real Videos

Use `perception/run_video_tests.py` to test on real shift recording videos:

```bash
# List available test videos
python3 perception/run_video_tests.py --list-only

# Run tests on up to 5 sample videos
python3 perception/run_video_tests.py --output perception/test_results.json

# Test one video with custom timeout
python3 perception/run_video_tests.py --max-videos 1 --timeout 1800
```

**Performance note:** YOLO inference on CPU is slow (~0.5-2 FPS). A 3-minute video may take 30-90 minutes. With GPU, expect ~30+ FPS.

Sample videos tested from `data/rawfootage/shiftRecordings/`:
- `Dec13/busygrill.ts` - likely has steak activity
- `Jan4/`, `Dec24/`, `November30/`, `Dec13/` - various shift recordings

The test runner outputs:
- Per-video stats (frames, packets, dedupes, max_grill, cumulative_steaks)
- Diagnostic notes (LOW_DETECTIONS, HIGH_DEDUPE, ID_FLICKER, EMPTY_GRILL)
- Summary with overall diagnosis

### Interpreting Real Video Results

| Observation | Interpretation |
|-------------|----------------|
| EMPTY_GRILL on all videos | Model not detecting steaks (retrain or check conf) |
| LOW_DETECTIONS on busy videos | Model recall is low (more training data) |
| HIGH_DEDUPE on all videos | Model produces overlapping boxes (tune NMS) |
| ID_FLICKER (high cumulative vs max_grill) | Backend needs tuning (increase max_age or match_distance) |
| Good stats on short video, bad on long | Model or backend degrades over time (investigate) |
