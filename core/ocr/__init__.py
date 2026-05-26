"""OCR-stage models and services for VOCra."""

from vocra.core.ocr.models import OcrInput, OcrOutput, OcrRunSummary
from vocra.core.ocr.registry import create_backend, register_backend
from vocra.core.ocr.service import OcrRunResult, run_ocr

__all__ = [
    "OcrInput",
    "OcrOutput",
    "OcrRunResult",
    "OcrRunSummary",
    "create_backend",
    "register_backend",
    "run_ocr",
]
