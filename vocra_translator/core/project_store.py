from __future__ import annotations

import json
import shutil
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from vocra_translator.core.app_config import merge_project_translator_defaults
from vocra_translator.core.format_registry import load_subtitle_document
from vocra_translator.core.format_utils import sanitize_project_name
from vocra_translator.core.models import SubtitleDocument


PROJECT_FILENAME = "project.json"


def default_projects_root() -> Path:
    return (Path.cwd() / "vocra_translator" / "projects").resolve()


def create_project_from_subtitle(
    subtitle_path: str,
    *,
    global_config: dict[str, Any] | None = None,
    projects_root: str | None = None,
) -> tuple[dict[str, Any], SubtitleDocument]:
    source_path = Path(subtitle_path).expanduser().resolve()
    if not source_path.exists():
        raise FileNotFoundError(source_path)

    root = Path(projects_root).expanduser().resolve() if projects_root else default_projects_root()
    root.mkdir(parents=True, exist_ok=True)
    project_dir = _allocate_project_dir(root, source_path.stem)
    (project_dir / "source").mkdir(parents=True, exist_ok=True)
    (project_dir / "cache").mkdir(parents=True, exist_ok=True)
    (project_dir / "exports").mkdir(parents=True, exist_ok=True)

    copied_source_path = project_dir / "source" / source_path.name
    shutil.copy2(source_path, copied_source_path)
    document = load_subtitle_document(str(copied_source_path))
    save_document(project_dir, document)

    translator_defaults = merge_project_translator_defaults({}, global_config or {"translator": {}})
    now = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    manifest = {
        "project_name": project_dir.name,
        "project_dir": str(project_dir),
        "created_at": now,
        "updated_at": now,
        "source_file": {
            "original_path": str(source_path),
            "copied_path": "source/" + source_path.name,
            "format": document.format_name,
        },
        "cache_files": {
            "document": "cache/document.json",
            "translation": "cache/translation.json",
        },
        "exports_dir": "exports",
        "context": "",
        "status": {
            "imported": True,
            "translation_done": False,
            "export_done": False,
        },
        "translator": translator_defaults,
    }
    save_manifest(project_dir, manifest)
    return manifest, document


def load_project(project_dir: str, *, global_config: dict[str, Any] | None = None) -> tuple[dict[str, Any], SubtitleDocument]:
    root = Path(project_dir).expanduser().resolve()
    manifest_path = root / PROJECT_FILENAME
    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing {PROJECT_FILENAME} in {root}")
    with manifest_path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)

    if global_config is not None:
        manifest["translator"] = merge_project_translator_defaults(manifest.get("translator", {}), global_config)
    document = load_document(root)
    return manifest, document


def save_project(project_dir: str, manifest: dict[str, Any], document: SubtitleDocument) -> None:
    root = Path(project_dir).expanduser().resolve()
    manifest["updated_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    save_document(root, document)
    save_manifest(root, manifest)


def save_manifest(project_dir: str | Path, manifest: dict[str, Any]) -> None:
    root = Path(project_dir).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    manifest_path = root / PROJECT_FILENAME
    payload = deepcopy(manifest)
    payload.setdefault("translator", {}).pop("api_key", None)
    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def load_document(project_dir: str | Path) -> SubtitleDocument:
    root = Path(project_dir).expanduser().resolve()
    document_path = root / "cache" / "document.json"
    with document_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return SubtitleDocument.from_dict(payload)


def save_document(project_dir: str | Path, document: SubtitleDocument) -> None:
    root = Path(project_dir).expanduser().resolve()
    (root / "cache").mkdir(parents=True, exist_ok=True)
    document_path = root / "cache" / "document.json"
    with document_path.open("w", encoding="utf-8") as handle:
        json.dump(document.to_dict(), handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def update_translation_config(project_dir: str, translator: dict[str, Any], context: str) -> tuple[dict[str, Any], SubtitleDocument]:
    manifest, document = load_project(project_dir)
    merged = deepcopy(manifest.get("translator", {}))
    merged.update(translator)
    manifest["translator"] = merged
    manifest["context"] = str(context or "")
    save_project(project_dir, manifest, document)
    return manifest, document


def project_export_path(project_dir: str, stem: str, extension: str) -> Path:
    root = Path(project_dir).expanduser().resolve()
    export_dir = root / "exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    return export_dir / f"{sanitize_project_name(stem)}.{extension.lstrip('.')}"


def _allocate_project_dir(root: Path, base_name: str) -> Path:
    stem = sanitize_project_name(base_name)
    candidate = root / stem
    if not candidate.exists():
        return candidate
    counter = 2
    while True:
        candidate = root / f"{stem}_{counter}"
        if not candidate.exists():
            return candidate
        counter += 1
