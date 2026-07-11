#!/usr/bin/env python3
"""
Generate synthetic test streams for core-engine testing.
Produces binary stream files (count + N×SteakPacket per frame) with known scenarios:
  - stable: one steak, consistent position across frames
  - flicker: one steak, detection drops every few frames
  - dual: two overlapping detections per frame (tests deduplication)
  - drift: one steak that moves gradually across frames
  - multi: multiple steaks, some appear/disappear

Usage:
  python3 generate_test_stream.py <scenario> <output_file> [--frames N]

Example:
  python3 generate_test_stream.py stable test_stable.bin --frames 100
  ./core-engine/steak_consumer < test_stable.bin
"""
from __future__ import annotations

import argparse
import os
import sys
import random

_dir = os.path.dirname(os.path.abspath(__file__))
if _dir not in sys.path:
    sys.path.insert(0, _dir)

from steak_packet import pack_frame


def generate_stable(frames: int) -> list:
    """One steak at fixed position for all frames."""
    result = []
    for f in range(1, frames + 1):
        result.append([{
            "steak_id": 1,
            "bbox": [100.0, 200.0, 150.0, 250.0],
            "conf": 0.95,
            "last_seen_frame": f,
        }])
    return result


def generate_flicker(frames: int, drop_every: int = 5) -> list:
    """One steak, detection drops every drop_every frames."""
    result = []
    for f in range(1, frames + 1):
        if f % drop_every == 0:
            result.append([])  # Empty frame (detection dropped)
        else:
            result.append([{
                "steak_id": 1,
                "bbox": [100.0, 200.0, 150.0, 250.0],
                "conf": 0.90,
                "last_seen_frame": f,
            }])
    return result


def generate_dual(frames: int, distance: float = 20.0) -> list:
    """Two overlapping detections per frame (same steak, dual detection)."""
    result = []
    for f in range(1, frames + 1):
        result.append([
            {
                "steak_id": 1,
                "bbox": [100.0, 200.0, 150.0, 250.0],
                "conf": 0.92,
                "last_seen_frame": f,
            },
            {
                "steak_id": 2,
                "bbox": [100.0 + distance, 200.0 + distance, 150.0 + distance, 250.0 + distance],
                "conf": 0.88,
                "last_seen_frame": f,
            },
        ])
    return result


def generate_drift(frames: int, speed: float = 2.0) -> list:
    """One steak that drifts across the frame."""
    result = []
    x, y = 100.0, 200.0
    for f in range(1, frames + 1):
        result.append([{
            "steak_id": 1,
            "bbox": [x, y, x + 50.0, y + 50.0],
            "conf": 0.93,
            "last_seen_frame": f,
        }])
        x += speed
        y += speed * 0.5
    return result


def generate_multi(frames: int, num_steaks: int = 3) -> list:
    """Multiple steaks, some appear/disappear mid-run."""
    result = []
    steaks = []
    for i in range(num_steaks):
        steaks.append({
            "id": i + 1,
            "start_frame": random.randint(1, frames // 3),
            "end_frame": random.randint(2 * frames // 3, frames),
            "x": 50.0 + i * 80.0,
            "y": 100.0 + i * 50.0,
        })
    for f in range(1, frames + 1):
        frame_data = []
        for s in steaks:
            if s["start_frame"] <= f <= s["end_frame"]:
                frame_data.append({
                    "steak_id": s["id"],
                    "bbox": [s["x"], s["y"], s["x"] + 50.0, s["y"] + 50.0],
                    "conf": 0.90 + random.uniform(-0.05, 0.05),
                    "last_seen_frame": f,
                })
        result.append(frame_data)
    return result


SCENARIOS = {
    "stable": generate_stable,
    "flicker": generate_flicker,
    "dual": generate_dual,
    "drift": generate_drift,
    "multi": generate_multi,
}


def main():
    parser = argparse.ArgumentParser(description="Generate test streams for core-engine")
    parser.add_argument("scenario", choices=SCENARIOS.keys(), help="Scenario name")
    parser.add_argument("output", help="Output binary file path")
    parser.add_argument("--frames", type=int, default=50, help="Number of frames (default 50)")
    args = parser.parse_args()

    generator = SCENARIOS[args.scenario]
    frames_data = generator(args.frames)

    with open(args.output, "wb") as f:
        for frame in frames_data:
            f.write(pack_frame(frame))

    print(f"Generated {args.scenario} scenario: {len(frames_data)} frames -> {args.output}")
    print(f"Run with: ./core-engine/steak_consumer < {args.output}")


if __name__ == "__main__":
    main()
