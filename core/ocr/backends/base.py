"""Base OCR backend contracts for VOCra."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Protocol

from vocra.core.ocr.models import OcrInput, OcrOutput


@dataclass(frozen=True)
class BackendTestResult:
    ok: bool
    message: str


class OcrBackend(Protocol):
    name: str

    def validate_config(self, config: dict[str, Any]) -> None:
        """Raise if the backend config is invalid."""

    def test_connection(self, config: dict[str, Any]) -> BackendTestResult:
        """Validate the backend is callable before a full OCR run."""

    def run(
        self,
        inputs: Iterable[OcrInput],
        config: dict[str, Any],
    ) -> Iterable[OcrOutput]:
        """Run OCR over prepared inputs and yield normalized outputs."""
