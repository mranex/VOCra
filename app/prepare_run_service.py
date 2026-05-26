"""GUI-facing Prepare run services."""

from __future__ import annotations

from pathlib import Path

from vocra.app.models import PrepareRunOutcome, PrepareRunProgress
from vocra.core.prepare.config import PrepareConfig
from vocra.core.prepare.detectors import create_text_detector_backend
from vocra.core.prepare.service import run_prepare
from vocra.core.prepare.similarity import compute_ssim_similarity
from vocra.core.progress import ProgressEvent
from vocra.core.project.manifest import ManifestValidationError, read_json_file
from vocra.core.project.schema import ProjectPaths
from vocra.core.project.workspace import (
    ProjectWorkspaceError,
    open_project,
    resolve_paths,
)


def run_prepare_from_project(
    project_root: Path,
    *,
    progress=None,
    cancel_requested=None,
) -> PrepareRunOutcome:
    project = open_project(project_root)
    paths = resolve_paths(project.root)
    config = _load_persisted_prepare_config(paths)
    _validate_prepare_run_inputs(config)
    try:
        detector_backend = create_text_detector_backend(config.detector)
    except ValueError as exc:
        raise ProjectWorkspaceError(str(exc)) from exc

    result = run_prepare(
        project.root,
        config=config,
        detector_backend=detector_backend,
        similarity_fn=compute_ssim_similarity,
        progress=_wrap_progress_callback(progress),
        cancel_requested=cancel_requested,
    )
    return PrepareRunOutcome(
        run_id=result.summary.run_id,
        run_dir=result.run_dir,
        report_path=result.artifacts.report_path,
        sampled_frame_count=result.summary.sampled_frame_count,
        detected_frame_count=result.summary.detected_frame_count,
        representative_candidate_count=result.summary.representative_candidate_count,
        deleted_duplicate_count=result.summary.deleted_duplicate_count,
        segment_count=result.summary.segment_count,
    )


def _load_persisted_prepare_config(paths: ProjectPaths) -> PrepareConfig:
    if not paths.prepare_config_file.exists():
        raise ProjectWorkspaceError(
            f"Prepare config is missing: {paths.prepare_config_file}. Save Prepare config before running Prepare."
        )
    try:
        payload = read_json_file(paths.prepare_config_file)
    except ManifestValidationError as exc:
        raise ProjectWorkspaceError(
            f"Prepare config is invalid: {paths.prepare_config_file}"
        ) from exc
    return PrepareConfig.from_dict(payload)


def _validate_prepare_run_inputs(config: PrepareConfig) -> None:
    if not config.use_fullframe and not config.crop_zones:
        raise ProjectWorkspaceError(
            "Prepare config must include at least one crop zone unless full-frame mode is enabled."
        )
    if not config.detector:
        raise ProjectWorkspaceError(
            "Prepare config must include a detector before running Prepare."
        )


def _wrap_progress_callback(progress):
    if progress is None:
        return None

    def emit(event: ProgressEvent) -> None:
        progress(
            PrepareRunProgress(
                stage=event.stage,
                message=event.message,
                current=event.current,
                total=event.total,
                percent=event.percent,
            )
        )

    return emit
