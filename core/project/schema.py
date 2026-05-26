"""Project data contracts for VOCra."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class SourceVideo:
    path: Path
    fingerprint: str
    duration_ms: int
    width: int
    height: int
    fps: float
    start_time_offset_ms: float = 0.0
    mode: str = "external_path"

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "path": str(self.path),
            "fingerprint": self.fingerprint,
            "duration_ms": self.duration_ms,
            "width": self.width,
            "height": self.height,
            "fps": self.fps,
            "start_time_offset_ms": self.start_time_offset_ms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SourceVideo:
        return cls(
            path=Path(data["path"]),
            fingerprint=str(data["fingerprint"]),
            duration_ms=int(data["duration_ms"]),
            width=int(data["width"]),
            height=int(data["height"]),
            fps=float(data["fps"]),
            start_time_offset_ms=float(data.get("start_time_offset_ms", 0.0)),
            mode=str(data.get("mode", "external_path")),
        )


@dataclass(frozen=True)
class ProjectMetadata:
    project_id: str
    name: str
    root: Path
    source: SourceVideo
    created_at: str
    updated_at: str
    schema_version: int = PROJECT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "project_id": self.project_id,
            "name": self.name,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "source": self.source.to_dict(),
        }

    @classmethod
    def from_dict(cls, root: Path, data: dict[str, Any]) -> ProjectMetadata:
        return cls(
            project_id=str(data["project_id"]),
            name=str(data["name"]),
            root=root,
            source=SourceVideo.from_dict(data["source"]),
            created_at=str(data["created_at"]),
            updated_at=str(data["updated_at"]),
            schema_version=int(data["schema_version"]),
        )


Project = ProjectMetadata


@dataclass(frozen=True)
class ProjectPaths:
    root: Path
    project_file: Path
    app_state_file: Path
    source_dir: Path
    source_ref_file: Path
    thumbnail_file: Path
    prepare_dir: Path
    prepare_config_file: Path
    crop_zones_file: Path
    timeline_file: Path
    frame_index_file: Path
    detection_boxes_file: Path
    subtitle_segments_file: Path
    representative_images_dir: Path
    prepare_debug_dir: Path
    prepare_runs_dir: Path
    ocr_dir: Path
    ocr_runs_dir: Path
    package_dir: Path
    package_runs_dir: Path
    logs_dir: Path
    app_log_file: Path
    prepare_log_file: Path
    ocr_log_file: Path
    package_log_file: Path
