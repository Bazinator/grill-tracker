#!/usr/bin/env python3
"""
Run pipeline tests on sample videos from data/rawfootage/shiftRecordings.
Uses the same model path as testModel.py and outputs stats for each video.

Usage:
  python3 perception/run_video_tests.py [--max-videos N] [--output stats_report.json]
  python3 perception/run_video_tests.py --list-only  # Just list videos
  python3 perception/run_video_tests.py --max-videos 1 --timeout 1800  # Test one video with 30min timeout

Outputs per-video JSON stats from steak_consumer and a summary report.

NOTE: YOLO inference on CPU is slow (~0.5-2 FPS). A 3-minute video (5400 frames) may take
30-90 minutes on CPU. With GPU, expect ~30+ FPS. Adjust --timeout accordingly.
For quick validation, use synthetic streams: python3 perception/generate_test_stream.py
"""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional
import cv2

# Sample videos to test (one from each folder + busygrill for variety)
SAMPLE_VIDEOS = [
    "add_steaks1.mp4",  # Likely has activity
    "manic_grill1.mp4",
    "remove_steaks1.mp4",
    "stable_grill1.mp4",
    "stable_grill2.mp4",
]


def resolve_path(base: str, relative: str) -> str:
    """Resolve a path relative to the script directory."""
    script_dir = Path(__file__).parent.resolve()
    return str((script_dir / relative).resolve())


def get_video_info(video_path: str) -> dict:
    """Return basic video metadata for display in test listing."""
    info = {"frames": 0, "fps": 0.0, "duration_s": 0.0}
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return info

    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
    duration_s = (frames / fps) if fps > 0 else 0.0
    cap.release()

    info["frames"] = frames
    info["fps"] = round(fps, 2)
    info["duration_s"] = round(duration_s, 2)
    return info


def run_pipeline(video_path: str, model_path: str, timeout: int = 600) -> Optional[dict]:
    """
    Run the detection pipeline on a video and return stats.
    Returns None if the pipeline fails or times out.
    """
    script_dir = Path(__file__).parent.resolve()
    test_model = script_dir / "testModel.py"
    steak_consumer = script_dir.parent / "core-engine" / "steak_consumer"
    
    # Error Handling
    if not test_model.exists():
        print(f"[ERROR] testModel.py not found at {test_model}", file=sys.stderr)
        return None
    if not steak_consumer.exists():
        print(f"[ERROR] steak_consumer not found at {steak_consumer}", file=sys.stderr)
        print("[INFO] Run 'cd core-engine && make' to build it", file=sys.stderr)
        return None
    if not os.path.exists(video_path):
        print(f"[ERROR] Video not found: {video_path}", file=sys.stderr)
        return None
    if not os.path.exists(model_path):
        print(f"[ERROR] Model not found: {model_path}", file=sys.stderr)
        return None

    cmd = (
        f"python3 -u {test_model} --video {video_path} --model {model_path} 2>/dev/null | "
        f"{steak_consumer} 2>&1"
    )

    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        elapsed = time.time() - start

        # Parse the JSON stats from the last line
        lines = result.stdout.strip().split("\n")
        for line in reversed(lines):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    stats = json.loads(line)
                    stats["elapsed_seconds"] = round(elapsed, 2)
                    stats["video"] = os.path.basename(video_path)
                    return stats
                except json.JSONDecodeError:
                    continue

        print(f"[WARN] No valid JSON stats found for {video_path}", file=sys.stderr)
        print(f"[DEBUG] stdout: {result.stdout}", file=sys.stderr)
        print(f"[DEBUG] stderr: {result.stderr}", file=sys.stderr)
        return None

    except subprocess.TimeoutExpired:
        print(f"[WARN] Timeout ({timeout}s) for {video_path}", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[ERROR] Pipeline failed for {video_path}: {e}", file=sys.stderr)
        return None


def analyze_stats(stats: dict) -> dict:
    """Analyze stats and add diagnostic notes."""
    notes = []
    
    frames = stats.get("frames_processed", 0)
    packets = stats.get("packets_total", 0)
    dedupes = stats.get("dedupes_total", 0)
    max_grill = stats.get("max_grill_size", 0)
    cumulative = stats.get("cumulative_steaks", 0)
    
    # Detection rate
    if frames > 0:
        detection_rate = packets / frames
        stats["detection_rate_per_frame"] = round(detection_rate, 2)
        if detection_rate < 0.1:
            notes.append("LOW_DETECTIONS: Model may not be detecting steaks well")
    
    # Dedupe rate
    if packets > 0:
        dedupe_rate = dedupes / packets
        stats["dedupe_rate"] = round(dedupe_rate, 3)
        if dedupe_rate > 0.3:
            notes.append("HIGH_DEDUPE: Model produces many overlapping boxes")
    
    # ID stability
    if cumulative > 0 and max_grill > 0:
        id_ratio = cumulative / max_grill
        stats["id_turnover_ratio"] = round(id_ratio, 2)
        if id_ratio > 3:
            notes.append("ID_FLICKER: Many IDs created vs max on grill (tune backend)")
    
    # Empty grill
    if max_grill == 0 and frames > 100:
        notes.append("EMPTY_GRILL: No steaks detected (check model or video content)")
    
    stats["diagnostic_notes"] = notes
    return stats


def main():
    parser = argparse.ArgumentParser(description="Run pipeline tests on sample videos")
    parser.add_argument("--max-videos", type=int, default=5, help="Max videos to test")
    parser.add_argument("--output", type=str, default=None, help="Output JSON report file")
    parser.add_argument("--model", type=str, required=True, help="Path to YOLO weights")
    parser.add_argument("--video-dir", type=str, required=True, help="Directory containing test videos")
    parser.add_argument("--timeout", type=int, default=3600, help="Timeout per video in seconds (default 1 hour for CPU inference)")
    parser.add_argument("--list-only", action="store_true", help="List videos only, don't run")
    args = parser.parse_args()

    script_dir = Path(__file__).parent.resolve()
    model_path = args.model
    video_dir = args.video_dir

    print(f"=== Video Pipeline Test ===")
    print(f"Model: {model_path}")
    print(f"Video dir: {video_dir}")
    print(f"Max videos: {args.max_videos}")
    print(f"Timeout per video: {args.timeout}s")
    print()

    # Collect videos to test
    videos = []
    for rel_path in SAMPLE_VIDEOS[:args.max_videos]:
        full_path = os.path.join(video_dir, rel_path)
        if os.path.exists(full_path):
            videos.append(full_path)
        else:
            print(f"[SKIP] Video not found: {full_path}")

    if not videos:
        print("[ERROR] No valid videos found to test")
        sys.exit(1)

    # Show video info
    print(f"Found {len(videos)} video(s):\n")
    for v in videos:
        info = get_video_info(v)
        print(f"  {os.path.basename(v)}: {info['frames']} frames, {info['duration_s']}s @ {info['fps']}fps")
    print()

    if args.list_only:
        print("--list-only specified, exiting without running tests")
        return

    print(f"Testing {len(videos)} video(s)...\n")

    results = []
    for i, video_path in enumerate(videos, 1):
        video_name = os.path.basename(video_path)
        print(f"[{i}/{len(videos)}] Testing: {video_name}")
        
        stats = run_pipeline(video_path, model_path, timeout=args.timeout)
        if stats:
            stats = analyze_stats(stats)
            results.append(stats)
            
            # Print summary
            print(f"  frames={stats['frames_processed']} packets={stats['packets_total']} "
                  f"dedupes={stats['dedupes_total']} max_grill={stats['max_grill_size']} "
                  f"cumulative={stats['cumulative_steaks']} time={stats['elapsed_seconds']}s")
            if stats.get("diagnostic_notes"):
                for note in stats["diagnostic_notes"]:
                    print(f"  -> {note}")
        else:
            print(f"  [FAILED]")
        print()

    # Summary
    print("=== Summary ===")
    if results:
        total_frames = sum(r.get("frames_processed", 0) for r in results)
        total_packets = sum(r.get("packets_total", 0) for r in results)
        total_dedupes = sum(r.get("dedupes_total", 0) for r in results)
        avg_grill = sum(r.get("max_grill_size", 0) for r in results) / len(results)
        avg_cumulative = sum(r.get("cumulative_steaks", 0) for r in results) / len(results)
        total_time = sum(r.get("elapsed_seconds", 0) for r in results)
        
        print(f"Videos tested: {len(results)}/{len(videos)}")
        print(f"Total frames: {total_frames}")
        print(f"Total packets: {total_packets}")
        print(f"Total dedupes: {total_dedupes}")
        print(f"Avg max_grill_size: {avg_grill:.1f}")
        print(f"Avg cumulative_steaks: {avg_cumulative:.1f}")
        print(f"Total time: {total_time:.1f}s")
        
        # Overall diagnostic
        if total_packets == 0:
            print("\n[DIAGNOSIS] No detections at all - check model path and training")
        elif total_dedupes / max(1, total_packets) > 0.3:
            print("\n[DIAGNOSIS] High dedupe rate - model may need NMS tuning or retraining")
        elif avg_cumulative > avg_grill * 3:
            print("\n[DIAGNOSIS] High ID turnover - backend may need tuning (match_distance, max_age)")
        else:
            print("\n[DIAGNOSIS] Stats look reasonable")
    else:
        print("No videos processed successfully")

    # Save report
    if args.output:
        report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "model": model_path,
            "video_dir": video_dir,
            "results": results,
        }
        with open(args.output, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nReport saved to: {args.output}")


if __name__ == "__main__":
    # Allow importing steak_packet from same directory when run as script
    _dir = os.path.dirname(os.path.abspath(__file__))
    if _dir not in sys.path:
        sys.path.insert(0, _dir)
    main()
