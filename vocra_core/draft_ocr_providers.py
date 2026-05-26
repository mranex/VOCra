from __future__ import annotations

from typing import Any, Protocol


class DraftOCRProvider(Protocol):
    def initialize(self) -> None: ...

    def recognize(self, image_path: str) -> tuple[str, float]: ...

    def close(self) -> None: ...


class PaddleOCRDraftProvider:
    def __init__(self, language: str = "auto"):
        self._engine = None
        self._language = language

    def initialize(self) -> None:
        if self._engine is not None:
            return

        try:
            from paddleocr import PaddleOCR

            lang = "ch" if self._language == "auto" else self._language
            # Draft OCR should stay lightweight and resilient. PaddleOCR 3.5.0 on
            # this environment fails when the document-orientation classifier is
            # auto-enabled, so we keep only the core OCR stages here.
            self._engine = PaddleOCR(
                lang=lang,
                use_doc_orientation_classify=False,
                use_doc_unwarping=False,
                use_textline_orientation=False,
            )
        except Exception as exc:
            raise RuntimeError(
                "Failed to initialize PaddleOCR draft provider. "
                f"Verify paddleocr/paddlepaddle installation and local model files. Root cause: {exc}"
            ) from exc

    def recognize(self, image_path: str) -> tuple[str, float]:
        if self._engine is None:
            self.initialize()

        result = self._engine.predict(image_path)
        lines, confidences = _extract_texts_and_scores(result)

        if not lines and not confidences:
            return ("", 0.0)

        full_text = " ".join(lines).strip()
        average_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        return (full_text, round(average_confidence, 4))

    def close(self) -> None:
        self._engine = None


def create_draft_provider(config: dict) -> DraftOCRProvider:
    provider_name = config.get("provider", "paddleocr")
    if provider_name == "paddleocr":
        return PaddleOCRDraftProvider(language=config.get("language", "auto"))
    raise ValueError(f"Unknown draft OCR provider: {provider_name}")


def _extract_texts_and_scores(result: Any) -> tuple[list[str], list[float]]:
    if not result:
        return ([], [])

    first = result[0] if isinstance(result, list) and result else result

    if hasattr(first, "get") and callable(first.get):
        rec_texts = first.get("rec_texts", [])
        rec_scores = first.get("rec_scores", [])
        lines = [str(text).strip() for text in rec_texts if str(text).strip()]
        confidences = [float(score) for score in rec_scores]
        return (lines, confidences)

    if isinstance(result, list) and result and isinstance(result[0], list):
        entries = result[0]
        lines: list[str] = []
        confidences: list[float] = []
        for entry in entries:
            if not isinstance(entry, (list, tuple)) or len(entry) < 2:
                continue
            data = entry[1]
            if not isinstance(data, (list, tuple)) or len(data) < 2:
                continue
            text = str(data[0]).strip()
            confidence = float(data[1])
            if text:
                lines.append(text)
            confidences.append(confidence)
        return (lines, confidences)

    return ([], [])
