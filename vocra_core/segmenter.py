from __future__ import annotations

import difflib
import json
from pathlib import Path
from typing import Callable

from vocra_core.project_manager import load_project, update_status


ProgressCallback = Callable[[int, int | None, str], None]


def build_segments(
    project_dir: str,
    similarity_threshold: float = 0.5,
    callback: ProgressCallback | None = None,
) -> int:
    progress = load_project(project_dir)
    project_path = Path(project_dir).expanduser().resolve()
    segments_path = project_path / progress["cache_files"]["segments"]
    ocr_path = project_path / progress["cache_files"]["ocr_origin"]

    if segments_path.exists() and progress["status"].get("segments_done", False):
        with segments_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        segments = data.get("segments", [])
        if callback:
            callback(len(segments), len(segments), "segments already built")
        return len(segments)

    with ocr_path.open("r", encoding="utf-8") as handle:
        ocr_payload = json.load(handle)

    items = sorted(ocr_payload.get("items", []), key=lambda item: item["image"])
    segments: list[dict] = []
    current_group: list[dict] = []
    total = len(items)

    for index, item in enumerate(items, start=1):
        text = _normalize_text(item.get("text", ""))
        if not text:
            if current_group:
                segments.append(_build_segment(len(segments) + 1, current_group))
                current_group = []
            if callback:
                callback(index, total, f"blank {item['image']}")
            continue

        if not current_group:
            current_group = [item]
            if callback:
                callback(index, total, f"start {item['image']}")
            continue

        previous_item = current_group[-1]
        previous_text = _normalize_text(previous_item.get("text", ""))
        similarity = difflib.SequenceMatcher(None, previous_text, text).ratio()

        if previous_text and similarity >= similarity_threshold:
            current_group.append(item)
            if callback:
                callback(index, total, f"group {item['image']} ({similarity:.2f})")
            continue

        segments.append(_build_segment(len(segments) + 1, current_group))
        current_group = [item]
        if callback:
            callback(index, total, f"new {item['image']} ({similarity:.2f})")

    if current_group:
        segments.append(_build_segment(len(segments) + 1, current_group))

    payload = {"segments": segments}
    with segments_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")

    update_status(project_dir, "segments_done", True)
    if callback:
        callback(len(segments), len(segments), "segments built")
    return len(segments)


def _build_segment(segment_id: int, group_items: list[dict]) -> dict:
    return {
        "id": segment_id,
        "start_image": group_items[0]["image"],
        "end_image": group_items[-1]["image"],
        "represent_image": _pick_representative(group_items),
        "source": "ocr_og",
    }


def _pick_representative(group_items: list[dict]) -> str:
    return group_items[0]["image"]


def _normalize_text(text: str) -> str:
    return " ".join(str(text).split()).strip()
