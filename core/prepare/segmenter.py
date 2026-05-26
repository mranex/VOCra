"""Prepare segment/layout grouping helpers extracted from legacy VideOCR."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from vocra.core.prepare.detectors.base import DetectionPolygon
from vocra.core.prepare.stitch import StitchTilePlacement

Rect = tuple[float, float, float, float]


@dataclass(frozen=True)
class DetectedFrame:
    frame_idx: int
    zone_idx: int
    polygons: tuple[DetectionPolygon, ...]
    detection_score: float
    grid_file: Path
    placement: StitchTilePlacement
    source_frame_indices: tuple[int, ...] = ()


@dataclass(frozen=True)
class LayoutGroup:
    union_rects: tuple[Rect, ...]
    frames: tuple[DetectedFrame, ...]


def get_line_rects(polygons: tuple[DetectionPolygon, ...]) -> tuple[Rect, ...]:
    """Convert polygons into merged line bounding boxes."""
    if not polygons:
        return ()

    rects: list[list[float]] = []
    for polygon in polygons:
        xs = [point[0] for point in polygon]
        ys = [point[1] for point in polygon]
        rects.append([min(xs), min(ys), max(xs), max(ys)])

    rects.sort(key=lambda rect: rect[1])
    merged_lines: list[list[float]] = []
    for rect in rects:
        if not merged_lines:
            merged_lines.append(rect)
            continue

        last = merged_lines[-1]
        overlap_top = max(last[1], rect[1])
        overlap_bottom = min(last[3], rect[3])
        if overlap_top < overlap_bottom:
            merged_lines[-1] = [
                min(last[0], rect[0]),
                min(last[1], rect[1]),
                max(last[2], rect[2]),
                max(last[3], rect[3]),
            ]
        else:
            merged_lines.append(rect)

    return tuple((rect[0], rect[1], rect[2], rect[3]) for rect in merged_lines)


def are_rect_lists_similar(
    rects1: tuple[Rect, ...],
    rects2: tuple[Rect, ...],
    tolerance: float,
) -> bool:
    """Compare bounding-box layouts using normalized size/center deltas."""
    if len(rects1) != len(rects2):
        return False

    for rect1, rect2 in zip(rects1, rects2):
        width1 = rect1[2] - rect1[0]
        height1 = rect1[3] - rect1[1]
        width2 = rect2[2] - rect2[0]
        height2 = rect2[3] - rect2[1]
        center_x1 = rect1[0] + width1 / 2
        center_y1 = rect1[1] + height1 / 2
        center_x2 = rect2[0] + width2 / 2
        center_y2 = rect2[1] + height2 / 2

        max_width = max(width1, width2, 1.0)
        max_height = max(height1, height2, 1.0)
        if not (
            abs(width1 - width2) / max_width <= tolerance
            and abs(height1 - height2) / max_height <= tolerance
            and abs(center_x1 - center_x2) / max_width <= tolerance
            and abs(center_y1 - center_y2) / max_height <= tolerance
        ):
            return False

    return True


def group_frames_by_layout(
    frames: tuple[DetectedFrame, ...],
    *,
    tolerance: float = 0.05,
) -> tuple[LayoutGroup, ...]:
    """Group frames whose detected text-box layouts are spatially similar."""
    sorted_frames = sorted(frames, key=lambda frame: frame.frame_idx)
    groups: list[LayoutGroup] = []
    current_frames: list[DetectedFrame] = []
    current_union_rects: tuple[Rect, ...] = ()

    for frame in sorted_frames:
        line_rects = get_line_rects(frame.polygons)
        if not line_rects:
            continue

        if not current_frames:
            current_frames = [frame]
            current_union_rects = line_rects
            continue

        if are_rect_lists_similar(current_union_rects, line_rects, tolerance):
            current_frames.append(frame)
            current_union_rects = _merge_rect_unions(current_union_rects, line_rects)
            continue

        groups.append(LayoutGroup(union_rects=current_union_rects, frames=tuple(current_frames)))
        current_frames = [frame]
        current_union_rects = line_rects

    if current_frames:
        groups.append(LayoutGroup(union_rects=current_union_rects, frames=tuple(current_frames)))
    return tuple(groups)


def _merge_rect_unions(rects1: tuple[Rect, ...], rects2: tuple[Rect, ...]) -> tuple[Rect, ...]:
    merged: list[Rect] = []
    for rect1, rect2 in zip(rects1, rects2):
        merged.append(
            (
                min(rect1[0], rect2[0]),
                min(rect1[1], rect2[1]),
                max(rect1[2], rect2[2]),
                max(rect1[3], rect2[3]),
            )
        )
    return tuple(merged)
