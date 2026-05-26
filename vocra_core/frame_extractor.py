from __future__ import annotations

import json
import math
import subprocess
from pathlib import Path
from typing import Callable

from vocra_core.project_manager import load_project, update_status


ProgressCallback = Callable[[int, int | None, str], None]


def extract_frames(project_dir: str, callback: ProgressCallback | None = None) -> int:
    progress = load_project(project_dir)
    project_path = Path(project_dir).expanduser().resolve()
    video_path = Path(progress["video_path"])
    interval_sec = float(progress["frame_extract"]["interval_sec"])
    frames_dir = project_path / progress["frame_extract"]["frames_dir"]
    timestamp_path = project_path / progress["cache_files"]["timestamp"]

    frames_dir.mkdir(parents=True, exist_ok=True)
    existing_frames = _list_png_files(frames_dir)
    if existing_frames and progress["status"].get("frames_extracted", False):
        if not timestamp_path.exists():
            _write_timestamp_file(timestamp_path, existing_frames, interval_sec)
        if callback:
            callback(len(existing_frames), len(existing_frames), "frames already extracted")
        return len(existing_frames)

    if existing_frames:
        for frame_path in existing_frames:
            frame_path.unlink()

    expected_total = _estimate_frame_count(video_path, interval_sec)
    if callback:
        callback(0, expected_total, "extracting frames")

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        f"fps=1/{interval_sec}",
        str(frames_dir / "%06d.png"),
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg frame extraction failed:\n{result.stderr}")

    frame_files = _list_png_files(frames_dir)
    if not frame_files:
        raise RuntimeError("ffmpeg completed but no frames were generated")

    _write_timestamp_file(timestamp_path, frame_files, interval_sec)
    update_status(project_dir, "frames_extracted", True)

    if callback:
        callback(len(frame_files), len(frame_files), "frames extracted")
    return len(frame_files)


def _build_timestamp(frame_name: str, interval_sec: float) -> str:
    frame_number = int(Path(frame_name).stem)
    total_millis = round((frame_number - 1) * interval_sec * 1000)
    hours, remainder = divmod(total_millis, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


def _estimate_frame_count(video_path: Path, interval_sec: float) -> int | None:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        return None

    try:
        duration = float(result.stdout.strip())
    except ValueError:
        return None

    if duration <= 0 or interval_sec <= 0:
        return None
    return max(1, math.ceil(duration / interval_sec))


def _list_png_files(directory: Path) -> list[Path]:
    return sorted(directory.glob("*.png"))


def _write_timestamp_file(timestamp_path: Path, frame_files: list[Path], interval_sec: float) -> None:
    payload = {
        "frames": [
            {"image": frame_path.name, "timestamp": _build_timestamp(frame_path.name, interval_sec)}
            for frame_path in frame_files
        ]
    }
    with timestamp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
