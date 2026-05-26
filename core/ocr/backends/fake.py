"""Deterministic fake OCR backend for VOCra tests and scaffolding."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from vocra.core.ocr.backends.base import BackendTestResult
from vocra.core.ocr.models import OcrInput, OcrOutput


class FakeOcrBackend:
    name = "fake"

    def validate_config(self, config: dict[str, Any]) -> None:
        fail_segment_ids = config.get("fail_segment_ids", [])
        if not isinstance(fail_segment_ids, list):
            raise ValueError("`fail_segment_ids` must be a list when provided.")

    def test_connection(self, config: dict[str, Any]) -> BackendTestResult:
        self.validate_config(config)
        return BackendTestResult(ok=True, message="Fake OCR backend is available.")

    def run(
        self,
        inputs: Iterable[OcrInput],
        config: dict[str, Any],
    ) -> Iterable[OcrOutput]:
        self.validate_config(config)
        fail_segment_ids = {str(value) for value in config.get("fail_segment_ids", [])}
        empty_segment_ids = {str(value) for value in config.get("empty_segment_ids", [])}
        text_template = str(config.get("text_template", "Text for {segment_id}"))

        for item in inputs:
            if item.segment_id in fail_segment_ids:
                yield OcrOutput(
                    segment_id=item.segment_id,
                    text="",
                    confidence=None,
                    raw={"error": f"Simulated OCR failure for {item.segment_id}"},
                    status="error",
                    error=f"Simulated OCR failure for {item.segment_id}",
                )
                continue

            text = "" if item.segment_id in empty_segment_ids else text_template.format(
                segment_id=item.segment_id,
                zone_idx=item.zone_idx,
            )
            yield OcrOutput(
                segment_id=item.segment_id,
                text=text,
                confidence=None,
                raw={
                    "backend": self.name,
                    "segment_id": item.segment_id,
                    "image_path": str(item.image_path),
                    "zone_idx": item.zone_idx,
                    "text": text,
                },
                status="ok",
            )
