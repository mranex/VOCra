"""OCR backend registry for VOCra."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from vocra.core.ocr.backends.fake import FakeOcrBackend
from vocra.core.ocr.backends.local_command import LocalCommandOcrBackend
from vocra.core.ocr.backends.ollama import OllamaOcrBackend
from vocra.core.ocr.backends.openai_compatible import OpenAICompatibleVisionBackend

BackendFactory = Callable[[], object]

_BACKEND_FACTORIES: dict[str, BackendFactory] = {
    "fake": FakeOcrBackend,
    "local-command": LocalCommandOcrBackend,
    "ollama": OllamaOcrBackend,
    "openai-compatible-vision": OpenAICompatibleVisionBackend,
}


def register_backend(name: str, factory: BackendFactory) -> None:
    normalized_name = name.strip().lower()
    if not normalized_name:
        raise ValueError("Backend name must not be empty.")
    _BACKEND_FACTORIES[normalized_name] = factory


def create_backend(config: dict[str, Any]) -> object:
    backend_name = str(config.get("backend", "")).strip().lower()
    if not backend_name:
        raise ValueError("OCR config must include a `backend` value.")

    try:
        factory = _BACKEND_FACTORIES[backend_name]
    except KeyError as exc:
        raise ValueError(f"Unsupported OCR backend: {backend_name}") from exc

    return factory()


def list_backends() -> tuple[str, ...]:
    return tuple(_BACKEND_FACTORIES.keys())
