"""SRT formatting helpers for VOCra."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from vocra.core.prepare.models import SubtitleSegment


@dataclass(frozen=True)
class SrtEntry:
    segment_id: str
    start_ms: int
    end_ms: int
    text: str
    zone_idx: int


def format_srt_timestamp(ms: int) -> str:
    total_ms = max(ms, 0)
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def build_srt(entries: Iterable[SrtEntry]) -> str:
    lines: list[str] = []
    for index, entry in enumerate(entries, start=1):
        lines.extend(
            [
                str(index),
                (
                    f"{format_srt_timestamp(entry.start_ms)} --> "
                    f"{format_srt_timestamp(entry.end_ms)}"
                ),
                entry.text,
                "",
            ]
        )
    return "\n".join(lines)


def build_entries(
    segments: Iterable[SubtitleSegment],
    text_by_segment: dict[str, str],
    *,
    min_subtitle_duration_ms: int = 0,
    empty_text_policy: str = "skip",
) -> list[SrtEntry]:
    entries: list[SrtEntry] = []
    for segment in sorted(segments, key=lambda item: (item.start_ms, item.zone_idx, item.segment_id)):
        text = text_by_segment.get(segment.segment_id, "").strip()
        if not text and empty_text_policy == "skip":
            continue

        end_ms = max(segment.end_ms, segment.start_ms + min_subtitle_duration_ms)
        entries.append(
            SrtEntry(
                segment_id=segment.segment_id,
                start_ms=segment.start_ms,
                end_ms=end_ms,
                text=text,
                zone_idx=segment.zone_idx,
            )
        )
    return entries
