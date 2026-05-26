"""GUI-facing OCR comparison services built on top of VOCra artifacts."""

from __future__ import annotations

from pathlib import Path

from vocra.app.models import (
    OcrComparisonApplyOutcome,
    OcrComparisonCandidate,
    OcrComparisonItem,
    OcrComparisonSummary,
)
from vocra.app.ocr_service import (
    find_ocr_run_item,
    load_ocr_stage_summary,
)
from vocra.core.package.srt import format_srt_timestamp
from vocra.core.prepare.models import SubtitleSegment
from vocra.core.project.jsonl import read_jsonl
from vocra.core.project.workspace import ProjectWorkspaceError, open_project
from vocra.core.review.models import ReviewState
from vocra.core.review.service import (
    load_review_state_map,
    resolve_review_state_path,
    save_review_edit,
)


def load_ocr_comparison_summary(
    project_root: Path,
    *,
    prepare_run: str | None = None,
    target_ocr_run: str | None = None,
    source_ocr_runs: tuple[str, ...] = (),
) -> OcrComparisonSummary:
    project = open_project(project_root)
    ocr_summary = load_ocr_stage_summary(project.root)
    warnings = list(ocr_summary.warnings)

    prepare_run_options = ocr_summary.prepare_run_options
    selected_prepare_run = _resolve_prepare_run(
        requested_prepare_run=prepare_run,
        prepare_run_options=prepare_run_options,
    )

    available_runs = tuple(
        item
        for item in ocr_summary.runs
        if item.prepare_run in {"", None, selected_prepare_run}
    )
    available_run_ids = tuple(item.run_id for item in available_runs)
    selected_target_run = _resolve_target_run(
        available_run_ids=available_run_ids,
        requested_target_run=target_ocr_run,
    )
    selected_source_runs = _resolve_source_runs(
        available_run_ids=available_run_ids,
        requested_source_runs=source_ocr_runs,
        selected_target_run=selected_target_run,
    )

    if len(selected_source_runs) < 2:
        warnings.append(
            "Compare OCR runs works best with at least two OCR runs for the same Prepare run."
        )

    items: tuple[OcrComparisonItem, ...] = ()
    if selected_prepare_run and selected_target_run and selected_source_runs:
        segments = _load_segments(
            _resolve_prepare_segments_path(project.root, selected_prepare_run)
        )
        run_items = {
            item.run_id: item
            for item in available_runs
            if item.run_id in selected_source_runs
        }
        ocr_rows_by_run = {
            run_id: _load_ocr_rows(_resolve_ocr_text_path(project.root, run_id))
            for run_id in selected_source_runs
        }
        target_review_states = load_review_state_map(project.root, selected_target_run)
        target_ocr_rows = ocr_rows_by_run.get(selected_target_run)
        if target_ocr_rows is None:
            target_ocr_rows = _load_ocr_rows(
                _resolve_ocr_text_path(project.root, selected_target_run)
            )

        items = tuple(
            _build_comparison_item(
                project_root=project.root,
                prepare_run=selected_prepare_run,
                segment=segment,
                selected_source_runs=selected_source_runs,
                run_items=run_items,
                ocr_rows_by_run=ocr_rows_by_run,
                target_ocr_rows=target_ocr_rows,
                target_review_states=target_review_states,
            )
            for segment in segments
            if any(
                segment.segment_id in ocr_rows_by_run[run_id]
                for run_id in selected_source_runs
            )
        )

    return OcrComparisonSummary(
        prepare_run_options=prepare_run_options,
        available_ocr_run_options=available_run_ids,
        selected_prepare_run=selected_prepare_run,
        selected_target_ocr_run=selected_target_run,
        selected_source_ocr_runs=selected_source_runs,
        item_count=len(items),
        items=items,
        warnings=tuple(dict.fromkeys(warnings)),
    )


def render_ocr_comparison_text(summary: OcrComparisonSummary) -> str:
    lines = [
        (
            "Prepare runs: "
            f"{', '.join(summary.prepare_run_options) if summary.prepare_run_options else 'none'}"
        ),
        (
            "Available OCR runs: "
            f"{', '.join(summary.available_ocr_run_options) if summary.available_ocr_run_options else 'none'}"
        ),
        f"Selected prepare run: {summary.selected_prepare_run or 'none'}",
        f"Selected target OCR run: {summary.selected_target_ocr_run or 'none'}",
        (
            "Selected source OCR runs: "
            f"{', '.join(summary.selected_source_ocr_runs) if summary.selected_source_ocr_runs else 'none'}"
        ),
        f"Comparison items: {summary.item_count}",
    ]
    if summary.warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in summary.warnings)
    return "\n".join(lines)


def find_ocr_comparison_item(
    summary: OcrComparisonSummary,
    segment_id: str,
) -> OcrComparisonItem | None:
    normalized = segment_id.strip()
    if not normalized:
        return None
    for item in summary.items:
        if item.segment_id == normalized:
            return item
    return None


def apply_ocr_comparison_choice(
    project_root: Path,
    *,
    target_ocr_run: str,
    source_ocr_run: str,
    segment_id: str,
    notes: str | None = None,
) -> OcrComparisonApplyOutcome:
    project = open_project(project_root)
    summary = load_ocr_stage_summary(project.root)
    target_item = find_ocr_run_item(summary, target_ocr_run)
    source_item = find_ocr_run_item(summary, source_ocr_run)
    if target_item is None:
        raise ProjectWorkspaceError(f"Target OCR run does not exist: {target_ocr_run}")
    if source_item is None:
        raise ProjectWorkspaceError(f"Source OCR run does not exist: {source_ocr_run}")
    target_prepare_run = (target_item.prepare_run or "").strip()
    source_prepare_run = (source_item.prepare_run or "").strip()
    if target_prepare_run and source_prepare_run and target_prepare_run != source_prepare_run:
        raise ProjectWorkspaceError(
            "Cannot compare OCR runs from different Prepare runs. "
            f"Target uses {target_prepare_run}, "
            f"source uses {source_prepare_run}."
        )

    target_rows = _load_ocr_rows(_resolve_ocr_text_path(project.root, target_ocr_run))
    source_rows = _load_ocr_rows(_resolve_ocr_text_path(project.root, source_ocr_run))
    target_row = target_rows.get(segment_id)
    source_row = source_rows.get(segment_id)
    if target_row is None:
        raise ProjectWorkspaceError(
            f"Target OCR run `{target_ocr_run}` has no OCR row for segment {segment_id}."
        )
    if source_row is None:
        raise ProjectWorkspaceError(
            f"Source OCR run `{source_ocr_run}` has no OCR row for segment {segment_id}."
        )

    chosen_text = str(source_row.get("text", ""))
    original_text = str(target_row.get("text", ""))
    review_status = (
        "accepted" if source_ocr_run == target_ocr_run and chosen_text == original_text else "edited"
    )
    resolved_notes = (
        notes
        if notes is not None
        else f"Chosen from OCR run {source_ocr_run} during compare review."
    )
    try:
        save_review_edit(
            project.root,
            ocr_run=target_ocr_run,
            segment_id=segment_id,
            review_status=review_status,
            edited_text=chosen_text,
            notes=resolved_notes,
        )
    except ValueError as exc:
        raise ProjectWorkspaceError(str(exc)) from exc

    return OcrComparisonApplyOutcome(
        target_ocr_run=target_ocr_run,
        source_ocr_run=source_ocr_run,
        segment_id=segment_id,
        chosen_text=chosen_text,
        review_status=review_status,
        review_state_path=resolve_review_state_path(project.root, target_ocr_run),
    )


def _resolve_prepare_run(
    *,
    requested_prepare_run: str | None,
    prepare_run_options: tuple[str, ...],
) -> str:
    requested = (requested_prepare_run or "").strip()
    if requested in prepare_run_options:
        return requested
    return prepare_run_options[0] if prepare_run_options else ""


def _resolve_target_run(
    *,
    available_run_ids: tuple[str, ...],
    requested_target_run: str | None,
) -> str:
    requested = (requested_target_run or "").strip()
    if requested in available_run_ids:
        return requested
    return available_run_ids[0] if available_run_ids else ""


def _resolve_source_runs(
    *,
    available_run_ids: tuple[str, ...],
    requested_source_runs: tuple[str, ...],
    selected_target_run: str,
) -> tuple[str, ...]:
    normalized = tuple(
        run_id.strip()
        for run_id in requested_source_runs
        if run_id.strip() in available_run_ids
    )
    if normalized:
        return tuple(dict.fromkeys(normalized))

    if len(available_run_ids) <= 2:
        return available_run_ids

    selected_target_index = (
        available_run_ids.index(selected_target_run) if selected_target_run in available_run_ids else -1
    )
    if selected_target_index >= 1:
        return (
            available_run_ids[selected_target_index - 1],
            available_run_ids[selected_target_index],
        )
    latest_run = available_run_ids[-1] if available_run_ids else ""
    prior_run = available_run_ids[-2] if len(available_run_ids) >= 2 else ""
    return tuple(run_id for run_id in (prior_run, latest_run) if run_id)


def _build_comparison_item(
    *,
    project_root: Path,
    prepare_run: str,
    segment: SubtitleSegment,
    selected_source_runs: tuple[str, ...],
    run_items: dict[str, object],
    ocr_rows_by_run: dict[str, dict[str, dict[str, object]]],
    target_ocr_rows: dict[str, dict[str, object]],
    target_review_states: dict[str, ReviewState],
) -> OcrComparisonItem:
    target_row = target_ocr_rows.get(segment.segment_id)
    if target_row is None:
        target_original_text = ""
    else:
        target_original_text = str(target_row.get("text", ""))
    target_state = target_review_states.get(segment.segment_id)
    target_review_status = target_state.review_status if target_state is not None else "pending"
    target_edited_text = (
        target_state.edited_text if target_state is not None else target_original_text
    )
    target_effective_text = (
        ""
        if target_review_status == "rejected"
        else target_edited_text
        if target_review_status in {"accepted", "edited"}
        else target_original_text
    )

    candidates = tuple(
        _build_candidate(
            run_id=run_id,
            run_item=run_items.get(run_id),
            payload=ocr_rows_by_run[run_id].get(segment.segment_id),
        )
        for run_id in selected_source_runs
    )
    return OcrComparisonItem(
        segment_id=segment.segment_id,
        zone_idx=segment.zone_idx,
        start_ms=segment.start_ms,
        end_ms=segment.end_ms,
        time_label=(
            f"{format_srt_timestamp(segment.start_ms)} --> "
            f"{format_srt_timestamp(segment.end_ms)}"
        ),
        representative_image_path=_resolve_representative_image_path(
            project_root=project_root,
            prepare_run=prepare_run,
            image_path=segment.representative_image,
        ),
        target_review_status=target_review_status,
        target_edited_text=target_edited_text,
        target_effective_text=target_effective_text,
        candidates=candidates,
    )


def _build_candidate(
    *,
    run_id: str,
    run_item: object | None,
    payload: dict[str, object] | None,
) -> OcrComparisonCandidate:
    backend_name = getattr(run_item, "backend_name", None)
    model_name = getattr(run_item, "model_name", None)
    if payload is None:
        return OcrComparisonCandidate(
            run_id=run_id,
            backend_name=backend_name,
            model_name=model_name,
            text="",
            status="missing",
            error="Segment is not present in this OCR run.",
        )
    return OcrComparisonCandidate(
        run_id=run_id,
        backend_name=backend_name,
        model_name=model_name,
        text=str(payload.get("text", "")),
        status=str(payload.get("status", "ok")),
        error=_coerce_optional_string(payload.get("error")),
    )


def _coerce_optional_string(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _load_segments(path: Path) -> list[SubtitleSegment]:
    return [
        SubtitleSegment.from_dict(payload)
        for payload in read_jsonl(
            path,
            required_fields=(
                "segment_id",
                "zone_idx",
                "start_ms",
                "end_ms",
                "representative_image",
                "source_frame_indices",
                "detection_boxes",
            ),
        )
    ]


def _load_ocr_rows(path: Path) -> dict[str, dict[str, object]]:
    return {
        str(payload["segment_id"]): payload
        for payload in read_jsonl(
            path,
            required_fields=("segment_id", "text", "status"),
        )
    }


def _resolve_prepare_segments_path(project_root: Path, prepare_run: str) -> Path:
    if prepare_run == "prepare_default":
        return project_root / "prepare" / "subtitle_segments.jsonl"
    return project_root / "prepare" / "runs" / prepare_run / "subtitle_segments.jsonl"


def _resolve_ocr_text_path(project_root: Path, ocr_run: str) -> Path:
    return project_root / "ocr" / "runs" / ocr_run / "normalized_text.jsonl"


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
