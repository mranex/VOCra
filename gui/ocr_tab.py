"""OCR-tab widgets for the VOCra GUI."""

from __future__ import annotations

from typing import Any

import PySimpleGUI as sg

from vocra.app.models import (
    OcrBackendFormSpec,
    OcrConfigForm,
    OcrRunListItem,
    OcrStageSummary,
)
from vocra.app.ocr_service import get_ocr_backend_form_spec, render_ocr_stage_text

OCR_SUMMARY_KEY = "-OCR-SUMMARY-"
OCR_RUN_TABLE_KEY = "-OCR-RUN-TABLE-"
OCR_RUN_STATUS_KEY = "-OCR-RUN-STATUS-"
OCR_RUN_LOG_KEY = "-OCR-RUN-LOG-"
OCR_PREPARE_RUN_KEY = "-OCR-PREPARE-RUN-"
OCR_BACKEND_KEY = "-OCR-BACKEND-"
OCR_RUN_ID_KEY = "-OCR-RUN-ID-"
OCR_FORCE_KEY = "-OCR-FORCE-"
OCR_TEXT_TEMPLATE_KEY = "-OCR-TEXT-TEMPLATE-"
OCR_ENDPOINT_KEY = "-OCR-ENDPOINT-"
OCR_API_KEY = "-OCR-API-KEY-"
OCR_MODEL_KEY = "-OCR-MODEL-"
OCR_PROMPT_TEMPLATE_KEY = "-OCR-PROMPT-TEMPLATE-"
OCR_TEMPERATURE_KEY = "-OCR-TEMPERATURE-"
OCR_MAX_TOKENS_KEY = "-OCR-MAX-TOKENS-"
OCR_TIMEOUT_SEC_KEY = "-OCR-TIMEOUT-SEC-"
OCR_COMMAND_TEMPLATE_KEY = "-OCR-COMMAND-TEMPLATE-"
OCR_STDOUT_FORMAT_KEY = "-OCR-STDOUT-FORMAT-"
OCR_WORKING_DIR_KEY = "-OCR-WORKING-DIR-"
OCR_CONFIG_META_KEY = "-OCR-CONFIG-META-"
OCR_TEST_STATUS_KEY = "-OCR-TEST-STATUS-"
_OCR_RUN_TABLE_HEADINGS = (
    "Run ID",
    "Backend",
    "Model",
    "OK",
    "Empty",
    "Error",
    "Edited",
    "Created",
)

_STDOUT_FORMAT_OPTIONS = ("plain_text", "json")
_FIELD_KEY_BY_NAME = {
    "text_template": OCR_TEXT_TEMPLATE_KEY,
    "endpoint": OCR_ENDPOINT_KEY,
    "api_key": OCR_API_KEY,
    "model": OCR_MODEL_KEY,
    "prompt_template": OCR_PROMPT_TEMPLATE_KEY,
    "temperature": OCR_TEMPERATURE_KEY,
    "max_tokens": OCR_MAX_TOKENS_KEY,
    "timeout_sec": OCR_TIMEOUT_SEC_KEY,
    "command_template": OCR_COMMAND_TEMPLATE_KEY,
    "stdout_format": OCR_STDOUT_FORMAT_KEY,
    "working_dir": OCR_WORKING_DIR_KEY,
}


def build_ocr_tab() -> list[list[Any]]:
    return [
        [
            sg.Frame(
                "OCR Config",
                [
                    [
                        sg.Text("Prepare run", size=(14, 1)),
                        sg.Combo(
                            (),
                            default_value="",
                            readonly=True,
                            key=OCR_PREPARE_RUN_KEY,
                            size=(24, 1),
                        ),
                        sg.Text("Backend", size=(10, 1)),
                        sg.Combo(
                            (),
                            default_value="fake",
                            readonly=True,
                            key=OCR_BACKEND_KEY,
                            enable_events=True,
                            size=(28, 1),
                        ),
                    ],
                    [
                        sg.Text("Run id", size=(14, 1)),
                        sg.Combo(
                            (),
                            default_value="",
                            key=OCR_RUN_ID_KEY,
                            size=(24, 1),
                        ),
                        sg.Checkbox(
                            "Force rerun",
                            key=OCR_FORCE_KEY,
                            default=False,
                        ),
                    ],
                    [
                        sg.Text("Text template", size=(14, 1)),
                        sg.Input("", key=OCR_TEXT_TEMPLATE_KEY, expand_x=True),
                    ],
                    [
                        sg.Text("Endpoint", size=(14, 1)),
                        sg.Input("", key=OCR_ENDPOINT_KEY, expand_x=True),
                    ],
                    [
                        sg.Text("API key", size=(14, 1)),
                        sg.Input("", key=OCR_API_KEY, password_char="*", expand_x=True),
                    ],
                    [
                        sg.Text("Model", size=(14, 1)),
                        sg.Input("", key=OCR_MODEL_KEY, expand_x=True),
                    ],
                    [
                        sg.Text("Prompt", size=(14, 1)),
                        sg.Input("", key=OCR_PROMPT_TEMPLATE_KEY, expand_x=True),
                    ],
                    [
                        sg.Text("Temperature", size=(14, 1)),
                        sg.Input("", key=OCR_TEMPERATURE_KEY, size=(12, 1)),
                        sg.Text("Max tokens", size=(10, 1)),
                        sg.Input("", key=OCR_MAX_TOKENS_KEY, size=(12, 1)),
                        sg.Text("Timeout sec", size=(10, 1)),
                        sg.Input("", key=OCR_TIMEOUT_SEC_KEY, size=(12, 1)),
                    ],
                    [
                        sg.Text("Command", size=(14, 1)),
                        sg.Input("", key=OCR_COMMAND_TEMPLATE_KEY, expand_x=True),
                    ],
                    [
                        sg.Text("Stdout format", size=(14, 1)),
                        sg.Combo(
                            _STDOUT_FORMAT_OPTIONS,
                            default_value="plain_text",
                            readonly=True,
                            key=OCR_STDOUT_FORMAT_KEY,
                            size=(16, 1),
                        ),
                        sg.Text("Working dir", size=(10, 1)),
                        sg.Input("", key=OCR_WORKING_DIR_KEY, expand_x=True),
                    ],
                    [sg.Text("", key=OCR_CONFIG_META_KEY, expand_x=True)],
                    [
                        sg.Button("Test Backend", key="-TEST-OCR-BACKEND-"),
                        sg.Button("Run OCR", key="-RUN-OCR-"),
                        sg.Button("Resume Failed Only", key="-RESUME-OCR-FAILED-"),
                        sg.Button("Rerun Empty Only", key="-RERUN-OCR-EMPTY-"),
                        sg.Button("Load Selected Run Config", key="-LOAD-OCR-RUN-CONFIG-"),
                        sg.Button("Refresh OCR Summary", key="-REFRESH-OCR-"),
                    ],
                    [sg.Text("Backend test is idle.", key=OCR_TEST_STATUS_KEY, expand_x=True)],
                    [sg.Text("OCR run is idle.", key=OCR_RUN_STATUS_KEY, expand_x=True)],
                    [
                        sg.Multiline(
                            "",
                            key=OCR_RUN_LOG_KEY,
                            expand_x=True,
                            disabled=True,
                            size=(88, 5),
                            autoscroll=True,
                        )
                    ],
                ],
                expand_x=True,
            )
        ],
        [
            sg.Frame(
                "OCR Runs",
                [
                    [
                        sg.Table(
                            values=[],
                            headings=_OCR_RUN_TABLE_HEADINGS,
                            key=OCR_RUN_TABLE_KEY,
                            auto_size_columns=False,
                            col_widths=[24, 18, 18, 6, 6, 6, 6, 19],
                            justification="left",
                            enable_events=True,
                            select_mode=sg.TABLE_SELECT_MODE_BROWSE,
                            num_rows=8,
                            expand_x=True,
                        )
                    ],
                    [
                        sg.Multiline(
                            "",
                            key=OCR_SUMMARY_KEY,
                            expand_x=True,
                            disabled=True,
                            size=(88, 8),
                        )
                    ]
                ],
                expand_x=True,
            )
        ],
        [
            sg.Button("Open OCR Runs Folder", key="-OPEN-OCR-RUNS-FOLDER-"),
            sg.Button("Open Selected OCR Config", key="-OPEN-LATEST-OCR-CONFIG-"),
            sg.Button("Open Selected Raw Output", key="-OPEN-LATEST-OCR-RAW-OUTPUT-"),
            sg.Button("Open Selected Normalized Output", key="-OPEN-LATEST-OCR-NORMALIZED-OUTPUT-"),
            sg.Button("Open Selected OCR Report", key="-OPEN-LATEST-OCR-REPORT-"),
        ],
        [
            sg.Text(
                "This first OCR GUI slice is service-backed and artifact-driven. Fake backend is the easiest first end-to-end path.",
            )
        ],
    ]


def set_empty_ocr_tab(window: sg.Window) -> None:
    update_ocr_config_form(window, _empty_ocr_config_form())
    apply_ocr_backend_form_spec(window, get_ocr_backend_form_spec("fake"))
    set_ocr_run_state(window, "OCR run is idle.")
    reset_ocr_run_log(window)
    window[OCR_RUN_TABLE_KEY].update(values=[])
    window[OCR_SUMMARY_KEY].update(
        "Load a project to inspect prepared runs, OCR runs, and OCR backend configuration."
    )


def update_ocr_tab(window: sg.Window, summary: OcrStageSummary) -> None:
    window[OCR_RUN_TABLE_KEY].update(values=_build_ocr_run_table_rows(summary))
    window[OCR_SUMMARY_KEY].update(render_ocr_stage_text(summary))


def update_ocr_config_form(window: sg.Window, form: OcrConfigForm) -> None:
    window[OCR_PREPARE_RUN_KEY].update(value=form.prepare_run)
    window[OCR_BACKEND_KEY].update(value=form.backend_name)
    window[OCR_RUN_ID_KEY].update(form.run_id)
    window[OCR_FORCE_KEY].update(value=form.force)
    window[OCR_TEXT_TEMPLATE_KEY].update(form.text_template)
    window[OCR_ENDPOINT_KEY].update(form.endpoint)
    window[OCR_API_KEY].update(form.api_key)
    window[OCR_MODEL_KEY].update(form.model)
    window[OCR_PROMPT_TEMPLATE_KEY].update(form.prompt_template)
    window[OCR_TEMPERATURE_KEY].update(form.temperature)
    window[OCR_MAX_TOKENS_KEY].update(form.max_tokens)
    window[OCR_TIMEOUT_SEC_KEY].update(form.timeout_sec)
    window[OCR_COMMAND_TEMPLATE_KEY].update(form.command_template)
    window[OCR_STDOUT_FORMAT_KEY].update(form.stdout_format)
    window[OCR_WORKING_DIR_KEY].update(form.working_dir)
    apply_ocr_backend_form_spec(window, get_ocr_backend_form_spec(form.backend_name))


def update_ocr_config_options(window: sg.Window, summary: OcrStageSummary) -> None:
    current_prepare = str(window[OCR_PREPARE_RUN_KEY].get() or "")
    if current_prepare not in summary.prepare_run_options:
        current_prepare = summary.prepare_run_options[0] if summary.prepare_run_options else ""
    window[OCR_PREPARE_RUN_KEY].update(
        values=list(summary.prepare_run_options),
        value=current_prepare,
    )

    current_backend = str(window[OCR_BACKEND_KEY].get() or "")
    if current_backend not in summary.backend_options:
        current_backend = summary.backend_options[0] if summary.backend_options else ""
    window[OCR_BACKEND_KEY].update(
        values=list(summary.backend_options),
        value=current_backend,
    )

    current_run_id = str(window[OCR_RUN_ID_KEY].get() or "")
    valid_run_ids = [item.run_id for item in summary.runs]
    if current_run_id not in valid_run_ids:
        current_run_id = ""
    window[OCR_RUN_ID_KEY].update(values=valid_run_ids, value=current_run_id)

    window[OCR_CONFIG_META_KEY].update(
        f"Prepare runs: {len(summary.prepare_run_options)} | Backends: {len(summary.backend_options)} | OCR runs: {summary.run_count}"
    )


def apply_ocr_backend_form_spec(window: sg.Window, spec: OcrBackendFormSpec) -> None:
    enabled_fields = set(spec.enabled_fields)
    for field_name, key in _FIELD_KEY_BY_NAME.items():
        window[key].update(disabled=field_name not in enabled_fields)
    required_fields = ", ".join(spec.required_fields) if spec.required_fields else "none"
    window[OCR_CONFIG_META_KEY].update(
        f"{spec.help_text} | Required fields: {required_fields}"
    )
    window[OCR_TEST_STATUS_KEY].update(f"Backend selected: {spec.backend_name}")


def set_ocr_run_state(
    window: sg.Window,
    message: str,
    *,
    running: bool = False,
) -> None:
    window[OCR_RUN_STATUS_KEY].update(message)
    window["-RUN-OCR-"].update(disabled=running)
    window["-RESUME-OCR-FAILED-"].update(disabled=running)
    window["-RERUN-OCR-EMPTY-"].update(disabled=running)
    window["-LOAD-OCR-RUN-CONFIG-"].update(disabled=running)
    window["-TEST-OCR-BACKEND-"].update(disabled=running)


def reset_ocr_run_log(window: sg.Window) -> None:
    window[OCR_RUN_LOG_KEY].update("")


def append_ocr_run_log(window: sg.Window, line: str) -> None:
    current = window[OCR_RUN_LOG_KEY].get() or ""
    next_value = f"{current}\n{line}".strip() if current else line
    window[OCR_RUN_LOG_KEY].update(next_value)


def build_ocr_config_form(values: dict[str, Any]) -> OcrConfigForm:
    return OcrConfigForm(
        prepare_run=str(values.get(OCR_PREPARE_RUN_KEY, "")),
        backend_name=str(values.get(OCR_BACKEND_KEY, "")),
        run_id=str(values.get(OCR_RUN_ID_KEY, "")),
        force=bool(values.get(OCR_FORCE_KEY, False)),
        text_template=str(values.get(OCR_TEXT_TEMPLATE_KEY, "")),
        endpoint=str(values.get(OCR_ENDPOINT_KEY, "")),
        api_key=str(values.get(OCR_API_KEY, "")),
        model=str(values.get(OCR_MODEL_KEY, "")),
        prompt_template=str(values.get(OCR_PROMPT_TEMPLATE_KEY, "")),
        temperature=str(values.get(OCR_TEMPERATURE_KEY, "")),
        max_tokens=str(values.get(OCR_MAX_TOKENS_KEY, "")),
        timeout_sec=str(values.get(OCR_TIMEOUT_SEC_KEY, "")),
        command_template=str(values.get(OCR_COMMAND_TEMPLATE_KEY, "")),
        stdout_format=str(values.get(OCR_STDOUT_FORMAT_KEY, "")),
        working_dir=str(values.get(OCR_WORKING_DIR_KEY, "")),
    )


def _empty_ocr_config_form() -> OcrConfigForm:
    return OcrConfigForm(
        prepare_run="",
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
    )


def set_selected_ocr_run(
    window: sg.Window,
    run_item: OcrRunListItem,
) -> None:
    window[OCR_RUN_ID_KEY].update(value=run_item.run_id)
    window[OCR_SUMMARY_KEY].update("\n".join(_build_selected_ocr_run_lines(run_item)))


def _build_ocr_run_table_rows(summary: OcrStageSummary) -> list[list[str]]:
    return [
        [
            item.run_id,
            item.backend_name or "",
            item.model_name or "",
            str(item.ok_count),
            str(item.empty_count),
            str(item.error_count),
            str(item.edited_count),
            item.created_label or "",
        ]
        for item in summary.runs
    ]


def _build_selected_ocr_run_lines(run_item: OcrRunListItem) -> list[str]:
    return [
        f"Selected run: {run_item.run_id}",
        f"Backend: {run_item.backend_name or 'unknown'}",
        f"Model: {run_item.model_name or 'unknown'}",
        f"Prepare run: {run_item.prepare_run or 'unknown'}",
        f"Counts: ok={run_item.ok_count} empty={run_item.empty_count} error={run_item.error_count}",
        f"Edited: {run_item.edited_count}",
        f"Created: {run_item.created_label or 'unknown'}",
        f"Config: {run_item.config_path}",
        f"Normalized output: {run_item.normalized_text_path}",
    ]
