"""OCR backend implementations for VOCra."""

from vocra.core.ocr.backends.base import BackendTestResult, OcrBackend
from vocra.core.ocr.backends.fake import FakeOcrBackend
from vocra.core.ocr.backends.local_command import LocalCommandOcrBackend
from vocra.core.ocr.backends.ollama import OllamaOcrBackend
from vocra.core.ocr.backends.openai_compatible import OpenAICompatibleVisionBackend

__all__ = [
    "BackendTestResult",
    "FakeOcrBackend",
    "LocalCommandOcrBackend",
    "OllamaOcrBackend",
    "OcrBackend",
    "OpenAICompatibleVisionBackend",
]
