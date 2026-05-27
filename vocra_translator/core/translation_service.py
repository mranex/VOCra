from __future__ import annotations

import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any, Callable

from vocra_translator.core.format_utils import compute_entries_hash
from vocra_translator.core.models import SubtitleDocument, TranslationCacheRow
from vocra_translator.core.project_store import load_project, save_project
from vocra_translator.core.provider_factory import create_translator


ProgressCallback = Callable[[int, int | None, str], None]


def build_translation_signature(manifest: dict[str, Any], document: SubtitleDocument) -> dict[str, Any]:
    translator = manifest.get("translator", {})
    style = str(translator.get("style", "default") or "default")
    custom_prompt = str(translator.get("custom_prompt", "") or "").strip() if style == "custom" else ""
    entries_hash = compute_entries_hash(
        {
            "id": entry.id,
            "start_ms": entry.start_ms,
            "end_ms": entry.end_ms,
            "source_text": entry.source_text,
        }
        for entry in document.entries
    )
    return {
        "provider": str(translator.get("provider", "openai_compatible") or "openai_compatible"),
        "base_url": str(translator.get("base_url", "") or ""),
        "model": str(translator.get("model", "") or ""),
        "source_lang": str(translator.get("source_lang", "auto") or "auto"),
        "target_lang": str(translator.get("target_lang", "vi") or "vi"),
        "style": style,
        "custom_prompt": custom_prompt,
        "context": str(manifest.get("context", "") or ""),
        "entries_hash": entries_hash,
    }


def load_translation_cache(project_dir: str) -> dict[str, Any]:
    cache_path = Path(project_dir).expanduser().resolve() / "cache" / "translation.json"
    if not cache_path.exists():
        return {"signature": {}, "rows": []}
    with cache_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    payload.setdefault("signature", {})
    payload.setdefault("rows", [])
    return payload


def apply_translation_cache(document: SubtitleDocument, cache_payload: dict[str, Any], expected_signature: dict[str, Any]) -> bool:
    signature_matches = cache_payload.get("signature", {}) == expected_signature
    rows_by_id = {
        int(row.entry_id): row
        for row in (TranslationCacheRow.from_dict(item) for item in cache_payload.get("rows", []))
    }
    for entry in document.entries:
        cached = rows_by_id.get(entry.id)
        if cached is None:
            entry.stale = False
            if entry.translation_text:
                entry.status = entry.status or "done"
            else:
                entry.translation_text = ""
                entry.status = "pending"
            continue
        entry.translation_text = cached.translation
        entry.edited = cached.edited
        entry.status = cached.status
        entry.stale = not signature_matches
    return signature_matches


def save_translation_cache(project_dir: str, document: SubtitleDocument, signature: dict[str, Any]) -> None:
    cache_path = Path(project_dir).expanduser().resolve() / "cache" / "translation.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        TranslationCacheRow(
            entry_id=entry.id,
            source_snapshot=entry.source_text,
            translation=entry.translation_text,
            status=entry.status,
            edited=entry.edited,
        ).to_dict()
        for entry in document.entries
    ]
    payload = {"signature": signature, "rows": rows}
    with cache_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def run_project_translation(
    project_dir: str,
    *,
    force: bool = False,
    callback: ProgressCallback | None = None,
) -> int:
    manifest, document = load_project(project_dir)
    signature = build_translation_signature(manifest, document)
    cache_payload = load_translation_cache(project_dir)
    signature_matches = apply_translation_cache(document, cache_payload, signature)

    translator_config = deepcopy(manifest.get("translator", {}))
    translator = create_translator(translator_config, video_context=str(manifest.get("context", "") or ""))
    source_lang = str(translator_config.get("source_lang", "auto") or "auto")
    target_lang = str(translator_config.get("target_lang", "vi") or "vi")
    batch_size = max(1, int(translator_config.get("batch_size", 300) or 300))

    pending_entries = []
    for entry in document.entries:
        if not entry.source_text.strip():
            entry.translation_text = ""
            entry.status = "done"
            entry.stale = False
            continue
        should_translate = force or not entry.translation_text.strip() or entry.stale or not signature_matches
        if should_translate:
            pending_entries.append(entry)

    total_batches = math.ceil(len(pending_entries) / batch_size) if pending_entries else 0
    if total_batches == 0:
        manifest.setdefault("status", {})["translation_done"] = True
        save_project(project_dir, manifest, document)
        save_translation_cache(project_dir, document, signature)
        return len(document.entries)

    for batch_index in range(total_batches):
        batch = pending_entries[batch_index * batch_size : (batch_index + 1) * batch_size]
        translations = translator.translate_batch([entry.source_text for entry in batch], source=source_lang, target=target_lang)
        if len(translations) != len(batch):
            raise RuntimeError("Translator returned the wrong number of items.")
        for entry, translated in zip(batch, translations):
            entry.translation_text = str(translated or "")
            entry.status = "done"
            entry.stale = False
            entry.edited = False

        save_translation_cache(project_dir, document, signature)
        save_project(project_dir, manifest, document)
        if callback is not None:
            callback(batch_index + 1, total_batches, f"Batch {batch_index + 1} / {total_batches} translated")

    manifest.setdefault("status", {})["translation_done"] = True
    save_project(project_dir, manifest, document)
    save_translation_cache(project_dir, document, signature)
    return len(document.entries)
