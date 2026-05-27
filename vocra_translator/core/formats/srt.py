from __future__ import annotations

from pathlib import Path

from vocra_translator.core.format_utils import format_srt_timestamp, normalize_newlines, parse_srt_timestamp
from vocra_translator.core.formats.base import SubtitleFormatAdapter
from vocra_translator.core.models import SubtitleDocument, SubtitleEntry


class SRTAdapter(SubtitleFormatAdapter):
    format_name = "srt"
    extensions = (".srt",)

    def load(self, path: str) -> SubtitleDocument:
        content = Path(path).read_text(encoding="utf-8-sig")
        blocks = [block for block in normalize_newlines(content).split("\n\n") if block.strip()]
        entries: list[SubtitleEntry] = []
        for index, block in enumerate(blocks, start=1):
            lines = [line for line in block.split("\n")]
            cursor = 0
            if lines and lines[0].strip().isdigit():
                cursor = 1
            if cursor >= len(lines) or "-->" not in lines[cursor]:
                continue
            timing = lines[cursor]
            start_text, end_text = [part.strip() for part in timing.split("-->", 1)]
            text = "\n".join(lines[cursor + 1 :]).strip()
            entries.append(
                SubtitleEntry(
                    id=index,
                    start_ms=parse_srt_timestamp(start_text),
                    end_ms=parse_srt_timestamp(end_text),
                    source_text=text,
                    format_metadata={},
                )
            )
        return SubtitleDocument(format_name=self.format_name, source_path=str(Path(path).resolve()), entries=entries, metadata={})

    def save(self, document: SubtitleDocument, path: str, *, text_source: str = "translation") -> str:
        lines: list[str] = []
        for index, entry in enumerate(document.entries, start=1):
            text = _resolve_text(entry, text_source)
            lines.extend(
                [
                    str(index),
                    f"{format_srt_timestamp(entry.start_ms)} --> {format_srt_timestamp(entry.end_ms)}",
                    normalize_newlines(text).strip("\n"),
                    "",
                ]
            )
        output_path = Path(path).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        return str(output_path)


def _resolve_text(entry: SubtitleEntry, text_source: str) -> str:
    return entry.source_text if text_source == "source" else entry.translation_text
