from __future__ import annotations

import json
from pathlib import Path

from vocra_core.project_manager import load_project


def export_srt(project_dir: str, output_path: str, use_translation: bool = False) -> str:
    entries = _build_export_entries(project_dir, use_translation=use_translation)
    lines: list[str] = []
    for index, entry in enumerate(entries, start=1):
        lines.extend(
            [
                str(index),
                f"{_to_srt_timestamp(entry['start'])} --> {_to_srt_timestamp(entry['end'])}",
                entry["text"],
                "",
            ]
        )
    content = "\n".join(lines).rstrip() + "\n"
    return _write_output(output_path, content)


def export_ass(project_dir: str, output_path: str, use_translation: bool = False) -> str:
    entries = _build_export_entries(project_dir, use_translation=use_translation)
    header = "\n".join(
        [
            "[Script Info]",
            "ScriptType: v4.00+",
            "Collisions: Normal",
            "PlayResX: 1920",
            "PlayResY: 1080",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            "Style: Default,Arial,42,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,0,0,0,0,100,100,0,0,1,2,0,2,40,40,40,1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
    )
    event_lines = [
        f"Dialogue: 0,{_to_ass_timestamp(entry['start'])},{_to_ass_timestamp(entry['end'])},Default,,0,0,0,,{_escape_ass_text(entry['text'])}"
        for entry in entries
    ]
    content = header + "\n" + "\n".join(event_lines) + "\n"
    return _write_output(output_path, content)


def export_txt(project_dir: str, output_path: str, use_translation: bool = False) -> str:
    entries = _build_export_entries(project_dir, use_translation=use_translation)
    content = "\n".join(f"[{entry['start']}] {entry['text']}" for entry in entries).rstrip() + "\n"
    return _write_output(output_path, content)


def _build_export_entries(project_dir: str, *, use_translation: bool) -> list[dict[str, str]]:
    progress = load_project(project_dir)
    project_path = Path(project_dir).expanduser().resolve()

    segments = _load_json(project_path / progress["cache_files"]["segments"]).get("segments", [])
    timestamps = _load_json(project_path / progress["cache_files"]["timestamp"]).get("frames", [])
    ocr_items = _load_json(project_path / progress["cache_files"]["ocr_final"]).get("items", [])
    translation_items = _load_json(project_path / progress["cache_files"]["translation"], default={"items": []}).get("items", [])

    timestamp_lookup = {item["image"]: item["timestamp"] for item in timestamps}
    ocr_lookup = {item["image"]: item for item in ocr_items}
    translation_lookup = {int(item["segment_id"]): item for item in translation_items}

    entries: list[dict[str, str]] = []
    for segment in segments:
        start_image = segment["start_image"]
        end_image = segment["end_image"]
        represent_image = segment["represent_image"]
        segment_id = int(segment["id"])

        if start_image not in timestamp_lookup or end_image not in timestamp_lookup:
            raise KeyError(f"Missing timestamp for segment {segment_id}")

        if use_translation:
            translated = translation_lookup.get(segment_id)
            if translated is None:
                raise KeyError(f"Missing translation for segment {segment_id}")
            text = str(translated.get("translation", "") or "")
        else:
            ocr_item = ocr_lookup.get(represent_image)
            if ocr_item is None:
                raise KeyError(f"Missing OCR final text for image {represent_image}")
            text = str(ocr_item.get("text", "") or "")

        entries.append(
            {
                "start": timestamp_lookup[start_image],
                "end": timestamp_lookup[end_image],
                "text": text,
            }
        )
    return entries


def _to_srt_timestamp(timestamp: str) -> str:
    return str(timestamp).replace(".", ",")


def _to_ass_timestamp(timestamp: str) -> str:
    hours, minutes, rest = str(timestamp).split(":")
    seconds, millis = rest.split(".")
    centis = int(round(int(millis) / 10.0))
    if centis >= 100:
        centis = 99
    return f"{int(hours)}:{minutes}:{seconds}.{centis:02d}"


def _escape_ass_text(text: str) -> str:
    return str(text).replace("\n", "\\N").replace("\r", "")


def _load_json(path: Path, default: dict | None = None) -> dict:
    if not path.exists():
        if default is not None:
            return default
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_output(output_path: str, content: str) -> str:
    output_file = Path(output_path).expanduser().resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(content, encoding="utf-8")
    return str(output_file)
