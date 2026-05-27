from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SubtitleEntry:
    id: int
    start_ms: int
    end_ms: int
    source_text: str
    translation_text: str = ""
    speaker: str = ""
    style_name: str = ""
    format_metadata: dict[str, Any] = field(default_factory=dict)
    edited: bool = False
    stale: bool = False
    status: str = "pending"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SubtitleEntry":
        return cls(
            id=int(payload.get("id", 0) or 0),
            start_ms=int(payload.get("start_ms", 0) or 0),
            end_ms=int(payload.get("end_ms", 0) or 0),
            source_text=str(payload.get("source_text", "") or ""),
            translation_text=str(payload.get("translation_text", "") or ""),
            speaker=str(payload.get("speaker", "") or ""),
            style_name=str(payload.get("style_name", "") or ""),
            format_metadata=dict(payload.get("format_metadata", {}) or {}),
            edited=bool(payload.get("edited", False)),
            stale=bool(payload.get("stale", False)),
            status=str(payload.get("status", "pending") or "pending"),
        )


@dataclass
class SubtitleDocument:
    format_name: str
    source_path: str
    entries: list[SubtitleEntry] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "format_name": self.format_name,
            "source_path": self.source_path,
            "entries": [entry.to_dict() for entry in self.entries],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SubtitleDocument":
        return cls(
            format_name=str(payload.get("format_name", "") or ""),
            source_path=str(payload.get("source_path", "") or ""),
            entries=[SubtitleEntry.from_dict(item) for item in payload.get("entries", [])],
            metadata=dict(payload.get("metadata", {}) or {}),
        )


@dataclass
class TranslationCacheRow:
    entry_id: int
    source_snapshot: str
    translation: str
    status: str = "done"
    edited: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "TranslationCacheRow":
        return cls(
            entry_id=int(payload.get("entry_id", 0) or 0),
            source_snapshot=str(payload.get("source_snapshot", "") or ""),
            translation=str(payload.get("translation", "") or ""),
            status=str(payload.get("status", "done") or "done"),
            edited=bool(payload.get("edited", False)),
        )
