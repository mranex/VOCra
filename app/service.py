"""Thin GUI-facing services built on top of VOCra core artifacts."""

from __future__ import annotations

from pathlib import Path

from vocra.app.models import (
    AppState,
    OcrConfigForm,
    OcrStageSummary,
    PackageStageSummary,
    PrepareConfigForm,
    PreparePreviewFrame,
    PrepareStageSummary,
    ProjectDashboard,
    RecentProjectSummary,
    ReviewStageSummary,
    SourceSummary,
    StageStatus,
)
from vocra.app.ocr_service import load_ocr_config_form, load_ocr_stage_summary
from vocra.app.package_service import load_package_stage_summary
from vocra.app.prepare_service import (
    load_prepare_crop_zones_form,
    write_crop_zones_artifact,
)
from vocra.app.review_service import load_review_stage_summary
from vocra.app.state import (
    RecentProjectEntry,
    load_recent_projects,
    remember_recent_project,
)
from vocra.core.prepare.config import PrepareConfig
from vocra.core.project.jsonl import JsonlArtifactError, read_jsonl
from vocra.core.project.manifest import (
    ManifestValidationError,
    read_json_file,
    write_json_file_atomic,
)
from vocra.core.project.schema import ProjectPaths
from vocra.core.project.workspace import (
    ProjectWorkspaceError,
    create_project,
    open_project,
    resolve_paths,
)
from vocra.core.video.capture import VideoCaptureError, open_video_capture
from vocra.core.video.preview import load_video_preview_frame
from vocra.core.video.probe import probe_video


def create_project_state(
    video_path: Path,
    project_root: Path,
    *,
    probe=probe_video,
    state_file: Path | None = None,
) -> AppState:
    project = create_project(video_path, project_root, probe=probe)
    return open_project_state(project.root, state_file=state_file)


def open_project_state(
    project_root: Path,
    *,
    state_file: Path | None = None,
) -> AppState:
    dashboard = load_project_dashboard(project_root)
    recent_projects = remember_recent_project(
        dashboard.project_root,
        project_name=dashboard.project_name,
        state_file=state_file,
    )
    prepare_summary = load_prepare_stage_summary(dashboard.project_root)
    prepare_config_form: PrepareConfigForm | None = None
    prepare_crop_zones_form = None
    ocr_summary: OcrStageSummary | None = None
    ocr_config_form: OcrConfigForm | None = None
    review_summary: ReviewStageSummary | None = None
    package_summary: PackageStageSummary | None = None
    error_message: str | None = None
    try:
        prepare_config_form = load_prepare_config_form(dashboard.project_root)
    except ProjectWorkspaceError as exc:
        error_message = str(exc)
    try:
        prepare_crop_zones_form = load_prepare_crop_zones_form(dashboard.project_root)
    except ProjectWorkspaceError as exc:
        message = str(exc)
        if error_message is None:
            error_message = message
        else:
            error_message = f"{error_message} | {message}"
    try:
        ocr_summary = load_ocr_stage_summary(dashboard.project_root)
        ocr_config_form = load_ocr_config_form(dashboard.project_root)
    except ProjectWorkspaceError as exc:
        message = str(exc)
        if error_message is None:
            error_message = message
        else:
            error_message = f"{error_message} | {message}"
    try:
        review_summary = load_review_stage_summary(dashboard.project_root)
    except ProjectWorkspaceError as exc:
        message = str(exc)
        if error_message is None:
            error_message = message
        else:
            error_message = f"{error_message} | {message}"
    try:
        package_summary = load_package_stage_summary(dashboard.project_root)
    except ProjectWorkspaceError as exc:
        message = str(exc)
        if error_message is None:
            error_message = message
        else:
            error_message = f"{error_message} | {message}"
    return AppState(
        project_root=dashboard.project_root,
        dashboard=dashboard,
        error_message=error_message,
        recent_projects=_to_recent_project_summaries(recent_projects),
        prepare_summary=prepare_summary,
        prepare_config_form=prepare_config_form,
        prepare_crop_zones_form=prepare_crop_zones_form,
        ocr_summary=ocr_summary,
        ocr_config_form=ocr_config_form,
        review_summary=review_summary,
        package_summary=package_summary,
    )


def load_recent_project_summaries(
    *,
    state_file: Path | None = None,
) -> tuple[RecentProjectSummary, ...]:
    return _to_recent_project_summaries(load_recent_projects(state_file=state_file))


def load_prepare_stage_summary(project_root: Path) -> PrepareStageSummary:
    project = open_project(project_root)
    paths = resolve_paths(project.root)
    warnings: list[str] = []

    segment_count, segment_error = _safe_count_jsonl_rows(paths.subtitle_segments_file)
    if segment_error is not None:
        warnings.append(str(segment_error))
        segment_count = 0
    elif not paths.subtitle_segments_file.exists():
        warnings.append("Prepare subtitle segments are missing.")

    representative_image_count = _count_image_files(paths.representative_images_dir)
    if representative_image_count == 0:
        warnings.append("No representative images are available yet.")

    detector_name = _load_detector_name(paths)
    latest_run_id, latest_run_segment_count = _load_latest_prepare_run_summary(paths)
    if latest_run_id is None and not paths.prepare_runs_dir.exists():
        warnings.append("No prepare run folders exist yet.")

    return PrepareStageSummary(
        prepare_dir=paths.prepare_dir,
        prepare_run_count=_count_run_dirs(paths.prepare_runs_dir),
        subtitle_segments_path=paths.subtitle_segments_file,
        segment_count=segment_count,
        representative_images_dir=paths.representative_images_dir,
        representative_image_count=representative_image_count,
        prepare_config_path=paths.prepare_config_file,
        crop_zones_path=paths.crop_zones_file,
        detector_name=detector_name,
        latest_run_id=latest_run_id,
        latest_run_segment_count=latest_run_segment_count,
        warnings=tuple(warnings),
    )


def load_prepare_config_form(project_root: Path) -> PrepareConfigForm:
    project = open_project(project_root)
    paths = resolve_paths(project.root)
    config = _load_prepare_config(paths)
    detector_name = config.detector.get("name")
    if detector_name is None:
        detector_name = ""
    detector_config_keys = tuple(
        sorted(key for key in config.detector if key != "name")
    )
    return PrepareConfigForm(
        time_start_ms=str(config.time_start_ms),
        time_end_ms=_format_optional_int(config.time_end_ms),
        frames_to_skip=str(config.frames_to_skip),
        ssim_threshold=_format_float(config.ssim_threshold),
        tight_box_ssim_threshold=_format_float(config.tight_box_ssim_threshold),
        subtitle_position=str(config.subtitle_position),
        ocr_image_max_width=str(config.ocr_image_max_width),
        brightness_threshold=_format_optional_int(config.brightness_threshold),
        use_fullframe=bool(config.use_fullframe),
        detector_name=str(detector_name),
        debug_mode=bool(config.debug_mode),
        crop_zone_count=len(config.crop_zones),
        detector_config_keys=detector_config_keys,
    )


def load_prepare_preview_frame(
    project_root: Path,
    *,
    target_ms: int,
    max_width: int = 640,
    max_height: int = 360,
    capture_factory=open_video_capture,
) -> PreparePreviewFrame:
    project = open_project(project_root)
    source_path = project.source.path
    if not source_path.exists():
        raise ProjectWorkspaceError(f"Source video is missing: {source_path}")
    try:
        preview = load_video_preview_frame(
            source_path,
            target_ms=target_ms,
            max_width=max_width,
            max_height=max_height,
            capture_factory=capture_factory,
        )
    except VideoCaptureError as exc:
        raise ProjectWorkspaceError(str(exc)) from exc
    return PreparePreviewFrame(
        requested_ms=preview.requested_ms,
        actual_ms=preview.actual_ms,
        source_width=preview.source_width,
        source_height=preview.source_height,
        display_width=preview.display_width,
        display_height=preview.display_height,
        png_bytes=preview.png_bytes,
    )


def save_prepare_config_form(
    project_root: Path,
    form: PrepareConfigForm,
) -> PrepareConfigForm:
    project = open_project(project_root)
    paths = resolve_paths(project.root)
    config = _load_prepare_config(paths)
    config_payload = config.to_dict()
    detector_payload = dict(config_payload.get("detector", {}))
    detector_name = form.detector_name.strip()
    if detector_name:
        detector_payload["name"] = detector_name
    else:
        detector_payload.pop("name", None)

    config_payload.update(
        {
            "time_start_ms": _parse_required_int(
                form.time_start_ms,
                field_name="time_start_ms",
                minimum=0,
            ),
            "time_end_ms": _parse_optional_int(
                form.time_end_ms,
                field_name="time_end_ms",
                minimum=0,
            ),
            "frames_to_skip": _parse_required_int(
                form.frames_to_skip,
                field_name="frames_to_skip",
                minimum=0,
            ),
            "ssim_threshold": _parse_required_float(
                form.ssim_threshold,
                field_name="ssim_threshold",
                minimum=0.0,
                maximum=1.0,
            ),
            "tight_box_ssim_threshold": _parse_required_float(
                form.tight_box_ssim_threshold,
                field_name="tight_box_ssim_threshold",
                minimum=0.0,
                maximum=1.0,
            ),
            "subtitle_position": _parse_subtitle_position(form.subtitle_position),
            "ocr_image_max_width": _parse_required_int(
                form.ocr_image_max_width,
                field_name="ocr_image_max_width",
                minimum=1,
            ),
            "brightness_threshold": _parse_optional_int(
                form.brightness_threshold,
                field_name="brightness_threshold",
                minimum=0,
            ),
            "use_fullframe": bool(form.use_fullframe),
            "debug_mode": bool(form.debug_mode),
            "detector": detector_payload,
        }
    )
    time_start_ms = int(config_payload["time_start_ms"])
    time_end_ms = config_payload["time_end_ms"]
    if time_end_ms is not None and int(time_end_ms) < time_start_ms:
        raise ProjectWorkspaceError(
            "Prepare config field 'time_end_ms' must be greater than or equal to "
            "'time_start_ms'."
        )

    saved_config = PrepareConfig.from_dict(config_payload)
    write_json_file_atomic(paths.prepare_config_file, saved_config.to_dict())
    write_crop_zones_artifact(paths, saved_config)
    return load_prepare_config_form(project.root)


def load_project_dashboard(project_root: Path) -> ProjectDashboard:
    project = open_project(project_root)
    paths = resolve_paths(project.root)
    warnings: list[str] = []
    if not project.source.path.exists():
        warnings.append(f"Source video is missing: {project.source.path}")

    stages = (
        _build_project_stage(paths.root),
        _build_prepare_stage(paths.subtitle_segments_file, paths.prepare_runs_dir),
        _build_ocr_stage(paths.ocr_runs_dir),
        _build_review_stage(paths.ocr_runs_dir),
        _build_package_stage(paths.package_runs_dir),
    )
    warnings.extend(_collect_stage_warnings(stages))
    return ProjectDashboard(
        project_name=project.name,
        project_root=project.root,
        project_id=project.project_id,
        created_at=project.created_at,
        updated_at=project.updated_at,
        source=SourceSummary(
            path=project.source.path,
            exists=project.source.path.exists(),
            duration_ms=project.source.duration_ms,
            width=project.source.width,
            height=project.source.height,
            fps=project.source.fps,
        ),
        warnings=tuple(warnings),
        stages=stages,
    )


def render_dashboard_text(dashboard: ProjectDashboard) -> str:
    return "\n".join([render_project_overview_text(dashboard), "", render_stage_status_text(dashboard)])


def render_project_overview_text(dashboard: ProjectDashboard) -> str:
    lines = [
        f"Project: {dashboard.project_name}",
        f"Project ID: {dashboard.project_id}",
        f"Root: {dashboard.project_root}",
        f"Created: {dashboard.created_at}",
        f"Updated: {dashboard.updated_at}",
        f"Source: {dashboard.source.path}",
        f"Source exists: {'yes' if dashboard.source.exists else 'no'}",
        (
            "Video: "
            f"{_format_duration(dashboard.source.duration_ms)} | "
            f"{dashboard.source.width}x{dashboard.source.height} | "
            f"{dashboard.source.fps:.3f} fps"
        ),
        "",
    ]
    if dashboard.warnings:
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in dashboard.warnings)
        lines.append("")
    return "\n".join(lines)


def render_stage_status_text(dashboard: ProjectDashboard) -> str:
    lines = ["Stages:"]
    for stage in dashboard.stages:
        lines.append(f"- {stage.name} [{stage.status}] {stage.headline}")
        lines.extend(f"  {detail}" for detail in stage.details)
    return "\n".join(lines)


def render_prepare_stage_text(summary: PrepareStageSummary) -> str:
    lines = [
        f"Prepare directory: {summary.prepare_dir}",
        f"Prepare runs: {summary.prepare_run_count}",
        f"Subtitle segments: {summary.segment_count}",
        f"Representative images: {summary.representative_image_count}",
        f"Prepare config: {'present' if summary.prepare_config_path.exists() else 'missing'}",
        f"Crop zones: {'present' if summary.crop_zones_path.exists() else 'missing'}",
        (
            "Detector: "
            f"{summary.detector_name if summary.detector_name is not None else 'unknown'}"
        ),
        (
            "Latest prepare run: "
            f"{summary.latest_run_id if summary.latest_run_id is not None else 'none'}"
        ),
    ]
    if summary.latest_run_segment_count is not None:
        lines.append(f"Latest run segments: {summary.latest_run_segment_count}")
    lines.extend(
        [
            f"Segments manifest: {summary.subtitle_segments_path}",
            f"Representative image dir: {summary.representative_images_dir}",
        ]
    )
    if summary.warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in summary.warnings)
    return "\n".join(lines)


def _build_project_stage(project_root: Path) -> StageStatus:
    return StageStatus(
        name="Project",
        status="ready",
        headline=f"Project manifest loaded from {project_root.name}",
        details=(f"Project root: {project_root}",),
    )


def _build_prepare_stage(segments_path: Path, runs_dir: Path) -> StageStatus:
    return _build_stage_from_rows(
        name="Prepare",
        path=segments_path,
        runs_dir=runs_dir,
        present_headline="Prepared subtitle segments are available",
        missing_headline="No prepared subtitle segments yet",
        row_label="segments",
    )


def _build_ocr_stage(runs_dir: Path) -> StageStatus:
    run_dirs = _list_run_dirs(runs_dir)
    if not run_dirs:
        return StageStatus(
            name="OCR",
            status="missing",
            headline="No OCR runs yet",
            details=(f"Runs directory: {runs_dir}",),
        )

    latest_run_dir = run_dirs[-1]
    normalized_text_path = latest_run_dir / "normalized_text.jsonl"
    row_count, error = _safe_count_jsonl_rows(normalized_text_path)
    status = "ready" if error is None else "error"
    headline = (
        f"{row_count} OCR rows in latest run {latest_run_dir.name}"
        if error is None
        else f"Latest OCR run is unreadable: {latest_run_dir.name}"
    )
    details = [
        f"OCR runs: {len(run_dirs)}",
        f"Latest run: {latest_run_dir.name}",
    ]
    if error is None:
        details.append(f"Latest artifact: {normalized_text_path}")
    else:
        details.append(str(error))
    return StageStatus(
        name="OCR",
        status=status,
        headline=headline,
        details=tuple(details),
    )


def _build_review_stage(ocr_runs_dir: Path) -> StageStatus:
    run_dirs = _list_run_dirs(ocr_runs_dir)
    review_runs = [
        run_dir for run_dir in run_dirs if (run_dir / "review_state.jsonl").exists()
    ]
    if not run_dirs:
        return StageStatus(
            name="Review",
            status="missing",
            headline="No OCR runs yet, so review has nothing to load",
            details=(f"OCR runs directory: {ocr_runs_dir}",),
        )
    if not review_runs:
        return StageStatus(
            name="Review",
            status="warning",
            headline="OCR exists, but no saved review state yet",
            details=(f"OCR runs: {len(run_dirs)}",),
        )

    latest_review_run = review_runs[-1]
    review_path = latest_review_run / "review_state.jsonl"
    row_count, error = _safe_count_jsonl_rows(review_path)
    status = "ready" if error is None else "error"
    headline = (
        f"{row_count} saved review rows in {latest_review_run.name}"
        if error is None
        else f"Latest review state is unreadable: {latest_review_run.name}"
    )
    details = [
        f"Reviewed OCR runs: {len(review_runs)}",
        f"Latest review run: {latest_review_run.name}",
    ]
    if error is None:
        details.append(f"Latest artifact: {review_path}")
    else:
        details.append(str(error))
    return StageStatus(
        name="Review",
        status=status,
        headline=headline,
        details=tuple(details),
    )


def _build_package_stage(runs_dir: Path) -> StageStatus:
    run_dirs = _list_run_dirs(runs_dir)
    if not run_dirs:
        return StageStatus(
            name="Package",
            status="missing",
            headline="No package runs yet",
            details=(f"Runs directory: {runs_dir}",),
        )

    latest_run_dir = run_dirs[-1]
    report_path = latest_run_dir / "package_report.json"
    if not report_path.exists():
        return StageStatus(
            name="Package",
            status="warning",
            headline=f"Latest package run {latest_run_dir.name} has no report yet",
            details=(f"Package runs: {len(run_dirs)}",),
        )
    try:
        payload = read_json_file(report_path, required_fields=("subtitle_count",))
    except ManifestValidationError as exc:
        return StageStatus(
            name="Package",
            status="error",
            headline=f"Latest package report is unreadable: {latest_run_dir.name}",
            details=(str(exc),),
        )
    return StageStatus(
        name="Package",
        status="ready",
        headline=(
            f"{int(payload['subtitle_count'])} subtitles in latest package run "
            f"{latest_run_dir.name}"
        ),
        details=(
            f"Package runs: {len(run_dirs)}",
            f"Latest artifact: {report_path}",
        ),
    )


def _build_stage_from_rows(
    *,
    name: str,
    path: Path,
    runs_dir: Path,
    present_headline: str,
    missing_headline: str,
    row_label: str,
) -> StageStatus:
    if not path.exists():
        return StageStatus(
            name=name,
            status="missing",
            headline=missing_headline,
            details=(f"Expected artifact: {path}", f"Run folders: {_count_run_dirs(runs_dir)}"),
        )
    row_count, error = _safe_count_jsonl_rows(path)
    if error is not None:
        return StageStatus(
            name=name,
            status="error",
            headline=f"{name} artifact exists but could not be read",
            details=(str(error),),
        )
    return StageStatus(
        name=name,
        status="ready",
        headline=f"{present_headline}: {row_count} {row_label}",
        details=(f"Artifact: {path}", f"Run folders: {_count_run_dirs(runs_dir)}"),
    )


def _collect_stage_warnings(stages: tuple[StageStatus, ...]) -> list[str]:
    warnings: list[str] = []
    for stage in stages:
        if stage.status in {"warning", "error"}:
            warnings.append(f"{stage.name}: {stage.headline}")
    return warnings


def _safe_count_jsonl_rows(path: Path) -> tuple[int, Exception | None]:
    try:
        return _count_jsonl_rows(path), None
    except JsonlArtifactError as exc:
        return 0, exc


def _count_jsonl_rows(path: Path) -> int:
    return sum(1 for _ in read_jsonl(path))


def _list_run_dirs(runs_dir: Path) -> list[Path]:
    parent = runs_dir.expanduser().resolve()
    if not parent.exists():
        return []
    return sorted(path for path in parent.iterdir() if path.is_dir())


def _count_run_dirs(runs_dir: Path) -> int:
    return len(_list_run_dirs(runs_dir))


def _format_duration(duration_ms: int) -> str:
    total_seconds = duration_ms // 1000
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _to_recent_project_summaries(
    entries: tuple[RecentProjectEntry, ...],
) -> tuple[RecentProjectSummary, ...]:
    summaries: list[RecentProjectSummary] = []
    for entry in entries:
        project_root = Path(entry.project_root)
        summaries.append(
            RecentProjectSummary(
                project_root=project_root,
                project_name=str(entry.project_name),
                last_opened_at=str(entry.last_opened_at),
            )
        )
    return tuple(summaries)


def _load_prepare_config(paths: ProjectPaths) -> PrepareConfig:
    if not paths.prepare_config_file.exists():
        return PrepareConfig()
    try:
        payload = read_json_file(paths.prepare_config_file)
    except ManifestValidationError as exc:
        raise ProjectWorkspaceError(
            f"Prepare config is invalid: {paths.prepare_config_file}"
        ) from exc
    return PrepareConfig.from_dict(payload)


def _format_optional_int(value: int | None) -> str:
    if value is None:
        return ""
    return str(value)


def _format_float(value: float) -> str:
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _parse_required_int(
    raw_value: str,
    *,
    field_name: str,
    minimum: int | None = None,
) -> int:
    value = raw_value.strip()
    if not value:
        raise ProjectWorkspaceError(f"Prepare config field '{field_name}' is required.")
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ProjectWorkspaceError(
            f"Prepare config field '{field_name}' must be an integer."
        ) from exc
    if minimum is not None and parsed < minimum:
        raise ProjectWorkspaceError(
            f"Prepare config field '{field_name}' must be >= {minimum}."
        )
    return parsed


def _parse_optional_int(
    raw_value: str,
    *,
    field_name: str,
    minimum: int | None = None,
) -> int | None:
    value = raw_value.strip()
    if not value:
        return None
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ProjectWorkspaceError(
            f"Prepare config field '{field_name}' must be an integer when provided."
        ) from exc
    if minimum is not None and parsed < minimum:
        raise ProjectWorkspaceError(
            f"Prepare config field '{field_name}' must be >= {minimum}."
        )
    return parsed


def _parse_required_float(
    raw_value: str,
    *,
    field_name: str,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    value = raw_value.strip()
    if not value:
        raise ProjectWorkspaceError(f"Prepare config field '{field_name}' is required.")
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ProjectWorkspaceError(
            f"Prepare config field '{field_name}' must be a number."
        ) from exc
    if minimum is not None and parsed < minimum:
        raise ProjectWorkspaceError(
            f"Prepare config field '{field_name}' must be >= {minimum}."
        )
    if maximum is not None and parsed > maximum:
        raise ProjectWorkspaceError(
            f"Prepare config field '{field_name}' must be <= {maximum}."
        )
    return parsed


def _parse_subtitle_position(raw_value: str) -> str:
    value = raw_value.strip().lower()
    allowed = {"left", "center", "right", "any"}
    if value not in allowed:
        raise ProjectWorkspaceError(
            "Prepare config field 'subtitle_position' must be one of: "
            "left, center, right, any."
        )
    return value


def _load_detector_name(paths: ProjectPaths) -> str | None:
    if not paths.prepare_config_file.exists():
        return None
    try:
        payload = read_json_file(paths.prepare_config_file)
    except ManifestValidationError:
        return None
    config = PrepareConfig.from_dict(payload)
    detector_name = config.detector.get("name")
    if detector_name is None:
        return None
    return str(detector_name)


def _load_latest_prepare_run_summary(
    paths: ProjectPaths,
) -> tuple[str | None, int | None]:
    run_dirs = _list_run_dirs(paths.prepare_runs_dir)
    if not run_dirs:
        return None, None
    latest_run_dir = run_dirs[-1]
    report_path = latest_run_dir / "run_report.json"
    if not report_path.exists():
        return latest_run_dir.name, None
    try:
        payload = read_json_file(report_path, required_fields=("segment_count",))
    except ManifestValidationError:
        return latest_run_dir.name, None
    return latest_run_dir.name, int(payload["segment_count"])


def _count_image_files(directory: Path) -> int:
    image_dir = directory.expanduser().resolve()
    if not image_dir.exists():
        return 0
    return sum(
        1
        for path in image_dir.iterdir()
        if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    )
