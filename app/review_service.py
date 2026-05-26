"""GUI-facing Review-tab services built on top of VOCra artifacts."""

from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path

from PIL import Image

from vocra.app.models import (
    ReviewBatchOutcome,
    ReviewEditForm,
    ReviewListItem,
    ReviewSaveOutcome,
    ReviewSelectionDetail,
    ReviewStageSummary,
)
from vocra.app.ocr_service import latest_ocr_run_item, load_ocr_stage_summary
from vocra.core.package.srt import format_srt_timestamp
from vocra.core.project.jsonl import read_jsonl
from vocra.core.project.workspace import ProjectWorkspaceError, open_project
from vocra.core.review.service import (
    load_review_items,
    resolve_review_state_path,
    save_review_batch,
    save_review_edit,
)

_REVIEW_FILTER_OPTIONS = (
    "all",
    "pending",
    "accepted",
    "edited",
    "rejected",
    "unreviewed",
    "errors",
    "empty",
    "suspicious",
)

_REVIEW_SHORTCUT_SUSPICIOUS_FLAGS = {
    "mostly_punctuation",
    "repeated_text",
    "replacement_character",
    "too_long",
    "too_short",
}


def load_review_stage_summary(
    project_root: Path,
    *,
    prepare_run: str | None = None,
    ocr_run: str | None = None,
    filter_name: str = "all",
) -> ReviewStageSummary:
    project = open_project(project_root)
    warnings: list[str] = []

    ocr_summary = load_ocr_stage_summary(project.root)
    prepare_run_options = ocr_summary.prepare_run_options
    ocr_run_options = tuple(item.run_id for item in ocr_summary.runs)

    if not prepare_run_options:
        warnings.append("No prepared subtitle segment artifacts are available yet.")
    if not ocr_run_options:
        warnings.append("No OCR runs with normalized output are available yet.")

    selected_ocr_run = _resolve_selected_ocr_run(ocr_summary, ocr_run)
    selected_prepare_run = _resolve_selected_prepare_run(
        requested_prepare_run=prepare_run,
        prepare_run_options=prepare_run_options,
        ocr_summary=ocr_summary,
        selected_ocr_run=selected_ocr_run,
    )
    selected_filter = filter_name if filter_name in _REVIEW_FILTER_OPTIONS else "all"

    items: tuple[ReviewListItem, ...] = ()
    if selected_prepare_run and selected_ocr_run:
        try:
            items = tuple(
                _to_review_list_item(
                    project_root=project.root,
                    prepare_run=selected_prepare_run,
                    item=item,
                )
                for item in load_review_items(
                    project.root,
                    prepare_run=selected_prepare_run,
                    ocr_run=selected_ocr_run,
                    filter_name=selected_filter,
                )
            )
        except ValueError as exc:
            raise ProjectWorkspaceError(str(exc)) from exc

    warnings.extend(ocr_summary.warnings)
    return ReviewStageSummary(
        prepare_run_options=prepare_run_options,
        ocr_run_options=ocr_run_options,
        filter_options=_REVIEW_FILTER_OPTIONS,
        selected_prepare_run=selected_prepare_run,
        selected_ocr_run=selected_ocr_run,
        selected_filter=selected_filter,
        item_count=len(items),
        items=items,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def render_review_stage_text(summary: ReviewStageSummary) -> str:
    lines = [
        (
            "Prepare runs: "
            f"{', '.join(summary.prepare_run_options) if summary.prepare_run_options else 'none'}"
        ),
        (
            "OCR runs: "
            f"{', '.join(summary.ocr_run_options) if summary.ocr_run_options else 'none'}"
        ),
        f"Selected prepare run: {summary.selected_prepare_run or 'none'}",
        f"Selected OCR run: {summary.selected_ocr_run or 'none'}",
        f"Selected filter: {summary.selected_filter}",
        f"Review items: {summary.item_count}",
    ]
    if summary.warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in summary.warnings)
    return "\n".join(lines)


def find_review_item(
    summary: ReviewStageSummary,
    segment_id: str,
) -> ReviewListItem | None:
    normalized = segment_id.strip()
    if not normalized:
        return None
    for item in summary.items:
        if item.segment_id == normalized:
            return item
    return None


def save_review_edit_from_form(
    project_root: Path,
    form: ReviewEditForm,
) -> ReviewSaveOutcome:
    if not form.ocr_run.strip():
        raise ProjectWorkspaceError("Choose an OCR run before saving review state.")
    if not form.segment_id.strip():
        raise ProjectWorkspaceError("Choose a review item before saving review state.")

    try:
        state = save_review_edit(
            project_root,
            ocr_run=form.ocr_run.strip(),
            segment_id=form.segment_id.strip(),
            review_status=form.review_status.strip(),
            edited_text=form.edited_text,
            notes=form.notes,
        )
    except ValueError as exc:
        raise ProjectWorkspaceError(str(exc)) from exc

    return ReviewSaveOutcome(
        segment_id=state.segment_id,
        review_status=state.review_status,
        edited_text=state.edited_text,
        notes=state.notes,
        review_state_path=resolve_review_state_path(project_root, form.ocr_run.strip()),
    )


def save_review_batch_from_filter(
    project_root: Path,
    *,
    prepare_run: str,
    ocr_run: str,
    filter_name: str,
    review_status: str,
    notes: str = "",
) -> ReviewBatchOutcome:
    normalized_prepare_run = prepare_run.strip()
    normalized_ocr_run = ocr_run.strip()
    normalized_filter = filter_name.strip() or "all"
    if not normalized_prepare_run:
        raise ProjectWorkspaceError("Choose a Prepare run before saving batch review state.")
    if not normalized_ocr_run:
        raise ProjectWorkspaceError("Choose an OCR run before saving batch review state.")

    try:
        states = save_review_batch(
            project_root,
            prepare_run=normalized_prepare_run,
            ocr_run=normalized_ocr_run,
            review_status=review_status,
            filter_name=normalized_filter,
            notes=notes,
        )
    except ValueError as exc:
        raise ProjectWorkspaceError(str(exc)) from exc

    return ReviewBatchOutcome(
        updated_count=len(states),
        review_status=review_status,
        filter_name=normalized_filter,
        segment_ids=tuple(state.segment_id for state in states),
        review_state_path=resolve_review_state_path(project_root, normalized_ocr_run),
    )


def load_review_selection_detail(
    project_root: Path,
    *,
    ocr_run: str,
    item: ReviewListItem,
    max_image_width: int = 720,
    max_image_height: int = 220,
) -> ReviewSelectionDetail:
    raw_output_path = _resolve_raw_output_path(project_root, ocr_run.strip())
    return ReviewSelectionDetail(
        segment_id=item.segment_id,
        representative_image_path=item.representative_image_path,
        image_png_bytes=_load_review_preview_png(
            item.representative_image_path,
            max_width=max_image_width,
            max_height=max_image_height,
        ),
        raw_output_path=raw_output_path,
        raw_output_text=_load_raw_output_text(
            raw_output_path,
            segment_id=item.segment_id,
        ),
    )


def move_review_selection(
    summary: ReviewStageSummary,
    segment_id: str,
    *,
    step: int,
) -> ReviewListItem | None:
    if not summary.items:
        return None
    current_index = _find_review_item_index(summary, segment_id)
    if current_index is None:
        return summary.items[0]
    next_index = current_index + step
    if next_index < 0 or next_index >= len(summary.items):
        return None
    return summary.items[next_index]


def find_next_suspicious_review_item(
    summary: ReviewStageSummary,
    segment_id: str,
) -> ReviewListItem | None:
    if not summary.items:
        return None
    current_index = _find_review_item_index(summary, segment_id)
    start_index = 0 if current_index is None else current_index + 1
    for item in summary.items[start_index:]:
        if any(flag in _REVIEW_SHORTCUT_SUSPICIOUS_FLAGS for flag in item.quality_flags):
            return item
    return None


def _resolve_selected_ocr_run(ocr_summary, requested_ocr_run: str | None) -> str:
    requested = (requested_ocr_run or "").strip()
    if requested:
        for item in ocr_summary.runs:
            if item.run_id == requested:
                return item.run_id
    latest_run = latest_ocr_run_item(ocr_summary)
    return latest_run.run_id if latest_run is not None else ""


def _resolve_selected_prepare_run(
    *,
    requested_prepare_run: str | None,
    prepare_run_options: tuple[str, ...],
    ocr_summary,
    selected_ocr_run: str,
) -> str:
    requested = (requested_prepare_run or "").strip()
    if requested in prepare_run_options:
        return requested
    if selected_ocr_run:
        for item in ocr_summary.runs:
            if item.run_id == selected_ocr_run and item.prepare_run in prepare_run_options:
                return item.prepare_run or ""
    return prepare_run_options[0] if prepare_run_options else ""


def _to_review_list_item(
    *,
    project_root: Path,
    prepare_run: str,
    item,
) -> ReviewListItem:
    return ReviewListItem(
        segment_id=item.segment_id,
        zone_idx=item.zone_idx,
        start_ms=item.start_ms,
        end_ms=item.end_ms,
        time_label=(
            f"{format_srt_timestamp(item.start_ms)} --> "
            f"{format_srt_timestamp(item.end_ms)}"
        ),
        representative_image_path=_resolve_representative_image_path(
            project_root=project_root,
            prepare_run=prepare_run,
            image_path=item.representative_image,
        ),
        original_text=item.original_text,
        edited_text=item.edited_text,
        effective_text=item.effective_text,
        review_status=item.review_status,
        notes=item.notes,
        ocr_status=item.ocr_status,
        ocr_error=item.ocr_error,
        quality_flags=item.quality_flags,
    )


def _resolve_representative_image_path(
    *,
    project_root: Path,
    prepare_run: str,
    image_path: Path,
) -> Path:
    if image_path.is_absolute():
        return image_path
    prepare_root = (
        project_root / "prepare"
        if prepare_run == "prepare_default"
        else project_root / "prepare" / "runs" / prepare_run
    )
    return (prepare_root / image_path).resolve()


def _find_review_item_index(
    summary: ReviewStageSummary,
    segment_id: str,
) -> int | None:
    normalized = segment_id.strip()
    if not normalized:
        return None
    for index, item in enumerate(summary.items):
        if item.segment_id == normalized:
            return index
    return None


def _resolve_raw_output_path(project_root: Path, ocr_run: str) -> Path:
    return resolve_review_state_path(project_root, ocr_run).with_name("raw_outputs.jsonl")


def _load_review_preview_png(
    image_path: Path,
    *,
    max_width: int,
    max_height: int,
) -> bytes | None:
    if not image_path.exists():
        return None
    try:
        with Image.open(image_path) as image:
            preview = image.convert("RGB")
            preview.thumbnail((max_width, max_height))
            buffer = BytesIO()
            preview.save(buffer, format="PNG")
            return buffer.getvalue()
    except OSError:
        return None


def _load_raw_output_text(
    path: Path,
    *,
    segment_id: str,
) -> str:
    if not path.exists():
        return (
            "Raw OCR output artifact is not available for this OCR run yet.\n"
            f"Expected path: {path}"
        )

    latest_payload: dict[str, object] | None = None
    try:
        for payload in read_jsonl(path, required_fields=("segment_id",)):
            if str(payload["segment_id"]) == segment_id:
                latest_payload = payload
    except ValueError as exc:
        return (
            "Raw OCR output artifact could not be parsed.\n"
            f"Path: {path}\n"
            f"Error: {exc}"
        )
    if latest_payload is None:
        return (
            f"No raw OCR output row was found for {segment_id} in:\n"
            f"{path}"
        )

    raw_value = latest_payload.get("raw")
    if raw_value is None:
        return json.dumps(latest_payload, indent=2, ensure_ascii=False)
    if isinstance(raw_value, str):
        return raw_value
    return json.dumps(raw_value, indent=2, ensure_ascii=False)
