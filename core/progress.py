"""Shared progress-event contracts for stage services."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProgressEvent:
    stage: str
    message: str
    current: int | float | None = None
    total: int | float | None = None
    percent: float | None = None
    segment_id: str | None = None
