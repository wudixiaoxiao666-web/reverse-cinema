#!/usr/bin/env python3
"""Prepare local video evidence, without claiming shot boundaries or exact PTS."""

import argparse
import csv
import html
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys


def finite_number(value):
    result = float(value)
    if not math.isfinite(result):
        raise argparse.ArgumentTypeError("must be a finite number")
    return result


def tool_path(value, name):
    found = shutil.which(value or name)
    if not found:
        raise ValueError(f"{name} not found; install FFmpeg or pass --{name} /path/to/{name}")
    return found


def run(command, timeout=120):
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise ValueError(f"{Path(command[0]).name} timed out after {timeout}s") from exc
    if result.returncode:
        raise ValueError(f"{Path(command[0]).name} failed: {result.stderr[-2000:]}")
    return result.stdout


def sample_times(start, end, interval, limit):
    span = end - start
    if interval is not None:
        if interval <= 0:
            raise ValueError("--interval must be positive")
        count = max(1, math.ceil(span / interval - 1e-9))
        if count > limit:
            raise ValueError(f"{count} frames requested, limit {limit}; narrow range or raise --max-frames")
        return [start + i * interval for i in range(count)]
    # Midpoints avoid requesting a non-existent frame exactly at EOF.
    count = min(limit, max(1, math.ceil(span)))
    return [start + span * (i + 0.5) / count for i in range(count)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path, help="local input file; URLs are not accepted")
    parser.add_argument("--out", type=Path, required=True, help="new or empty evidence directory")
    parser.add_argument("--start", type=finite_number, default=0)
    parser.add_argument("--end", type=finite_number)
    parser.add_argument("--interval", type=finite_number, help="requested seconds between samples")
    parser.add_argument("--max-frames", type=int, default=48)
    parser.add_argument("--width", type=int, default=960, help="maximum output dimension")
    parser.add_argument("--audio", action="store_true", help="export mono 16kHz listening copy")
    parser.add_argument("--ffmpeg", default=os.environ.get("FFMPEG"))
    parser.add_argument("--ffprobe", default=os.environ.get("FFPROBE"))
    args = parser.parse_args()

    source = args.video.expanduser().resolve()
    output = args.out.expanduser().resolve()
    if not source.is_file():
        raise ValueError("input must be an existing local video file")
    if not 1 <= args.max_frames <= 240:
        raise ValueError("--max-frames must be between 1 and 240")
    if not 64 <= args.width <= 4096:
        raise ValueError("--width must be between 64 and 4096")
    if args.start < 0:
        raise ValueError("--start cannot be negative")
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        raise ValueError("output must be a new or empty directory; refusing to overwrite")
    ffmpeg = tool_path(args.ffmpeg, "ffmpeg")
    ffprobe = tool_path(args.ffprobe, "ffprobe")
    # Reject nested network protocols in container inputs as well as URL input paths.
    metadata = json.loads(run([
        ffprobe, "-v", "error", "-protocol_whitelist", "file,pipe",
        "-show_format", "-show_streams", "-of", "json", str(source),
    ]))
    videos = [s for s in metadata.get("streams", []) if s.get("codec_type") == "video"]
    if not videos:
        raise ValueError("no video stream found")
    duration_value = videos[0].get("duration") or metadata.get("format", {}).get("duration")
    try:
        duration = float(duration_value)
    except (TypeError, ValueError) as exc:
        raise ValueError("no usable duration found; use a readable video container") from exc
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("video duration is invalid")
    end = duration if args.end is None else args.end
    if not args.start < end <= duration:
        raise ValueError(f"require 0 <= start < end <= duration ({duration:.3f}s)")
    times = sample_times(args.start, end, args.interval, args.max_frames)

    frames_dir = output / "frames"
    frames_dir.mkdir(parents=True)
    manifest = {
        "schema_version": 1,
        "source_name": source.name,
        "duration_seconds": duration,
        "range_seconds": [args.start, end],
        "sampling": "explicit_interval" if args.interval is not None else "uniform_midpoints",
        "timestamp_semantics": "requested seek times, approximate; not exact frame PTS or shot boundaries",
        "coverage": "sparse samples; not proof of full motion, cuts, story, or audio",
        "video": {key: videos[0].get(key) for key in (
            "codec_name", "width", "height", "avg_frame_rate", "r_frame_rate",
            "pix_fmt", "color_space", "color_transfer", "color_primaries", "side_data_list",
        )},
        "audio_stream_present": any(s.get("codec_type") == "audio" for s in metadata.get("streams", [])),
        "audio_exported": False,
        "frames": [],
    }
    manifest_path = output / "manifest.json"

    def save_manifest(status):
        manifest["status"] = status
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    save_manifest("in_progress")
    try:
        for i, time in enumerate(times, 1):
            relative = f"frames/F{i:04d}.jpg"
            run([
                ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
                "-protocol_whitelist", "file,pipe", "-ss", f"{time:.6f}", "-i", str(source),
                "-map", "0:v:0", "-frames:v", "1", "-an",
                "-vf", f"scale={args.width}:{args.width}:force_original_aspect_ratio=decrease",
                "-q:v", "3", str(output / relative),
            ])
            if not (output / relative).is_file() or (output / relative).stat().st_size == 0:
                raise ValueError(f"no frame decoded near requested time {time:.3f}s")
            manifest["frames"].append({"id": f"F{i:04d}", "file": relative, "requested_time_seconds": round(time, 6)})
        if args.audio and manifest["audio_stream_present"]:
            run([
                ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-n",
                "-protocol_whitelist", "file,pipe", "-ss", f"{args.start:.6f}", "-i", str(source),
                "-t", f"{end - args.start:.6f}", "-map", "0:a:0", "-vn",
                "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(output / "audio.wav"),
            ], timeout=300)
            manifest["audio_exported"] = True
            manifest["audio_note"] = "Mono 16kHz listening copy; not evidence of original spatial mix or fidelity."
        elif args.audio:
            manifest["audio_note"] = "No audio stream; nothing exported."
        with (output / "frames.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=["id", "file", "requested_time_seconds"])
            writer.writeheader()
            writer.writerows(manifest["frames"])
        cards = "\n".join(
            f'<figure><img loading="lazy" src="{row["file"]}" alt="{row["id"]}">'
            f'<figcaption>{row["id"]} · approx. {row["requested_time_seconds"]:.3f}s (requested)</figcaption></figure>'
            for row in manifest["frames"]
        )
        page = (
            '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            '<title>Reverse Cinema Evidence</title><style>body{font:16px system-ui;margin:24px;background:#151515;color:#eee}'
            'main{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}'
            'figure{margin:0}img{width:100%;height:240px;object-fit:contain;background:#000}figcaption{padding:8px 0}</style>'
            f'<h1>{html.escape(source.name)}</h1><p>稀疏抽帧 · 标签为请求时间约数 · 不代表镜头边界或连续观看</p>'
            f'<main>{cards}</main></html>'
        )
        (output / "index.html").write_text(page, encoding="utf-8")
        save_manifest("complete")
    except Exception:
        save_manifest("incomplete")
        raise
    print(json.dumps({"output": str(output), "frames": len(times), "audio_exported": manifest["audio_exported"]}, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
