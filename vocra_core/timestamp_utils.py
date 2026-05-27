from __future__ import annotations

from pathlib import Path


def build_interval_timestamp(frame_name: str, interval_sec: float) -> str:
    frame_number = int(Path(frame_name).stem)
    return seconds_to_timestamp((frame_number - 1) * interval_sec)


def seconds_to_timestamp(total_seconds: float) -> str:
    total_millis = max(0, round(float(total_seconds) * 1000))
    hours, remainder = divmod(total_millis, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, millis = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


def get_preferred_timestamp(frame_entry: dict) -> str:
    return str(frame_entry.get("pts_time") or frame_entry.get("timestamp") or "")


def resolve_end_timestamp(
    end_image: str,
    *,
    timestamp_lookup: dict[str, dict],
    frame_order: list[str],
    interval_sec: float,
) -> str:
    if end_image not in timestamp_lookup:
        raise KeyError(f"Missing timestamp for frame {end_image}")

    try:
        index = frame_order.index(end_image)
    except ValueError:
        index = -1

    if index >= 0 and index + 1 < len(frame_order):
        next_image = frame_order[index + 1]
        next_entry = timestamp_lookup.get(next_image)
        if next_entry is not None:
            return get_preferred_timestamp(next_entry)

    return add_interval_to_timestamp(get_preferred_timestamp(timestamp_lookup[end_image]), interval_sec)


def add_interval_to_timestamp(timestamp: str, interval_sec: float) -> str:
    total_millis = timestamp_to_millis(timestamp)
    return seconds_to_timestamp((total_millis / 1000.0) + float(interval_sec))


def timestamp_to_millis(timestamp: str) -> int:
    hours, minutes, rest = str(timestamp).split(":")
    seconds, millis = rest.split(".")
    return (
        int(hours) * 3_600_000
        + int(minutes) * 60_000
        + int(seconds) * 1_000
        + int(millis)
    )
