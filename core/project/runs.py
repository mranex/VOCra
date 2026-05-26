"""Run folder helpers for VOCra artifact stages."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from vocra.core.project.schema import ProjectMetadata
from vocra.core.project.workspace import resolve_paths

_SANITIZE_PATTERN = re.compile(r"[^a-z0-9]+")


def new_run_id(prefix: str, *, now: datetime | None = None) -> str:
    sanitized_prefix = _sanitize_name(prefix)
    if not sanitized_prefix:
        raise ValueError("Run prefix must contain at least one alphanumeric character.")

    timestamp = (now or datetime.now()).strftime("%Y-%m-%d_%H%M%S_%f")
    return f"{timestamp}_{sanitized_prefix}"


def create_prepare_run(project: ProjectMetadata, name: str | None = None) -> Path:
    paths = resolve_paths(project.root)
    run_dir = _create_unique_run_dir(paths.prepare_runs_dir, name or "prepare")
    (run_dir / "representative_images").mkdir(parents=True, exist_ok=True)
    (run_dir / "debug").mkdir(parents=True, exist_ok=True)
    return run_dir


def create_ocr_run(project: ProjectMetadata, backend_name: str) -> Path:
    paths = resolve_paths(project.root)
    return _create_unique_run_dir(paths.ocr_runs_dir, backend_name)


def create_package_run(project: ProjectMetadata, format_name: str) -> Path:
    paths = resolve_paths(project.root)
    return _create_unique_run_dir(paths.package_runs_dir, format_name)


def _create_unique_run_dir(parent_dir: Path, prefix: str) -> Path:
    parent = parent_dir.expanduser().resolve()
    parent.mkdir(parents=True, exist_ok=True)

    candidate = parent / new_run_id(prefix)
    counter = 1
    while candidate.exists():
        candidate = parent / f"{new_run_id(prefix)}_{counter:02d}"
        counter += 1

    candidate.mkdir(parents=True, exist_ok=False)
    return candidate


def _sanitize_name(value: str) -> str:
    normalized = _SANITIZE_PATTERN.sub("-", value.strip().lower())
    return normalized.strip("-")
