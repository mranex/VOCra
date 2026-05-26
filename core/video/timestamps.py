"""Timestamp helpers extracted from legacy VideOCR behavior."""

from __future__ import annotations

import datetime as _dt
from collections.abc import Mapping


def parse_time_str_to_ms(time_str: str) -> float:
    """Parse `MM:SS` or `HH:MM:SS` into milliseconds."""
    pieces = [float(part) for part in time_str.split(":")]
    if len(pieces) == 3:
        delta = _dt.timedelta(hours=pieces[0], minutes=pieces[1], seconds=pieces[2])
    elif len(pieces) == 2:
        delta = _dt.timedelta(minutes=pieces[0], seconds=pieces[1])
    else:
        raise ValueError(f'Time data "{time_str}" does not match format "%H:%M:%S"')
    return delta.total_seconds() * 1000


def format_srt_timestamp(frame_index: int, fps: float, offset_ms: float = 0.0) -> str:
    """Convert a frame index into an SRT timestamp."""
    if fps <= 0:
        raise ValueError("fps must be greater than zero.")
    return format_srt_timestamp_from_ms(frame_index / fps * 1000 + offset_ms)


def format_srt_timestamp_from_ms(ms: float) -> str:
    """Convert milliseconds into an SRT timestamp."""
    delta = _dt.timedelta(milliseconds=ms)
    minutes, seconds = divmod(delta.seconds, 60)
    hours, minutes = divmod(minutes, 60)
    milliseconds = delta.microseconds // 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def compute_subtitle_ms_range(
    start_frame_idx: int,
    end_frame_idx: int,
    frame_timestamps: Mapping[int, float],
    *,
    start_time_offset_ms: float = 0.0,
    avg_frame_duration_ms: float = 0.0,
) -> tuple[float, float]:
    """Rebuild subtitle timing from frame timestamps and the container offset."""
    start_time_ms = frame_timestamps.get(start_frame_idx, 0.0)
    end_time_ms = frame_timestamps.get(end_frame_idx + 1)
    if end_time_ms is None:
        last_frame_ms = frame_timestamps.get(end_frame_idx, start_time_ms)
        end_time_ms = last_frame_ms + avg_frame_duration_ms

    corrected_start = start_time_ms - start_time_offset_ms
    corrected_end = end_time_ms - start_time_offset_ms
    return corrected_start, corrected_end
