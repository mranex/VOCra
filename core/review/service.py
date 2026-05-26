"""Review services for VOCra."""

from __future__ import annotations

from pathlib import Path

from vocra.core.prepare.models import SubtitleSegment
from vocra.core.project.jsonl import read_jsonl, write_jsonl_atomic
from vocra.core.project.workspace import open_project, resolve_paths
from vocra.core.review.models import ReviewItem, ReviewState
from vocra.core.review.quality import apply_quality_flags, filter_review_items


def load_review_items(
    project_root: Path,
    *,
    prepare_run: str,
    ocr_run: str,
    filter_name: str = "all",
) -> list[ReviewItem]:
    project = open_project(project_root)
    paths = resolve_paths(project.root)
    segments = _load_segments(_resolve_prepare_segments_path(paths.root, prepare_run))
    ocr_rows = _load_ocr_rows(_resolve_ocr_text_path(paths.root, ocr_run))
    review_states = load_review_state_map(project.root, ocr_run)

    items = [
        _build_review_item(segment, ocr_rows.get(segment.segment_id), review_states)
        for segment in segments
        if segment.segment_id in ocr_rows
    ]
    enriched_items = apply_quality_flags(items)
    return filter_review_items(enriched_items, filter_name)


def load_review_state_map(project_root: Path, ocr_run: str) -> dict[str, ReviewState]:
    review_state_path = resolve_review_state_path(project_root, ocr_run)
    if not review_state_path.exists():
        return {}
    return {
        review_state.segment_id: review_state
        for review_state in _read_review_states(review_state_path)
    }


def resolve_review_state_path(project_root: Path, ocr_run: str) -> Path:
    project = open_project(project_root)
    paths = resolve_paths(project.root)
    return paths.ocr_runs_dir / ocr_run / "review_state.jsonl"


def save_review_edit(
    project_root: Path,
    *,
    ocr_run: str,
    segment_id: str,
    review_status: str,
    edited_text: str | None = None,
    notes: str = "",
) -> ReviewState:
    if review_status not in {"pending", "accepted", "edited", "rejected"}:
        raise ValueError(f"Unsupported review status: {review_status}")

    states = save_review_batch(
        project_root,
        prepare_run="prepare_default",
        ocr_run=ocr_run,
        review_status=review_status,
        segment_ids=(segment_id,),
        edited_text=edited_text,
        notes=notes,
    )
    return states[0]


def save_review_batch(
    project_root: Path,
    *,
    prepare_run: str,
    ocr_run: str,
    review_status: str,
    segment_ids: tuple[str, ...] = (),
    filter_name: str | None = None,
    edited_text: str | None = None,
    notes: str = "",
) -> list[ReviewState]:
    if review_status not in {"pending", "accepted", "edited", "rejected"}:
        raise ValueError(f"Unsupported review status: {review_status}")
    if bool(segment_ids) == bool(filter_name):
        raise ValueError("Provide exactly one of `segment_ids` or `filter_name`.")
    if edited_text is not None and len(segment_ids) > 1:
        raise ValueError("Batch edited_text is only supported for a single segment.")

    project = open_project(project_root)
    ocr_rows = _load_ocr_rows(_resolve_ocr_text_path(project.root, ocr_run))
    existing_states = load_review_state_map(project.root, ocr_run)
    resolved_segment_ids = (
        _resolve_filtered_segment_ids(
            project.root,
            prepare_run=prepare_run,
            ocr_run=ocr_run,
            filter_name=filter_name,
        )
        if filter_name is not None
        else segment_ids
    )
    if not resolved_segment_ids:
        return []

    updated_states: list[ReviewState] = []
    for segment_id in resolved_segment_ids:
        if segment_id not in ocr_rows:
            raise ValueError(
                f"Segment does not exist in OCR run `{ocr_run}`: {segment_id}"
            )
        next_state = _build_review_state(
            segment_id=segment_id,
            current_row=ocr_rows[segment_id],
            current_state=existing_states.get(segment_id),
            review_status=review_status,
            edited_text=edited_text,
            notes=notes,
        )
        existing_states[segment_id] = next_state
        updated_states.append(next_state)

    _write_review_states(project.root, ocr_run=ocr_run, states=existing_states.values())
    return updated_states


def _build_review_item(
    segment: SubtitleSegment,
    ocr_row: dict[str, object] | None,
    review_states: dict[str, ReviewState],
) -> ReviewItem:
    if ocr_row is None:
        raise ValueError(f"Missing OCR row for segment: {segment.segment_id}")
    review_state = review_states.get(segment.segment_id)
    original_text = str(ocr_row.get("text", ""))
    review_status = "pending"
    edited_text = original_text
    notes = ""
    if review_state is not None:
        review_status = review_state.review_status
        edited_text = review_state.edited_text
        notes = review_state.notes
    return ReviewItem(
        segment_id=segment.segment_id,
        zone_idx=segment.zone_idx,
        start_ms=segment.start_ms,
        end_ms=segment.end_ms,
        representative_image=segment.representative_image,
        original_text=original_text,
        edited_text=edited_text,
        review_status=review_status,
        notes=notes,
        ocr_status=str(ocr_row.get("status", "ok")),
        ocr_error=_coerce_optional_string(ocr_row.get("error")),
    )


def _build_review_state(
    *,
    segment_id: str,
    current_row: dict[str, object],
    current_state: ReviewState | None,
    review_status: str,
    edited_text: str | None,
    notes: str,
) -> ReviewState:
    original_text = (
        current_state.original_text
        if current_state is not None
        else str(current_row.get("text", ""))
    )
    resolved_edited_text = original_text if edited_text is None else edited_text
    return ReviewState(
        segment_id=segment_id,
        original_text=original_text,
        edited_text=resolved_edited_text,
        review_status=review_status,
        notes=notes,
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


def _read_review_states(path: Path) -> list[ReviewState]:
    return [
        ReviewState.from_dict(payload)
        for payload in read_jsonl(
            path,
            required_fields=(
                "segment_id",
                "original_text",
                "edited_text",
                "review_status",
            ),
        )
    ]


def _sort_review_states(states: object) -> list[ReviewState]:
    return sorted(
        list(states),
        key=lambda item: item.segment_id,
    )


def _resolve_filtered_segment_ids(
    project_root: Path,
    *,
    prepare_run: str,
    ocr_run: str,
    filter_name: str,
) -> tuple[str, ...]:
    items = load_review_items(
        project_root,
        prepare_run=prepare_run,
        ocr_run=ocr_run,
        filter_name=filter_name,
    )
    return tuple(item.segment_id for item in items)


def _write_review_states(
    project_root: Path,
    *,
    ocr_run: str,
    states: object,
) -> None:
    ordered_states = _sort_review_states(states)
    write_jsonl_atomic(
        resolve_review_state_path(project_root, ocr_run),
        (state.to_dict() for state in ordered_states),
    )


def _resolve_prepare_segments_path(project_root: Path, prepare_run: str) -> Path:
    if prepare_run == "prepare_default":
        return project_root / "prepare" / "subtitle_segments.jsonl"
    return project_root / "prepare" / "runs" / prepare_run / "subtitle_segments.jsonl"


def _resolve_ocr_text_path(project_root: Path, ocr_run: str) -> Path:
    return project_root / "ocr" / "runs" / ocr_run / "normalized_text.jsonl"
