"""Package-tab widgets for the VOCra GUI."""

from __future__ import annotations

from typing import Any

import PySimpleGUI as sg

from vocra.app.models import (
    PackageConfigForm,
    PackagePreviewOutcome,
    PackageRunListItem,
    PackageStageSummary,
)
from vocra.app.package_service import render_package_stage_text

PACKAGE_PREPARE_RUN_KEY = "-PACKAGE-PREPARE-RUN-"
PACKAGE_OCR_RUN_KEY = "-PACKAGE-OCR-RUN-"
PACKAGE_FORMAT_KEY = "-PACKAGE-FORMAT-"
PACKAGE_REVIEW_POLICY_KEY = "-PACKAGE-REVIEW-POLICY-"
PACKAGE_EMPTY_TEXT_POLICY_KEY = "-PACKAGE-EMPTY-TEXT-POLICY-"
PACKAGE_MIN_DURATION_KEY = "-PACKAGE-MIN-DURATION-"
PACKAGE_OUTPUT_PATH_KEY = "-PACKAGE-OUTPUT-PATH-"
PACKAGE_RUN_TABLE_KEY = "-PACKAGE-RUN-TABLE-"
PACKAGE_SELECTED_RUN_ID_KEY = "-PACKAGE-SELECTED-RUN-ID-"
PACKAGE_SUMMARY_KEY = "-PACKAGE-SUMMARY-"
PACKAGE_PREVIEW_STATUS_KEY = "-PACKAGE-PREVIEW-STATUS-"
PACKAGE_PREVIEW_KEY = "-PACKAGE-PREVIEW-"

_PACKAGE_RUN_TABLE_HEADINGS = ("Run ID", "Subtitles", "Created", "Output")


def build_package_tab() -> list[list[Any]]:
    return [
        [
            sg.Frame(
                "Package Config",
                [
                    [
                        sg.Text("Prepare run", size=(14, 1)),
                        sg.Combo(
                            (),
                            default_value="",
                            readonly=True,
                            key=PACKAGE_PREPARE_RUN_KEY,
                            size=(22, 1),
                        ),
                        sg.Text("OCR run", size=(10, 1)),
                        sg.Combo(
                            (),
                            default_value="",
                            readonly=True,
                            key=PACKAGE_OCR_RUN_KEY,
                            size=(22, 1),
                        ),
                    ],
                    [
                        sg.Text("Format", size=(14, 1)),
                        sg.Combo(
                            ("srt",),
                            default_value="srt",
                            readonly=True,
                            key=PACKAGE_FORMAT_KEY,
                            size=(16, 1),
                        ),
                        sg.Text("Review state", size=(10, 1)),
                        sg.Combo(
                            (),
                            default_value="auto",
                            readonly=True,
                            key=PACKAGE_REVIEW_POLICY_KEY,
                            size=(16, 1),
                        ),
                    ],
                    [
                        sg.Text("Empty text", size=(14, 1)),
                        sg.Combo(
                            ("skip", "keep"),
                            default_value="skip",
                            readonly=True,
                            key=PACKAGE_EMPTY_TEXT_POLICY_KEY,
                            size=(16, 1),
                        ),
                    ],
                    [
                        sg.Text("Min duration ms", size=(14, 1)),
                        sg.Input("0", key=PACKAGE_MIN_DURATION_KEY, size=(14, 1)),
                        sg.Text("Output path", size=(10, 1)),
                        sg.Input("", key=PACKAGE_OUTPUT_PATH_KEY, expand_x=True),
                    ],
                    [
                        sg.Button("Preview SRT", key="-PREVIEW-PACKAGE-"),
                        sg.Button("Export SRT", key="-EXPORT-PACKAGE-"),
                        sg.Button("Open Output Folder", key="-OPEN-PACKAGE-OUTPUT-FOLDER-"),
                        sg.Button("Refresh Package Summary", key="-REFRESH-PACKAGE-"),
                    ],
                    [sg.Text("Package preview is idle.", key=PACKAGE_PREVIEW_STATUS_KEY, expand_x=True)],
                ],
                expand_x=True,
            )
        ],
        [
            sg.Frame(
                "Package Runs",
                [
                    [sg.Text("", key=PACKAGE_SELECTED_RUN_ID_KEY, visible=False)],
                    [
                        sg.Table(
                            values=[],
                            headings=_PACKAGE_RUN_TABLE_HEADINGS,
                            key=PACKAGE_RUN_TABLE_KEY,
                            auto_size_columns=False,
                            col_widths=[24, 10, 19, 38],
                            justification="left",
                            enable_events=True,
                            select_mode=sg.TABLE_SELECT_MODE_BROWSE,
                            num_rows=6,
                            expand_x=True,
                        )
                    ],
                    [
                        sg.Multiline(
                            "",
                            key=PACKAGE_SUMMARY_KEY,
                            expand_x=True,
                            disabled=True,
                            size=(88, 8),
                        )
                    ],
                    [
                        sg.Button("Open Package Runs Folder", key="-OPEN-PACKAGE-RUNS-FOLDER-"),
                        sg.Button("Open Selected Package Output", key="-OPEN-PACKAGE-OUTPUT-"),
                        sg.Button("Open Selected Package Report", key="-OPEN-PACKAGE-REPORT-"),
                    ],
                ],
                expand_x=True,
            )
        ],
        [
            sg.Frame(
                "SRT Preview",
                [
                    [
                        sg.Multiline(
                            "",
                            key=PACKAGE_PREVIEW_KEY,
                            expand_x=True,
                            disabled=True,
                            size=(88, 14),
                        )
                    ]
                ],
                expand_x=True,
            )
        ],
    ]


def set_empty_package_tab(window: sg.Window) -> None:
    update_package_config_form(window, _empty_package_config_form())
    window[PACKAGE_PREPARE_RUN_KEY].update(values=[], value="")
    window[PACKAGE_OCR_RUN_KEY].update(values=[], value="")
    window[PACKAGE_FORMAT_KEY].update(values=("srt",), value="srt")
    window[PACKAGE_REVIEW_POLICY_KEY].update(values=[], value="auto")
    window[PACKAGE_RUN_TABLE_KEY].update(values=[])
    window[PACKAGE_SELECTED_RUN_ID_KEY].update("")
    window[PACKAGE_SUMMARY_KEY].update(
        "Load a project to inspect package runs and preview/export SRT output from prepared artifacts."
    )
    window[PACKAGE_PREVIEW_KEY].update("")
    window[PACKAGE_PREVIEW_STATUS_KEY].update("Package preview is idle.")


def update_package_tab(window: sg.Window, summary: PackageStageSummary) -> None:
    window[PACKAGE_PREPARE_RUN_KEY].update(
        values=list(summary.prepare_run_options),
        value=summary.selected_prepare_run,
    )
    window[PACKAGE_OCR_RUN_KEY].update(
        values=list(summary.ocr_run_options),
        value=summary.selected_ocr_run,
    )
    window[PACKAGE_REVIEW_POLICY_KEY].update(
        values=list(summary.review_state_policy_options),
        value=summary.selected_review_state_policy,
    )
    window[PACKAGE_FORMAT_KEY].update(
        values=list(summary.format_options),
        value=summary.selected_format_name,
    )
    window[PACKAGE_RUN_TABLE_KEY].update(values=_build_package_run_table_rows(summary))
    window[PACKAGE_SUMMARY_KEY].update(render_package_stage_text(summary))


def update_package_config_form(window: sg.Window, form: PackageConfigForm) -> None:
    window[PACKAGE_PREPARE_RUN_KEY].update(value=form.prepare_run)
    window[PACKAGE_OCR_RUN_KEY].update(value=form.ocr_run)
    window[PACKAGE_FORMAT_KEY].update(value=form.format_name)
    window[PACKAGE_REVIEW_POLICY_KEY].update(value=form.review_state_policy)
    window[PACKAGE_EMPTY_TEXT_POLICY_KEY].update(value=form.empty_text_policy)
    window[PACKAGE_MIN_DURATION_KEY].update(form.min_subtitle_duration_ms)
    window[PACKAGE_OUTPUT_PATH_KEY].update(form.output_path)


def build_package_config_form(values: dict[str, Any]) -> PackageConfigForm:
    return PackageConfigForm(
        prepare_run=str(values.get(PACKAGE_PREPARE_RUN_KEY, "")),
        ocr_run=str(values.get(PACKAGE_OCR_RUN_KEY, "")),
        format_name=str(values.get(PACKAGE_FORMAT_KEY, "srt")),
        review_state_policy=str(values.get(PACKAGE_REVIEW_POLICY_KEY, "auto")),
        empty_text_policy=str(values.get(PACKAGE_EMPTY_TEXT_POLICY_KEY, "skip")),
        min_subtitle_duration_ms=str(values.get(PACKAGE_MIN_DURATION_KEY, "0")),
        output_path=str(values.get(PACKAGE_OUTPUT_PATH_KEY, "")),
    )


def set_package_preview_state(window: sg.Window, message: str) -> None:
    window[PACKAGE_PREVIEW_STATUS_KEY].update(message)


def set_package_preview(window: sg.Window, preview: PackagePreviewOutcome) -> None:
    window[PACKAGE_PREVIEW_KEY].update(preview.preview_text)
    review_source = (
        str(preview.review_source_path)
        if preview.review_source_path is not None
        else "none"
    )
    window[PACKAGE_PREVIEW_STATUS_KEY].update(
        "Preview ready: "
        f"{preview.subtitle_count} subtitles | "
        f"Prepare: {preview.prepare_source_path.name} | "
        f"OCR: {preview.ocr_source_path.name} | "
        f"Review: {review_source}"
    )


def set_selected_package_run(window: sg.Window, run_item: PackageRunListItem) -> None:
    window[PACKAGE_SELECTED_RUN_ID_KEY].update(run_item.run_id)
    window[PACKAGE_SUMMARY_KEY].update("\n".join(_build_selected_package_run_lines(run_item)))


def _empty_package_config_form() -> PackageConfigForm:
    return PackageConfigForm(
        prepare_run="",
        ocr_run="",
        format_name="srt",
        review_state_policy="auto",
        empty_text_policy="skip",
        min_subtitle_duration_ms="0",
        output_path="",
    )


def _build_package_run_table_rows(summary: PackageStageSummary) -> list[list[str]]:
    return [
        [
            item.run_id,
            str(item.subtitle_count) if item.subtitle_count is not None else "",
            item.created_label or "",
            str(item.output_path),
        ]
        for item in summary.runs
    ]


def _build_selected_package_run_lines(run_item: PackageRunListItem) -> list[str]:
    return [
        f"Selected package run: {run_item.run_id}",
        (
            "Subtitle count: "
            f"{run_item.subtitle_count if run_item.subtitle_count is not None else 'unknown'}"
        ),
        f"Created: {run_item.created_label or 'unknown'}",
        f"Output: {run_item.output_path}",
        f"Config: {run_item.config_path}",
        f"Report: {run_item.report_path}",
    ]
