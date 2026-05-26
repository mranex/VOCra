"""Detector backend factory helpers for Prepare."""

from __future__ import annotations

from typing import Any

from vocra.core.prepare.detectors.fake import FakeTextDetectorBackend
from vocra.core.prepare.detectors.paddle import PaddleTextDetectorBackend


def create_text_detector_backend(detector_config: dict[str, Any]):
    detector_name = normalize_detector_name(str(detector_config.get("name", "")))
    if detector_name == "fake":
        return FakeTextDetectorBackend()
    if detector_name == "paddleocr-text-detection":
        return PaddleTextDetectorBackend()
    raise ValueError(f"Unsupported detector backend '{detector_name}'.")


def normalize_detector_name(name: str) -> str:
    if name == "fake-text-detector":
        return "fake"
    return name.strip()
