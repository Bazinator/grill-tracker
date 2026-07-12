# Evaluation data contract

`manifest.json` lists benchmark clips without committing private video. Each clip has:

- `path`: path relative to `--video-dir`;
- `split`: `train`, `validation`, `holdout`, or `unassigned`;
- `ground_truth`: relative sidecar path, or `null` until labeled.

All committed clips begin as `unassigned`. The owner must group clips by recording shift so near-identical frames cannot leak between train, validation, and holdout data.

`ground_truth.example.json` defines the minimal human annotation: visible-count time ranges, key add/remove/occlusion events, the visible count expected after each event, and scene conditions. Copy it beside private evaluation data, label it after viewing the clip, and set the manifest's `ground_truth` field relative to `--video-dir`. Do not commit private footage. The runner calculates count mean absolute error, exact-count rate, and event latency from this sidecar.

Run one clip and produce a reproducible report plus review video:

```bash
python3 perception/run_video_tests.py \
  --manifest evaluation/manifest.json \
  --video-dir /path/to/clips \
  --model /path/to/best.pt \
  --clip remove_steaks1.mp4 \
  --output runs/evaluation.json \
  --reviews-dir runs/reviews
```

Green rectangles are raw model detections. Cyan points are matched state-engine IDs; red points are IDs retained during missed detections. Generated reports, JSONL streams, and videos are ignored by Git.
