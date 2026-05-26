"""Helpers for building final Prepare subtitle segments."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from vocra.core.prepare.frame_filter import RepresentativeFrame
from vocra.core.prepare.models import DetectionBox, SubtitleSegment
from vocra.core.prepare.sampler import compute_average_frame_duration_ms
from vocra.core.video.timestamps import compute_subtitle_ms_range


def build_subtitle_segments(
    representatives: tuple[RepresentativeFrame, ...],
    frame_timestamps: Mapping[int, float],
    *,
    start_time_offset_ms: float = 0.0,
    avg_frame_duration_ms: float | None = None,
) -> tuple[SubtitleSegment, ...]:
    """Convert representative batches into final timing-owned subtitle segments."""
    average_frame_duration_ms = (
        compute_average_frame_duration_ms(frame_timestamps)
        if avg_frame_duration_ms is None
        else avg_frame_duration_ms
    )
    segments: list[SubtitleSegment] = []

    for index, representative in enumerate(representatives, start=1):
        start_ms, end_ms = compute_subtitle_ms_range(
            representative.frame_idx,
            representative.end_frame_idx,
            frame_timestamps,
            start_time_offset_ms=start_time_offset_ms,
            avg_frame_duration_ms=average_frame_duration_ms,
        )
        segments.append(
            SubtitleSegment(
                segment_id=f"seg_{index:06d}",
                zone_idx=representative.zone_idx,
                start_ms=max(0, int(round(start_ms))),
                end_ms=max(0, int(round(end_ms))),
                start_frame_idx=representative.frame_idx,
                end_frame_idx=representative.end_frame_idx,
                representative_image=Path(
                    f"representative_images/seg_{index:06d}_z{representative.zone_idx}.jpg"
                ),
                source_frame_indices=representative.source_frame_indices,
                detection_boxes=_resolve_detection_boxes(representative),
                status="prepared",
            )
        )

    return tuple(segments)


def _resolve_detection_boxes(representative: RepresentativeFrame) -> tuple[DetectionBox, ...]:
    if representative.source_polygons:
        return tuple(
            tuple((float(point[0]), float(point[1])) for point in polygon)
            for polygon in representative.source_polygons
        )
    return tuple(_rect_to_box(rect) for rect in representative.union_rects)


def _rect_to_box(rect: tuple[float, float, float, float]) -> DetectionBox:
    return (
        (rect[0], rect[1]),
        (rect[2], rect[1]),
        (rect[2], rect[3]),
        (rect[0], rect[3]),
    )
