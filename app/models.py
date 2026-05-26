"""GUI-facing app models for VOCra."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RecentProjectSummary:
    project_root: Path
    project_name: str
    last_opened_at: str


@dataclass(frozen=True)
class PrepareStageSummary:
    prepare_dir: Path
    prepare_run_count: int
    subtitle_segments_path: Path
    segment_count: int
    representative_images_dir: Path
    representative_image_count: int
    prepare_config_path: Path
    crop_zones_path: Path
    detector_name: str | None
    latest_run_id: str | None
    latest_run_segment_count: int | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class PrepareConfigForm:
    time_start_ms: str
    time_end_ms: str
    frames_to_skip: str
    ssim_threshold: str
    tight_box_ssim_threshold: str
    subtitle_position: str
    ocr_image_max_width: str
    brightness_threshold: str
    use_fullframe: bool
    detector_name: str
    debug_mode: bool
    crop_zone_count: int
    detector_config_keys: tuple[str, ...]


@dataclass(frozen=True)
class PreparePreviewFrame:
    requested_ms: int
    actual_ms: int
    source_width: int
    source_height: int
    display_width: int
    display_height: int
    png_bytes: bytes


@dataclass(frozen=True)
class PrepareCropZonesForm:
    zone_specs: tuple[str, str]
    persisted_zone_count: int
    use_fullframe: bool


@dataclass(frozen=True)
class PrepareRunOutcome:
    run_id: str
    run_dir: Path
    report_path: Path
    sampled_frame_count: int
    detected_frame_count: int
    representative_candidate_count: int
    deleted_duplicate_count: int
    segment_count: int


@dataclass(frozen=True)
class PrepareRunProgress:
    stage: str
    message: str
    current: int | float | None = None
    total: int | float | None = None
    percent: float | None = None


@dataclass(frozen=True)
class OcrRunListItem:
    run_id: str
    backend_name: str | None
    model_name: str | None
    prepare_run: str | None
    created_label: str | None
    ok_count: int
    error_count: int
    empty_count: int
    edited_count: int
    config_path: Path
    raw_outputs_path: Path
    normalized_text_path: Path
    errors_path: Path
    report_path: Path


@dataclass(frozen=True)
class OcrStageSummary:
    ocr_runs_dir: Path
    prepare_run_options: tuple[str, ...]
    backend_options: tuple[str, ...]
    run_count: int
    runs: tuple[OcrRunListItem, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class OcrBackendFormSpec:
    backend_name: str
    enabled_fields: tuple[str, ...]
    required_fields: tuple[str, ...]
    help_text: str


@dataclass(frozen=True)
class OcrConfigForm:
    prepare_run: str
    backend_name: str
    run_id: str
    force: bool
    text_template: str
    endpoint: str
    api_key: str
    model: str
    prompt_template: str
    temperature: str
    max_tokens: str
    timeout_sec: str
    command_template: str
    stdout_format: str
    working_dir: str


@dataclass(frozen=True)
class OcrBackendTestOutcome:
    backend_name: str
    ok: bool
    message: str


@dataclass(frozen=True)
class OcrRunOutcome:
    run_id: str
    run_dir: Path
    config_path: Path
    raw_outputs_path: Path
    normalized_text_path: Path
    errors_path: Path
    report_path: Path
    ok_count: int
    error_count: int
    empty_count: int


@dataclass(frozen=True)
class OcrComparisonCandidate:
    run_id: str
    backend_name: str | None
    model_name: str | None
    text: str
    status: str
    error: str | None


@dataclass(frozen=True)
class OcrComparisonItem:
    segment_id: str
    zone_idx: int
    start_ms: int
    end_ms: int
    time_label: str
    representative_image_path: Path
    target_review_status: str
    target_edited_text: str
    target_effective_text: str
    candidates: tuple[OcrComparisonCandidate, ...]


@dataclass(frozen=True)
class OcrComparisonSummary:
    prepare_run_options: tuple[str, ...]
    available_ocr_run_options: tuple[str, ...]
    selected_prepare_run: str
    selected_target_ocr_run: str
    selected_source_ocr_runs: tuple[str, ...]
    item_count: int
    items: tuple[OcrComparisonItem, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class OcrComparisonApplyOutcome:
    target_ocr_run: str
    source_ocr_run: str
    segment_id: str
    chosen_text: str
    review_status: str
    review_state_path: Path


@dataclass(frozen=True)
class ReviewListItem:
    segment_id: str
    zone_idx: int
    start_ms: int
    end_ms: int
    time_label: str
    representative_image_path: Path
    original_text: str
    edited_text: str
    effective_text: str
    review_status: str
    notes: str
    ocr_status: str
    ocr_error: str | None
    quality_flags: tuple[str, ...]


@dataclass(frozen=True)
class ReviewStageSummary:
    prepare_run_options: tuple[str, ...]
    ocr_run_options: tuple[str, ...]
    filter_options: tuple[str, ...]
    selected_prepare_run: str
    selected_ocr_run: str
    selected_filter: str
    item_count: int
    items: tuple[ReviewListItem, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ReviewEditForm:
    prepare_run: str
    ocr_run: str
    filter_name: str
    segment_id: str
    review_status: str
    edited_text: str
    notes: str


@dataclass(frozen=True)
class ReviewSaveOutcome:
    segment_id: str
    review_status: str
    edited_text: str
    notes: str
    review_state_path: Path


@dataclass(frozen=True)
class ReviewBatchOutcome:
    updated_count: int
    review_status: str
    filter_name: str
    segment_ids: tuple[str, ...]
    review_state_path: Path


@dataclass(frozen=True)
class ReviewSelectionDetail:
    segment_id: str
    representative_image_path: Path
    image_png_bytes: bytes | None
    raw_output_path: Path
    raw_output_text: str


@dataclass(frozen=True)
class PackageRunListItem:
    run_id: str
    subtitle_count: int | None
    created_label: str | None
    output_path: Path
    config_path: Path
    report_path: Path


@dataclass(frozen=True)
class PackageStageSummary:
    package_runs_dir: Path
    prepare_run_options: tuple[str, ...]
    ocr_run_options: tuple[str, ...]
    review_state_policy_options: tuple[str, ...]
    format_options: tuple[str, ...]
    selected_prepare_run: str
    selected_ocr_run: str
    selected_review_state_policy: str
    selected_format_name: str
    resolved_review_state_path: Path | None
    review_state_status: str
    run_count: int
    runs: tuple[PackageRunListItem, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class PackageConfigForm:
    prepare_run: str
    ocr_run: str
    format_name: str
    review_state_policy: str
    empty_text_policy: str
    min_subtitle_duration_ms: str
    output_path: str


@dataclass(frozen=True)
class PackagePreviewOutcome:
    subtitle_count: int
    preview_text: str
    prepare_source_path: Path
    ocr_source_path: Path
    review_source_path: Path | None


@dataclass(frozen=True)
class PackageExportOutcome:
    run_id: str
    run_dir: Path
    output_path: Path
    report_path: Path
    subtitle_count: int


@dataclass(frozen=True)
class SourceSummary:
    path: Path
    exists: bool
    duration_ms: int
    width: int
    height: int
    fps: float


@dataclass(frozen=True)
class StageStatus:
    name: str
    status: str
    headline: str
    details: tuple[str, ...]


@dataclass(frozen=True)
class ProjectDashboard:
    project_name: str
    project_root: Path
    project_id: str
    created_at: str
    updated_at: str
    source: SourceSummary
    warnings: tuple[str, ...]
    stages: tuple[StageStatus, ...]


@dataclass(frozen=True)
class AppState:
    project_root: Path | None = None
    dashboard: ProjectDashboard | None = None
    error_message: str | None = None
    recent_projects: tuple[RecentProjectSummary, ...] = ()
    prepare_summary: PrepareStageSummary | None = None
    prepare_config_form: PrepareConfigForm | None = None
    prepare_crop_zones_form: PrepareCropZonesForm | None = None
    ocr_summary: OcrStageSummary | None = None
    ocr_config_form: OcrConfigForm | None = None
    review_summary: ReviewStageSummary | None = None
    package_summary: PackageStageSummary | None = None
