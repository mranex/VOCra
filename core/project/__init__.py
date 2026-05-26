"""Project schema and workspace helpers for VOCra."""

from vocra.core.project.jsonl import (
    JsonlArtifactError,
    append_jsonl,
    read_jsonl,
    write_jsonl_atomic,
)
from vocra.core.project.manifest import (
    ManifestValidationError,
    read_json_file,
    validate_required_fields,
    write_json_file_atomic,
)
from vocra.core.project.runs import (
    create_ocr_run,
    create_package_run,
    create_prepare_run,
    new_run_id,
)
from vocra.core.project.schema import (
    Project,
    ProjectMetadata,
    ProjectPaths,
    SourceVideo,
)
from vocra.core.project.workspace import (
    ProjectWorkspaceError,
    create_project,
    open_project,
    resolve_paths,
    validate_project,
)

__all__ = [
    "JsonlArtifactError",
    "ManifestValidationError",
    "Project",
    "ProjectMetadata",
    "ProjectPaths",
    "ProjectWorkspaceError",
    "SourceVideo",
    "append_jsonl",
    "create_ocr_run",
    "create_package_run",
    "create_prepare_run",
    "create_project",
    "new_run_id",
    "open_project",
    "read_json_file",
    "read_jsonl",
    "resolve_paths",
    "validate_required_fields",
    "validate_project",
    "write_json_file_atomic",
    "write_jsonl_atomic",
]
