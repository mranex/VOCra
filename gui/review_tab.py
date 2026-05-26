"""Review-tab widgets for the VOCra GUI."""

from __future__ import annotations

from typing import Any

import PySimpleGUI as sg

from vocra.app.models import (
    OcrComparisonItem,
    OcrComparisonSummary,
    ReviewEditForm,
    ReviewListItem,
    ReviewSelectionDetail,
    ReviewStageSummary,
)
from vocra.app.ocr_compare_service import render_ocr_comparison_text
from vocra.app.review_service import render_review_stage_text

REVIEW_PREPARE_RUN_KEY = "-REVIEW-PREPARE-RUN-"
REVIEW_OCR_RUN_KEY = "-REVIEW-OCR-RUN-"
REVIEW_FILTER_KEY = "-REVIEW-FILTER-"
REVIEW_TABLE_KEY = "-REVIEW-TABLE-"
REVIEW_SUMMARY_KEY = "-REVIEW-SUMMARY-"
REVIEW_SELECTED_SEGMENT_ID_KEY = "-REVIEW-SELECTED-SEGMENT-ID-"
REVIEW_SELECTED_SEGMENT_KEY = "-REVIEW-SELECTED-SEGMENT-"
REVIEW_SELECTED_META_KEY = "-REVIEW-SELECTED-META-"
REVIEW_SELECTED_IMAGE_KEY = "-REVIEW-SELECTED-IMAGE-"
REVIEW_IMAGE_PREVIEW_KEY = "-REVIEW-IMAGE-PREVIEW-"
REVIEW_SELECTED_FLAGS_KEY = "-REVIEW-SELECTED-FLAGS-"
REVIEW_SELECTED_OCR_STATUS_KEY = "-REVIEW-SELECTED-OCR-STATUS-"
REVIEW_ORIGINAL_TEXT_KEY = "-REVIEW-ORIGINAL-TEXT-"
REVIEW_RAW_OUTPUT_KEY = "-REVIEW-RAW-OUTPUT-"
REVIEW_EDITED_TEXT_KEY = "-REVIEW-EDITED-TEXT-"
REVIEW_NOTES_KEY = "-REVIEW-NOTES-"
REVIEW_STATUS_KEY = "-REVIEW-STATUS-"
REVIEW_SAVE_STATUS_KEY = "-REVIEW-SAVE-STATUS-"
REVIEW_PREVIOUS_KEY = "-REVIEW-PREVIOUS-"
REVIEW_NEXT_KEY = "-REVIEW-NEXT-"
REVIEW_NEXT_SUSPICIOUS_KEY = "-REVIEW-NEXT-SUSPICIOUS-"
REVIEW_BATCH_ACCEPT_KEY = "-REVIEW-BATCH-ACCEPT-"
REVIEW_BATCH_REJECT_KEY = "-REVIEW-BATCH-REJECT-"
REVIEW_BATCH_PENDING_KEY = "-REVIEW-BATCH-PENDING-"
REVIEW_COMPARE_SOURCE_RUNS_KEY = "-REVIEW-COMPARE-SOURCE-RUNS-"
REVIEW_COMPARE_TARGET_RUN_KEY = "-REVIEW-COMPARE-TARGET-RUN-"
REVIEW_COMPARE_TABLE_KEY = "-REVIEW-COMPARE-TABLE-"
REVIEW_COMPARE_SUMMARY_KEY = "-REVIEW-COMPARE-SUMMARY-"
REVIEW_COMPARE_STATUS_KEY = "-REVIEW-COMPARE-STATUS-"
REVIEW_COMPARE_USE_WINNER_KEY = "-REVIEW-COMPARE-USE-WINNER-"
REVIEW_COMPARE_REFRESH_KEY = "-REFRESH-REVIEW-COMPARE-"

_REVIEW_TABLE_HEADINGS = ("Segment", "Time", "Status", "Flags", "Text")
_REVIEW_STATUS_OPTIONS = ("pending", "accepted", "edited", "rejected")
_REVIEW_COMPARE_TABLE_HEADINGS = ("Run ID", "Backend", "Model", "Status", "Text")


def build_review_tab() -> list[list[Any]]:
    return [
        [
            sg.Frame(
                "Review Controls",
                [
                    [
                        sg.Text("Prepare run", size=(12, 1)),
                        sg.Combo(
                            (),
                            default_value="",
                            readonly=True,
                            enable_events=True,
                            key=REVIEW_PREPARE_RUN_KEY,
                            size=(22, 1),
                        ),
                        sg.Text("OCR run", size=(8, 1)),
                        sg.Combo(
                            (),
                            default_value="",
                            readonly=True,
                            enable_events=True,
                            key=REVIEW_OCR_RUN_KEY,
                            size=(22, 1),
                        ),
                        sg.Text("Filter", size=(6, 1)),
                        sg.Combo(
                            (),
                            default_value="all",
                            readonly=True,
                            enable_events=True,
                            key=REVIEW_FILTER_KEY,
                            size=(16, 1),
                        ),
                        sg.Button("Refresh Review", key="-REFRESH-REVIEW-"),
                    ],
                    [sg.Text("Review save is idle.", key=REVIEW_SAVE_STATUS_KEY, expand_x=True)],
                ],
                expand_x=True,
            )
        ],
        [
            sg.Frame(
                "Review Items",
                [
                    [
                        sg.Table(
                            values=[],
                            headings=_REVIEW_TABLE_HEADINGS,
                            key=REVIEW_TABLE_KEY,
                            auto_size_columns=False,
                            col_widths=[14, 28, 10, 20, 36],
                            justification="left",
                            enable_events=True,
                            select_mode=sg.TABLE_SELECT_MODE_BROWSE,
                            num_rows=10,
                            expand_x=True,
                        )
                    ]
                ],
                expand_x=True,
            )
        ],
        [
            sg.Frame(
                "Selected Item",
                [
                    [sg.Text("", key=REVIEW_SELECTED_SEGMENT_ID_KEY, visible=False)],
                    [sg.Text("Segment: none selected", key=REVIEW_SELECTED_SEGMENT_KEY, expand_x=True)],
                    [sg.Text("", key=REVIEW_SELECTED_META_KEY, expand_x=True)],
                    [sg.Image(data=b"", key=REVIEW_IMAGE_PREVIEW_KEY, size=(720, 220), expand_x=True)],
                    [sg.Text("", key=REVIEW_SELECTED_IMAGE_KEY, expand_x=True)],
                    [sg.Text("", key=REVIEW_SELECTED_FLAGS_KEY, expand_x=True)],
                    [sg.Text("", key=REVIEW_SELECTED_OCR_STATUS_KEY, expand_x=True)],
                    [sg.Text("Original OCR text")],
                    [
                        sg.Multiline(
                            "",
                            key=REVIEW_ORIGINAL_TEXT_KEY,
                            disabled=True,
                            expand_x=True,
                            size=(88, 4),
                        )
                    ],
                    [sg.Text("Raw OCR output")],
                    [
                        sg.Multiline(
                            "",
                            key=REVIEW_RAW_OUTPUT_KEY,
                            disabled=True,
                            expand_x=True,
                            size=(88, 7),
                        )
                    ],
                    [sg.Text("Edited text")],
                    [
                        sg.Multiline(
                            "",
                            key=REVIEW_EDITED_TEXT_KEY,
                            expand_x=True,
                            size=(88, 4),
                        )
                    ],
                    [sg.Text("Notes")],
                    [
                        sg.Multiline(
                            "",
                            key=REVIEW_NOTES_KEY,
                            expand_x=True,
                            size=(88, 3),
                        )
                    ],
                    [
                        sg.Text("Status", size=(10, 1)),
                        sg.Combo(
                            _REVIEW_STATUS_OPTIONS,
                            default_value="pending",
                            readonly=True,
                            key=REVIEW_STATUS_KEY,
                            size=(16, 1),
                        ),
                        sg.Button("Save Review", key="-SAVE-REVIEW-"),
                        sg.Button("Accept", key="-REVIEW-SET-ACCEPTED-"),
                        sg.Button("Reject", key="-REVIEW-SET-REJECTED-"),
                        sg.Button("Mark Pending", key="-REVIEW-SET-PENDING-"),
                        sg.Button("Previous", key=REVIEW_PREVIOUS_KEY),
                        sg.Button("Next", key=REVIEW_NEXT_KEY),
                        sg.Button("Next Suspicious", key=REVIEW_NEXT_SUSPICIOUS_KEY),
                    ],
                    [
                        sg.Button("Accept Filtered", key=REVIEW_BATCH_ACCEPT_KEY),
                        sg.Button("Reject Filtered", key=REVIEW_BATCH_REJECT_KEY),
                        sg.Button("Pending Filtered", key=REVIEW_BATCH_PENDING_KEY),
                        sg.Button("Open Segment Image", key="-OPEN-REVIEW-IMAGE-"),
                    ],
                    [sg.Text("Shortcuts: Enter accept | E edit | R reject | N next | P previous | Ctrl+S save")],
                ],
                expand_x=True,
            )
        ],
        [
            sg.Frame(
                "OCR Compare",
                [
                    [
                        sg.Text("Target review run", size=(14, 1)),
                        sg.Text("", key=REVIEW_COMPARE_TARGET_RUN_KEY, expand_x=True),
                    ],
                    [
                        sg.Text("Source OCR runs", size=(14, 1)),
                        sg.Listbox(
                            values=[],
                            default_values=[],
                            select_mode=sg.LISTBOX_SELECT_MODE_MULTIPLE,
                            size=(28, 5),
                            expand_x=False,
                            enable_events=True,
                            key=REVIEW_COMPARE_SOURCE_RUNS_KEY,
                        ),
                        sg.Column(
                            [
                                [sg.Button("Refresh Compare", key=REVIEW_COMPARE_REFRESH_KEY)],
                                [sg.Button("Use Selected Candidate", key=REVIEW_COMPARE_USE_WINNER_KEY)],
                                [sg.Text("Compare winner is idle.", key=REVIEW_COMPARE_STATUS_KEY, expand_x=True)],
                            ],
                            expand_x=True,
                            vertical_alignment="top",
                        ),
                    ],
                    [
                        sg.Table(
                            values=[],
                            headings=_REVIEW_COMPARE_TABLE_HEADINGS,
                            key=REVIEW_COMPARE_TABLE_KEY,
                            auto_size_columns=False,
                            col_widths=[16, 18, 18, 10, 36],
                            justification="left",
                            enable_events=True,
                            select_mode=sg.TABLE_SELECT_MODE_BROWSE,
                            num_rows=5,
                            expand_x=True,
                        )
                    ],
                    [
                        sg.Multiline(
                            "",
                            key=REVIEW_COMPARE_SUMMARY_KEY,
                            disabled=True,
                            expand_x=True,
                            size=(88, 6),
                        )
                    ],
                ],
                expand_x=True,
            )
        ],
        [
            sg.Frame(
                "Review Summary",
                [
                    [
                        sg.Multiline(
                            "",
                            key=REVIEW_SUMMARY_KEY,
                            disabled=True,
                            expand_x=True,
                            size=(88, 8),
                        )
                    ]
                ],
                expand_x=True,
            )
        ],
    ]


def set_empty_review_tab(window: sg.Window) -> None:
    window[REVIEW_PREPARE_RUN_KEY].update(values=[], value="")
    window[REVIEW_OCR_RUN_KEY].update(values=[], value="")
    window[REVIEW_FILTER_KEY].update(values=[], value="all")
    window[REVIEW_TABLE_KEY].update(values=[])
    clear_selected_review_item(window)
    clear_review_compare(window)
    window[REVIEW_SUMMARY_KEY].update(
        "Load a project to inspect OCR review items and saved review-state artifacts."
    )
    window[REVIEW_SAVE_STATUS_KEY].update("Review save is idle.")


def update_review_tab(window: sg.Window, summary: ReviewStageSummary) -> None:
    window[REVIEW_PREPARE_RUN_KEY].update(
        values=list(summary.prepare_run_options),
        value=summary.selected_prepare_run,
    )
    window[REVIEW_OCR_RUN_KEY].update(
        values=list(summary.ocr_run_options),
        value=summary.selected_ocr_run,
    )
    window[REVIEW_FILTER_KEY].update(
        values=list(summary.filter_options),
        value=summary.selected_filter,
    )
    window[REVIEW_TABLE_KEY].update(values=_build_review_table_rows(summary))
    window[REVIEW_SUMMARY_KEY].update(render_review_stage_text(summary))


def set_selected_review_item(window: sg.Window, item: ReviewListItem) -> None:
    window[REVIEW_SELECTED_SEGMENT_ID_KEY].update(item.segment_id)
    window[REVIEW_SELECTED_SEGMENT_KEY].update(f"Segment: {item.segment_id}")
    window[REVIEW_SELECTED_META_KEY].update(
        f"{item.time_label} | Zone {item.zone_idx} | Status: {item.review_status}"
    )
    window[REVIEW_SELECTED_IMAGE_KEY].update(
        f"Representative image: {item.representative_image_path}"
    )
    window[REVIEW_SELECTED_FLAGS_KEY].update(
        "Quality flags: "
        f"{', '.join(item.quality_flags) if item.quality_flags else 'none'}"
    )
    ocr_status = f"OCR status: {item.ocr_status}"
    if item.ocr_error:
        ocr_status = f"{ocr_status} | Error: {item.ocr_error}"
    window[REVIEW_SELECTED_OCR_STATUS_KEY].update(ocr_status)
    window[REVIEW_ORIGINAL_TEXT_KEY].update(item.original_text)
    window[REVIEW_EDITED_TEXT_KEY].update(item.edited_text)
    window[REVIEW_NOTES_KEY].update(item.notes)
    window[REVIEW_STATUS_KEY].update(value=item.review_status)


def set_selected_review_detail(window: sg.Window, detail: ReviewSelectionDetail) -> None:
    window[REVIEW_IMAGE_PREVIEW_KEY].update(data=detail.image_png_bytes or b"")
    window[REVIEW_RAW_OUTPUT_KEY].update(detail.raw_output_text)


def build_review_edit_form(values: dict[str, Any]) -> ReviewEditForm:
    return ReviewEditForm(
        prepare_run=str(values.get(REVIEW_PREPARE_RUN_KEY, "")),
        ocr_run=str(values.get(REVIEW_OCR_RUN_KEY, "")),
        filter_name=str(values.get(REVIEW_FILTER_KEY, "all")),
        segment_id=str(values.get(REVIEW_SELECTED_SEGMENT_ID_KEY, "")),
        review_status=str(values.get(REVIEW_STATUS_KEY, "pending")),
        edited_text=str(values.get(REVIEW_EDITED_TEXT_KEY, "")),
        notes=str(values.get(REVIEW_NOTES_KEY, "")),
    )


def set_review_save_state(window: sg.Window, message: str) -> None:
    window[REVIEW_SAVE_STATUS_KEY].update(message)


def update_review_compare_controls(
    window: sg.Window,
    summary: OcrComparisonSummary,
) -> None:
    values = list(summary.available_ocr_run_options)
    selected_indices = [
        index
        for index, run_id in enumerate(values)
        if run_id in summary.selected_source_ocr_runs
    ]
    window[REVIEW_COMPARE_TARGET_RUN_KEY].update(summary.selected_target_ocr_run or "none")
    window[REVIEW_COMPARE_SOURCE_RUNS_KEY].update(
        values=values,
        set_to_index=selected_indices,
    )
    window[REVIEW_COMPARE_SUMMARY_KEY].update(render_ocr_comparison_text(summary))


def set_selected_review_compare_item(
    window: sg.Window,
    item: OcrComparisonItem,
) -> None:
    window[REVIEW_COMPARE_TABLE_KEY].update(values=_build_review_compare_candidate_rows(item))
    current_text = _single_line_text(item.target_effective_text)
    if not current_text:
        current_text = "(empty)"
    window[REVIEW_COMPARE_STATUS_KEY].update(
        "Current chosen text: "
        f"{current_text} | review status: {item.target_review_status}"
    )


def clear_review_compare(window: sg.Window) -> None:
    window[REVIEW_COMPARE_TARGET_RUN_KEY].update("none")
    window[REVIEW_COMPARE_SOURCE_RUNS_KEY].update(values=[], set_to_index=[])
    window[REVIEW_COMPARE_TABLE_KEY].update(values=[])
    window[REVIEW_COMPARE_SUMMARY_KEY].update(
        "Load a project and choose OCR runs to compare candidate text per segment."
    )
    window[REVIEW_COMPARE_STATUS_KEY].update("Compare winner is idle.")


def get_review_compare_source_runs(values: dict[str, Any]) -> tuple[str, ...]:
    selected = values.get(REVIEW_COMPARE_SOURCE_RUNS_KEY, [])
    if not isinstance(selected, (list, tuple)):
        return ()
    return tuple(str(item) for item in selected if str(item).strip())


def clear_selected_review_item(window: sg.Window) -> None:
    window[REVIEW_SELECTED_SEGMENT_ID_KEY].update("")
    window[REVIEW_SELECTED_SEGMENT_KEY].update("Segment: none selected")
    window[REVIEW_SELECTED_META_KEY].update("")
    window[REVIEW_IMAGE_PREVIEW_KEY].update(data=b"")
    window[REVIEW_SELECTED_IMAGE_KEY].update("")
    window[REVIEW_SELECTED_FLAGS_KEY].update("")
    window[REVIEW_SELECTED_OCR_STATUS_KEY].update("")
    window[REVIEW_ORIGINAL_TEXT_KEY].update("")
    window[REVIEW_RAW_OUTPUT_KEY].update("")
    window[REVIEW_EDITED_TEXT_KEY].update("")
    window[REVIEW_NOTES_KEY].update("")
    window[REVIEW_STATUS_KEY].update(value="pending")


def select_review_table_row(window: sg.Window, index: int) -> None:
    window[REVIEW_TABLE_KEY].update(select_rows=[index])


def _build_review_table_rows(summary: ReviewStageSummary) -> list[list[str]]:
    return [
        [
            item.segment_id,
            item.time_label,
            item.review_status,
            ",".join(item.quality_flags),
            _single_line_text(item.effective_text or item.original_text),
        ]
        for item in summary.items
    ]


def _build_review_compare_candidate_rows(item: OcrComparisonItem) -> list[list[str]]:
    return [
        [
            candidate.run_id,
            candidate.backend_name or "",
            candidate.model_name or "",
            candidate.status,
            _single_line_text(candidate.text if candidate.text.strip() else "(empty)"),
        ]
        for candidate in item.candidates
    ]


def _single_line_text(text: str) -> str:
    return " ".join(text.split())
