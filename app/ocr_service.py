"""GUI-facing OCR tab services built on top of VOCra artifacts."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from vocra.app.models import (
    OcrBackendFormSpec,
    OcrConfigForm,
    OcrRunListItem,
    OcrStageSummary,
)
from vocra.core.ocr.registry import list_backends
from vocra.core.project.jsonl import JsonlArtifactError, read_jsonl
from vocra.core.project.manifest import ManifestValidationError, read_json_file
from vocra.core.project.workspace import (
    ProjectWorkspaceError,
    open_project,
    resolve_paths,
)

_DEFAULT_SUBTITLE_PROMPT = "OCR this subtitle image. Return only the subtitle text."

_BACKEND_SPECS: dict[str, OcrBackendFormSpec] = {
    "fake": OcrBackendFormSpec(
        backend_name="fake",
        enabled_fields=("text_template",),
        required_fields=(),
        help_text=(
            "Fake backend is deterministic and local-only. "
            "Use it first to verify prepared artifacts and OCR packaging flow."
        ),
    ),
    "openai-compatible-vision": OcrBackendFormSpec(
        backend_name="openai-compatible-vision",
        enabled_fields=(
            "endpoint",
            "api_key",
            "model",
            "prompt_template",
            "temperature",
            "max_tokens",
            "timeout_sec",
        ),
        required_fields=("endpoint", "model", "prompt_template"),
        help_text=(
            "OpenAI-compatible vision sends images to the configured endpoint. "
            "Keep the endpoint local unless the user explicitly wants remote OCR."
        ),
    ),
    "ollama": OcrBackendFormSpec(
        backend_name="ollama",
        enabled_fields=(
            "endpoint",
            "model",
            "prompt_template",
            "temperature",
            "timeout_sec",
        ),
        required_fields=("model", "prompt_template"),
        help_text=(
            "Ollama is local-first by default and talks to the configured Ollama API endpoint."
        ),
    ),
    "local-command": OcrBackendFormSpec(
        backend_name="local-command",
        enabled_fields=("command_template", "stdout_format", "working_dir", "timeout_sec"),
        required_fields=("command_template",),
        help_text=(
            "Local command runs an arbitrary OCR executable on this machine. "
            "Use placeholders like {image}, {segment_id}, {zone_idx}, {start_ms}, and {end_ms}."
        ),
    ),
}


def load_ocr_stage_summary(project_root: Path) -> OcrStageSummary:
    project = open_project(project_root)
    paths = resolve_paths(project.root)
    warnings: list[str] = []

    prepare_run_options = _collect_prepare_run_options(paths.root)
    if not prepare_run_options:
        warnings.append("No prepared subtitle segment artifacts are available yet.")

    run_items: list[OcrRunListItem] = []
    for run_dir in _list_run_dirs(paths.ocr_runs_dir):
        try:
            run_items.append(_build_ocr_run_list_item(run_dir))
        except (JsonlArtifactError, ManifestValidationError, ValueError) as exc:
            warnings.append(f"OCR run {run_dir.name} could not be summarized: {exc}")

    if not run_items:
        warnings.append("No OCR runs exist yet.")

    return OcrStageSummary(
        ocr_runs_dir=paths.ocr_runs_dir,
        prepare_run_options=prepare_run_options,
        backend_options=_ordered_backend_options(),
        run_count=len(run_items),
        runs=tuple(run_items),
        warnings=tuple(warnings),
    )


def load_ocr_config_form(project_root: Path) -> OcrConfigForm:
    summary = load_ocr_stage_summary(project_root)
    prepare_run = summary.prepare_run_options[0] if summary.prepare_run_options else ""
    return apply_ocr_backend_defaults(
        OcrConfigForm(
            prepare_run=prepare_run,
            backend_name="fake",
            run_id="",
            force=False,
            text_template="Text for {segment_id}",
            endpoint="",
            api_key="",
            model="",
            prompt_template="",
            temperature="0",
            max_tokens="256",
            timeout_sec="120",
            command_template="",
            stdout_format="plain_text",
            working_dir="",
        ),
        "fake",
    )


def load_ocr_config_form_for_run(
    project_root: Path,
    run_id: str,
) -> OcrConfigForm:
    summary = load_ocr_stage_summary(project_root)
    run_item = find_ocr_run_item(summary, run_id)
    if run_item is None:
        raise ProjectWorkspaceError(f"OCR run does not exist: {run_id}")
    if not run_item.config_path.exists():
        raise ProjectWorkspaceError(
            f"OCR run config does not exist for selected run: {run_item.config_path}"
        )

    payload = read_json_file(run_item.config_path)
    form = OcrConfigForm(
        prepare_run=str(payload.get("input_prepare_id", run_item.prepare_run or "")),
        backend_name=str(payload.get("backend", run_item.backend_name or "")),
        run_id=run_item.run_id,
        force=False,
        text_template=str(payload.get("text_template", "")),
        endpoint=str(payload.get("endpoint", "")),
        api_key=str(payload.get("api_key", "")),
        model=str(payload.get("model", run_item.model_name or "")),
        prompt_template=str(payload.get("prompt_template", "")),
        temperature=_stringify_optional(payload.get("temperature")),
        max_tokens=_stringify_optional(payload.get("max_tokens")),
        timeout_sec=_stringify_optional(payload.get("timeout_sec")),
        command_template=str(payload.get("command_template", "")),
        stdout_format=str(payload.get("stdout_format", "")),
        working_dir=str(payload.get("working_dir", "")),
    )
    return apply_ocr_backend_defaults(form, form.backend_name)


def get_ocr_backend_form_spec(backend_name: str) -> OcrBackendFormSpec:
    normalized = backend_name.strip().lower()
    return _BACKEND_SPECS.get(
        normalized,
        OcrBackendFormSpec(
            backend_name=normalized or "unknown",
            enabled_fields=(),
            required_fields=(),
            help_text="Unknown backend. Save or test config only after selecting a supported backend.",
        ),
    )


def apply_ocr_backend_defaults(
    form: OcrConfigForm,
    backend_name: str,
) -> OcrConfigForm:
    normalized = backend_name.strip().lower()
    endpoint = form.endpoint
    prompt_template = form.prompt_template
    timeout_sec = form.timeout_sec
    temperature = form.temperature
    max_tokens = form.max_tokens
    stdout_format = form.stdout_format
    text_template = form.text_template

    if normalized == "fake":
        if not text_template.strip():
            text_template = "Text for {segment_id}"
    elif normalized == "openai-compatible-vision":
        if not endpoint.strip():
            endpoint = "http://127.0.0.1:8080/v1"
        if not prompt_template.strip():
            prompt_template = _DEFAULT_SUBTITLE_PROMPT
        if not temperature.strip():
            temperature = "0"
        if not max_tokens.strip():
            max_tokens = "256"
        if not timeout_sec.strip():
            timeout_sec = "120"
    elif normalized == "ollama":
        if not endpoint.strip():
            endpoint = "http://127.0.0.1:11434"
        if not prompt_template.strip():
            prompt_template = _DEFAULT_SUBTITLE_PROMPT
        if not temperature.strip():
            temperature = "0"
        if not timeout_sec.strip():
            timeout_sec = "120"
    elif normalized == "local-command":
        if not stdout_format.strip():
            stdout_format = "plain_text"
        if not timeout_sec.strip():
            timeout_sec = "120"

    return OcrConfigForm(
        prepare_run=form.prepare_run,
        backend_name=normalized or form.backend_name,
        run_id=form.run_id,
        force=form.force,
        text_template=text_template,
        endpoint=endpoint,
        api_key=form.api_key,
        model=form.model,
        prompt_template=prompt_template,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout_sec=timeout_sec,
        command_template=form.command_template,
        stdout_format=stdout_format,
        working_dir=form.working_dir,
    )


def render_ocr_stage_text(summary: OcrStageSummary) -> str:
    lines = [
        f"OCR runs directory: {summary.ocr_runs_dir}",
        f"Available prepare runs: {', '.join(summary.prepare_run_options) if summary.prepare_run_options else 'none'}",
        f"Available backends: {', '.join(summary.backend_options) if summary.backend_options else 'none'}",
        f"OCR run count: {summary.run_count}",
    ]
    latest_run = summary.runs[-1] if summary.runs else None
    if latest_run is None:
        lines.append("Latest run: none")
    else:
        lines.extend(
            [
                f"Latest run: {latest_run.run_id}",
                f"Latest backend: {latest_run.backend_name or 'unknown'}",
                f"Latest prepare source: {latest_run.prepare_run or 'unknown'}",
                (
                    "Latest counts: "
                    f"ok={latest_run.ok_count} | "
                    f"error={latest_run.error_count} | "
                    f"empty={latest_run.empty_count} | "
                    f"edited={latest_run.edited_count}"
                ),
                f"Latest created: {latest_run.created_label or 'unknown'}",
                f"Latest normalized output: {latest_run.normalized_text_path}",
            ]
        )
    if summary.runs:
        lines.append("")
        lines.append("Runs:")
        for item in summary.runs:
            lines.append(
                f"- {item.run_id} | backend={item.backend_name or 'unknown'} | "
                f"model={item.model_name or 'unknown'} | "
                f"prepare={item.prepare_run or 'unknown'} | "
                f"ok={item.ok_count} error={item.error_count} empty={item.empty_count} "
                f"edited={item.edited_count} created={item.created_label or 'unknown'}"
            )
    if summary.warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in summary.warnings)
    return "\n".join(lines)


def latest_ocr_run_item(summary: OcrStageSummary) -> OcrRunListItem | None:
    if not summary.runs:
        return None
    return summary.runs[-1]


def find_ocr_run_item(
    summary: OcrStageSummary,
    run_id: str,
) -> OcrRunListItem | None:
    normalized = run_id.strip()
    if not normalized:
        return None
    for item in summary.runs:
        if item.run_id == normalized:
            return item
    return None


def _ordered_backend_options() -> tuple[str, ...]:
    preferred = (
        "fake",
        "openai-compatible-vision",
        "ollama",
        "local-command",
    )
    available = set(list_backends())
    ordered = [name for name in preferred if name in available]
    ordered.extend(sorted(name for name in available if name not in preferred))
    return tuple(ordered)


def _collect_prepare_run_options(project_root: Path) -> tuple[str, ...]:
    prepare_options: list[str] = []
    default_segments = project_root / "prepare" / "subtitle_segments.jsonl"
    if default_segments.exists():
        prepare_options.append("prepare_default")

    runs_dir = project_root / "prepare" / "runs"
    for run_dir in _list_run_dirs(runs_dir):
        if (run_dir / "subtitle_segments.jsonl").exists():
            prepare_options.append(run_dir.name)
    return tuple(prepare_options)


def _build_ocr_run_list_item(run_dir: Path) -> OcrRunListItem:
    config_path = run_dir / "ocr_config.json"
    raw_outputs_path = run_dir / "raw_outputs.jsonl"
    normalized_text_path = run_dir / "normalized_text.jsonl"
    errors_path = run_dir / "errors.jsonl"
    report_path = run_dir / "run_report.json"
    review_state_path = run_dir / "review_state.jsonl"

    backend_name, model_name, prepare_run = _read_ocr_run_metadata(
        config_path,
        normalized_text_path,
    )
    ok_count, error_count, empty_count = _read_ocr_run_counts(
        normalized_text_path,
        errors_path,
        report_path,
    )
    edited_count = _read_edited_count(review_state_path)
    return OcrRunListItem(
        run_id=run_dir.name,
        backend_name=backend_name,
        model_name=model_name,
        prepare_run=prepare_run,
        created_label=_format_run_created_label(run_dir.name),
        ok_count=ok_count,
        error_count=error_count,
        empty_count=empty_count,
        edited_count=edited_count,
        config_path=config_path,
        raw_outputs_path=raw_outputs_path,
        normalized_text_path=normalized_text_path,
        errors_path=errors_path,
        report_path=report_path,
    )


def _read_ocr_run_metadata(
    config_path: Path,
    normalized_text_path: Path,
) -> tuple[str | None, str | None, str | None]:
    backend_name: str | None = None
    model_name: str | None = None
    prepare_run: str | None = None
    if config_path.exists():
        payload = read_json_file(config_path)
        backend_value = payload.get("backend")
        if backend_value is not None:
            backend_name = str(backend_value)
        model_value = payload.get("model")
        if model_value is not None:
            model_name = str(model_value)
        prepare_value = payload.get("input_prepare_id")
        if prepare_value is not None:
            prepare_run = str(prepare_value)
    if normalized_text_path.exists() and backend_name is None:
        for row in read_jsonl(normalized_text_path):
            source = row.get("source")
            if isinstance(source, dict) and source.get("backend") is not None:
                backend_name = str(source["backend"])
            break
    return backend_name, model_name, prepare_run


def _read_ocr_run_counts(
    normalized_text_path: Path,
    errors_path: Path,
    report_path: Path,
) -> tuple[int, int, int]:
    if report_path.exists():
        payload = read_json_file(
            report_path,
            required_fields=("ok_count", "error_count", "empty_count"),
        )
        return (
            int(payload["ok_count"]),
            int(payload["error_count"]),
            int(payload["empty_count"]),
        )

    ok_count = 0
    empty_count = 0
    if normalized_text_path.exists():
        for row in read_jsonl(normalized_text_path):
            status = str(row.get("status", ""))
            text = str(row.get("text", ""))
            if status != "error":
                ok_count += 1
                if not text.strip():
                    empty_count += 1

    error_count = 0
    if errors_path.exists():
        error_count = sum(1 for _ in read_jsonl(errors_path))
    return ok_count, error_count, empty_count


def _list_run_dirs(runs_dir: Path) -> list[Path]:
    parent = runs_dir.expanduser().resolve()
    if not parent.exists():
        return []
    return sorted(path for path in parent.iterdir() if path.is_dir())


def _stringify_optional(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _read_edited_count(review_state_path: Path) -> int:
    if not review_state_path.exists():
        return 0
    edited_count = 0
    for payload in read_jsonl(
        review_state_path,
        required_fields=("segment_id", "review_status"),
    ):
        if str(payload.get("review_status", "")) == "edited":
            edited_count += 1
    return edited_count


def _format_run_created_label(run_id: str) -> str | None:
    parts = run_id.split("_", 3)
    if len(parts) < 3:
        return None
    timestamp_value = "_".join(parts[:3])
    try:
        parsed = datetime.strptime(timestamp_value, "%Y-%m-%d_%H%M%S_%f")
    except ValueError:
        return None
    return parsed.strftime("%Y-%m-%d %H:%M:%S")
