from __future__ import annotations

from pathlib import Path

from vocra_translator.core.formats.ass import ASSAdapter
from vocra_translator.core.formats.base import SubtitleFormatAdapter
from vocra_translator.core.formats.srt import SRTAdapter
from vocra_translator.core.formats.vtt import VTTAdapter
from vocra_translator.core.models import SubtitleDocument


ADAPTERS: list[SubtitleFormatAdapter] = [
    SRTAdapter(),
    VTTAdapter(),
    ASSAdapter(),
]


def adapter_for_path(path: str) -> SubtitleFormatAdapter:
    suffix = Path(path).suffix.lower()
    for adapter in ADAPTERS:
        if suffix in adapter.extensions:
            return adapter
    raise ValueError(f"Unsupported subtitle file: {path}")


def adapter_for_format(format_name: str) -> SubtitleFormatAdapter:
    target = str(format_name or "").lower()
    for adapter in ADAPTERS:
        if adapter.format_name == target:
            return adapter
    raise ValueError(f"Unsupported subtitle format: {format_name}")


def supported_formats() -> list[str]:
    return [adapter.format_name for adapter in ADAPTERS]


def load_subtitle_document(path: str) -> SubtitleDocument:
    return adapter_for_path(path).load(path)


def save_subtitle_document(document: SubtitleDocument, output_path: str, *, target_format: str, text_source: str) -> str:
    adapter = adapter_for_format(target_format)
    return adapter.save(document, output_path, text_source=text_source)
