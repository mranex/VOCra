"""GUI-facing OCR run services."""

from __future__ import annotations

from pathlib import Path

from vocra.app.models import (
    OcrBackendTestOutcome,
    OcrConfigForm,
    OcrRunListItem,
    OcrRunOutcome,
    OcrStageSummary,
)
from vocra.app.ocr_service import load_ocr_stage_summary
from vocra.core.ocr.registry import create_backend
from vocra.core.ocr.service import run_ocr
from vocra.core.project.workspace import ProjectWorkspaceError, open_project


def run_ocr_from_project(
    project_root: Path,
    form: OcrConfigForm,
) -> OcrRunOutcome:
    return _run_ocr_from_project(
        project_root,
        form,
        action="run",
    )


def resume_failed_ocr_from_project(
    project_root: Path,
    form: OcrConfigForm,
) -> OcrRunOutcome:
    return _run_ocr_from_project(
        project_root,
        form,
        action="resume_failed_only",
    )


def rerun_empty_ocr_from_project(
    project_root: Path,
    form: OcrConfigForm,
) -> OcrRunOutcome:
    return _run_ocr_from_project(
        project_root,
        form,
        action="rerun_empty_only",
    )


def _run_ocr_from_project(
    project_root: Path,
    form: OcrConfigForm,
    *,
    action: str,
) -> OcrRunOutcome:
    project = open_project(project_root)
    summary = load_ocr_stage_summary(project.root)
    prepare_run = form.prepare_run.strip()
    if not prepare_run:
        raise ProjectWorkspaceError("Choose a prepare run before starting OCR.")
    if prepare_run not in summary.prepare_run_options:
        raise ProjectWorkspaceError(
            f"Prepare run is not available for OCR: {prepare_run}"
        )

    backend_name = form.backend_name.strip()
    if not backend_name:
        raise ProjectWorkspaceError("Choose an OCR backend before starting OCR.")

    config = _build_ocr_config(form)
    rerun_empty = action == "rerun_empty_only"
    run_id = _resolve_target_run_id(
        summary,
        form,
        action=action,
    )
    try:
        result = run_ocr(
            project.root,
            prepare_run=prepare_run,
            config=config,
            run_id=run_id,
            force=bool(form.force),
            rerun_empty=rerun_empty,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise ProjectWorkspaceError(str(exc)) from exc

    return OcrRunOutcome(
        run_id=result.summary.run_id,
        run_dir=result.run_dir,
        config_path=result.config_path,
        raw_outputs_path=result.raw_outputs_path,
        normalized_text_path=result.normalized_text_path,
        errors_path=result.errors_path,
        report_path=result.report_path,
        ok_count=result.summary.ok_count,
        error_count=result.summary.error_count,
        empty_count=result.summary.empty_count,
    )


def test_ocr_backend_connection(form: OcrConfigForm) -> OcrBackendTestOutcome:
    backend_name = form.backend_name.strip()
    if not backend_name:
        raise ProjectWorkspaceError("Choose an OCR backend before testing it.")

    config = _build_ocr_config(form)
    try:
        backend = create_backend(config)
    except ValueError as exc:
        raise ProjectWorkspaceError(str(exc)) from exc

    result = backend.test_connection(config)
    return OcrBackendTestOutcome(
        backend_name=backend_name,
        ok=result.ok,
        message=result.message,
    )


def _resolve_target_run_id(
    summary: OcrStageSummary,
    form: OcrConfigForm,
    *,
    action: str,
) -> str | None:
    requested_run_id = form.run_id.strip()
    if action == "run":
        return requested_run_id or None

    if requested_run_id:
        target = next(
            (item for item in summary.runs if item.run_id == requested_run_id),
            None,
        )
        if target is None:
            raise ProjectWorkspaceError(
                f"OCR run does not exist for resume/rerun: {requested_run_id}"
            )
        _validate_target_run(target, form)
        return target.run_id

    matching_runs = [
        item
        for item in summary.runs
        if item.prepare_run == form.prepare_run.strip()
        and item.backend_name == form.backend_name.strip()
    ]
    if len(matching_runs) == 1:
        return matching_runs[0].run_id
    if not matching_runs:
        raise ProjectWorkspaceError(
            "Choose an existing OCR run id before resume/rerun. "
            "No matching OCR run exists yet for the selected prepare run and backend."
        )
    raise ProjectWorkspaceError(
        "Choose an OCR run id before resume/rerun. "
        "Multiple matching OCR runs exist for the selected prepare run and backend."
    )


def _validate_target_run(target: OcrRunListItem, form: OcrConfigForm) -> None:
    expected_prepare_run = form.prepare_run.strip()
    if target.prepare_run and target.prepare_run != expected_prepare_run:
        raise ProjectWorkspaceError(
            "Selected OCR run belongs to a different prepare run. "
            f"Expected {expected_prepare_run}, found {target.prepare_run}."
        )
    expected_backend = form.backend_name.strip()
    if target.backend_name and target.backend_name != expected_backend:
        raise ProjectWorkspaceError(
            "Selected OCR run belongs to a different backend. "
            f"Expected {expected_backend}, found {target.backend_name}."
        )


def _build_ocr_config(form: OcrConfigForm) -> dict[str, object]:
    config: dict[str, object] = {"backend": form.backend_name.strip()}
    if form.text_template.strip():
        config["text_template"] = form.text_template.strip()
    if form.endpoint.strip():
        config["endpoint"] = form.endpoint.strip()
    if form.api_key.strip():
        config["api_key"] = form.api_key.strip()
    if form.model.strip():
        config["model"] = form.model.strip()
    if form.prompt_template.strip():
        config["prompt_template"] = form.prompt_template.strip()
    if form.temperature.strip():
        config["temperature"] = _parse_float(
            form.temperature,
            field_name="temperature",
        )
    if form.max_tokens.strip():
        config["max_tokens"] = _parse_int(
            form.max_tokens,
            field_name="max_tokens",
            minimum=1,
        )
    if form.timeout_sec.strip():
        config["timeout_sec"] = _parse_float(
            form.timeout_sec,
            field_name="timeout_sec",
            minimum=0.001,
        )
    if form.command_template.strip():
        config["command_template"] = form.command_template.strip()
    if form.stdout_format.strip():
        config["stdout_format"] = form.stdout_format.strip()
    if form.working_dir.strip():
        config["working_dir"] = form.working_dir.strip()
    return config


def _parse_int(
    raw_value: str,
    *,
    field_name: str,
    minimum: int | None = None,
) -> int:
    try:
        parsed = int(raw_value.strip())
    except ValueError as exc:
        raise ProjectWorkspaceError(
            f"OCR field '{field_name}' must be an integer when provided."
        ) from exc
    if minimum is not None and parsed < minimum:
        raise ProjectWorkspaceError(
            f"OCR field '{field_name}' must be >= {minimum}."
        )
    return parsed


def _parse_float(
    raw_value: str,
    *,
    field_name: str,
    minimum: float | None = None,
) -> float:
    try:
        parsed = float(raw_value.strip())
    except ValueError as exc:
        raise ProjectWorkspaceError(
            f"OCR field '{field_name}' must be a number when provided."
        ) from exc
    if minimum is not None and parsed < minimum:
        raise ProjectWorkspaceError(
            f"OCR field '{field_name}' must be >= {minimum}."
        )
    return parsed
