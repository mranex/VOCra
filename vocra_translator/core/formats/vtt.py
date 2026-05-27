from __future__ import annotations

from pathlib import Path

from vocra_translator.core.format_utils import format_vtt_timestamp, normalize_newlines, parse_vtt_timestamp
from vocra_translator.core.formats.base import SubtitleFormatAdapter
from vocra_translator.core.models import SubtitleDocument, SubtitleEntry


class VTTAdapter(SubtitleFormatAdapter):
    format_name = "vtt"
    extensions = (".vtt",)

    def load(self, path: str) -> SubtitleDocument:
        content = normalize_newlines(Path(path).read_text(encoding="utf-8-sig"))
        lines = content.split("\n")
        header_lines: list[str] = []
        body_lines = lines
        if lines and lines[0].startswith("WEBVTT"):
            header_lines.append(lines[0])
            cursor = 1
            while cursor < len(lines) and lines[cursor].strip():
                header_lines.append(lines[cursor])
                cursor += 1
            body_lines = lines[cursor + 1 :] if cursor < len(lines) else []

        blocks = []
        current: list[str] = []
        for line in body_lines:
            if line.strip():
                current.append(line)
                continue
            if current:
                blocks.append(current)
                current = []
        if current:
            blocks.append(current)

        entries: list[SubtitleEntry] = []
        ordered_blocks: list[dict[str, object]] = []
        next_id = 1
        for block in blocks:
            timing_index = next((index for index, line in enumerate(block) if "-->" in line), -1)
            if timing_index == -1:
                ordered_blocks.append({"type": "meta", "lines": block})
                continue
            identifier = "\n".join(block[:timing_index]).strip()
            timing_line = block[timing_index]
            cue_lines = block[timing_index + 1 :]
            start_text, end_part = [part.strip() for part in timing_line.split("-->", 1)]
            end_bits = end_part.split()
            end_text = end_bits[0]
            settings = " ".join(end_bits[1:])
            entry = SubtitleEntry(
                id=next_id,
                start_ms=parse_vtt_timestamp(start_text),
                end_ms=parse_vtt_timestamp(end_text),
                source_text="\n".join(cue_lines).strip(),
                format_metadata={"identifier": identifier, "settings": settings},
            )
            entries.append(entry)
            ordered_blocks.append({"type": "cue", "entry_id": next_id})
            next_id += 1

        return SubtitleDocument(
            format_name=self.format_name,
            source_path=str(Path(path).resolve()),
            entries=entries,
            metadata={"header_lines": header_lines or ["WEBVTT"], "ordered_blocks": ordered_blocks},
        )

    def save(self, document: SubtitleDocument, path: str, *, text_source: str = "translation") -> str:
        output_lines: list[str] = []
        header_lines = document.metadata.get("header_lines", ["WEBVTT"])
        output_lines.extend([str(line) for line in header_lines])
        output_lines.append("")

        entries_by_id = {entry.id: entry for entry in document.entries}
        if document.format_name == self.format_name and document.metadata.get("ordered_blocks"):
            for block in document.metadata.get("ordered_blocks", []):
                if block.get("type") == "meta":
                    output_lines.extend(str(line) for line in block.get("lines", []))
                    output_lines.append("")
                    continue
                entry = entries_by_id.get(int(block.get("entry_id", 0) or 0))
                if entry is None:
                    continue
                output_lines.extend(_cue_lines(entry, text_source))
                output_lines.append("")
        else:
            for entry in document.entries:
                output_lines.extend(_cue_lines(entry, text_source))
                output_lines.append("")

        output_path = Path(path).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(output_lines).rstrip() + "\n", encoding="utf-8")
        return str(output_path)


def _cue_lines(entry: SubtitleEntry, text_source: str) -> list[str]:
    identifier = str(entry.format_metadata.get("identifier", "") or "")
    settings = str(entry.format_metadata.get("settings", "") or "")
    timing_line = f"{format_vtt_timestamp(entry.start_ms)} --> {format_vtt_timestamp(entry.end_ms)}"
    if settings:
        timing_line = f"{timing_line} {settings}"
    lines: list[str] = []
    if identifier:
        lines.append(identifier)
    lines.append(timing_line)
    text = entry.source_text if text_source == "source" else entry.translation_text
    lines.extend(normalize_newlines(text).split("\n"))
    return lines
