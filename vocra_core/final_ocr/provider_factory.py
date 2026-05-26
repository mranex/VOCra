from __future__ import annotations

from vocra_core.final_ocr.base import FinalOCRProvider
from vocra_core.final_ocr.chrome_lens import ChromeLensOCRProvider
from vocra_core.final_ocr.openai_compatible import OpenAICompatibleOCRProvider
from vocra_core.final_ocr.paddleocr_vl import PaddleOCRVLLocalProvider


def create_final_ocr_provider(config: dict) -> FinalOCRProvider:
    provider = str(config.get("provider", "llama_cpp") or "llama_cpp")
    if provider == "llama_cpp":
        return PaddleOCRVLLocalProvider(config)
    if provider == "openai_compatible":
        return OpenAICompatibleOCRProvider(config)
    if provider == "chrome_lens":
        return ChromeLensOCRProvider(config)
    raise ValueError(f"Unknown final OCR provider: {provider}")
