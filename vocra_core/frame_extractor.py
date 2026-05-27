from __future__ import annotations

import json
import math
import re
import subprocess
from pathlib import Path
from typing import Callable

from vocra_core.project_manager import load_project, update_status
from vocra_core.timestamp_utils import build_interval_timestamp, seconds_to_timestamp


ProgressCallback = Callable[[int, int | None, str], None]
TIMESTAMP_SCHEMA_VERSION = 2


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
        if _timestamp_file_needs_refresh(timestamp_path, existing_frames, interval_sec):
            _refresh_timestamp_file(video_path, timestamp_path, existing_frames, interval_sec)
        if callback:
            callback(len(existing_frames), len(existing_frames), "frames already extracted")
        return len(existing_frames)

    if existing_frames:
        for frame_path in existing_frames:
            frame_path.unlink()

    expected_total = _estimate_frame_count(video_path, interval_sec)
    if callback:
        callback(0, expected_total, "extracting frames")

    result = _run_ffmpeg_sampling(
        video_path,
        interval_sec,
        output_target=str(frames_dir / "%06d.png"),
    )
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg frame extraction failed:\n{result.stderr}")

    frame_files = _list_png_files(frames_dir)
    if not frame_files:
        raise RuntimeError("ffmpeg completed but no frames were generated")

    pts_times = _normalize_pts_count(_parse_showinfo_pts(result.stderr), len(frame_files))
    _write_timestamp_file(timestamp_path, frame_files, interval_sec, pts_times=pts_times)
    update_status(project_dir, "frames_extracted", True)

    if callback:
        callback(len(frame_files), len(frame_files), "frames extracted")
    return len(frame_files)


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


def _write_timestamp_file(
    timestamp_path: Path,
    frame_files: list[Path],
    interval_sec: float,
    *,
    pts_times: list[float] | None = None,
) -> None:
    payload = {
        "version": TIMESTAMP_SCHEMA_VERSION,
        "interval_sec": float(interval_sec),
        "timestamp_source": "pts" if pts_times else "computed",
        "frames": [
            _build_timestamp_entry(frame_path.name, interval_sec, pts_times, index)
            for index, frame_path in enumerate(frame_files)
        ]
    }
    with timestamp_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def _build_timestamp_entry(
    frame_name: str,
    interval_sec: float,
    pts_times: list[float] | None,
    index: int,
) -> dict:
    entry = {
        "image": frame_name,
        "timestamp": build_interval_timestamp(frame_name, interval_sec),
    }
    if pts_times and index < len(pts_times):
        entry["pts_time"] = seconds_to_timestamp(pts_times[index])
    return entry


def _refresh_timestamp_file(
    video_path: Path,
    timestamp_path: Path,
    frame_files: list[Path],
    interval_sec: float,
) -> None:
    result = _run_ffmpeg_sampling(video_path, interval_sec, output_target="-", null_output=True)
    pts_times = _normalize_pts_count(_parse_showinfo_pts(result.stderr), len(frame_files))
    _write_timestamp_file(timestamp_path, frame_files, interval_sec, pts_times=pts_times)


def _run_ffmpeg_sampling(
    video_path: Path,
    interval_sec: float,
    *,
    output_target: str,
    null_output: bool = False,
):
    command = [
        "ffmpeg",
        "-v",
        "info",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        f"fps=1/{interval_sec},showinfo",
    ]
    if null_output:
        command.extend(["-f", "null"])
    command.append(output_target)
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _parse_showinfo_pts(stderr: str) -> list[float]:
    pattern = re.compile(r"pts_time:(-?\d+(?:\.\d+)?)")
    return [float(match.group(1)) for match in pattern.finditer(str(stderr))]


def _normalize_pts_count(pts_times: list[float], frame_count: int) -> list[float] | None:
    if len(pts_times) != frame_count:
        return None
    return pts_times


def _timestamp_file_needs_refresh(timestamp_path: Path, frame_files: list[Path], interval_sec: float) -> bool:
    if not timestamp_path.exists():
        return True

    try:
        with timestamp_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception:
        return True

    if int(payload.get("version", 0) or 0) < TIMESTAMP_SCHEMA_VERSION:
        return True

    cached_interval = payload.get("interval_sec")
    try:
        if cached_interval is None or abs(float(cached_interval) - float(interval_sec)) > 1e-9:
            return True
    except (TypeError, ValueError):
        return True

    frames = payload.get("frames", [])
    if len(frames) != len(frame_files):
        return True

    cached_names = [str(frame.get("image", "")) for frame in frames]
    frame_names = [frame_path.name for frame_path in frame_files]
    return cached_names != frame_names
