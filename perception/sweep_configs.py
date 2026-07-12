#!/usr/bin/env python3
"""Run a bounded grid of validation benchmark configurations."""

from __future__ import annotations

import argparse
import itertools
import json
import subprocess
import sys
from pathlib import Path


def label(values: tuple[float, ...]) -> str:
    return "_".join(str(value).replace(".", "p") for value in values)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--video-dir", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--confidence", type=float, nargs="+", default=[0.4])
    parser.add_argument("--nms-iou", type=float, nargs="+", default=[0.4])
    parser.add_argument("--match-distance", type=float, nargs="+", default=[90.0])
    parser.add_argument("--dedupe-iou", type=float, nargs="+", default=[0.2])
    parser.add_argument("--max-age", type=int, nargs="+", default=[25])
    parser.add_argument("--max-runs", type=int, default=24)
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    configurations = list(itertools.product(
        args.confidence, args.nms_iou, args.match_distance,
        args.dedupe_iou, args.max_age,
    ))
    if len(configurations) > args.max_runs:
        raise SystemExit(f"refusing {len(configurations)} runs; raise --max-runs intentionally")

    runner = Path(__file__).with_name("run_video_tests.py")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary = []
    for index, (confidence, nms_iou, match_distance, dedupe_iou, max_age) in enumerate(configurations, 1):
        name = label((confidence, nms_iou, match_distance, dedupe_iou, float(max_age)))
        report_path = args.output_dir / f"{name}.json"
        command = [
            sys.executable, str(runner),
            "--manifest", str(args.manifest), "--split", "validation",
            "--video-dir", str(args.video_dir), "--model", str(args.model),
            "--output", str(report_path),
            "--confidence", str(confidence), "--iou", str(nms_iou),
            "--match-distance", str(match_distance), "--dedupe-iou", str(dedupe_iou),
            "--max-age", str(max_age), "--timeout", str(args.timeout),
        ]
        print(f"[{index}/{len(configurations)}] {' '.join(command)}")
        if not args.dry_run:
            subprocess.run(command, check=True)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            errors = [result["ground_truth"]["count_mean_absolute_error"]
                      for result in report["results"]
                      if result.get("ground_truth")
                      and result["ground_truth"]["count_mean_absolute_error"] is not None]
            summary.append({
                "report": str(report_path),
                "count_mean_absolute_error": round(sum(errors) / len(errors), 3) if errors else None,
                "config": report["config"],
            })
    if not args.dry_run:
        summary.sort(key=lambda item: (item["count_mean_absolute_error"] is None,
                                       item["count_mean_absolute_error"] or 0))
        (args.output_dir / "index.json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
