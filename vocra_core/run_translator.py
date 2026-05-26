from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Callable

from vocra_core.project_manager import load_project, update_status
from vocra_core.text_cleaner import is_meta_ocr_response
from vocra_core.translator.provider_factory import create_translator


ProgressCallback = Callable[[int, int | None, str], None]


def run_translation(
    project_dir: str,
    force: bool = False,
    callback: ProgressCallback | None = None,
) -> int:
    progress = load_project(project_dir)
    project_path = Path(project_dir).expanduser().resolve()
    ocr_final_path = project_path / progress["cache_files"]["ocr_final"]
    translation_path = project_path / progress["cache_files"]["translation"]

    with ocr_final_path.open("r", encoding="utf-8") as handle:
        ocr_payload = json.load(handle)
    ocr_items = ocr_payload.get("items", [])
    if not ocr_items:
        raise RuntimeError("No final OCR items found for translation")

    translation_payload = _load_translation_payload(translation_path, progress["translator"])
    items_by_segment = {int(item["segment_id"]): item for item in translation_payload["items"]}
    translator = create_translator(progress["translator"])

    source_lang = str(progress["translator"].get("source_lang", "auto") or "auto")
    target_lang = str(progress["translator"].get("target_lang", "vi") or "vi")
    batch_size = max(1, int(progress["translator"].get("batch_size", 300) or 300))

    pending_items = []
    for item in ocr_items:
        segment_id = int(item["segment_id"])
        existing = items_by_segment.get(segment_id)
        if existing and existing.get("status") == "done" and not force:
            continue
        pending_items.append(item)

    total_batches = math.ceil(len(pending_items) / batch_size) if pending_items else 0
    if total_batches == 0:
        update_status(project_dir, "translation_done", True)
        return len(items_by_segment)

    for batch_index in range(total_batches):
        batch_items = pending_items[batch_index * batch_size : (batch_index + 1) * batch_size]
        translations_map: dict[int, str] = {}
        translatable_pairs: list[tuple[int, dict]] = []

        for index, item in enumerate(batch_items):
            source_text = str(item.get("text", "") or "")
            if not source_text.strip() or is_meta_ocr_response(source_text):
                translations_map[index] = ""
                continue
            translatable_pairs.append((index, item))

        if translatable_pairs:
            texts = [str(item.get("text", "") or "") for _, item in translatable_pairs]
            translations = translator.translate_batch(texts, source=source_lang, target=target_lang)
            if len(translations) != len(translatable_pairs):
                raise RuntimeError("Translator returned the wrong number of items.")
            for (index, _item), translation in zip(translatable_pairs, translations):
                translations_map[index] = str(translation or "")

        for index, item in enumerate(batch_items):
            segment_id = int(item["segment_id"])
            items_by_segment[segment_id] = {
                "segment_id": segment_id,
                "image": item["image"],
                "original": str(item.get("text", "") or ""),
                "translation": str(translations_map.get(index, "") or ""),
                "status": "done",
                "edited": False,
            }

        _save_translation_payload(
            translation_path,
            source_lang=source_lang,
            target_lang=target_lang,
            items_by_segment=items_by_segment,
        )
        if callback:
            callback(batch_index + 1, total_batches, f"Batch {batch_index + 1} done")

    update_status(project_dir, "translation_done", True)
    return len(items_by_segment)


def _load_translation_payload(translation_path: Path, config: dict) -> dict:
    if not translation_path.exists():
        return {
            "source_lang": str(config.get("source_lang", "auto") or "auto"),
            "target_lang": str(config.get("target_lang", "vi") or "vi"),
            "items": [],
        }
    with translation_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    items = data.get("items", [])
    if not isinstance(items, list):
        raise ValueError(f"Invalid translation payload in {translation_path}")
    return {
        "source_lang": str(data.get("source_lang", config.get("source_lang", "auto"))),
        "target_lang": str(data.get("target_lang", config.get("target_lang", "vi"))),
        "items": items,
    }


def _save_translation_payload(
    translation_path: Path,
    *,
    source_lang: str,
    target_lang: str,
    items_by_segment: dict[int, dict],
) -> None:
    translation_path.parent.mkdir(parents=True, exist_ok=True)
    items = [items_by_segment[key] for key in sorted(items_by_segment)]
    payload = {
        "source_lang": source_lang,
        "target_lang": target_lang,
        "items": items,
    }
    with translation_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
