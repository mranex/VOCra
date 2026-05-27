from __future__ import annotations

import hashlib
import json
import re
from typing import Iterable


TIMESTAMP_RE = re.compile(r"^(?:(\d+):)?(\d{2}):(\d{2})[,.](\d{3})$")


def parse_srt_timestamp(text: str) -> int:
    match = TIMESTAMP_RE.match(str(text or "").strip())
    if not match:
        raise ValueError(f"Invalid SRT timestamp: {text}")
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2))
    seconds = int(match.group(3))
    millis = int(match.group(4))
    return (((hours * 60) + minutes) * 60 + seconds) * 1000 + millis


def format_srt_timestamp(value_ms: int) -> str:
    total = max(0, int(value_ms))
    hours, rem = divmod(total, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, millis = divmod(rem, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def parse_vtt_timestamp(text: str) -> int:
    cleaned = str(text or "").strip()
    parts = cleaned.split(":")
    if len(parts) == 2:
        hours = 0
        minutes = int(parts[0])
        seconds_part = parts[1]
    elif len(parts) == 3:
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds_part = parts[2]
    else:
        raise ValueError(f"Invalid VTT timestamp: {text}")
    seconds_text, millis_text = seconds_part.split(".")
    seconds = int(seconds_text)
    millis = int(millis_text)
    return (((hours * 60) + minutes) * 60 + seconds) * 1000 + millis


def format_vtt_timestamp(value_ms: int, *, always_hours: bool = True) -> str:
    total = max(0, int(value_ms))
    hours, rem = divmod(total, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, millis = divmod(rem, 1_000)
    if always_hours or hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"
    return f"{minutes:02d}:{seconds:02d}.{millis:03d}"


def parse_ass_timestamp(text: str) -> int:
    cleaned = str(text or "").strip()
    parts = cleaned.split(":")
    if len(parts) != 3:
        raise ValueError(f"Invalid ASS timestamp: {text}")
    hours = int(parts[0])
    minutes = int(parts[1])
    seconds_text, centis_text = parts[2].split(".")
    seconds = int(seconds_text)
    centis = int(centis_text)
    return (((hours * 60) + minutes) * 60 + seconds) * 1000 + (centis * 10)


def format_ass_timestamp(value_ms: int) -> str:
    total = max(0, int(value_ms))
    hours, rem = divmod(total, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, millis = divmod(rem, 1_000)
    centis = min(99, int(round(millis / 10.0)))
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centis:02d}"


def format_display_timestamp(value_ms: int) -> str:
    total = max(0, int(value_ms))
    hours, rem = divmod(total, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, millis = divmod(rem, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


def normalize_newlines(text: str) -> str:
    return str(text or "").replace("\r\n", "\n").replace("\r", "\n")


def compute_entries_hash(entries: Iterable[dict[str, object]]) -> str:
    payload = json.dumps(list(entries), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def sanitize_project_name(name: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(name or "").strip())
    return cleaned.strip("._") or "subtitle_project"


def split_text_proportional(text: str, lengths: list[int]) -> list[str]:
    if not lengths:
        return []
    text = str(text or "")
    if len(lengths) == 1:
        return [text]
    total_weight = sum(max(1, value) for value in lengths)
    cut_points = [0]
    running = 0
    for value in lengths[:-1]:
        running += max(1, value)
        cut_points.append(round(len(text) * running / total_weight))
    cut_points.append(len(text))
    segments: list[str] = []
    for start, end in zip(cut_points, cut_points[1:]):
        segments.append(text[start:end])
    return segments
