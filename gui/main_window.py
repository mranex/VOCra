"""Minimal GUI shell for VOCra Phase 13."""

from __future__ import annotations

import os
import subprocess
import threading
from dataclasses import replace
from pathlib import Path

import PySimpleGUI as sg

from vocra.app.models import (
    OcrComparisonSummary,
    OcrStageSummary,
    PackageStageSummary,
    PreparePreviewFrame,
    ReviewEditForm,
    ReviewListItem,
    ReviewStageSummary,
)
from vocra.app.ocr_compare_service import (
    apply_ocr_comparison_choice,
    find_ocr_comparison_item,
    load_ocr_comparison_summary,
)
from vocra.app.ocr_run_service import (
    rerun_empty_ocr_from_project,
    resume_failed_ocr_from_project,
    run_ocr_from_project,
    test_ocr_backend_connection,
)
from vocra.app.ocr_service import (
    apply_ocr_backend_defaults,
    find_ocr_run_item,
    latest_ocr_run_item,
    load_ocr_config_form_for_run,
    load_ocr_stage_summary,
)
from vocra.app.package_service import (
    export_package_from_form,
    find_package_run_item,
    latest_package_run_item,
    load_package_config_form,
    load_package_stage_summary,
    preview_package_from_form,
    resolve_package_output_folder,
)
from vocra.app.prepare_run_service import run_prepare_from_project
from vocra.app.prepare_service import (
    format_crop_zone_spec,
    load_prepare_crop_zones_form,
    load_prepare_preview_with_crop_overlay,
    preview_selection_for_zone_spec,
    preview_selection_to_crop_zone,
    save_prepare_crop_zones_form,
)
from vocra.app.review_service import (
    find_next_suspicious_review_item,
    find_review_item,
    load_review_selection_detail,
    load_review_stage_summary,
    move_review_selection,
    save_review_batch_from_filter,
    save_review_edit_from_form,
)
from vocra.app.service import (
    create_project_state,
    load_prepare_config_form,
    load_prepare_stage_summary,
    load_project_dashboard,
    load_recent_project_summaries,
    open_project_state,
    save_prepare_config_form,
)
from vocra.core.prepare.errors import PrepareCancelledError
from vocra.core.project.workspace import ProjectWorkspaceError
from vocra.gui.ocr_tab import (
    OCR_BACKEND_KEY,
    OCR_PREPARE_RUN_KEY,
    OCR_RUN_ID_KEY,
    OCR_RUN_TABLE_KEY,
    append_ocr_run_log,
    build_ocr_config_form,
    build_ocr_tab,
    reset_ocr_run_log,
    set_empty_ocr_tab,
    set_ocr_run_state,
    set_selected_ocr_run,
    update_ocr_config_form,
    update_ocr_config_options,
    update_ocr_tab,
)
from vocra.gui.package_tab import (
    PACKAGE_FORMAT_KEY,
    PACKAGE_OCR_RUN_KEY,
    PACKAGE_PREPARE_RUN_KEY,
    PACKAGE_REVIEW_POLICY_KEY,
    PACKAGE_RUN_TABLE_KEY,
    PACKAGE_SELECTED_RUN_ID_KEY,
    build_package_config_form,
    build_package_tab,
    set_empty_package_tab,
    set_package_preview,
    set_package_preview_state,
    set_selected_package_run,
    update_package_config_form,
    update_package_tab,
)
from vocra.gui.prepare_tab import (
    PREPARE_CROP_ZONE0_KEY,
    PREPARE_CROP_ZONE1_KEY,
    append_prepare_run_log,
    build_prepare_config_form,
    build_prepare_crop_zones_form,
    build_prepare_tab,
    reset_prepare_run_log,
    set_empty_prepare_tab,
    set_prepare_preview_context,
    set_prepare_run_state,
    set_prepare_selection_state,
    update_prepare_config_form,
    update_prepare_crop_zones_form,
    update_prepare_preview,
    update_prepare_preview_selection,
    update_prepare_tab,
)
from vocra.gui.project_tab import (
    CREATE_PROJECT_BUTTON_KEY,
    CREATE_PROJECT_PATH_KEY,
    CREATE_VIDEO_KEY,
    build_project_tab,
    parse_recent_project_selection,
    set_empty_project_tab,
    update_project_tab,
    update_recent_projects,
)
from vocra.gui.review_tab import (
    REVIEW_BATCH_ACCEPT_KEY,
    REVIEW_BATCH_PENDING_KEY,
    REVIEW_BATCH_REJECT_KEY,
    REVIEW_COMPARE_REFRESH_KEY,
    REVIEW_COMPARE_SOURCE_RUNS_KEY,
    REVIEW_COMPARE_STATUS_KEY,
    REVIEW_COMPARE_TABLE_KEY,
    REVIEW_COMPARE_USE_WINNER_KEY,
    REVIEW_EDITED_TEXT_KEY,
    REVIEW_FILTER_KEY,
    REVIEW_NEXT_KEY,
    REVIEW_NEXT_SUSPICIOUS_KEY,
    REVIEW_NOTES_KEY,
    REVIEW_OCR_RUN_KEY,
    REVIEW_PREPARE_RUN_KEY,
    REVIEW_PREVIOUS_KEY,
    REVIEW_SELECTED_SEGMENT_ID_KEY,
    REVIEW_STATUS_KEY,
    REVIEW_TABLE_KEY,
    build_review_edit_form,
    build_review_tab,
    clear_review_compare,
    clear_selected_review_item,
    get_review_compare_source_runs,
    select_review_table_row,
    set_empty_review_tab,
    set_review_save_state,
    set_selected_review_compare_item,
    set_selected_review_detail,
    set_selected_review_item,
    update_review_compare_controls,
    update_review_tab,
)
from vocra.gui.widgets import (
    PREPARE_ACTIVE_CROP_ZONE_KEY,
    PREPARE_CROP_EDIT_MODE_KEY,
    PREPARE_PREVIEW_GRAPH_KEY,
    move_preview_selection,
    normalize_preview_selection,
    resize_preview_selection,
)

DEFAULT_WINDOW_SIZE = (1180, 860)
MIN_WINDOW_SIZE = (1024, 720)


def run_main_window(initial_project: str | None = None) -> int:
    sg.theme("SystemDefault")
    status_key = "-STATUS-"
    project_path_key = "-PROJECT-PATH-"
    window = sg.Window(
        "VOCra",
        _build_layout(
            initial_project or "",
            status_key=status_key,
            project_path_key=project_path_key,
        ),
        size=DEFAULT_WINDOW_SIZE,
        resizable=True,
        finalize=True,
    )
    window.set_min_size(MIN_WINDOW_SIZE)
    window.bind("<Control-s>", "-REVIEW-SHORTCUT-SAVE-")
    window.bind("<Return>", "-REVIEW-SHORTCUT-ACCEPT-")
    window.bind("<KeyPress-e>", "-REVIEW-SHORTCUT-EDIT-")
    window.bind("<KeyPress-r>", "-REVIEW-SHORTCUT-REJECT-")
    window.bind("<KeyPress-n>", "-REVIEW-SHORTCUT-NEXT-")
    window.bind("<KeyPress-p>", "-REVIEW-SHORTCUT-PREVIOUS-")
    set_empty_project_tab(window)
    set_empty_prepare_tab(window)
    set_empty_ocr_tab(window)
    set_empty_review_tab(window)
    set_empty_package_tab(window)
    update_recent_projects(window, load_recent_project_summaries())
    current_project_root: Path | None = None
    current_prepare_preview = None
    current_ocr_summary = None
    current_review_summary = None
    current_compare_summary = None
    current_package_summary = None
    current_stage_tab = "Project"
    pending_crop_selection: tuple[int, int, int, int] | None = None
    pending_crop_drag_anchor: tuple[float, float] | None = None
    pending_crop_selection_origin: tuple[int, int, int, int] | None = None
    pending_crop_edit_mode: str | None = None
    prepare_run_in_flight = False
    prepare_cancel_event: threading.Event | None = None
    ocr_run_in_flight = False

    if initial_project:
        current_project_root = _open_project(
            window,
            Path(initial_project),
            status_key=status_key,
        )
        if current_project_root is not None:
            current_ocr_summary = load_ocr_stage_summary(current_project_root)
            current_review_summary = load_review_stage_summary(current_project_root)
            current_compare_summary = _refresh_review_compare_summary(
                window,
                current_project_root,
                current_review_summary,
            )
            current_package_summary = load_package_stage_summary(current_project_root)
    update_prepare_preview_selection(window, None, None)

    while True:
        event, values = window.read()
        if event == sg.WINDOW_CLOSED:
            break
        if event == "-MAIN-TABS-":
            current_stage_tab = str(values.get("-MAIN-TABS-", current_stage_tab))
        remapped_review_event = _map_review_shortcut_event(
            window,
            event,
            review_tab_active=(current_stage_tab == "Review"),
        )
        if remapped_review_event == "__review_edit__":
            if current_review_summary is None:
                window[status_key].update("Refresh Review items before editing a segment.")
            else:
                window[REVIEW_EDITED_TEXT_KEY].set_focus()
                window[REVIEW_STATUS_KEY].update(value="edited")
                window[status_key].update("Focused Review editor and marked the current item as edited.")
            continue
        if remapped_review_event is not None:
            event = remapped_review_event
        if (
            (prepare_run_in_flight or ocr_run_in_flight)
            and event in {"-OPEN-PROJECT-", "-OPEN-RECENT-PROJECT-", CREATE_PROJECT_BUTTON_KEY}
        ):
            busy_stage = "Prepare" if prepare_run_in_flight else "OCR"
            window[status_key].update(
                f"Wait for the active {busy_stage} run to finish before switching projects."
            )
            continue
        if event == "-OPEN-PROJECT-":
            raw_path = str(values.get(project_path_key, "")).strip()
            if not raw_path:
                window[status_key].update("Choose a project folder first.")
                continue
            current_project_root = _open_project(
                window,
                Path(raw_path),
                status_key=status_key,
            )
            current_prepare_preview = None
            current_ocr_summary = None
            current_review_summary = None
            current_compare_summary = None
            current_package_summary = None
            pending_crop_selection = None
            pending_crop_drag_anchor = None
            pending_crop_selection_origin = None
            pending_crop_edit_mode = None
            update_prepare_preview_selection(window, None, None)
            set_prepare_selection_state(
                window,
                "Load a preview to start interactive crop selection.",
                can_stage=False,
            )
            set_prepare_run_state(window, "Prepare run is idle.")
            reset_prepare_run_log(window)
            if current_project_root is not None:
                current_ocr_summary = load_ocr_stage_summary(current_project_root)
                current_review_summary = load_review_stage_summary(current_project_root)
                current_compare_summary = _refresh_review_compare_summary(
                    window,
                    current_project_root,
                    current_review_summary,
                )
                current_package_summary = load_package_stage_summary(current_project_root)
                current_prepare_preview = _prime_prepare_preview(
                    window,
                    current_project_root,
                    status_key=status_key,
                )
        if event == "-OPEN-RECENT-PROJECT-":
            selected_project = parse_recent_project_selection(values)
            if selected_project is None:
                window[status_key].update("Choose a recent project first.")
                continue
            window[project_path_key].update(str(selected_project))
            current_project_root = _open_project(
                window,
                selected_project,
                status_key=status_key,
            )
            current_prepare_preview = None
            current_ocr_summary = None
            current_review_summary = None
            current_compare_summary = None
            current_package_summary = None
            pending_crop_selection = None
            pending_crop_drag_anchor = None
            pending_crop_selection_origin = None
            pending_crop_edit_mode = None
            update_prepare_preview_selection(window, None, None)
            set_prepare_selection_state(
                window,
                "Load a preview to start interactive crop selection.",
                can_stage=False,
            )
            set_prepare_run_state(window, "Prepare run is idle.")
            reset_prepare_run_log(window)
            if current_project_root is not None:
                current_ocr_summary = load_ocr_stage_summary(current_project_root)
                current_review_summary = load_review_stage_summary(current_project_root)
                current_compare_summary = _refresh_review_compare_summary(
                    window,
                    current_project_root,
                    current_review_summary,
                )
                current_package_summary = load_package_stage_summary(current_project_root)
                current_prepare_preview = _prime_prepare_preview(
                    window,
                    current_project_root,
                    status_key=status_key,
                )
        if event == CREATE_PROJECT_BUTTON_KEY:
            raw_video = str(values.get(CREATE_VIDEO_KEY, "")).strip()
            raw_project = str(values.get(CREATE_PROJECT_PATH_KEY, "")).strip()
            if not raw_video or not raw_project:
                window[status_key].update(
                    "Choose both a source video path and a project folder path."
                )
                continue
            current_project_root = _create_project(
                window,
                video_path=Path(raw_video),
                project_root=Path(raw_project),
                project_path_key=project_path_key,
                status_key=status_key,
            )
            current_prepare_preview = None
            current_ocr_summary = None
            current_review_summary = None
            current_compare_summary = None
            current_package_summary = None
            pending_crop_selection = None
            pending_crop_drag_anchor = None
            pending_crop_selection_origin = None
            pending_crop_edit_mode = None
            update_prepare_preview_selection(window, None, None)
            set_prepare_selection_state(
                window,
                "Load a preview to start interactive crop selection.",
                can_stage=False,
            )
            set_prepare_run_state(window, "Prepare run is idle.")
            reset_prepare_run_log(window)
            if current_project_root is not None:
                current_ocr_summary = load_ocr_stage_summary(current_project_root)
                current_review_summary = load_review_stage_summary(current_project_root)
                current_compare_summary = _refresh_review_compare_summary(
                    window,
                    current_project_root,
                    current_review_summary,
                )
                current_package_summary = load_package_stage_summary(current_project_root)
                current_prepare_preview = _prime_prepare_preview(
                    window,
                    current_project_root,
                    status_key=status_key,
                )
        if event == "-REFRESH-PREPARE-":
            if current_project_root is None:
                window[status_key].update("Load a project before refreshing Prepare summary.")
                continue
            _refresh_prepare_summary(
                window,
                current_project_root,
                status_key=status_key,
            )
        if event == "-RELOAD-PREPARE-CONFIG-":
            if current_project_root is None:
                window[status_key].update("Load a project before reloading Prepare config.")
                continue
            _refresh_prepare_config(
                window,
                current_project_root,
                status_key=status_key,
            )
        if event == "-SAVE-PREPARE-CONFIG-":
            if current_project_root is None:
                window[status_key].update("Load a project before saving Prepare config.")
                continue
            _save_prepare_config(
                window,
                current_project_root,
                values,
                status_key=status_key,
            )
        if event == "-SAVE-PREPARE-CROP-ZONES-":
            if current_project_root is None:
                window[status_key].update("Load a project before saving crop zones.")
                continue
            current_prepare_preview = _save_prepare_crop_zones(
                window,
                current_project_root,
                values,
                status_key=status_key,
            )
            pending_crop_selection = None
            pending_crop_drag_anchor = None
            pending_crop_selection_origin = None
            pending_crop_edit_mode = None
        if event == "-RELOAD-PREPARE-CROP-ZONES-":
            if current_project_root is None:
                window[status_key].update("Load a project before reloading crop zones.")
                continue
            _refresh_prepare_crop_zones(
                window,
                current_project_root,
                status_key=status_key,
            )
        if event == "-CLEAR-PREPARE-CROP-ZONES-":
            window[PREPARE_CROP_ZONE0_KEY].update("")
            window[PREPARE_CROP_ZONE1_KEY].update("")
            window[status_key].update("Cleared crop-zone editor fields. Save to persist the change.")
        if event == "-LOAD-PREPARE-PREVIEW-":
            if current_project_root is None:
                window[status_key].update("Load a project before requesting preview frames.")
                continue
            current_prepare_preview = _load_prepare_preview(
                window,
                current_project_root,
                values,
                status_key=status_key,
            )
            pending_crop_selection = None
            pending_crop_drag_anchor = None
            pending_crop_selection_origin = None
            pending_crop_edit_mode = None
            if current_prepare_preview is not None:
                set_prepare_selection_state(
                    window,
                    "Drag to create a selection, or stage the active zone to move/resize it on the preview.",
                    can_stage=True,
                )
        if event == "-USE-PREPARE-START-TIME-":
            start_time_value = str(values.get("-PREPARE-TIME-START-MS-", "0")).strip() or "0"
            try:
                start_time_ms = max(int(start_time_value), 0)
            except ValueError:
                window[status_key].update("Prepare start time must be an integer before using it for preview.")
                continue
            window["-PREPARE-PREVIEW-TARGET-"].update(value=start_time_ms)
            window[status_key].update(f"Set preview target to Prepare start time: {start_time_ms} ms")
        if event == "-STAGE-PREPARE-ACTIVE-ZONE-":
            if current_prepare_preview is None:
                window[status_key].update("Load a preview before staging a crop zone on it.")
                continue
            active_zone_idx = str(values.get(PREPARE_ACTIVE_CROP_ZONE_KEY, "0"))
            active_zone_key = PREPARE_CROP_ZONE0_KEY if active_zone_idx == "0" else PREPARE_CROP_ZONE1_KEY
            active_zone_spec = str(values.get(active_zone_key, "")).strip()
            if not active_zone_spec:
                window[status_key].update(f"Zone {active_zone_idx} is empty. Save or enter a crop zone first.")
                continue
            try:
                pending_crop_selection = preview_selection_for_zone_spec(
                    current_prepare_preview,
                    active_zone_spec,
                )
            except ProjectWorkspaceError as exc:
                message = str(exc)
                window[status_key].update(message)
                sg.popup_error(message, title="VOCra")
                continue
            if pending_crop_selection is None:
                window[status_key].update(f"Zone {active_zone_idx} could not be staged on the preview.")
                continue
            pending_crop_drag_anchor = None
            pending_crop_selection_origin = pending_crop_selection
            pending_crop_edit_mode = str(values.get(PREPARE_CROP_EDIT_MODE_KEY, "create"))
            update_prepare_preview_selection(window, current_prepare_preview, pending_crop_selection)
            set_prepare_selection_state(
                window,
                f"Zone {active_zone_idx} staged on the preview. Drag in {pending_crop_edit_mode} mode, then apply it back to the zone.",
                can_apply=True,
                can_clear=True,
                can_stage=True,
            )
            window[status_key].update(f"Staged Zone {active_zone_idx} on the preview for visual editing.")
        if event == PREPARE_PREVIEW_GRAPH_KEY:
            if current_prepare_preview is None:
                window[status_key].update("Load a preview before using interactive crop selection.")
                continue
            preview_point = _parse_preview_point(values.get(PREPARE_PREVIEW_GRAPH_KEY))
            if preview_point is None:
                continue
            selected_edit_mode = str(values.get(PREPARE_CROP_EDIT_MODE_KEY, "create"))
            if pending_crop_edit_mode != selected_edit_mode:
                pending_crop_drag_anchor = None
                pending_crop_selection_origin = pending_crop_selection
                pending_crop_edit_mode = selected_edit_mode
            if selected_edit_mode == "create":
                if pending_crop_drag_anchor is None:
                    pending_crop_drag_anchor = preview_point
                pending_crop_selection = normalize_preview_selection(
                    pending_crop_drag_anchor,
                    preview_point,
                    display_width=current_prepare_preview.display_width,
                    display_height=current_prepare_preview.display_height,
                )
            elif selected_edit_mode == "move":
                if pending_crop_selection is None:
                    window[status_key].update("Stage or draw a selection before moving it on the preview.")
                    continue
                if pending_crop_drag_anchor is None or pending_crop_selection_origin is None:
                    pending_crop_drag_anchor = preview_point
                    pending_crop_selection_origin = pending_crop_selection
                delta_x = preview_point[0] - pending_crop_drag_anchor[0]
                delta_y = preview_point[1] - pending_crop_drag_anchor[1]
                pending_crop_selection = move_preview_selection(
                    pending_crop_selection_origin,
                    delta_x=delta_x,
                    delta_y=delta_y,
                    display_width=current_prepare_preview.display_width,
                    display_height=current_prepare_preview.display_height,
                )
            else:
                if pending_crop_selection is None:
                    window[status_key].update("Stage or draw a selection before resizing it on the preview.")
                    continue
                if pending_crop_selection_origin is None:
                    pending_crop_selection_origin = pending_crop_selection
                pending_crop_selection = resize_preview_selection(
                    pending_crop_selection_origin,
                    handle=selected_edit_mode.removeprefix("resize-"),
                    target_xy=preview_point,
                    display_width=current_prepare_preview.display_width,
                    display_height=current_prepare_preview.display_height,
                )
            update_prepare_preview_selection(window, current_prepare_preview, pending_crop_selection)
            if pending_crop_selection is None:
                set_prepare_selection_state(
                    window,
                    "Drag farther inside the preview to stage a valid crop selection.",
                    can_apply=False,
                    can_clear=True,
                    can_stage=True,
                )
            else:
                active_zone = str(values.get(PREPARE_ACTIVE_CROP_ZONE_KEY, "0"))
                set_prepare_selection_state(
                    window,
                    f"Selection staged for Zone {active_zone} in {selected_edit_mode} mode: {pending_crop_selection[0]},{pending_crop_selection[1]} -> {pending_crop_selection[2]},{pending_crop_selection[3]}",
                    can_apply=True,
                    can_clear=True,
                    can_stage=True,
                )
        if event == "-CLEAR-PREPARE-CROP-SELECTION-":
            pending_crop_selection = None
            pending_crop_drag_anchor = None
            pending_crop_selection_origin = None
            pending_crop_edit_mode = None
            update_prepare_preview_selection(window, current_prepare_preview, None)
            if current_prepare_preview is None:
                set_prepare_selection_state(
                    window,
                    "Load a preview to start interactive crop selection.",
                    can_stage=False,
                )
            else:
                set_prepare_selection_state(
                    window,
                    "Selection cleared. Drag to create a new selection or stage the active zone to edit it.",
                    can_stage=True,
                )
        if event == "-APPLY-PREPARE-CROP-SELECTION-":
            if current_prepare_preview is None:
                window[status_key].update("Load a preview before applying an interactive crop selection.")
                continue
            if pending_crop_selection is None:
                window[status_key].update("Drag a valid rectangle in the preview before applying it.")
                continue
            try:
                active_zone_idx = int(str(values.get(PREPARE_ACTIVE_CROP_ZONE_KEY, "0")))
                crop_zone = preview_selection_to_crop_zone(
                    current_prepare_preview,
                    zone_idx=active_zone_idx,
                    start_xy=(pending_crop_selection[0], pending_crop_selection[1]),
                    end_xy=(pending_crop_selection[2], pending_crop_selection[3]),
                )
            except (ProjectWorkspaceError, ValueError) as exc:
                message = str(exc)
                window[status_key].update(message)
                sg.popup_error(message, title="VOCra")
                continue
            target_key = PREPARE_CROP_ZONE0_KEY if active_zone_idx == 0 else PREPARE_CROP_ZONE1_KEY
            window[target_key].update(format_crop_zone_spec(crop_zone))
            pending_crop_drag_anchor = None
            pending_crop_selection_origin = pending_crop_selection
            set_prepare_selection_state(
                window,
                f"Zone {active_zone_idx} updated from preview editing. Save crop zones to persist it.",
                can_apply=True,
                can_clear=True,
                can_stage=True,
            )
            window[status_key].update(
                f"Updated Zone {active_zone_idx} from preview editing: {format_crop_zone_spec(crop_zone)}"
            )
        if event == "-RUN-PREPARE-":
            if current_project_root is None:
                window[status_key].update("Load a project before running Prepare.")
                continue
            if ocr_run_in_flight:
                window[status_key].update("Wait for the active OCR run to finish before running Prepare.")
                continue
            if prepare_run_in_flight:
                window[status_key].update("Prepare is already running.")
                continue
            if not _persist_prepare_editor_state(
                window,
                current_project_root,
                values,
                status_key=status_key,
            ):
                continue
            prepare_run_in_flight = True
            prepare_cancel_event = threading.Event()
            reset_prepare_run_log(window)
            append_prepare_run_log(window, "[prepare.start] Persisted editor state and queued Prepare run.")
            set_prepare_run_state(
                window,
                "Prepare is running with the persisted config. The window stays responsive; summary will refresh on completion.",
                running=True,
            )
            window[status_key].update("Started Prepare run.")
            window.perform_long_operation(
                lambda root=current_project_root, cancel_event=prepare_cancel_event: _execute_prepare_run(
                    root,
                    window,
                    cancel_event,
                ),
                "-PREPARE-RUN-DONE-",
            )
        if event == "-STOP-PREPARE-":
            if not prepare_run_in_flight or prepare_cancel_event is None:
                window[status_key].update("No active Prepare run to stop.")
                continue
            prepare_cancel_event.set()
            set_prepare_run_state(
                window,
                "Stop requested. Prepare will cancel at the next safe checkpoint.",
                running=True,
            )
            append_prepare_run_log(
                window,
                "[prepare.stop] Stop requested. Waiting for the next safe cancellation checkpoint.",
            )
            window[status_key].update("Stop requested for the active Prepare run.")
        if event == "-PREPARE-RUN-PROGRESS-":
            progress = values.get("-PREPARE-RUN-PROGRESS-")
            if progress is None:
                continue
            append_prepare_run_log(
                window,
                _format_prepare_progress_line(progress),
            )
            set_prepare_run_state(
                window,
                f"{progress.stage}: {progress.message}",
                running=True,
            )
        if event == "-PREPARE-RUN-DONE-":
            prepare_run_in_flight = False
            prepare_cancel_event = None
            result = values.get("-PREPARE-RUN-DONE-")
            if not isinstance(result, tuple) or len(result) != 2:
                set_prepare_run_state(
                    window,
                    "Prepare finished, but GUI did not receive a valid result payload.",
                    running=False,
                )
                window[status_key].update("Prepare finished with an invalid GUI result payload.")
                continue
            state, payload = result
            if state == "error":
                message = str(payload)
                append_prepare_run_log(window, f"[prepare.error] {message}")
                set_prepare_run_state(window, f"Prepare failed: {message}", running=False)
                window[status_key].update(message)
                sg.popup_error(message, title="VOCra")
                continue
            if state == "cancelled":
                message = str(payload)
                append_prepare_run_log(window, f"[prepare.cancelled] {message}")
                set_prepare_run_state(window, message, running=False)
                _refresh_prepare_summary(window, current_project_root, status_key=status_key)
                window[status_key].update(message)
                continue
            outcome = payload
            _refresh_prepare_summary(window, current_project_root, status_key=status_key)
            current_prepare_preview = _load_prepare_preview(
                window,
                current_project_root,
                values,
                status_key=status_key,
            )
            current_ocr_summary = _refresh_ocr_summary(
                window,
                current_project_root,
                status_key=status_key,
            )
            current_review_summary = _refresh_review_summary(
                window,
                current_project_root,
                status_key=status_key,
            )
            set_prepare_run_state(
                window,
                "Prepare finished: "
                f"{outcome.segment_count} segments from {outcome.sampled_frame_count} sampled frames "
                f"into run {outcome.run_id}.",
                running=False,
            )
            append_prepare_run_log(
                window,
                "[prepare.done] "
                f"Run {outcome.run_id} completed with {outcome.segment_count} segment(s) "
                f"from {outcome.sampled_frame_count} sampled frame(s).",
            )
            window[status_key].update(
                f"Prepare run completed: {outcome.run_id} ({outcome.segment_count} segments)."
            )
        if event == "-REFRESH-OCR-":
            if current_project_root is None:
                window[status_key].update("Load a project before refreshing OCR summary.")
                continue
            current_ocr_summary = _refresh_ocr_summary(
                window,
                current_project_root,
                status_key=status_key,
            )
            current_review_summary = _refresh_review_summary(
                window,
                current_project_root,
                status_key=status_key,
            )
        if event == OCR_RUN_TABLE_KEY:
            if current_ocr_summary is None:
                window[status_key].update("Refresh OCR summary before selecting an OCR run.")
                continue
            selected_rows = values.get(OCR_RUN_TABLE_KEY)
            if not selected_rows:
                continue
            try:
                selected_index = int(selected_rows[0])
            except (TypeError, ValueError, IndexError):
                continue
            if selected_index < 0 or selected_index >= len(current_ocr_summary.runs):
                continue
            selected_run = current_ocr_summary.runs[selected_index]
            selected_form = replace(
                build_ocr_config_form(values),
                prepare_run=selected_run.prepare_run or str(values.get(OCR_PREPARE_RUN_KEY, "")),
                backend_name=selected_run.backend_name or str(values.get(OCR_BACKEND_KEY, "")),
                run_id=selected_run.run_id,
            )
            selected_form = apply_ocr_backend_defaults(
                selected_form,
                selected_form.backend_name,
            )
            update_ocr_config_form(window, selected_form)
            set_selected_ocr_run(window, selected_run)
            window[status_key].update(
                f"Selected OCR run {selected_run.run_id} for resume/rerun and artifact inspection."
            )
        if event == "-LOAD-OCR-RUN-CONFIG-":
            if current_project_root is None:
                window[status_key].update("Load a project before loading OCR run config.")
                continue
            selected_run_id = str(values.get(OCR_RUN_ID_KEY, "")).strip()
            if not selected_run_id:
                window[status_key].update("Choose an OCR run before loading its saved config.")
                continue
            try:
                loaded_form = load_ocr_config_form_for_run(
                    current_project_root,
                    selected_run_id,
                )
            except ProjectWorkspaceError as exc:
                message = str(exc)
                window[status_key].update(message)
                sg.popup_error(message, title="VOCra")
                continue
            update_ocr_config_form(window, loaded_form)
            if current_ocr_summary is not None:
                selected_run = find_ocr_run_item(current_ocr_summary, selected_run_id)
                if selected_run is not None:
                    set_selected_ocr_run(window, selected_run)
            window[status_key].update(
                f"Loaded saved OCR config from run {selected_run_id} into the current form."
            )
        if event == OCR_BACKEND_KEY:
            selected_backend = str(values.get(OCR_BACKEND_KEY, "")).strip()
            adjusted_form = apply_ocr_backend_defaults(
                build_ocr_config_form(values),
                selected_backend,
            )
            update_ocr_config_form(window, adjusted_form)
            window[status_key].update(f"OCR backend selected: {selected_backend}")
        if event == "-TEST-OCR-BACKEND-":
            selected_backend = str(values.get(OCR_BACKEND_KEY, "")).strip()
            if not selected_backend:
                window[status_key].update("Choose an OCR backend before testing it.")
                continue
            set_ocr_run_state(
                window,
                "Testing OCR backend configuration...",
                running=True,
            )
            append_ocr_run_log(
                window,
                f"[ocr.test] Testing backend {selected_backend}.",
            )
            backend_form = apply_ocr_backend_defaults(
                build_ocr_config_form(values),
                selected_backend,
            )
            update_ocr_config_form(window, backend_form)
            window.perform_long_operation(
                lambda form=backend_form: _execute_ocr_backend_test(form),
                "-OCR-BACKEND-TEST-DONE-",
            )
        if event == "-OCR-BACKEND-TEST-DONE-":
            result = values.get("-OCR-BACKEND-TEST-DONE-")
            set_ocr_run_state(window, "OCR run is idle.", running=False)
            if not isinstance(result, tuple) or len(result) != 2:
                window[status_key].update("Backend test finished with an invalid GUI result payload.")
                continue
            state, payload = result
            if state == "error":
                message = str(payload)
                append_ocr_run_log(window, f"[ocr.test.error] {message}")
                window[status_key].update(message)
                sg.popup_error(message, title="VOCra")
                continue
            outcome = payload
            if outcome.ok:
                append_ocr_run_log(
                    window,
                    f"[ocr.test.ok] {outcome.backend_name}: {outcome.message}",
                )
                window[status_key].update(
                    f"OCR backend test succeeded for {outcome.backend_name}."
                )
            else:
                append_ocr_run_log(
                    window,
                    f"[ocr.test.fail] {outcome.backend_name}: {outcome.message}",
                )
                window[status_key].update(
                    f"OCR backend test failed for {outcome.backend_name}: {outcome.message}"
                )
        if event in {"-RUN-OCR-", "-RESUME-OCR-FAILED-", "-RERUN-OCR-EMPTY-"}:
            if current_project_root is None:
                window[status_key].update("Load a project before running OCR.")
                continue
            if prepare_run_in_flight:
                window[status_key].update("Wait for the active Prepare run to finish before running OCR.")
                continue
            if ocr_run_in_flight:
                window[status_key].update("OCR is already running.")
                continue
            action_name, start_message, status_message = _resolve_ocr_action_labels(event)
            ocr_run_in_flight = True
            reset_ocr_run_log(window)
            append_ocr_run_log(window, f"[ocr.start] Queued {action_name} from the current GUI form.")
            set_ocr_run_state(
                window,
                status_message,
                running=True,
            )
            window[status_key].update(start_message)
            ocr_form = build_ocr_config_form(values)
            window.perform_long_operation(
                lambda root=current_project_root, form=ocr_form, action=event: _execute_ocr_run(
                    root,
                    form,
                    action=action,
                ),
                "-OCR-RUN-DONE-",
            )
        if event == "-OCR-RUN-DONE-":
            ocr_run_in_flight = False
            result = values.get("-OCR-RUN-DONE-")
            if not isinstance(result, tuple) or len(result) != 2:
                set_ocr_run_state(
                    window,
                    "OCR finished, but GUI did not receive a valid result payload.",
                    running=False,
                )
                window[status_key].update("OCR finished with an invalid GUI result payload.")
                continue
            state, payload = result
            if state == "error":
                message = str(payload)
                append_ocr_run_log(window, f"[ocr.error] {message}")
                set_ocr_run_state(window, f"OCR failed: {message}", running=False)
                window[status_key].update(message)
                sg.popup_error(message, title="VOCra")
                continue
            outcome = payload
            current_ocr_summary = _refresh_ocr_summary(
                window,
                current_project_root,
                status_key=status_key,
            )
            current_package_summary = _refresh_package_summary(
                window,
                current_project_root,
                status_key=status_key,
            )
            set_ocr_run_state(
                window,
                "OCR finished: "
                f"run {outcome.run_id} produced ok={outcome.ok_count}, "
                f"error={outcome.error_count}, empty={outcome.empty_count}.",
                running=False,
            )
            append_ocr_run_log(
                window,
                "[ocr.done] "
                f"Run {outcome.run_id} completed with ok={outcome.ok_count}, "
                f"error={outcome.error_count}, empty={outcome.empty_count}.",
            )
            window[status_key].update(
                f"OCR run completed: {outcome.run_id} (ok={outcome.ok_count}, error={outcome.error_count})."
            )
        if event in {"-REFRESH-REVIEW-", REVIEW_PREPARE_RUN_KEY, REVIEW_OCR_RUN_KEY, REVIEW_FILTER_KEY}:
            if current_project_root is None:
                window[status_key].update("Load a project before refreshing Review items.")
                continue
            current_review_summary = _refresh_review_summary(
                window,
                current_project_root,
                status_key=status_key,
            )
            current_compare_summary = _refresh_review_compare_summary(
                window,
                current_project_root,
                current_review_summary,
            )
            window[status_key].update("Refreshed Review items.")
        if event in {REVIEW_COMPARE_SOURCE_RUNS_KEY, REVIEW_COMPARE_REFRESH_KEY}:
            if current_project_root is None:
                window[status_key].update("Load a project before refreshing OCR comparison data.")
                continue
            if current_review_summary is None:
                current_review_summary = _refresh_review_summary(
                    window,
                    current_project_root,
                    status_key=status_key,
                )
            current_compare_summary = _refresh_review_compare_summary(
                window,
                current_project_root,
                current_review_summary,
            )
            window[status_key].update("Refreshed OCR comparison candidates for the current Review run.")
        if event == REVIEW_TABLE_KEY:
            if current_review_summary is None or current_project_root is None:
                window[status_key].update("Refresh Review items before selecting a segment.")
                continue
            selected_rows = values.get(REVIEW_TABLE_KEY)
            if not selected_rows:
                continue
            try:
                selected_index = int(selected_rows[0])
            except (TypeError, ValueError, IndexError):
                continue
            if selected_index < 0 or selected_index >= len(current_review_summary.items):
                continue
            selected_item = current_review_summary.items[selected_index]
            _apply_review_selection(
                window,
                project_root=current_project_root,
                summary=current_review_summary,
                item=selected_item,
            )
            _apply_review_compare_selection(
                window,
                summary=current_compare_summary,
                segment_id=selected_item.segment_id,
            )
            window[status_key].update(
                f"Selected review item {selected_item.segment_id} from OCR run {current_review_summary.selected_ocr_run}."
            )
        if event in {REVIEW_PREVIOUS_KEY, REVIEW_NEXT_KEY, REVIEW_NEXT_SUSPICIOUS_KEY}:
            if current_project_root is None or current_review_summary is None:
                window[status_key].update("Refresh Review items before navigating segments.")
                continue
            current_segment_id = str(values.get(REVIEW_SELECTED_SEGMENT_ID_KEY, "")).strip()
            if event == REVIEW_NEXT_SUSPICIOUS_KEY:
                selected_item = find_next_suspicious_review_item(
                    current_review_summary,
                    current_segment_id,
                )
                if selected_item is None:
                    window[status_key].update("No later suspicious review item exists in the current filtered list.")
                    continue
            else:
                selected_item = move_review_selection(
                    current_review_summary,
                    current_segment_id,
                    step=(-1 if event == REVIEW_PREVIOUS_KEY else 1),
                )
                if selected_item is None:
                    direction = "previous" if event == REVIEW_PREVIOUS_KEY else "next"
                    window[status_key].update(f"No {direction} review item exists in the current filtered list.")
                    continue
            _apply_review_selection(
                window,
                project_root=current_project_root,
                summary=current_review_summary,
                item=selected_item,
            )
            _apply_review_compare_selection(
                window,
                summary=current_compare_summary,
                segment_id=selected_item.segment_id,
            )
            window[status_key].update(
                f"Moved Review selection to {selected_item.segment_id}."
            )
        if event in {"-SAVE-REVIEW-", "-REVIEW-SET-ACCEPTED-", "-REVIEW-SET-REJECTED-", "-REVIEW-SET-PENDING-"}:
            if current_project_root is None:
                window[status_key].update("Load a project before saving review state.")
                continue
            status_override = None
            if event == "-REVIEW-SET-ACCEPTED-":
                status_override = "accepted"
            elif event == "-REVIEW-SET-REJECTED-":
                status_override = "rejected"
            elif event == "-REVIEW-SET-PENDING-":
                status_override = "pending"
            try:
                review_form = _normalize_review_form_for_save(
                    values,
                    current_review_summary,
                )
                if status_override is not None:
                    review_form = replace(review_form, review_status=status_override)
                outcome = save_review_edit_from_form(current_project_root, review_form)
            except ProjectWorkspaceError as exc:
                message = str(exc)
                set_review_save_state(window, message)
                window[status_key].update(message)
                sg.popup_error(message, title="VOCra")
                continue
            current_review_summary = _refresh_review_summary(
                window,
                current_project_root,
                status_key=status_key,
            )
            current_compare_summary = _refresh_review_compare_summary(
                window,
                current_project_root,
                current_review_summary,
            )
            current_package_summary = _refresh_package_summary(
                window,
                current_project_root,
                status_key=status_key,
            )
            refreshed_item = (
                None
                if current_review_summary is None
                else find_review_item(current_review_summary, outcome.segment_id)
            )
            if refreshed_item is not None:
                _apply_review_selection(
                    window,
                    project_root=current_project_root,
                    summary=current_review_summary,
                    item=refreshed_item,
                )
                _apply_review_compare_selection(
                    window,
                    summary=current_compare_summary,
                    segment_id=refreshed_item.segment_id,
                )
            set_review_save_state(
                window,
                f"Saved {outcome.review_status} review state for {outcome.segment_id}.",
            )
            window[status_key].update(
                f"Saved review state for {outcome.segment_id} in OCR run {review_form.ocr_run}."
            )
        if event in {REVIEW_BATCH_ACCEPT_KEY, REVIEW_BATCH_REJECT_KEY, REVIEW_BATCH_PENDING_KEY}:
            if current_project_root is None:
                window[status_key].update("Load a project before saving batch review state.")
                continue
            review_form = build_review_edit_form(values)
            batch_status = "accepted"
            if event == REVIEW_BATCH_REJECT_KEY:
                batch_status = "rejected"
            elif event == REVIEW_BATCH_PENDING_KEY:
                batch_status = "pending"
            try:
                outcome = save_review_batch_from_filter(
                    current_project_root,
                    prepare_run=review_form.prepare_run,
                    ocr_run=review_form.ocr_run,
                    filter_name=review_form.filter_name,
                    review_status=batch_status,
                    notes=review_form.notes,
                )
            except ProjectWorkspaceError as exc:
                message = str(exc)
                set_review_save_state(window, message)
                window[status_key].update(message)
                sg.popup_error(message, title="VOCra")
                continue
            current_review_summary = _refresh_review_summary(
                window,
                current_project_root,
                status_key=status_key,
            )
            current_compare_summary = _refresh_review_compare_summary(
                window,
                current_project_root,
                current_review_summary,
            )
            current_package_summary = _refresh_package_summary(
                window,
                current_project_root,
                status_key=status_key,
            )
            set_review_save_state(
                window,
                f"Saved {batch_status} review state for {outcome.updated_count} filtered item(s).",
            )
            window[status_key].update(
                f"Updated {outcome.updated_count} Review item(s) with status {batch_status} using filter {outcome.filter_name}."
            )
        if event == REVIEW_COMPARE_USE_WINNER_KEY:
            if current_project_root is None:
                window[status_key].update("Load a project before applying a compare winner.")
                continue
            if current_review_summary is None or current_compare_summary is None:
                window[status_key].update("Refresh Review and OCR comparison data before applying a compare winner.")
                continue
            selected_segment_id = str(values.get(REVIEW_SELECTED_SEGMENT_ID_KEY, "")).strip()
            comparison_item = find_ocr_comparison_item(
                current_compare_summary,
                selected_segment_id,
            )
            if comparison_item is None:
                window[status_key].update("Choose a Review segment before applying a compare winner.")
                continue
            selected_rows = values.get(REVIEW_COMPARE_TABLE_KEY)
            if not selected_rows:
                window[status_key].update("Choose a compare candidate row before applying a winner.")
                continue
            try:
                selected_index = int(selected_rows[0])
            except (TypeError, ValueError, IndexError):
                window[status_key].update("Choose a valid compare candidate row before applying a winner.")
                continue
            if selected_index < 0 or selected_index >= len(comparison_item.candidates):
                window[status_key].update("Choose a valid compare candidate row before applying a winner.")
                continue
            candidate = comparison_item.candidates[selected_index]
            try:
                outcome = apply_ocr_comparison_choice(
                    current_project_root,
                    target_ocr_run=current_review_summary.selected_ocr_run,
                    source_ocr_run=candidate.run_id,
                    segment_id=selected_segment_id,
                    notes=(str(values.get(REVIEW_NOTES_KEY, "")).strip() or None),
                )
            except ProjectWorkspaceError as exc:
                message = str(exc)
                window[REVIEW_COMPARE_STATUS_KEY].update(message)
                window[status_key].update(message)
                sg.popup_error(message, title="VOCra")
                continue
            current_review_summary = _refresh_review_summary(
                window,
                current_project_root,
                status_key=status_key,
            )
            current_compare_summary = _refresh_review_compare_summary(
                window,
                current_project_root,
                current_review_summary,
            )
            current_package_summary = _refresh_package_summary(
                window,
                current_project_root,
                status_key=status_key,
            )
            refreshed_item = (
                None
                if current_review_summary is None
                else find_review_item(current_review_summary, outcome.segment_id)
            )
            if refreshed_item is not None:
                _apply_review_selection(
                    window,
                    project_root=current_project_root,
                    summary=current_review_summary,
                    item=refreshed_item,
                )
                _apply_review_compare_selection(
                    window,
                    summary=current_compare_summary,
                    segment_id=refreshed_item.segment_id,
                )
            else:
                clear_review_compare(window)
            set_review_save_state(
                window,
                f"Applied compare winner from {outcome.source_ocr_run} to {outcome.segment_id}.",
            )
            window[REVIEW_COMPARE_STATUS_KEY].update(
                f"Applied compare winner from {outcome.source_ocr_run} to {outcome.segment_id} ({outcome.review_status})."
            )
            window[status_key].update(
                f"Applied compare winner from OCR run {outcome.source_ocr_run} to target run {outcome.target_ocr_run} for {outcome.segment_id}."
            )
        if event in {"-REFRESH-PACKAGE-", PACKAGE_PREPARE_RUN_KEY, PACKAGE_OCR_RUN_KEY, PACKAGE_REVIEW_POLICY_KEY, PACKAGE_FORMAT_KEY}:
            if current_project_root is None:
                window[status_key].update("Load a project before refreshing Package summary.")
                continue
            current_package_summary = _refresh_package_summary(
                window,
                current_project_root,
                status_key=status_key,
            )
        if event == PACKAGE_RUN_TABLE_KEY:
            if current_package_summary is None:
                window[status_key].update("Refresh Package runs before selecting a package output.")
                continue
            selected_rows = values.get(PACKAGE_RUN_TABLE_KEY)
            if not selected_rows:
                continue
            try:
                selected_index = int(selected_rows[0])
            except (TypeError, ValueError, IndexError):
                continue
            if selected_index < 0 or selected_index >= len(current_package_summary.runs):
                continue
            selected_run = current_package_summary.runs[selected_index]
            set_selected_package_run(window, selected_run)
            window[status_key].update(f"Selected package run {selected_run.run_id}.")
        if event == "-PREVIEW-PACKAGE-":
            if current_project_root is None:
                window[status_key].update("Load a project before previewing SRT packaging.")
                continue
            try:
                preview = preview_package_from_form(
                    current_project_root,
                    build_package_config_form(values),
                )
            except ProjectWorkspaceError as exc:
                message = str(exc)
                set_package_preview_state(window, message)
                window[status_key].update(message)
                sg.popup_error(message, title="VOCra")
                continue
            set_package_preview(window, preview)
            window[status_key].update(
                f"Built SRT preview with {preview.subtitle_count} subtitle(s)."
            )
        if event == "-EXPORT-PACKAGE-":
            if current_project_root is None:
                window[status_key].update("Load a project before exporting packaged subtitles.")
                continue
            try:
                outcome = export_package_from_form(
                    current_project_root,
                    build_package_config_form(values),
                )
            except ProjectWorkspaceError as exc:
                message = str(exc)
                set_package_preview_state(window, message)
                window[status_key].update(message)
                sg.popup_error(message, title="VOCra")
                continue
            current_package_summary = _refresh_package_summary(
                window,
                current_project_root,
                status_key=status_key,
            )
            if current_package_summary is not None:
                selected_run = find_package_run_item(current_package_summary, outcome.run_id)
                if selected_run is not None:
                    set_selected_package_run(window, selected_run)
            update_project_tab(window, load_project_dashboard(current_project_root))
            set_package_preview_state(
                window,
                f"Exported {outcome.subtitle_count} subtitle(s) to {outcome.output_path}.",
            )
            window[status_key].update(
                f"Exported SRT package run {outcome.run_id} with {outcome.subtitle_count} subtitle(s)."
            )
        if event == "-OPEN-PACKAGE-OUTPUT-FOLDER-":
            if current_project_root is None:
                window[status_key].update("Load a project before opening a package output folder.")
                continue
            try:
                output_folder = resolve_package_output_folder(
                    current_project_root,
                    build_package_config_form(values),
                    selected_run_id=str(values.get(PACKAGE_SELECTED_RUN_ID_KEY, "")).strip() or None,
                )
            except ProjectWorkspaceError as exc:
                message = str(exc)
                window[status_key].update(message)
                sg.popup_error(message, title="VOCra")
                continue
            if not output_folder.exists():
                window[status_key].update(f"Package output folder does not exist yet: {output_folder}")
                continue
            _open_project_folder(output_folder)
            window[status_key].update(f"Opened package output folder: {output_folder}")
        if event == "-OPEN-REVIEW-IMAGE-":
            if current_review_summary is None:
                window[status_key].update("Refresh Review items before opening a segment image.")
                continue
            review_form = build_review_edit_form(values)
            selected_item = find_review_item(current_review_summary, review_form.segment_id)
            if selected_item is None:
                window[status_key].update("Choose a review item before opening its representative image.")
                continue
            if not selected_item.representative_image_path.exists():
                window[status_key].update(
                    f"Representative image does not exist: {selected_item.representative_image_path}"
                )
                continue
            _open_project_folder(selected_item.representative_image_path)
            window[status_key].update(
                f"Opened representative image: {selected_item.representative_image_path}"
            )
        if event == "-OPEN-PACKAGE-RUNS-FOLDER-":
            if current_project_root is None:
                window[status_key].update("Load a project before opening package runs.")
                continue
            package_runs_path = current_project_root / "package" / "runs"
            _open_project_folder(package_runs_path)
            window[status_key].update(f"Opened package runs folder: {package_runs_path}")
        if event == "-OPEN-PACKAGE-OUTPUT-":
            if current_project_root is None:
                window[status_key].update("Load a project before opening package artifacts.")
                continue
            current_package_summary = current_package_summary or _refresh_package_summary(
                window,
                current_project_root,
                status_key=status_key,
            )
            active_run = _resolve_active_package_run(window, current_package_summary)
            if active_run is None or not active_run.output_path.exists():
                window[status_key].update("No selected package output artifact is available yet.")
                continue
            _open_project_folder(active_run.output_path)
            window[status_key].update(f"Opened package output: {active_run.output_path}")
        if event == "-OPEN-PACKAGE-REPORT-":
            if current_project_root is None:
                window[status_key].update("Load a project before opening package artifacts.")
                continue
            current_package_summary = current_package_summary or _refresh_package_summary(
                window,
                current_project_root,
                status_key=status_key,
            )
            active_run = _resolve_active_package_run(window, current_package_summary)
            if active_run is None or not active_run.report_path.exists():
                window[status_key].update("No selected package report artifact is available yet.")
                continue
            _open_project_folder(active_run.report_path)
            window[status_key].update(f"Opened package report: {active_run.report_path}")
        if event == "-OPEN-OCR-RUNS-FOLDER-":
            if current_project_root is None:
                window[status_key].update("Load a project before opening OCR runs.")
                continue
            ocr_runs_path = current_project_root / "ocr" / "runs"
            _open_project_folder(ocr_runs_path)
            window[status_key].update(f"Opened OCR runs folder: {ocr_runs_path}")
        if event == "-OPEN-LATEST-OCR-CONFIG-":
            if current_project_root is None:
                window[status_key].update("Load a project before opening OCR artifacts.")
                continue
            current_ocr_summary = current_ocr_summary or _refresh_ocr_summary(
                window,
                current_project_root,
                status_key=status_key,
            )
            active_run = _resolve_active_ocr_run(current_ocr_summary, values)
            if active_run is None or not active_run.config_path.exists():
                window[status_key].update("No selected OCR config artifact is available yet.")
                continue
            _open_project_folder(active_run.config_path)
            window[status_key].update(f"Opened OCR config: {active_run.config_path}")
        if event == "-OPEN-LATEST-OCR-RAW-OUTPUT-":
            if current_project_root is None:
                window[status_key].update("Load a project before opening OCR artifacts.")
                continue
            current_ocr_summary = current_ocr_summary or _refresh_ocr_summary(
                window,
                current_project_root,
                status_key=status_key,
            )
            active_run = _resolve_active_ocr_run(current_ocr_summary, values)
            if active_run is None or not active_run.raw_outputs_path.exists():
                window[status_key].update("No selected raw OCR output artifact is available yet.")
                continue
            _open_project_folder(active_run.raw_outputs_path)
            window[status_key].update(f"Opened raw OCR output: {active_run.raw_outputs_path}")
        if event == "-OPEN-LATEST-OCR-NORMALIZED-OUTPUT-":
            if current_project_root is None:
                window[status_key].update("Load a project before opening OCR artifacts.")
                continue
            current_ocr_summary = current_ocr_summary or _refresh_ocr_summary(
                window,
                current_project_root,
                status_key=status_key,
            )
            active_run = _resolve_active_ocr_run(current_ocr_summary, values)
            if active_run is None or not active_run.normalized_text_path.exists():
                window[status_key].update("No selected normalized OCR output artifact is available yet.")
                continue
            _open_project_folder(active_run.normalized_text_path)
            window[status_key].update(
                f"Opened normalized OCR output: {active_run.normalized_text_path}"
            )
        if event == "-OPEN-LATEST-OCR-REPORT-":
            if current_project_root is None:
                window[status_key].update("Load a project before opening OCR artifacts.")
                continue
            current_ocr_summary = current_ocr_summary or _refresh_ocr_summary(
                window,
                current_project_root,
                status_key=status_key,
            )
            active_run = _resolve_active_ocr_run(current_ocr_summary, values)
            if active_run is None or not active_run.report_path.exists():
                window[status_key].update("No selected OCR report artifact is available yet.")
                continue
            _open_project_folder(active_run.report_path)
            window[status_key].update(f"Opened OCR report: {active_run.report_path}")
        if event == "-OPEN-PREPARE-FOLDER-":
            if current_project_root is None:
                window[status_key].update("Load a project before opening Prepare artifacts.")
                continue
            _open_project_folder(current_project_root / "prepare")
            window[status_key].update(
                f"Opened Prepare folder: {current_project_root / 'prepare'}"
            )
        if event == "-OPEN-PREPARED-IMAGES-":
            if current_project_root is None:
                window[status_key].update("Load a project before opening prepared images.")
                continue
            prepared_images_path = current_project_root / "prepare" / "representative_images"
            if not prepared_images_path.exists():
                window[status_key].update(
                    f"Prepared images directory does not exist yet: {prepared_images_path}"
                )
                continue
            _open_project_folder(prepared_images_path)
            window[status_key].update(f"Opened prepared images: {prepared_images_path}")
        if event == "-OPEN-PREPARE-CONFIG-":
            if current_project_root is None:
                window[status_key].update("Load a project before opening Prepare config.")
                continue
            config_path = current_project_root / "prepare" / "prepare_config.json"
            if not config_path.exists():
                window[status_key].update(f"Prepare config does not exist yet: {config_path}")
                continue
            _open_project_folder(config_path)
            window[status_key].update(f"Opened Prepare config: {config_path}")
        if event == "-OPEN-SEGMENT-MANIFEST-":
            if current_project_root is None:
                window[status_key].update("Load a project before opening the segment manifest.")
                continue
            manifest_path = current_project_root / "prepare" / "subtitle_segments.jsonl"
            if not manifest_path.exists():
                window[status_key].update(f"Segment manifest does not exist: {manifest_path}")
                continue
            _open_project_folder(manifest_path)
            window[status_key].update(f"Opened segment manifest: {manifest_path}")
        if event == "-OPEN-PROJECT-FOLDER-":
            if current_project_root is None:
                window[status_key].update("Load a project before opening its folder.")
                continue
            _open_project_folder(current_project_root)
            window[status_key].update(f"Opened project folder: {current_project_root}")

    window.close()
    return 0


def _build_layout(
    initial_project: str,
    *,
    status_key: str,
    project_path_key: str,
) -> list[list[object]]:
    return [
        [
            sg.Text("Project folder"),
            sg.Input(initial_project, key=project_path_key, expand_x=True),
            sg.FolderBrowse(target=project_path_key),
            sg.Button("Open Project", key="-OPEN-PROJECT-"),
            sg.Button("Open Project Folder", key="-OPEN-PROJECT-FOLDER-"),
        ],
        [
            sg.TabGroup(
                [
                    [
                        sg.Tab(
                            "Project",
                            build_project_tab(),
                        ),
                        sg.Tab(
                            "Prepare",
                            build_prepare_tab(),
                        ),
                        sg.Tab(
                            "OCR",
                            build_ocr_tab(),
                        ),
                        sg.Tab(
                            "Review",
                            build_review_tab(),
                        ),
                        sg.Tab(
                            "Package",
                            build_package_tab(),
                        ),
                        sg.Tab(
                            "Logs",
                            [[sg.Text("Phase 13 shell: Logs tab wiring comes next.")]],
                        ),
                    ]
                ],
                key="-MAIN-TABS-",
                enable_events=True,
                expand_x=True,
                expand_y=True,
            )
        ],
        [sg.Text("", key=status_key, expand_x=True)],
    ]


def _open_project(
    window: sg.Window,
    project_root: Path,
    *,
    status_key: str,
) -> Path | None:
    try:
        app_state = open_project_state(project_root)
    except ProjectWorkspaceError as exc:
        message = str(exc)
        window[status_key].update(message)
        sg.popup_error(message, title="VOCra")
        return None

    dashboard = app_state.dashboard
    if dashboard is None:
        window[status_key].update("Project loaded, but dashboard state was empty.")
        return None

    update_project_tab(window, dashboard)
    update_recent_projects(window, app_state.recent_projects)
    _sync_prepare_preview_context(window, app_state)
    if app_state.prepare_summary is not None:
        update_prepare_tab(window, app_state.prepare_summary)
    if app_state.prepare_config_form is not None:
        update_prepare_config_form(window, app_state.prepare_config_form)
    if app_state.prepare_crop_zones_form is not None:
        update_prepare_crop_zones_form(window, app_state.prepare_crop_zones_form)
    if app_state.ocr_summary is not None:
        update_ocr_tab(window, app_state.ocr_summary)
        update_ocr_config_options(window, app_state.ocr_summary)
    if app_state.ocr_config_form is not None:
        update_ocr_config_form(window, app_state.ocr_config_form)
    if app_state.review_summary is not None:
        update_review_tab(window, app_state.review_summary)
        if app_state.review_summary.items:
            _apply_review_selection(
                window,
                project_root=dashboard.project_root,
                summary=app_state.review_summary,
                item=app_state.review_summary.items[0],
            )
    if app_state.package_summary is not None:
        update_package_tab(window, app_state.package_summary)
        update_package_config_form(
            window,
            load_package_config_form(dashboard.project_root),
        )
    if app_state.error_message is not None:
        window[status_key].update(
            f"Loaded project: {dashboard.project_name} | Warning: {app_state.error_message}"
        )
    else:
        window[status_key].update(f"Loaded project: {dashboard.project_name}")
    window.set_title(f"VOCra - {dashboard.project_name}")
    return dashboard.project_root


def _create_project(
    window: sg.Window,
    *,
    video_path: Path,
    project_root: Path,
    project_path_key: str,
    status_key: str,
) -> Path | None:
    try:
        app_state = create_project_state(video_path, project_root)
    except ProjectWorkspaceError as exc:
        message = str(exc)
        window[status_key].update(message)
        sg.popup_error(message, title="VOCra")
        return None

    dashboard = app_state.dashboard
    if dashboard is None:
        window[status_key].update("Project created, but dashboard state was empty.")
        return None

    window[project_path_key].update(str(dashboard.project_root))
    update_project_tab(window, dashboard)
    update_recent_projects(window, app_state.recent_projects)
    _sync_prepare_preview_context(window, app_state)
    if app_state.prepare_summary is not None:
        update_prepare_tab(window, app_state.prepare_summary)
    if app_state.prepare_config_form is not None:
        update_prepare_config_form(window, app_state.prepare_config_form)
    if app_state.prepare_crop_zones_form is not None:
        update_prepare_crop_zones_form(window, app_state.prepare_crop_zones_form)
    if app_state.ocr_summary is not None:
        update_ocr_tab(window, app_state.ocr_summary)
        update_ocr_config_options(window, app_state.ocr_summary)
    if app_state.ocr_config_form is not None:
        update_ocr_config_form(window, app_state.ocr_config_form)
    if app_state.review_summary is not None:
        update_review_tab(window, app_state.review_summary)
        if app_state.review_summary.items:
            _apply_review_selection(
                window,
                project_root=dashboard.project_root,
                summary=app_state.review_summary,
                item=app_state.review_summary.items[0],
            )
    if app_state.package_summary is not None:
        update_package_tab(window, app_state.package_summary)
        update_package_config_form(
            window,
            load_package_config_form(dashboard.project_root),
        )
    if app_state.error_message is not None:
        window[status_key].update(
            f"Created project: {dashboard.project_name} | Warning: {app_state.error_message}"
        )
    else:
        window[status_key].update(f"Created project: {dashboard.project_name}")
    window.set_title(f"VOCra - {dashboard.project_name}")
    return dashboard.project_root


def _open_project_folder(project_root: Path) -> None:
    resolved = project_root.expanduser().resolve()
    if os.name == "nt":
        os.startfile(str(resolved))
        return
    subprocess.run(["xdg-open", str(resolved)], check=False)


def _refresh_prepare_summary(
    window: sg.Window,
    project_root: Path,
    *,
    status_key: str,
) -> None:
    summary = load_prepare_stage_summary(project_root)
    update_prepare_tab(window, summary)
    window[status_key].update("Refreshed Prepare summary.")


def _refresh_ocr_summary(
    window: sg.Window,
    project_root: Path,
    *,
    status_key: str,
) -> OcrStageSummary:
    summary = load_ocr_stage_summary(project_root)
    update_ocr_tab(window, summary)
    update_ocr_config_options(window, summary)
    selected_run_id = str(window[OCR_RUN_ID_KEY].get() or "").strip()
    selected_run = find_ocr_run_item(summary, selected_run_id)
    if selected_run is not None:
        set_selected_ocr_run(window, selected_run)
    window[status_key].update("Refreshed OCR summary.")
    return summary


def _refresh_review_summary(
    window: sg.Window,
    project_root: Path,
    *,
    status_key: str,
) -> ReviewStageSummary:
    requested_prepare_run = str(window[REVIEW_PREPARE_RUN_KEY].get() or "").strip()
    requested_ocr_run = str(window[REVIEW_OCR_RUN_KEY].get() or "").strip()
    requested_filter = str(window[REVIEW_FILTER_KEY].get() or "all").strip() or "all"
    summary = load_review_stage_summary(
        project_root,
        prepare_run=requested_prepare_run or None,
        ocr_run=requested_ocr_run or None,
        filter_name=requested_filter,
    )
    update_review_tab(window, summary)
    selected_segment_id = str(window[REVIEW_SELECTED_SEGMENT_ID_KEY].get() or "").strip()
    selected_item = find_review_item(summary, selected_segment_id)
    if selected_item is None and summary.items:
        selected_item = summary.items[0]
    if selected_item is not None:
        _apply_review_selection(
            window,
            project_root=project_root,
            summary=summary,
            item=selected_item,
        )
    else:
        clear_selected_review_item(window)
    set_review_save_state(window, "Review save is idle.")
    window[status_key].update("Refreshed Review items.")
    return summary


def _refresh_review_compare_summary(
    window: sg.Window,
    project_root: Path,
    review_summary: ReviewStageSummary | None,
) -> OcrComparisonSummary | None:
    if review_summary is None:
        clear_review_compare(window)
        return None

    summary = load_ocr_comparison_summary(
        project_root,
        prepare_run=review_summary.selected_prepare_run or None,
        target_ocr_run=review_summary.selected_ocr_run or None,
        source_ocr_runs=get_review_compare_source_runs(
            {
                REVIEW_COMPARE_SOURCE_RUNS_KEY: window[REVIEW_COMPARE_SOURCE_RUNS_KEY].get(),
            }
        ),
    )
    update_review_compare_controls(window, summary)
    selected_segment_id = str(window[REVIEW_SELECTED_SEGMENT_ID_KEY].get() or "").strip()
    if not selected_segment_id and review_summary.items:
        selected_segment_id = review_summary.items[0].segment_id
    _apply_review_compare_selection(
        window,
        summary=summary,
        segment_id=selected_segment_id,
    )
    return summary


def _apply_review_compare_selection(
    window: sg.Window,
    *,
    summary: OcrComparisonSummary | None,
    segment_id: str,
) -> None:
    if summary is None:
        clear_review_compare(window)
        return
    comparison_item = find_ocr_comparison_item(summary, segment_id)
    if comparison_item is None:
        window[REVIEW_COMPARE_TABLE_KEY].update(values=[])
        window[REVIEW_COMPARE_STATUS_KEY].update(
            "No compare candidates are available for the currently selected Review segment."
        )
        return
    set_selected_review_compare_item(window, comparison_item)


def _refresh_package_summary(
    window: sg.Window,
    project_root: Path,
    *,
    status_key: str,
) -> PackageStageSummary:
    requested_prepare_run = str(window[PACKAGE_PREPARE_RUN_KEY].get() or "").strip()
    requested_ocr_run = str(window[PACKAGE_OCR_RUN_KEY].get() or "").strip()
    requested_review_policy = str(window[PACKAGE_REVIEW_POLICY_KEY].get() or "auto").strip()
    summary = load_package_stage_summary(
        project_root,
        prepare_run=requested_prepare_run or None,
        ocr_run=requested_ocr_run or None,
        review_state_policy=requested_review_policy or "auto",
    )
    update_package_tab(window, summary)
    selected_run_id = str(window[PACKAGE_SELECTED_RUN_ID_KEY].get() or "").strip()
    selected_run = find_package_run_item(summary, selected_run_id)
    if selected_run is not None:
        set_selected_package_run(window, selected_run)
    set_package_preview_state(window, "Package preview is idle.")
    window[status_key].update("Refreshed Package summary.")
    return summary


def _refresh_prepare_config(
    window: sg.Window,
    project_root: Path,
    *,
    status_key: str,
) -> None:
    form = load_prepare_config_form(project_root)
    update_prepare_config_form(window, form)
    window[status_key].update("Reloaded Prepare config.")


def _refresh_prepare_crop_zones(
    window: sg.Window,
    project_root: Path,
    *,
    status_key: str,
) -> None:
    form = load_prepare_crop_zones_form(project_root)
    update_prepare_crop_zones_form(window, form)
    window[status_key].update("Reloaded crop zones.")


def _persist_prepare_editor_state(
    window: sg.Window,
    project_root: Path,
    values: dict[str, object],
    *,
    status_key: str,
) -> bool:
    try:
        saved_config = save_prepare_config_form(
            project_root,
            build_prepare_config_form(values),
        )
        saved_crop_zones = save_prepare_crop_zones_form(
            project_root,
            build_prepare_crop_zones_form(
                values,
                use_fullframe=saved_config.use_fullframe,
            ),
            use_fullframe=saved_config.use_fullframe,
        )
    except ProjectWorkspaceError as exc:
        message = str(exc)
        window[status_key].update(message)
        sg.popup_error(message, title="VOCra")
        return False

    update_prepare_config_form(window, saved_config)
    update_prepare_crop_zones_form(window, saved_crop_zones)
    return True


def _save_prepare_config(
    window: sg.Window,
    project_root: Path,
    values: dict[str, object],
    *,
    status_key: str,
) -> None:
    try:
        form = build_prepare_config_form(values)
        saved_form = save_prepare_config_form(project_root, form)
    except ProjectWorkspaceError as exc:
        message = str(exc)
        window[status_key].update(message)
        sg.popup_error(message, title="VOCra")
        return

    update_prepare_config_form(window, saved_form)
    _update_prepare_preview_target_from_form(window, saved_form.time_start_ms)
    _refresh_prepare_crop_zones(window, project_root, status_key=status_key)
    _refresh_prepare_summary(window, project_root, status_key=status_key)
    window[status_key].update("Saved Prepare config.")


def _load_prepare_preview(
    window: sg.Window,
    project_root: Path,
    values: dict[str, object],
    *,
    status_key: str,
) -> PreparePreviewFrame | None:
    raw_target = values.get("-PREPARE-PREVIEW-TARGET-", 0)
    try:
        target_ms = max(int(float(raw_target)), 0)
    except (TypeError, ValueError):
        window[status_key].update("Preview target must be a numeric millisecond value.")
        return

    try:
        preview = load_prepare_preview_with_crop_overlay(
            project_root,
            target_ms=target_ms,
            form=build_prepare_crop_zones_form(
                values,
                use_fullframe=bool(values.get("-PREPARE-USE-FULLFRAME-", False)),
            ),
            use_fullframe=bool(values.get("-PREPARE-USE-FULLFRAME-", False)),
        )
    except ProjectWorkspaceError as exc:
        message = str(exc)
        window[status_key].update(message)
        sg.popup_error(message, title="VOCra")
        return None

    update_prepare_preview(window, preview)
    window[status_key].update(f"Loaded preview frame near {preview.actual_ms} ms.")
    return preview


def _save_prepare_crop_zones(
    window: sg.Window,
    project_root: Path,
    values: dict[str, object],
    *,
    status_key: str,
) -> PreparePreviewFrame | None:
    try:
        saved_form = save_prepare_crop_zones_form(
            project_root,
            build_prepare_crop_zones_form(
                values,
                use_fullframe=bool(values.get("-PREPARE-USE-FULLFRAME-", False)),
            ),
            use_fullframe=bool(values.get("-PREPARE-USE-FULLFRAME-", False)),
        )
    except ProjectWorkspaceError as exc:
        message = str(exc)
        window[status_key].update(message)
        sg.popup_error(message, title="VOCra")
        return None

    update_prepare_crop_zones_form(window, saved_form)
    _refresh_prepare_summary(window, project_root, status_key=status_key)
    preview = _load_prepare_preview(window, project_root, values, status_key=status_key)
    if values.get("-PREPARE-USE-FULLFRAME-"):
        window[status_key].update("Saved crop zones in full-frame mode.")
    else:
        window[status_key].update("Saved crop zones.")
    return preview


def _sync_prepare_preview_context(window: sg.Window, app_state) -> None:
    dashboard = app_state.dashboard
    if dashboard is None:
        set_prepare_preview_context(
            window,
            duration_ms=0,
            target_ms=0,
            source_available=False,
        )
        return
    target_ms = 0
    if app_state.prepare_config_form is not None:
        try:
            target_ms = max(int(app_state.prepare_config_form.time_start_ms), 0)
        except ValueError:
            target_ms = 0
    set_prepare_preview_context(
        window,
        duration_ms=dashboard.source.duration_ms,
        target_ms=target_ms,
        source_available=dashboard.source.exists,
    )


def _update_prepare_preview_target_from_form(window: sg.Window, start_time_ms: str) -> None:
    try:
        target_ms = max(int(start_time_ms), 0)
    except ValueError:
        return
    window["-PREPARE-PREVIEW-TARGET-"].update(value=target_ms)


def _prime_prepare_preview(
    window: sg.Window,
    project_root: Path,
    *,
    status_key: str,
) -> PreparePreviewFrame | None:
    try:
        crop_form = load_prepare_crop_zones_form(project_root)
        config_form = load_prepare_config_form(project_root)
        target_ms = max(int(config_form.time_start_ms), 0)
        preview = load_prepare_preview_with_crop_overlay(
            project_root,
            target_ms=target_ms,
            form=crop_form,
            use_fullframe=crop_form.use_fullframe,
        )
    except (ProjectWorkspaceError, TypeError, ValueError):
        return None

    update_prepare_preview(window, preview)
    set_prepare_selection_state(
        window,
        "Preview loaded. Drag to create a selection, or stage the active zone to move/resize it on the preview.",
        can_stage=True,
    )
    window[status_key].update(f"Loaded project and primed Prepare preview near {preview.actual_ms} ms.")
    return preview


def _parse_preview_point(raw_value: object) -> tuple[float, float] | None:
    if not isinstance(raw_value, tuple) or len(raw_value) != 2:
        return None
    try:
        return (float(raw_value[0]), float(raw_value[1]))
    except (TypeError, ValueError):
        return None


def _execute_prepare_run(
    project_root: Path,
    window: sg.Window,
    cancel_event: threading.Event | None,
) -> tuple[str, object]:
    try:
        outcome = run_prepare_from_project(
            project_root,
            progress=lambda event: window.write_event_value("-PREPARE-RUN-PROGRESS-", event),
            cancel_requested=(None if cancel_event is None else cancel_event.is_set),
        )
    except PrepareCancelledError as exc:
        return ("cancelled", str(exc))
    except Exception as exc:  # noqa: BLE001
        return ("error", str(exc))
    return ("ok", outcome)


def _execute_ocr_run(
    project_root: Path,
    form,
    *,
    action: str,
) -> tuple[str, object]:
    try:
        if action == "-RUN-OCR-":
            outcome = run_ocr_from_project(project_root, form)
        elif action == "-RESUME-OCR-FAILED-":
            outcome = resume_failed_ocr_from_project(project_root, form)
        elif action == "-RERUN-OCR-EMPTY-":
            outcome = rerun_empty_ocr_from_project(project_root, form)
        else:
            raise ValueError(f"Unsupported OCR GUI action: {action}")
    except Exception as exc:  # noqa: BLE001
        return ("error", str(exc))
    return ("ok", outcome)


def _execute_ocr_backend_test(form) -> tuple[str, object]:
    try:
        outcome = test_ocr_backend_connection(form)
    except Exception as exc:  # noqa: BLE001
        return ("error", str(exc))
    return ("ok", outcome)


def _format_prepare_progress_line(progress) -> str:
    suffix = ""
    if progress.current is not None and progress.total is not None:
        suffix = f" ({progress.current}/{progress.total})"
    elif progress.percent is not None:
        suffix = f" ({progress.percent:.1f}%)"
    return f"[{progress.stage}] {progress.message}{suffix}"


def _resolve_ocr_action_labels(event: str) -> tuple[str, str, str]:
    if event == "-RUN-OCR-":
        return (
            "OCR run",
            "Started OCR run.",
            "OCR is running through the persisted prepare artifacts. Summary will refresh on completion.",
        )
    if event == "-RESUME-OCR-FAILED-":
        return (
            "Resume Failed Only",
            "Started Resume Failed Only for the selected OCR run.",
            "OCR is rerunning only failed segments for the selected run. Summary will refresh on completion.",
        )
    if event == "-RERUN-OCR-EMPTY-":
        return (
            "Rerun Empty Only",
            "Started Rerun Empty Only for the selected OCR run.",
            "OCR is rerunning only empty-text segments for the selected run. Summary will refresh on completion.",
        )
    raise ValueError(f"Unsupported OCR GUI action: {event}")


def _resolve_active_ocr_run(
    summary: OcrStageSummary,
    values: dict[str, object],
):
    selected_run_id = str(values.get(OCR_RUN_ID_KEY, "")).strip()
    if selected_run_id:
        selected_run = find_ocr_run_item(summary, selected_run_id)
        if selected_run is not None:
            return selected_run
    return latest_ocr_run_item(summary)


def _resolve_active_package_run(
    window: sg.Window,
    summary: PackageStageSummary | None,
):
    if summary is None:
        return None
    selected_run_id = str(window[PACKAGE_SELECTED_RUN_ID_KEY].get() or "").strip()
    if selected_run_id:
        selected_run = find_package_run_item(summary, selected_run_id)
        if selected_run is not None:
            return selected_run
    return latest_package_run_item(summary)


def _apply_review_selection(
    window: sg.Window,
    *,
    project_root: Path,
    summary: ReviewStageSummary,
    item: ReviewListItem,
) -> None:
    set_selected_review_item(window, item)
    for index, candidate in enumerate(summary.items):
        if candidate.segment_id == item.segment_id:
            select_review_table_row(window, index)
            break
    detail = load_review_selection_detail(
        project_root,
        ocr_run=summary.selected_ocr_run,
        item=item,
    )
    set_selected_review_detail(window, detail)


def _normalize_review_form_for_save(
    values: dict[str, object],
    summary: ReviewStageSummary | None,
) -> ReviewEditForm:
    form = build_review_edit_form(values)
    if summary is None:
        return form
    selected_item = find_review_item(summary, form.segment_id)
    if selected_item is None:
        return form
    edited_text = form.edited_text.strip()
    original_text = selected_item.original_text.strip()
    if (
        form.review_status in {"pending", "accepted"}
        and edited_text != original_text
        and form.review_status != "rejected"
    ):
        return replace(form, review_status="edited")
    return form


def _map_review_shortcut_event(
    window: sg.Window,
    event: object,
    *,
    review_tab_active: bool,
) -> str | None:
    if not review_tab_active:
        return None
    if event == "-REVIEW-SHORTCUT-SAVE-":
        return "-SAVE-REVIEW-"
    if _review_shortcuts_should_defer_to_text_input(window):
        return None
    if event == "-REVIEW-SHORTCUT-ACCEPT-":
        return "-REVIEW-SET-ACCEPTED-"
    if event == "-REVIEW-SHORTCUT-EDIT-":
        return "__review_edit__"
    if event == "-REVIEW-SHORTCUT-REJECT-":
        return "-REVIEW-SET-REJECTED-"
    if event == "-REVIEW-SHORTCUT-NEXT-":
        return REVIEW_NEXT_KEY
    if event == "-REVIEW-SHORTCUT-PREVIOUS-":
        return REVIEW_PREVIOUS_KEY
    return None


def _review_shortcuts_should_defer_to_text_input(window: sg.Window) -> bool:
    try:
        focus_widget = window.TKroot.focus_get()
    except AttributeError:
        return False
    if focus_widget is None:
        return False
    try:
        widget_class = str(focus_widget.winfo_class())
    except Exception:  # noqa: BLE001
        return False
    return widget_class in {"Text", "Entry", "TCombobox", "Spinbox"}
