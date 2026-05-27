from __future__ import annotations

from abc import ABC, abstractmethod

from vocra_translator.core.models import SubtitleDocument


class SubtitleFormatAdapter(ABC):
    format_name: str
    extensions: tuple[str, ...]

    @abstractmethod
    def load(self, path: str) -> SubtitleDocument:
        raise NotImplementedError

    @abstractmethod
    def save(self, document: SubtitleDocument, path: str, *, text_source: str = "translation") -> str:
        raise NotImplementedError
