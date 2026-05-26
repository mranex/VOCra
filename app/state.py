"""Application-level state persistence for VOCra GUI helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from vocra.core.project.manifest import (
    ManifestValidationError,
    read_json_file,
    write_json_file_atomic,
)

APP_STATE_SCHEMA_VERSION = 1
MAX_RECENT_PROJECTS = 10


@dataclass(frozen=True)
class RecentProjectEntry:
    project_root: Path
    project_name: str
    last_opened_at: str

    def to_dict(self) -> dict[str, str]:
        return {
            "project_root": str(self.project_root),
            "project_name": self.project_name,
            "last_opened_at": self.last_opened_at,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> RecentProjectEntry:
        return cls(
            project_root=Path(str(payload["project_root"])).expanduser().resolve(),
            project_name=str(payload["project_name"]),
            last_opened_at=str(payload["last_opened_at"]),
        )


def resolve_app_state_path() -> Path:
    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "VOCra" / "app_state.json"
    return Path.home() / ".vocra" / "app_state.json"


def load_recent_projects(
    *,
    state_file: Path | None = None,
) -> tuple[RecentProjectEntry, ...]:
    resolved_state_file = _resolve_state_file(state_file)
    if not resolved_state_file.exists():
        return ()
    try:
        payload = read_json_file(
            resolved_state_file,
            required_fields=("schema_version", "recent_projects"),
            expected_schema_version=APP_STATE_SCHEMA_VERSION,
        )
    except ManifestValidationError:
        return ()

    recent_projects = payload.get("recent_projects", [])
    if not isinstance(recent_projects, list):
        return ()
    return tuple(
        RecentProjectEntry.from_dict(item)
        for item in recent_projects
        if isinstance(item, dict)
    )


def remember_recent_project(
    project_root: Path,
    *,
    project_name: str,
    state_file: Path | None = None,
) -> tuple[RecentProjectEntry, ...]:
    resolved_root = project_root.expanduser().resolve()
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")
    entries = [
        entry
        for entry in load_recent_projects(state_file=state_file)
        if entry.project_root != resolved_root
    ]
    entries.insert(
        0,
        RecentProjectEntry(
            project_root=resolved_root,
            project_name=project_name,
            last_opened_at=timestamp,
        ),
    )
    trimmed_entries = tuple(entries[:MAX_RECENT_PROJECTS])
    _write_recent_projects(trimmed_entries, state_file=state_file)
    return trimmed_entries


def _write_recent_projects(
    entries: tuple[RecentProjectEntry, ...],
    *,
    state_file: Path | None = None,
) -> None:
    resolved_state_file = _resolve_state_file(state_file)
    write_json_file_atomic(
        resolved_state_file,
        {
            "schema_version": APP_STATE_SCHEMA_VERSION,
            "recent_projects": [entry.to_dict() for entry in entries],
        },
    )


def _resolve_state_file(state_file: Path | None) -> Path:
    return (state_file or resolve_app_state_path()).expanduser().resolve()
