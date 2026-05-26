"""Review-stage data contracts for VOCra."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ReviewState:
    segment_id: str
    original_text: str
    edited_text: str
    review_status: str
    notes: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReviewState:
        return cls(
            segment_id=str(data["segment_id"]),
            original_text=str(data.get("original_text", "")),
            edited_text=str(data.get("edited_text", "")),
            review_status=str(data.get("review_status", "pending")),
            notes=str(data.get("notes", "")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "original_text": self.original_text,
            "edited_text": self.edited_text,
            "review_status": self.review_status,
            "notes": self.notes,
        }


@dataclass(frozen=True)
class ReviewItem:
    segment_id: str
    zone_idx: int
    start_ms: int
    end_ms: int
    representative_image: Path
    original_text: str
    edited_text: str
    review_status: str
    notes: str
    ocr_status: str
    ocr_error: str | None
    quality_flags: tuple[str, ...] = ()

    @property
    def effective_text(self) -> str:
        if self.review_status == "rejected":
            return ""
        if self.review_status in {"accepted", "edited"}:
            return self.edited_text
        return self.original_text

    def to_dict(self) -> dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "zone_idx": self.zone_idx,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "representative_image": self.representative_image.as_posix(),
            "original_text": self.original_text,
            "edited_text": self.edited_text,
            "effective_text": self.effective_text,
            "review_status": self.review_status,
            "notes": self.notes,
            "ocr_status": self.ocr_status,
            "ocr_error": self.ocr_error,
            "quality_flags": list(self.quality_flags),
        }
