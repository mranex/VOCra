"""Prepare detector backends for VOCra."""

from vocra.core.prepare.detectors.base import (
    DetectionGridResult,
    DetectionPoint,
    DetectionPolygon,
    TextDetectorBackend,
)
from vocra.core.prepare.detectors.fake import FakeTextDetectorBackend
from vocra.core.prepare.detectors.paddle import (
    PaddleTextDetectorBackend,
    parse_paddle_text_detection_lines,
)
from vocra.core.prepare.detectors.registry import (
    create_text_detector_backend,
    normalize_detector_name,
)

__all__ = [
    "DetectionGridResult",
    "DetectionPoint",
    "DetectionPolygon",
    "FakeTextDetectorBackend",
    "PaddleTextDetectorBackend",
    "TextDetectorBackend",
    "create_text_detector_backend",
    "normalize_detector_name",
    "parse_paddle_text_detection_lines",
]
