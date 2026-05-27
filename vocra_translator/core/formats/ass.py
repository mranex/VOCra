from __future__ import annotations

from pathlib import Path

from vocra_translator.core.format_utils import format_ass_timestamp, format_srt_timestamp, normalize_newlines, parse_ass_timestamp, split_text_proportional
from vocra_translator.core.formats.base import SubtitleFormatAdapter
from vocra_translator.core.models import SubtitleDocument, SubtitleEntry


DEFAULT_ASS_FORMAT_FIELDS = [
    "Layer",
    "Start",
    "End",
    "Style",
    "Name",
    "MarginL",
    "MarginR",
    "MarginV",
    "Effect",
    "Text",
]


class ASSAdapter(SubtitleFormatAdapter):
    format_name = "ass"
    extensions = (".ass",)

    def load(self, path: str) -> SubtitleDocument:
        content = normalize_newlines(Path(path).read_text(encoding="utf-8-sig"))
        lines = content.split("\n")
        entries: list[SubtitleEntry] = []
        ordered_blocks: list[dict[str, object]] = []
        current_section = ""
        event_fields = list(DEFAULT_ASS_FORMAT_FIELDS)
        next_id = 1

        for raw_line in lines:
            line = raw_line.rstrip("\n")
            stripped = line.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                current_section = stripped
                ordered_blocks.append({"type": "raw", "line": line})
                continue

            if current_section == "[Events]" and stripped.lower().startswith("format:"):
                event_fields = [item.strip() for item in line.split(":", 1)[1].split(",")]
                ordered_blocks.append({"type": "raw", "line": line})
                continue

            if current_section == "[Events]" and ":" in line:
                event_type, rest = line.split(":", 1)
                event_type = event_type.strip()
                if event_type == "Dialogue":
                    values = [item.strip() for item in rest.split(",", len(event_fields) - 1)]
                    if len(values) == len(event_fields):
                        field_map = dict(zip(event_fields, values))
                        raw_text = field_map.get("Text", "")
                        visible_text, ass_tokens = strip_ass_text(raw_text)
                        entry = SubtitleEntry(
                            id=next_id,
                            start_ms=parse_ass_timestamp(field_map.get("Start", "0:00:00.00")),
                            end_ms=parse_ass_timestamp(field_map.get("End", "0:00:00.00")),
                            source_text=visible_text,
                            speaker=str(field_map.get("Name", "") or ""),
                            style_name=str(field_map.get("Style", "") or ""),
                            format_metadata={
                                "event_type": event_type,
                                "event_fields": event_fields,
                                "ass_fields": field_map,
                                "ass_tokens": ass_tokens,
                            },
                        )
                        entries.append(entry)
                        ordered_blocks.append({"type": "entry", "entry_id": next_id})
                        next_id += 1
                        continue

            ordered_blocks.append({"type": "raw", "line": line})

        return SubtitleDocument(
            format_name=self.format_name,
            source_path=str(Path(path).resolve()),
            entries=entries,
            metadata={"ordered_blocks": ordered_blocks},
        )

    def save(self, document: SubtitleDocument, path: str, *, text_source: str = "translation") -> str:
        output_lines: list[str] = []
        entries_by_id = {entry.id: entry for entry in document.entries}
        if document.format_name == self.format_name and document.metadata.get("ordered_blocks"):
            for block in document.metadata.get("ordered_blocks", []):
                if block.get("type") == "raw":
                    output_lines.append(str(block.get("line", "")))
                    continue
                entry = entries_by_id.get(int(block.get("entry_id", 0) or 0))
                if entry is None:
                    continue
                output_lines.append(_render_preserved_dialogue(entry, text_source))
        else:
            output_lines.extend(_default_ass_header())
            for entry in document.entries:
                output_lines.append(_render_generic_dialogue(entry, text_source))

        output_path = Path(path).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(output_lines).rstrip() + "\n", encoding="utf-8")
        return str(output_path)


def strip_ass_text(text: str) -> tuple[str, list[dict[str, str]]]:
    tokens: list[dict[str, str]] = []
    text = str(text or "")
    cursor = 0
    while cursor < len(text):
        if text[cursor] == "{":
            end = text.find("}", cursor)
            if end == -1:
                tokens.append({"kind": "text", "value": text[cursor:]})
                break
            tokens.append({"kind": "tag", "value": text[cursor : end + 1]})
            cursor = end + 1
            continue
        if text.startswith("\\N", cursor) or text.startswith("\\n", cursor):
            tokens.append({"kind": "newline", "value": text[cursor : cursor + 2]})
            cursor += 2
            continue
        next_positions = [pos for pos in (text.find("{", cursor), text.find("\\N", cursor), text.find("\\n", cursor)) if pos != -1]
        next_cursor = min(next_positions) if next_positions else len(text)
        tokens.append({"kind": "text", "value": text[cursor:next_cursor]})
        cursor = next_cursor
    visible = []
    for token in tokens:
        if token["kind"] == "text":
            visible.append(token["value"].replace("\\h", " "))
        elif token["kind"] == "newline":
            visible.append("\n")
    return "".join(visible), tokens


def rebuild_ass_text(tokens: list[dict[str, str]], translated_text: str) -> str:
    translated_lines = normalize_newlines(translated_text).split("\n")
    segments: list[list[dict[str, str]]] = [[]]
    for token in tokens:
        if token["kind"] == "newline":
            segments.append([])
            continue
        segments[-1].append(token)

    rebuilt_lines: list[str] = []
    for line_index, segment_tokens in enumerate(segments):
        translated_line = translated_lines[line_index] if line_index < len(translated_lines) else ""
        text_tokens = [token for token in segment_tokens if token["kind"] == "text"]
        lengths = [len(token["value"]) for token in text_tokens]
        replacements = split_text_proportional(translated_line, lengths)
        text_cursor = 0
        parts: list[str] = []
        for token in segment_tokens:
            if token["kind"] == "tag":
                parts.append(token["value"])
                continue
            replacement = replacements[text_cursor] if text_cursor < len(replacements) else ""
            parts.append(replacement)
            text_cursor += 1
        rebuilt_lines.append("".join(parts))
    return "\\N".join(rebuilt_lines)


def flatten_ass_for_plain_text(text: str) -> str:
    visible, _tokens = strip_ass_text(text)
    return visible


def _render_preserved_dialogue(entry: SubtitleEntry, text_source: str) -> str:
    fields = dict(entry.format_metadata.get("ass_fields", {}) or {})
    tokens = list(entry.format_metadata.get("ass_tokens", []) or [])
    fields["Start"] = format_ass_timestamp(entry.start_ms)
    fields["End"] = format_ass_timestamp(entry.end_ms)
    text = entry.source_text if text_source == "source" else entry.translation_text
    fields["Text"] = rebuild_ass_text(tokens, text)
    field_order = list(entry.format_metadata.get("event_fields", DEFAULT_ASS_FORMAT_FIELDS))
    values = [str(fields.get(field, "")) for field in field_order]
    return f"{entry.format_metadata.get('event_type', 'Dialogue')}: {','.join(values)}"


def _render_generic_dialogue(entry: SubtitleEntry, text_source: str) -> str:
    text = entry.source_text if text_source == "source" else entry.translation_text
    payload = {
        "Layer": "0",
        "Start": format_ass_timestamp(entry.start_ms),
        "End": format_ass_timestamp(entry.end_ms),
        "Style": entry.style_name or "Default",
        "Name": entry.speaker,
        "MarginL": "0",
        "MarginR": "0",
        "MarginV": "0",
        "Effect": "",
        "Text": normalize_newlines(text).replace("\n", "\\N"),
    }
    return "Dialogue: " + ",".join(str(payload[field]) for field in DEFAULT_ASS_FORMAT_FIELDS)


def _default_ass_header() -> list[str]:
    return [
        "[Script Info]",
        "ScriptType: v4.00+",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Default,Arial,42,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,2,0,2,40,40,40,1",
        "",
        "[Events]",
        f"Format: {', '.join(DEFAULT_ASS_FORMAT_FIELDS)}",
    ]
