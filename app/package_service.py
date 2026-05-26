"""GUI-facing Package-tab services built on top of VOCra artifacts."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from vocra.app.models import (
    PackageConfigForm,
    PackageExportOutcome,
    PackagePreviewOutcome,
    PackageRunListItem,
    PackageStageSummary,
)
from vocra.app.ocr_service import find_ocr_run_item, load_ocr_stage_summary
from vocra.core.package.service import (
    PackageOptions,
    package_srt,
    preview_srt,
)
from vocra.core.project.manifest import ManifestValidationError, read_json_file
from vocra.core.project.workspace import (
    ProjectWorkspaceError,
    open_project,
    resolve_paths,
)

_REVIEW_STATE_POLICY_OPTIONS = ("auto", "ignore", "require")
_EMPTY_TEXT_POLICY_OPTIONS = ("skip", "keep")
_FORMAT_OPTIONS = ("srt",)


def load_package_stage_summary(
    project_root: Path,
    *,
    prepare_run: str | None = None,
    ocr_run: str | None = None,
    review_state_policy: str = "auto",
) -> PackageStageSummary:
    project = open_project(project_root)
    paths = resolve_paths(project.root)
    warnings: list[str] = []

    ocr_summary = load_ocr_stage_summary(project.root)
    prepare_run_options = ocr_summary.prepare_run_options
    ocr_run_options = tuple(item.run_id for item in ocr_summary.runs)
    selected_ocr_run = _resolve_selected_ocr_run(ocr_summary, ocr_run)
    selected_prepare_run = _resolve_selected_prepare_run(
        requested_prepare_run=prepare_run,
        prepare_run_options=prepare_run_options,
        ocr_summary=ocr_summary,
        selected_ocr_run=selected_ocr_run,
    )
    selected_review_state_policy = (
        review_state_policy
        if review_state_policy in _REVIEW_STATE_POLICY_OPTIONS
        else "auto"
    )
    resolved_review_state_path, review_state_status = _summarize_review_state_selection(
        project.root,
        selected_ocr_run=selected_ocr_run,
        review_state_policy=selected_review_state_policy,
    )

    if not prepare_run_options:
        warnings.append("No prepared subtitle segment artifacts are available yet.")
    if not ocr_run_options:
        warnings.append("No OCR runs with normalized output are available yet.")
    if selected_review_state_policy == "require" and resolved_review_state_path is None:
        warnings.append("Selected review-state policy is 'require', but no review_state.jsonl exists for the selected OCR run.")

    run_items: list[PackageRunListItem] = []
    for run_dir in _list_run_dirs(paths.package_runs_dir):
        try:
            run_items.append(_build_package_run_item(run_dir))
        except (ManifestValidationError, ValueError) as exc:
            warnings.append(f"Package run {run_dir.name} could not be summarized: {exc}")
    if not run_items:
        warnings.append("No package runs exist yet.")

    warnings.extend(ocr_summary.warnings)
    return PackageStageSummary(
        package_runs_dir=paths.package_runs_dir,
        prepare_run_options=prepare_run_options,
        ocr_run_options=ocr_run_options,
        review_state_policy_options=_REVIEW_STATE_POLICY_OPTIONS,
        format_options=_FORMAT_OPTIONS,
        selected_prepare_run=selected_prepare_run,
        selected_ocr_run=selected_ocr_run,
        selected_review_state_policy=selected_review_state_policy,
        selected_format_name="srt",
        resolved_review_state_path=resolved_review_state_path,
        review_state_status=review_state_status,
        run_count=len(run_items),
        runs=tuple(run_items),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def load_package_config_form(project_root: Path) -> PackageConfigForm:
    summary = load_package_stage_summary(project_root)
    return PackageConfigForm(
        prepare_run=summary.selected_prepare_run,
        ocr_run=summary.selected_ocr_run,
        format_name=summary.selected_format_name,
        review_state_policy=summary.selected_review_state_policy,
        empty_text_policy="skip",
        min_subtitle_duration_ms="0",
        output_path="",
    )


def render_package_stage_text(summary: PackageStageSummary) -> str:
    lines = [
        f"Package runs directory: {summary.package_runs_dir}",
        (
            "Available prepare runs: "
            f"{', '.join(summary.prepare_run_options) if summary.prepare_run_options else 'none'}"
        ),
        (
            "Available OCR runs: "
            f"{', '.join(summary.ocr_run_options) if summary.ocr_run_options else 'none'}"
        ),
        f"Selected prepare run: {summary.selected_prepare_run or 'none'}",
        f"Selected OCR run: {summary.selected_ocr_run or 'none'}",
        f"Format: {summary.selected_format_name}",
        f"Review state: {summary.review_state_status}",
        f"Package run count: {summary.run_count}",
    ]
    if summary.resolved_review_state_path is not None:
        lines.append(f"Resolved review artifact: {summary.resolved_review_state_path}")
    latest_run = latest_package_run_item(summary)
    if latest_run is None:
        lines.append("Latest package run: none")
    else:
        lines.extend(
            [
                f"Latest package run: {latest_run.run_id}",
                f"Latest subtitle count: {latest_run.subtitle_count if latest_run.subtitle_count is not None else 'unknown'}",
                f"Latest output: {latest_run.output_path}",
            ]
        )
    if summary.warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in summary.warnings)
    return "\n".join(lines)


def preview_package_from_form(
    project_root: Path,
    form: PackageConfigForm,
) -> PackagePreviewOutcome:
    options = _build_package_options(form)
    preview = preview_srt(
        project_root,
        prepare_run=form.prepare_run.strip(),
        ocr_run=form.ocr_run.strip(),
        options=options,
    )
    return PackagePreviewOutcome(
        subtitle_count=preview.subtitle_count,
        preview_text=preview.rendered_text,
        prepare_source_path=preview.prepare_source_path,
        ocr_source_path=preview.ocr_source_path,
        review_source_path=preview.review_source_path,
    )


def export_package_from_form(
    project_root: Path,
    form: PackageConfigForm,
) -> PackageExportOutcome:
    options = _build_package_options(form)
    output_path = form.output_path.strip()
    result = package_srt(
        project_root,
        prepare_run=form.prepare_run.strip(),
        ocr_run=form.ocr_run.strip(),
        options=options,
        output_path=(Path(output_path) if output_path else None),
    )
    return PackageExportOutcome(
        run_id=result.run_dir.name,
        run_dir=result.run_dir,
        output_path=result.output_path,
        report_path=result.package_report_path,
        subtitle_count=result.subtitle_count,
    )


def resolve_package_output_folder(
    project_root: Path,
    form: PackageConfigForm,
    *,
    selected_run_id: str | None = None,
) -> Path:
    output_path = form.output_path.strip()
    if output_path:
        return Path(output_path).expanduser().resolve().parent

    summary = load_package_stage_summary(
        project_root,
        prepare_run=form.prepare_run.strip() or None,
        ocr_run=form.ocr_run.strip() or None,
        review_state_policy=form.review_state_policy.strip() or "auto",
    )
    if selected_run_id:
        selected_run = find_package_run_item(summary, selected_run_id)
        if selected_run is not None:
            return selected_run.output_path.expanduser().resolve().parent
    latest_run = latest_package_run_item(summary)
    if latest_run is not None:
        return latest_run.output_path.expanduser().resolve().parent
    project = open_project(project_root)
    return resolve_paths(project.root).package_runs_dir


def find_package_run_item(
    summary: PackageStageSummary,
    run_id: str,
) -> PackageRunListItem | None:
    normalized = run_id.strip()
    if not normalized:
        return None
    for item in summary.runs:
        if item.run_id == normalized:
            return item
    return None


def latest_package_run_item(summary: PackageStageSummary) -> PackageRunListItem | None:
    if not summary.runs:
        return None
    return summary.runs[-1]


def _build_package_options(form: PackageConfigForm) -> PackageOptions:
    prepare_run = form.prepare_run.strip()
    ocr_run = form.ocr_run.strip()
    if not prepare_run:
        raise ProjectWorkspaceError("Choose a Prepare run before previewing or exporting SRT.")
    if not ocr_run:
        raise ProjectWorkspaceError("Choose an OCR run before previewing or exporting SRT.")

    min_duration = form.min_subtitle_duration_ms.strip()
    try:
        min_subtitle_duration_ms = int(min_duration or "0")
    except ValueError as exc:
        raise ProjectWorkspaceError(
            "Minimum subtitle duration must be an integer millisecond value."
        ) from exc
    if min_subtitle_duration_ms < 0:
        raise ProjectWorkspaceError("Minimum subtitle duration must be >= 0.")

    empty_text_policy = form.empty_text_policy.strip() or "skip"
    if empty_text_policy not in _EMPTY_TEXT_POLICY_OPTIONS:
        raise ProjectWorkspaceError(
            "Empty-text policy must be one of: skip, keep."
        )
    review_state_policy = form.review_state_policy.strip() or "auto"
    if review_state_policy not in _REVIEW_STATE_POLICY_OPTIONS:
        raise ProjectWorkspaceError(
            "Review-state policy must be one of: auto, ignore, require."
        )

    return PackageOptions(
        format=_validate_format_name(form.format_name),
        empty_text_policy=empty_text_policy,
        min_subtitle_duration_ms=min_subtitle_duration_ms,
        review_state_policy=review_state_policy,
    )


def _validate_format_name(format_name: str) -> str:
    normalized = format_name.strip().lower() or "srt"
    if normalized not in _FORMAT_OPTIONS:
        raise ProjectWorkspaceError("Package format must currently be 'srt'.")
    return normalized


def _resolve_selected_ocr_run(summary, requested_ocr_run: str | None) -> str:
    if requested_ocr_run:
        normalized = requested_ocr_run.strip()
        if normalized and find_ocr_run_item(summary, normalized) is not None:
            return normalized
    latest_run = summary.runs[-1] if summary.runs else None
    return latest_run.run_id if latest_run is not None else ""


def _resolve_selected_prepare_run(
    *,
    requested_prepare_run: str | None,
    prepare_run_options: tuple[str, ...],
    ocr_summary,
    selected_ocr_run: str,
) -> str:
    if requested_prepare_run:
        normalized = requested_prepare_run.strip()
        if normalized in prepare_run_options:
            return normalized
    selected_ocr_item = find_ocr_run_item(ocr_summary, selected_ocr_run)
    if selected_ocr_item is not None and selected_ocr_item.prepare_run in prepare_run_options:
        return str(selected_ocr_item.prepare_run)
    return prepare_run_options[0] if prepare_run_options else ""


def _list_run_dirs(runs_dir: Path) -> list[Path]:
    parent = runs_dir.expanduser().resolve()
    if not parent.exists():
        return []
    return sorted(path for path in parent.iterdir() if path.is_dir())


def _build_package_run_item(run_dir: Path) -> PackageRunListItem:
    report_path = run_dir / "package_report.json"
    config_path = run_dir / "package_config.json"
    output_path = run_dir / "output.srt"
    subtitle_count: int | None = None
    if report_path.exists():
        payload = read_json_file(report_path, required_fields=("subtitle_count", "output_path"))
        subtitle_count = int(payload["subtitle_count"])
        output_path = Path(str(payload["output_path"])).expanduser()
    return PackageRunListItem(
        run_id=run_dir.name,
        subtitle_count=subtitle_count,
        created_label=_label_from_run_id(run_dir.name),
        output_path=output_path,
        config_path=config_path,
        report_path=report_path,
    )


def _summarize_review_state_selection(
    project_root: Path,
    *,
    selected_ocr_run: str,
    review_state_policy: str,
) -> tuple[Path | None, str]:
    if not selected_ocr_run:
        return None, "No OCR run selected"
    review_state_path = project_root / "ocr" / "runs" / selected_ocr_run / "review_state.jsonl"
    if review_state_policy == "ignore":
        return None, "Ignore saved review state"
    if review_state_path.exists():
        if review_state_policy == "require":
            return review_state_path, f"Require review state from {selected_ocr_run}"
        return review_state_path, f"Auto-use review state from {selected_ocr_run}"
    if review_state_policy == "require":
        return None, f"Required review state missing for {selected_ocr_run}"
    return None, f"No saved review state for {selected_ocr_run}; package will use normalized OCR text"


def _label_from_run_id(run_id: str) -> str | None:
    prefix = run_id.split("_srt", maxsplit=1)[0]
    try:
        parsed = datetime.strptime(prefix, "%Y-%m-%d_%H%M%S")
    except ValueError:
        return None
    return parsed.strftime("%Y-%m-%d %H:%M:%S")
