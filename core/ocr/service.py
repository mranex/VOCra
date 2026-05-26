"""OCR service orchestration for VOCra."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vocra.core.ocr.models import OcrInput, OcrOutput, OcrRunSummary
from vocra.core.ocr.registry import create_backend
from vocra.core.prepare.models import SubtitleSegment
from vocra.core.project.jsonl import append_jsonl, read_jsonl, write_jsonl_atomic
from vocra.core.project.manifest import write_json_file_atomic
from vocra.core.project.runs import create_ocr_run
from vocra.core.project.workspace import open_project, resolve_paths


@dataclass(frozen=True)
class OcrRunResult:
    run_dir: Path
    config_path: Path
    raw_outputs_path: Path
    normalized_text_path: Path
    errors_path: Path
    report_path: Path
    summary: OcrRunSummary


def run_ocr(
    project_root: Path,
    *,
    prepare_run: str,
    config: dict[str, Any],
    run_id: str | None = None,
    force: bool = False,
    rerun_empty: bool = False,
) -> OcrRunResult:
    project = open_project(project_root)
    paths = resolve_paths(project.root)
    backend = create_backend(config)
    backend.validate_config(config)

    prepare_segments_path = _resolve_prepare_segments_path(paths.root, prepare_run)
    segments = _load_segments(prepare_segments_path)
    inputs = _build_inputs(paths.root, prepare_run, segments)

    if run_id is None:
        run_dir = create_ocr_run(project, str(config["backend"]))
        is_resume = False
    else:
        run_dir = paths.ocr_runs_dir / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        is_resume = True

    config_path = run_dir / "ocr_config.json"
    raw_outputs_path = run_dir / "raw_outputs.jsonl"
    normalized_text_path = run_dir / "normalized_text.jsonl"
    errors_path = run_dir / "errors.jsonl"
    report_path = run_dir / "run_report.json"

    latest_rows_by_segment: dict[str, dict[str, Any]] = {}
    if is_resume and normalized_text_path.exists() and not force:
        latest_rows_by_segment = _load_latest_rows_by_segment(normalized_text_path)

    if force:
        selected_inputs = list(inputs)
    elif rerun_empty:
        empty_segment_ids = {
            segment_id
            for segment_id, payload in latest_rows_by_segment.items()
            if str(payload.get("status", "")) != "error"
            and not str(payload.get("text", "")).strip()
        }
        selected_inputs = [
            item for item in inputs if item.segment_id in empty_segment_ids
        ]
    else:
        completed_segment_ids = {
            segment_id
            for segment_id, payload in latest_rows_by_segment.items()
            if str(payload.get("status", "")) != "error"
        }
        selected_inputs = [
            item for item in inputs if item.segment_id not in completed_segment_ids
        ]
    input_map = {item.segment_id: item for item in inputs}

    effective_run_id = run_dir.name
    write_json_file_atomic(
        config_path,
        {
            "schema_version": 1,
            "run_id": effective_run_id,
            "input_prepare_id": prepare_run,
            **config,
        },
    )
    if not raw_outputs_path.exists():
        write_jsonl_atomic(raw_outputs_path, [])
    if not normalized_text_path.exists():
        write_jsonl_atomic(normalized_text_path, [])
    if not errors_path.exists():
        write_jsonl_atomic(errors_path, [])

    ok_count = 0
    error_count = 0
    empty_count = 0
    for output in backend.run(selected_inputs, config):
        append_jsonl(
            raw_outputs_path,
            _build_raw_output_row(
                output,
                input_map=input_map,
                backend_name=str(config["backend"]),
            ),
        )
        append_jsonl(
            normalized_text_path,
            _build_normalized_output_row(
                output,
                run_id=effective_run_id,
                backend_name=str(config["backend"]),
                input_map=input_map,
            ),
        )
        if output.status == "error":
            append_jsonl(
                errors_path,
                {
                    "segment_id": output.segment_id,
                    "backend": str(config["backend"]),
                    "error": output.error,
                    "raw": output.raw,
                },
            )
            error_count += 1
            continue

        ok_count += 1
        if not output.text.strip():
            empty_count += 1

    summary = OcrRunSummary(
        run_id=effective_run_id,
        ok_count=ok_count,
        error_count=error_count,
        empty_count=empty_count,
    )
    write_json_file_atomic(
        report_path,
        {
            "schema_version": 1,
            "run_id": summary.run_id,
            "backend": str(config["backend"]),
            "processed_segments": len(selected_inputs),
            "ok_count": summary.ok_count,
            "error_count": summary.error_count,
            "empty_count": summary.empty_count,
            "skipped_existing_count": len(inputs) - len(selected_inputs),
        },
    )
    return OcrRunResult(
        run_dir=run_dir,
        config_path=config_path,
        raw_outputs_path=raw_outputs_path,
        normalized_text_path=normalized_text_path,
        errors_path=errors_path,
        report_path=report_path,
        summary=summary,
    )


def _resolve_prepare_segments_path(project_root: Path, prepare_run: str) -> Path:
    if prepare_run == "prepare_default":
        return project_root / "prepare" / "subtitle_segments.jsonl"
    return project_root / "prepare" / "runs" / prepare_run / "subtitle_segments.jsonl"


def _resolve_prepare_base_dir(project_root: Path, prepare_run: str) -> Path:
    if prepare_run == "prepare_default":
        return project_root / "prepare"
    return project_root / "prepare" / "runs" / prepare_run


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


def _build_inputs(
    project_root: Path,
    prepare_run: str,
    segments: list[SubtitleSegment],
) -> list[OcrInput]:
    prepare_base_dir = _resolve_prepare_base_dir(project_root, prepare_run)
    inputs: list[OcrInput] = []
    for segment in segments:
        image_path = prepare_base_dir / segment.representative_image
        if not image_path.exists():
            raise FileNotFoundError(f"Representative image does not exist: {image_path}")
        inputs.append(
            OcrInput(
                segment_id=segment.segment_id,
                image_path=image_path,
                zone_idx=segment.zone_idx,
                start_ms=segment.start_ms,
                end_ms=segment.end_ms,
                metadata={
                    "start_frame_idx": segment.start_frame_idx,
                    "end_frame_idx": segment.end_frame_idx,
                    "source_frame_indices": list(segment.source_frame_indices),
                },
            )
        )
    return inputs


def _load_latest_rows_by_segment(path: Path) -> dict[str, dict[str, Any]]:
    latest_rows: dict[str, dict[str, Any]] = {}
    for payload in read_jsonl(
        path,
        required_fields=("segment_id", "status"),
    ):
        latest_rows[str(payload["segment_id"])] = payload
    return latest_rows


def _build_raw_output_row(
    output: OcrOutput,
    *,
    input_map: dict[str, OcrInput],
    backend_name: str,
) -> dict[str, Any]:
    item = input_map[output.segment_id]
    return {
        "segment_id": output.segment_id,
        "image": str(item.image_path),
        "backend": backend_name,
        "raw": output.raw,
    }


def _build_normalized_output_row(
    output: OcrOutput,
    *,
    run_id: str,
    backend_name: str,
    input_map: dict[str, OcrInput],
) -> dict[str, Any]:
    item = input_map[output.segment_id]
    return {
        "segment_id": output.segment_id,
        "zone_idx": item.zone_idx,
        "text": output.text,
        "confidence": output.confidence,
        "status": output.status,
        "error": output.error,
        "source": {
            "backend": backend_name,
            "run_id": run_id,
        },
    }
