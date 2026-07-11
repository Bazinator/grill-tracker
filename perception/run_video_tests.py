#!/usr/bin/env python3
"""Run a reproducible, manifest-driven video benchmark."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import cv2


TRACKER_RULES = {"match_distance_px": 90, "dedupe_distance_px": 40, "max_age_frames": 25}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest(path: Path) -> dict:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest.get("version"), int) or not isinstance(manifest.get("clips"), list):
        raise ValueError("manifest requires integer 'version' and array 'clips'")
    for clip in manifest["clips"]:
        if not clip.get("path") or clip.get("split") not in {"train", "validation", "holdout", "unassigned"}:
            raise ValueError("each clip requires path and split: train, validation, holdout, or unassigned")
    return manifest


def video_info(path: Path) -> dict:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        return {"frames": 0, "fps": 0.0, "duration_seconds": 0.0}
    frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    capture.release()
    return {
        "frames": frames,
        "fps": round(fps, 3),
        "duration_seconds": round(frames / fps, 3) if fps else 0.0,
    }


def read_jsonl(path: Path) -> dict[int, dict]:
    if not path.exists():
        return {}
    return {
        item["frame"]: item
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and (item := json.loads(line))
    }


def render_review(video: Path, detections_path: Path, state_path: Path, output: Path) -> None:
    detections = read_jsonl(detections_path)
    states = read_jsonl(state_path)
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise RuntimeError(f"cannot open review video: {video}")
    fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    output.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(output), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"cannot create review video: {output}")

    frame_number = 0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        frame_number += 1
        for detection in detections.get(frame_number, {}).get("detections", []):
            x1, y1, x2, y2 = map(int, detection["bbox"])
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 220, 0), 2)
            cv2.putText(frame, f"raw {detection['conf']:.2f}", (x1, max(18, y1 - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 220, 0), 2)
        for steak in states.get(frame_number, {}).get("steaks", []):
            point = (int(steak["cx"]), int(steak["cy"]))
            color = (0, 80, 255) if steak["miss_count"] else (255, 220, 0)
            cv2.circle(frame, point, 7, color, -1)
            cv2.putText(frame, f"ID {steak['stable_id']} m{steak['miss_count']}",
                        (point[0] + 9, point[1]), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
        writer.write(frame)

    capture.release()
    writer.release()


def analyze(stats: dict) -> dict:
    frames = stats.get("frames_processed", 0)
    packets = stats.get("packets_total", 0)
    maximum = stats.get("max_grill_size", 0)
    cumulative = stats.get("cumulative_steaks", 0)
    stats["detection_rate_per_frame"] = round(packets / frames, 3) if frames else 0.0
    stats["dedupe_rate"] = round(stats.get("dedupes_total", 0) / packets, 3) if packets else 0.0
    stats["id_turnover_ratio"] = round(cumulative / maximum, 3) if maximum else 0.0
    return stats


def run_pipeline(
    video: Path,
    model: Path,
    artifacts: Path,
    confidence: float,
    iou: float,
    image_size: int,
    timeout: int,
) -> tuple[dict, Path, Path]:
    root = Path(__file__).resolve().parent.parent
    detector = root / "perception" / "testModel.py"
    consumer = root / "core-engine" / "steak_consumer"
    if not consumer.exists():
        raise FileNotFoundError("core-engine/steak_consumer is missing; run make -C core-engine")

    safe_name = video.stem.replace(" ", "_")
    detections_path = artifacts / f"{safe_name}.detections.jsonl"
    state_path = artifacts / f"{safe_name}.state.jsonl"
    env = os.environ.copy()
    env["STEAK_STATE_PATH"] = str(state_path)
    start = time.monotonic()
    state_process = subprocess.Popen(
        [str(consumer)], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE, env=env,
    )
    inference_process = subprocess.Popen(
        [sys.executable, "-u", str(detector), "--pipe", "--video", str(video),
         "--model", str(model), "--confidence", str(confidence), "--iou", str(iou),
         "--image-size", str(image_size), "--detections", str(detections_path)],
        stdout=state_process.stdin, stderr=subprocess.DEVNULL,
    )
    state_process.stdin.close()
    try:
        inference_code = inference_process.wait(timeout=timeout)
        stderr = state_process.stderr.read().decode("utf-8", errors="replace")
        state_code = state_process.wait(timeout=max(1, timeout - (time.monotonic() - start)))
    except subprocess.TimeoutExpired:
        inference_process.kill()
        state_process.kill()
        raise TimeoutError(f"pipeline exceeded {timeout}s")
    if inference_code or state_code:
        raise RuntimeError(f"pipeline failed: inference={inference_code}, state={state_code}")
    stats = next((json.loads(line) for line in reversed(stderr.splitlines())
                  if line.startswith("{") and line.endswith("}")), None)
    if not stats:
        raise RuntimeError("state engine returned no statistics")
    elapsed = time.monotonic() - start
    stats.update({
        "elapsed_seconds": round(elapsed, 3),
        "processing_fps": round(stats["frames_processed"] / elapsed, 3) if elapsed else 0.0,
    })
    return analyze(stats), detections_path, state_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--video-dir", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split", choices=["train", "validation", "holdout", "unassigned"])
    parser.add_argument("--clip", help="Run one manifest clip by path")
    parser.add_argument("--reviews-dir", type=Path)
    parser.add_argument("--confidence", type=float, default=0.4)
    parser.add_argument("--iou", type=float, default=0.4)
    parser.add_argument("--image-size", type=int, default=640)
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--max-videos", type=int)
    parser.add_argument("--list-only", action="store_true")
    args = parser.parse_args()

    manifest = load_manifest(args.manifest)
    clips = [clip for clip in manifest["clips"]
             if (not args.split or clip["split"] == args.split)
             and (not args.clip or clip["path"] == args.clip)]
    if args.max_videos is not None:
        clips = clips[:args.max_videos]
    if not clips:
        raise SystemExit("manifest contains no matching clips")
    args.model = args.model.resolve()
    if not args.model.exists():
        raise SystemExit(f"model not found: {args.model}")

    artifacts = args.output.resolve().parent / f"{args.output.stem}_artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    results = []
    for clip in clips:
        video = (args.video_dir / clip["path"]).resolve()
        if not video.exists():
            results.append({"clip": clip["path"], "split": clip["split"],
                            "error": f"video not found: {video}"})
            print(f"Missing {clip['path']}")
            continue
        info = video_info(video)
        if args.list_only:
            print(f"{clip['split']:10} {clip['path']} {info['frames']} frames")
            continue
        print(f"Running {clip['path']} ({clip['split']})")
        try:
            stats, detections, states = run_pipeline(
                video, args.model, artifacts, args.confidence, args.iou,
                args.image_size, args.timeout,
            )
            review = None
            if args.reviews_dir:
                review = args.reviews_dir / f"{video.stem}.review.mp4"
                render_review(video, detections, states, review)
            results.append({
                "clip": clip["path"], "split": clip["split"],
                "ground_truth": clip.get("ground_truth"), "video": info,
                "stats": stats, "review": str(review) if review else None,
            })
        except Exception as error:
            results.append({"clip": clip["path"], "split": clip["split"], "error": str(error)})

    if args.list_only:
        return
    report = {
        "report_version": 1,
        "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "manifest": {"path": str(args.manifest), "version": manifest["version"],
                     "sha256": sha256(args.manifest)},
        "model": {"path": str(args.model), "sha256": sha256(args.model)},
        "config": {"confidence": args.confidence, "iou": args.iou,
                   "image_size": args.image_size, "tracker": TRACKER_RULES},
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Report: {args.output}")


if __name__ == "__main__":
    main()
