"""OCR-stage data contracts for VOCra."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class OcrInput:
    segment_id: str
    image_path: Path
    zone_idx: int
    start_ms: int
    end_ms: int
    metadata: dict[str, Any]


@dataclass(frozen=True)
class OcrOutput:
    segment_id: str
    text: str
    confidence: float | None
    raw: Any
    status: str
    error: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OcrOutput:
        return cls(
            segment_id=str(data["segment_id"]),
            text=str(data.get("text", "")),
            confidence=(
                None if data.get("confidence") is None else float(data["confidence"])
            ),
            raw=data.get("raw"),
            status=str(data["status"]),
            error=None if data.get("error") is None else str(data["error"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "text": self.text,
            "confidence": self.confidence,
            "raw": self.raw,
            "status": self.status,
            "error": self.error,
        }


@dataclass(frozen=True)
class OcrRunSummary:
    run_id: str
    ok_count: int
    error_count: int
    empty_count: int
