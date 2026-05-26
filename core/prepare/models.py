"""Prepare-stage data contracts for VOCra."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

DetectionPoint = tuple[float, float]
DetectionBox = tuple[DetectionPoint, DetectionPoint, DetectionPoint, DetectionPoint]


@dataclass(frozen=True)
class CropZone:
    zone_idx: int
    x: int
    y: int
    width: int
    height: int


@dataclass(frozen=True)
class SubtitleSegment:
    segment_id: str
    zone_idx: int
    start_ms: int
    end_ms: int
    start_frame_idx: int
    end_frame_idx: int
    representative_image: Path
    source_frame_indices: tuple[int, ...]
    detection_boxes: tuple[DetectionBox, ...]
    status: str = "prepared"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SubtitleSegment:
        boxes = tuple(
            tuple((float(point[0]), float(point[1])) for point in box)
            for box in data.get("detection_boxes", [])
        )
        return cls(
            segment_id=str(data["segment_id"]),
            zone_idx=int(data["zone_idx"]),
            start_ms=int(data["start_ms"]),
            end_ms=int(data["end_ms"]),
            start_frame_idx=int(data.get("start_frame_idx", 0)),
            end_frame_idx=int(data.get("end_frame_idx", 0)),
            representative_image=Path(data["representative_image"]),
            source_frame_indices=tuple(int(value) for value in data["source_frame_indices"]),
            detection_boxes=boxes,
            status=str(data.get("status", "prepared")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "zone_idx": self.zone_idx,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "start_frame_idx": self.start_frame_idx,
            "end_frame_idx": self.end_frame_idx,
            "representative_image": self.representative_image.as_posix(),
            "source_frame_indices": list(self.source_frame_indices),
            "detection_boxes": [
                [[_serialize_number(point[0]), _serialize_number(point[1])] for point in box]
                for box in self.detection_boxes
            ],
            "status": self.status,
        }


def _serialize_number(value: float) -> int | float:
    integer_value = int(value)
    if integer_value == value:
        return integer_value
    return value


@dataclass(frozen=True)
class PrepareSummary:
    segment_count: int
    representative_image_count: int
    source_frame_count: int


@dataclass(frozen=True)
class PrepareRunSummary:
    run_id: str
    sampled_frame_count: int
    detected_frame_count: int
    layout_group_count: int
    representative_candidate_count: int
    deleted_duplicate_count: int
    segment_count: int = 0
