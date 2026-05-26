"""Helpers for reading and writing VOCra JSON manifests."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any


class ManifestValidationError(RuntimeError):
    """Raised when a VOCra JSON manifest is missing or malformed."""


def read_json_file(
    path: Path,
    *,
    required_fields: tuple[str, ...] = (),
    expected_schema_version: int | None = None,
) -> dict[str, Any]:
    manifest_path = path.expanduser().resolve()
    if not manifest_path.exists():
        raise ManifestValidationError(f"Manifest file does not exist: {manifest_path}")

    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManifestValidationError(
            f"Manifest file is not valid JSON: {manifest_path}"
        ) from exc

    if not isinstance(payload, dict):
        raise ManifestValidationError(
            f"Manifest root must be a JSON object: {manifest_path}"
        )

    validate_required_fields(payload, required_fields, manifest_path)
    if expected_schema_version is not None:
        schema_version = payload.get("schema_version")
        if schema_version != expected_schema_version:
            raise ManifestValidationError(
                "Unsupported schema version "
                f"{schema_version!r} in {manifest_path}; "
                f"expected {expected_schema_version}."
            )

    return payload


def write_json_file_atomic(path: Path, payload: dict[str, Any]) -> None:
    manifest_path = path.expanduser().resolve()
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=manifest_path.parent,
        delete=False,
        suffix=".tmp",
    ) as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=True)
        handle.write("\n")
        temp_path = Path(handle.name)
    temp_path.replace(manifest_path)


def validate_required_fields(
    payload: dict[str, Any],
    required_fields: tuple[str, ...],
    path: Path,
) -> None:
    missing_fields = [field for field in required_fields if field not in payload]
    if missing_fields:
        missing = ", ".join(sorted(missing_fields))
        raise ManifestValidationError(f"Manifest {path} is missing fields: {missing}")
