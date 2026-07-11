# core-engine

Pipeline consumer for steak state detection: reads binary frames from stdin, parses them into `SteakPacket`s, and runs **steak_state** (Grill + SteakTracker) to reduce dual detections and keep stable IDs. See the repository [roadmap](../ROADMAP.md) for the v1 architecture and acceptance gates.

## Build

From this directory:

```bash
make
```

Produces:

- **steak_consumer** – main pipeline binary (reads from stdin). Use this in the live pipeline.
- **reader_test** – file-based test that reads a single packet from `perception/steak_pulse_test.bin`. The live pipeline uses `main.cpp` + stdin.

## Pipeline

Wire format (per frame): **count** (4 bytes LE) + **N × SteakPacket** (20 bytes each). See `include/SteakPacket.h` and `perception/steak_packet.py`.

**Run the pipeline:**

```bash
# From repo root; use -u for unbuffered stdout so C++ gets each frame promptly
python3 -u perception/testModel.py --pipe --video /path/to/video 2>/dev/null | ./core-engine/steak_consumer
```

Redirect stderr so logs do not mix with binary data.

**End-to-end (when you have a video):**

```bash
cd core-engine && make
python3 -u ../perception/testModel.py --pipe --video /path/to/your/video 2>/dev/null | ./steak_consumer
```

**steak_state** (Grill + SteakTracker) is implemented: `main.cpp` passes each frame’s packets to `SteakTracker::ingest()`. Grill stores steaks by stable id; the tracker dedupes same-frame detections, associates packets to steaks by centroid distance, and prunes stale tracks. Use `STEAK_VERBOSE=1` to log packets and Grill state to stderr.

## Run Statistics

At EOF, `steak_consumer` emits JSON stats to stderr (or to `STEAK_STATS_PATH` if set):

```json
{"frames_processed":1200,"packets_total":3500,"dedupes_total":150,"max_grill_size":8,"cumulative_steaks":12}
```

Save to file:

```bash
STEAK_STATS_PATH=stats.json ./steak_consumer < stream.bin 2>/dev/null
```

Emit one JSON state event per frame for offline review or overlays:

```bash
STEAK_STATE_PATH=state.jsonl ./steak_consumer < stream.bin
```

Each line contains the frame number and active steaks with `stable_id`, centroid, confidence, and `miss_count`.

## Tests

```bash
make test           # Basic stream tests
make test-scenarios # Synthetic scenarios (stable, flicker, dual, drift, multi)
```

Runs `perception/generate_test_stream.py` to create synthetic streams and validates tracking behavior.

## Testing and Diagnostics

See **[TESTING.md](TESTING.md)** for:

- How to run and interpret test scenarios
- How to diagnose issues: **model vs backend**
- Tuning parameters (match_distance, dedupe_distance, max_age)
- Decision tree for troubleshooting

## Roadmap

See the repository **[ROADMAP.md](../ROADMAP.md)** for the live-input, evaluation, persistence, and overlay plan.
