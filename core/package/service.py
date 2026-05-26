"""Package services for VOCra."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vocra.core.package.srt import build_entries, build_srt
from vocra.core.prepare.models import SubtitleSegment
from vocra.core.project.jsonl import read_jsonl
from vocra.core.project.manifest import write_json_file_atomic
from vocra.core.project.runs import create_package_run
from vocra.core.project.workspace import (
    ProjectWorkspaceError,
    open_project,
    resolve_paths,
)
from vocra.core.review.models import ReviewState
from vocra.core.review.service import (
    load_review_state_map,
    resolve_review_state_path,
)


@dataclass(frozen=True)
class PackageOptions:
    format: str = "srt"
    empty_text_policy: str = "skip"
    line_break_policy: str = "preserve"
    min_subtitle_duration_ms: int = 0
    max_merge_gap_ms: int = 0
    review_state_policy: str = "auto"


@dataclass(frozen=True)
class PackageResult:
    run_dir: Path
    output_path: Path
    package_report_path: Path
    subtitle_count: int


@dataclass(frozen=True)
class PackagePreview:
    rendered_text: str
    subtitle_count: int
    prepare_source_path: Path
    ocr_source_path: Path
    review_source_path: Path | None


def package_srt(
    project_root: Path,
    *,
    prepare_run: str,
    ocr_run: str,
    options: PackageOptions,
    output_path: Path | None = None,
) -> PackageResult:
    project = open_project(project_root)
    paths = resolve_paths(project.root)
    preview = preview_srt(
        project_root,
        prepare_run=prepare_run,
        ocr_run=ocr_run,
        options=options,
    )

    run_dir = create_package_run(project, options.format)
    resolved_output_path = (
        output_path.expanduser().resolve()
        if output_path is not None
        else run_dir / "output.srt"
    )
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_output_path.write_text(preview.rendered_text, encoding="utf-8", newline="\n")

    package_config_path = run_dir / "package_config.json"
    report_path = run_dir / "package_report.json"
    write_json_file_atomic(
        package_config_path,
        {
            "schema_version": 1,
            "prepare_source": str(preview.prepare_source_path.relative_to(paths.root)),
            "ocr_source": str(preview.ocr_source_path.relative_to(paths.root)),
            "review_source": (
                str(preview.review_source_path.relative_to(paths.root))
                if preview.review_source_path is not None
                else None
            ),
            "format": options.format,
            "min_subtitle_duration_ms": options.min_subtitle_duration_ms,
            "max_merge_gap_ms": options.max_merge_gap_ms,
            "empty_text_policy": options.empty_text_policy,
            "line_break_policy": options.line_break_policy,
            "review_state_policy": options.review_state_policy,
        },
    )
    write_json_file_atomic(
        report_path,
        {
            "schema_version": 1,
            "format": options.format,
            "subtitle_count": preview.subtitle_count,
            "output_path": str(resolved_output_path),
        },
    )
    return PackageResult(
        run_dir=run_dir,
        output_path=resolved_output_path,
        package_report_path=report_path,
        subtitle_count=preview.subtitle_count,
    )


def preview_srt(
    project_root: Path,
    *,
    prepare_run: str,
    ocr_run: str,
    options: PackageOptions,
) -> PackagePreview:
    project = open_project(project_root)
    paths = resolve_paths(project.root)
    segments_path = _resolve_prepare_segments_path(paths.root, prepare_run)
    ocr_path = _resolve_ocr_text_path(paths.root, ocr_run)
    review_state_path = resolve_review_state_path(paths.root, ocr_run)

    segments = [
        SubtitleSegment.from_dict(payload)
        for payload in read_jsonl(
            segments_path,
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
    review_states = _load_review_states(
        paths.root,
        ocr_run=ocr_run,
        review_state_path=review_state_path,
        review_state_policy=options.review_state_policy,
    )
    text_by_segment = _load_text_by_segment(ocr_path, review_states=review_states)
    entries = build_entries(
        segments,
        text_by_segment,
        min_subtitle_duration_ms=options.min_subtitle_duration_ms,
        empty_text_policy=options.empty_text_policy,
    )
    return PackagePreview(
        rendered_text=build_srt(entries),
        subtitle_count=len(entries),
        prepare_source_path=segments_path,
        ocr_source_path=ocr_path,
        review_source_path=(review_state_path if review_states else None),
    )


def _resolve_prepare_segments_path(project_root: Path, prepare_run: str) -> Path:
    if prepare_run == "prepare_default":
        return project_root / "prepare" / "subtitle_segments.jsonl"
    return project_root / "prepare" / "runs" / prepare_run / "subtitle_segments.jsonl"


def _resolve_ocr_text_path(project_root: Path, ocr_run: str) -> Path:
    return project_root / "ocr" / "runs" / ocr_run / "normalized_text.jsonl"


def _load_review_states(
    project_root: Path,
    *,
    ocr_run: str,
    review_state_path: Path,
    review_state_policy: str,
) -> dict[str, ReviewState]:
    if review_state_policy == "ignore":
        return {}
    if review_state_policy == "auto":
        if not review_state_path.exists():
            return {}
        return load_review_state_map(project_root, ocr_run)
    if review_state_policy == "require":
        if not review_state_path.exists():
            raise ProjectWorkspaceError(
                f"Required review state does not exist: {review_state_path}"
            )
        return load_review_state_map(project_root, ocr_run)
    raise ValueError(f"Unsupported review_state_policy: {review_state_policy}")


def _load_text_by_segment(
    path: Path,
    *,
    review_states: dict[str, ReviewState],
) -> dict[str, str]:
    text_by_segment: dict[str, str] = {}
    for payload in read_jsonl(
        path,
        required_fields=("segment_id", "text", "status"),
    ):
        segment_id = str(payload["segment_id"])
        text_by_segment[segment_id] = _select_text(payload)

    for segment_id, review_state in review_states.items():
        review_status = review_state.review_status
        if review_status == "rejected":
            text_by_segment[segment_id] = ""
            continue
        if review_status in {"accepted", "edited"}:
            text_by_segment[segment_id] = review_state.edited_text
    return text_by_segment


def _select_text(payload: dict[str, Any]) -> str:
    status = str(payload["status"])
    if status == "error":
        return ""
    return str(payload.get("text", ""))
