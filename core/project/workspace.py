"""Workspace creation and loading for VOCra projects."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from uuid import uuid4

from vocra.core.project.manifest import (
    ManifestValidationError,
    read_json_file,
    write_json_file_atomic,
)
from vocra.core.project.schema import (
    PROJECT_SCHEMA_VERSION,
    ProjectMetadata,
    ProjectPaths,
)
from vocra.core.video.probe import VideoProbeError, probe_video


class ProjectWorkspaceError(RuntimeError):
    """Raised when a VOCra project workspace cannot be created or loaded."""


def resolve_paths(project_root: Path) -> ProjectPaths:
    root = project_root.expanduser().resolve()
    source_dir = root / "source"
    prepare_dir = root / "prepare"
    prepare_runs_dir = prepare_dir / "runs"
    ocr_dir = root / "ocr"
    package_dir = root / "package"
    logs_dir = root / "logs"
    return ProjectPaths(
        root=root,
        project_file=root / "project.json",
        app_state_file=root / "app_state.json",
        source_dir=source_dir,
        source_ref_file=source_dir / "source_ref.json",
        thumbnail_file=source_dir / "thumbnail.jpg",
        prepare_dir=prepare_dir,
        prepare_config_file=prepare_dir / "prepare_config.json",
        crop_zones_file=prepare_dir / "crop_zones.json",
        timeline_file=prepare_dir / "timeline.jsonl",
        frame_index_file=prepare_dir / "frame_index.jsonl",
        detection_boxes_file=prepare_dir / "detection_boxes.jsonl",
        subtitle_segments_file=prepare_dir / "subtitle_segments.jsonl",
        representative_images_dir=prepare_dir / "representative_images",
        prepare_debug_dir=prepare_dir / "debug",
        prepare_runs_dir=prepare_runs_dir,
        ocr_dir=ocr_dir,
        ocr_runs_dir=ocr_dir / "runs",
        package_dir=package_dir,
        package_runs_dir=package_dir / "runs",
        logs_dir=logs_dir,
        app_log_file=logs_dir / "app.log",
        prepare_log_file=logs_dir / "prepare.log",
        ocr_log_file=logs_dir / "ocr.log",
        package_log_file=logs_dir / "package.log",
    )


def create_project(
    video_path: Path,
    project_root: Path,
    *,
    probe=probe_video,
) -> ProjectMetadata:
    source_path = video_path.expanduser().resolve()
    if not source_path.exists():
        raise ProjectWorkspaceError(f"Source video does not exist: {source_path}")
    if not source_path.is_file():
        raise ProjectWorkspaceError(f"Source video is not a file: {source_path}")

    paths = resolve_paths(project_root)
    _ensure_project_root_available(paths.root)
    _create_workspace_directories(paths)

    try:
        source = probe(source_path)
    except VideoProbeError as exc:
        raise ProjectWorkspaceError(str(exc)) from exc

    timestamp = _now_isoformat()
    project = ProjectMetadata(
        project_id=str(uuid4()),
        name=paths.root.stem,
        root=paths.root,
        source=source,
        created_at=timestamp,
        updated_at=timestamp,
        schema_version=PROJECT_SCHEMA_VERSION,
    )

    write_json_file_atomic(paths.project_file, project.to_dict())
    write_json_file_atomic(
        paths.source_ref_file,
        {
            "schema_version": PROJECT_SCHEMA_VERSION,
            "project_id": project.project_id,
            "source": source.to_dict(),
        },
    )
    paths.app_log_file.touch(exist_ok=True)
    return project


def open_project(project_root: Path) -> ProjectMetadata:
    paths = resolve_paths(project_root)
    try:
        data = read_json_file(
            paths.project_file,
            required_fields=(
                "schema_version",
                "project_id",
                "name",
                "created_at",
                "updated_at",
                "source",
            ),
            expected_schema_version=PROJECT_SCHEMA_VERSION,
        )
    except ManifestValidationError as exc:
        raise ProjectWorkspaceError(str(exc)) from exc
    return ProjectMetadata.from_dict(paths.root, data)


def validate_project(project_root: Path) -> None:
    paths = resolve_paths(project_root)
    project = open_project(paths.root)
    required_paths = [
        paths.project_file,
        paths.source_dir,
        paths.source_ref_file,
        paths.logs_dir,
        paths.app_log_file,
    ]
    for required_path in required_paths:
        if not required_path.exists():
            raise ProjectWorkspaceError(
                f"Project is missing required path: {required_path}"
            )

    if not project.source.path.exists():
        raise ProjectWorkspaceError(
            f"Project source video is missing: {project.source.path}"
        )


def _create_workspace_directories(paths: ProjectPaths) -> None:
    directories = [
        paths.root,
        paths.source_dir,
        paths.prepare_dir,
        paths.representative_images_dir,
        paths.prepare_debug_dir,
        paths.prepare_runs_dir,
        paths.ocr_runs_dir,
        paths.package_runs_dir,
        paths.logs_dir,
    ]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


def _ensure_project_root_available(project_root: Path) -> None:
    if project_root.exists() and any(project_root.iterdir()):
        raise ProjectWorkspaceError(
            f"Project directory already exists and is not empty: {project_root}"
        )


def _now_isoformat() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
