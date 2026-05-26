"""Base detector contracts for VOCra Prepare backends."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

DetectionPoint = tuple[float, float]
DetectionPolygon = tuple[DetectionPoint, DetectionPoint, DetectionPoint, DetectionPoint]


@dataclass(frozen=True)
class DetectionGridResult:
    input_path: Path
    polygons: tuple[DetectionPolygon, ...]
    scores: tuple[float, ...]
    raw: dict[str, Any] | None = None


class TextDetectorBackend(Protocol):
    name: str

    def validate_config(self, config: dict[str, Any]) -> None:
        """Raise if the detector config is invalid."""

    def detect_grids(
        self,
        image_dir: Path,
        output_dir: Path,
        config: dict[str, Any],
    ) -> tuple[DetectionGridResult, ...]:
        """Run text detection against stitched grid images."""
