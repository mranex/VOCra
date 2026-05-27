from __future__ import annotations

from pathlib import Path

from vocra_translator.core.format_registry import save_subtitle_document
from vocra_translator.core.project_store import load_project, save_project
from vocra_translator.core.translation_service import apply_translation_cache, build_translation_signature, load_translation_cache


def build_default_export_name(manifest: dict, *, target_format: str) -> str:
    copied_path = Path(manifest.get("source_file", {}).get("copied_path", "subtitle"))
    stem = copied_path.stem
    return f"{stem}.translated.{target_format}"


def export_project_subtitles(
    project_dir: str,
    *,
    output_path: str,
    target_format: str,
    text_source: str = "translation",
) -> str:
    manifest, document = load_project(project_dir)
    cache_payload = load_translation_cache(project_dir)
    apply_translation_cache(document, cache_payload, build_translation_signature(manifest, document))
    written_path = save_subtitle_document(document, output_path, target_format=target_format, text_source=text_source)
    manifest.setdefault("status", {})["export_done"] = True
    save_project(project_dir, manifest, document)
    return written_path
