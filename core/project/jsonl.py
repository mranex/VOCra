"""Append-friendly JSONL helpers for VOCra artifacts."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from vocra.core.project.manifest import (
    ManifestValidationError,
    validate_required_fields,
)


class JsonlArtifactError(RuntimeError):
    """Raised when a VOCra JSONL artifact is missing or malformed."""


def read_jsonl(
    path: Path,
    *,
    required_fields: tuple[str, ...] = (),
) -> Iterator[dict[str, Any]]:
    artifact_path = path.expanduser().resolve()
    if not artifact_path.exists():
        raise JsonlArtifactError(f"JSONL file does not exist: {artifact_path}")

    with artifact_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            raw_line = line.strip()
            if not raw_line:
                continue

            try:
                payload = json.loads(raw_line)
            except json.JSONDecodeError as exc:
                raise JsonlArtifactError(
                    f"Invalid JSONL record at {artifact_path}:{line_number}"
                ) from exc

            if not isinstance(payload, dict):
                raise JsonlArtifactError(
                    f"JSONL record at {artifact_path}:{line_number} must be an object"
                )

            try:
                validate_required_fields(payload, required_fields, artifact_path)
            except ManifestValidationError as exc:
                raise JsonlArtifactError(str(exc)) from exc

            yield payload


def append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    artifact_path = path.expanduser().resolve()
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    with artifact_path.open("a", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=True)
        handle.write("\n")


def write_jsonl_atomic(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    artifact_path = path.expanduser().resolve()
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=artifact_path.parent,
        delete=False,
        suffix=".tmp",
    ) as handle:
        for payload in rows:
            json.dump(payload, handle, ensure_ascii=True)
            handle.write("\n")
        temp_path = Path(handle.name)
    temp_path.replace(artifact_path)
