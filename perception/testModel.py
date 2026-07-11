from __future__ import annotations

import argparse
import os
import sys

import cv2
# Keep Ultralytics config/cache in a writable project-local folder so it
# cannot emit cache permission errors into stdout (which corrupts pipe bytes).
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_YOLO_CONFIG_DIR = os.path.join(_SCRIPT_DIR, ".ultralytics")
os.environ.setdefault("YOLO_CONFIG_DIR", _YOLO_CONFIG_DIR)
os.makedirs(os.environ["YOLO_CONFIG_DIR"], exist_ok=True)
from ultralytics import YOLO

from steak_packet import pack_frame

# Resolve tracker config path relative to this script (works regardless of CWD)
_TRACKER_CONFIG = os.path.join(_SCRIPT_DIR, "custom_bytetrackconfig.yaml")


def test_video_path(video_path: str) -> bool:
    """Test if video file exists and can be opened. Logs to stderr so pipe mode keeps stdout clean."""
    if not os.path.exists(video_path):
        print(f"[ERROR] Video file not found: {video_path}", file=sys.stderr)
        return False
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"[ERROR] Failed to open video: {video_path}", file=sys.stderr)
        cap.release()
        return False
    cap.release()
    print(f"[SUCCESS] Video path valid and openable: {video_path}", file=sys.stderr)
    return True


def _display_available() -> bool:
    """True if we likely have a display (e.g. not Docker/headless Linux)."""
    return bool(os.environ.get("DISPLAY", "").strip())


def _run_headless_loop(model: YOLO, cap: cv2.VideoCapture) -> int:
    """Run inference and print results to stderr; no GUI (for Docker/headless)."""
    frame_idx = 0
    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            break
        frame_idx += 1

        results = model.track(
            frame,
            persist=True,
            tracker=_TRACKER_CONFIG,
            conf=0.4,
            iou=0.4,
            imgsz=640,
            verbose=False,
        )

        state = []
        if results[0].boxes is not None and len(results[0].boxes) > 0:
            boxes = results[0].boxes.xyxy.cpu().numpy()
            confs = results[0].boxes.conf.cpu().tolist()
            if results[0].boxes.id is not None:
                yids = results[0].boxes.id.int().cpu().tolist()
            else:
                yids = [-1] * len(confs)

            for box, conf, yid in zip(boxes, confs, yids):
                state.append(
                    {
                        "steak_id": int(yid),
                        "bbox": [float(box[0]), float(box[1]), float(box[2]), float(box[3])],
                        "conf": float(conf),
                        "last_seen_frame": int(frame_idx),
                    }
                )

        print(f"[Frame {frame_idx}] detections: {len(state)}", file=sys.stderr)
        for s in state:
            print(
                f"  steak_id={s['steak_id']} bbox={s['bbox']} conf={s['conf']:.2f}",
                file=sys.stderr,
            )

    return frame_idx


def _run_display_loop(model: YOLO, cap: cv2.VideoCapture) -> int:
    """Run inference and show annotated frames in a window; print results to stderr."""
    frame_idx = 0
    window_name = "Steak detection"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            break
        frame_idx += 1

        results = model.track(
            frame,
            persist=True,
            tracker=_TRACKER_CONFIG,
            conf=0.4,
            iou=0.4,
            imgsz=640,
            verbose=False,
        )

        state = []
        if results[0].boxes is not None and len(results[0].boxes) > 0:
            boxes = results[0].boxes.xyxy.cpu().numpy()
            confs = results[0].boxes.conf.cpu().tolist()
            if results[0].boxes.id is not None:
                yids = results[0].boxes.id.int().cpu().tolist()
            else:
                yids = [-1] * len(confs)

            for box, conf, yid in zip(boxes, confs, yids):
                state.append(
                    {
                        "steak_id": int(yid),
                        "bbox": [float(box[0]), float(box[1]), float(box[2]), float(box[3])],
                        "conf": float(conf),
                        "last_seen_frame": int(frame_idx),
                    }
                )

        print(f"[Frame {frame_idx}] detections: {len(state)}", file=sys.stderr)
        for s in state:
            print(
                f"  steak_id={s['steak_id']} bbox={s['bbox']} conf={s['conf']:.2f}",
                file=sys.stderr,
            )

        annotated = results[0].plot()
        cv2.imshow(window_name, annotated)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            print("[SYSTEM] Quit requested (q)", file=sys.stderr)
            break

    cv2.destroyAllWindows()
    return frame_idx


def _run_pipe_loop(model: YOLO, cap: cv2.VideoCapture) -> int:
    """Run inference and write packed frames (count + N×SteakPacket) to stdout."""
    frame_idx = 0
    while cap.isOpened():
        success, frame = cap.read()
        if not success:
            break
        frame_idx += 1

        results = model.track(
            frame,
            persist=True,
            tracker=_TRACKER_CONFIG,
            conf=0.4,
            iou=0.4,
            imgsz=640,
            verbose=False,
        )

        state = []
        if results[0].boxes is not None and len(results[0].boxes) > 0:
            boxes = results[0].boxes.xyxy.cpu().numpy()
            confs = results[0].boxes.conf.cpu().tolist()
            if results[0].boxes.id is not None:
                yids = results[0].boxes.id.int().cpu().tolist()
            else:
                yids = [-1] * len(confs)

            for box, conf, yid in zip(boxes, confs, yids):
                state.append(
                    {
                        "steak_id": int(yid),
                        "bbox": [float(box[0]), float(box[1]), float(box[2]), float(box[3])],
                        "conf": float(conf),
                        "last_seen_frame": int(frame_idx),
                    }
                )

        sys.stdout.buffer.write(pack_frame(state))
        sys.stdout.buffer.flush()

    return frame_idx


def run_display(model_path: str, video_path: str, headless: bool = False) -> None:
    """Display mode: show annotated video and print inference results to stderr.
    Uses headless (no GUI) when headless=True or when DISPLAY is not set (e.g. Docker)."""
    model = YOLO(model_path)
    if not test_video_path(video_path):
        return
    cap = cv2.VideoCapture(video_path)
    use_gui = not headless and _display_available()
    if use_gui:
        print(f"[SYSTEM] Starting inference (display) on: {video_path}", file=sys.stderr)
        _run_display_loop(model, cap)
    else:
        if not headless:
            print(
                "[SYSTEM] No DISPLAY (headless/Docker); showing inference results in terminal only.",
                file=sys.stderr,
            )
        print(f"[SYSTEM] Starting inference (headless) on: {video_path}", file=sys.stderr)
        _run_headless_loop(model, cap)
    cap.release()


def run_pipe(model_path: str, video_path: str) -> None:
    """Pipe mode: no GUI; write packed frames to stdout, flush each frame."""
    model = YOLO(model_path)
    if not test_video_path(video_path):
        return
    cap = cv2.VideoCapture(video_path)
    print(f"[SYSTEM] Starting inference (pipe) on: {video_path}", file=sys.stderr)
    _run_pipe_loop(model, cap)
    cap.release()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Steak detection: show inference results (display + stderr) or pipe to stdout"
    )
    parser.add_argument("--video", type=str, required=True, help="Video path")
    parser.add_argument(
        "--model",
        type=str,
        required=True,
        help="Path to YOLO weights",
    )
    parser.add_argument(
        "--pipe",
        action="store_true",
        help="Write packed binary frames to stdout instead of displaying results",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="No GUI; print inference results to stderr only (for Docker/CI)",
    )
    args = parser.parse_args()
    if args.pipe:
        run_pipe(args.model, args.video)
    else:
        run_display(args.model, args.video, headless=args.headless)


if __name__ == "__main__":
    # Allow importing steak_packet from same directory when run as script
    _dir = os.path.dirname(os.path.abspath(__file__))
    if _dir not in sys.path:
        sys.path.insert(0, _dir)
    main()
