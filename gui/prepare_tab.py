"""Prepare-tab widgets for the VOCra GUI."""

from __future__ import annotations

from typing import Any

import PySimpleGUI as sg

from vocra.app.models import (
    PrepareConfigForm,
    PrepareCropZonesForm,
    PreparePreviewFrame,
    PrepareStageSummary,
)
from vocra.app.service import render_prepare_stage_text
from vocra.gui.widgets import (
    PREPARE_ACTIVE_CROP_ZONE_KEY,
    PREPARE_CROP_EDIT_MODE_KEY,
    PREPARE_PREVIEW_GRAPH_KEY,
    build_prepare_preview_graph,
    render_prepare_preview_graph,
)

PREPARE_SUMMARY_KEY = "-PREPARE-SUMMARY-"
PREPARE_PREVIEW_TARGET_KEY = "-PREPARE-PREVIEW-TARGET-"
PREPARE_PREVIEW_META_KEY = "-PREPARE-PREVIEW-META-"
PREPARE_SELECTION_META_KEY = "-PREPARE-SELECTION-META-"
PREPARE_RUN_STATUS_KEY = "-PREPARE-RUN-STATUS-"
PREPARE_RUN_LOG_KEY = "-PREPARE-RUN-LOG-"
PREPARE_CROP_ZONE0_KEY = "-PREPARE-CROP-ZONE-0-"
PREPARE_CROP_ZONE1_KEY = "-PREPARE-CROP-ZONE-1-"
PREPARE_CROP_META_KEY = "-PREPARE-CROP-META-"
PREPARE_TIME_START_KEY = "-PREPARE-TIME-START-MS-"
PREPARE_TIME_END_KEY = "-PREPARE-TIME-END-MS-"
PREPARE_FRAMES_TO_SKIP_KEY = "-PREPARE-FRAMES-TO-SKIP-"
PREPARE_SSIM_KEY = "-PREPARE-SSIM-THRESHOLD-"
PREPARE_TIGHT_SSIM_KEY = "-PREPARE-TIGHT-SSIM-THRESHOLD-"
PREPARE_SUBTITLE_POSITION_KEY = "-PREPARE-SUBTITLE-POSITION-"
PREPARE_MAX_WIDTH_KEY = "-PREPARE-MAX-WIDTH-"
PREPARE_BRIGHTNESS_KEY = "-PREPARE-BRIGHTNESS-"
PREPARE_USE_FULLFRAME_KEY = "-PREPARE-USE-FULLFRAME-"
PREPARE_DETECTOR_NAME_KEY = "-PREPARE-DETECTOR-NAME-"
PREPARE_DEBUG_MODE_KEY = "-PREPARE-DEBUG-MODE-"
PREPARE_CONFIG_META_KEY = "-PREPARE-CONFIG-META-"

_SUBTITLE_POSITION_OPTIONS = ("left", "center", "right", "any")
_CROP_EDIT_MODE_OPTIONS = (
    "create",
    "move",
    "resize-bottom-right",
    "resize-top-left",
    "resize-top-right",
    "resize-bottom-left",
)


def build_prepare_tab() -> list[list[Any]]:
    return [
        [
            sg.Frame(
                "Video Preview",
                [
                    [build_prepare_preview_graph()],
                    [
                        sg.Text("Preview target (ms)", size=(16, 1)),
                        sg.Slider(
                            range=(0, 0),
                            default_value=0,
                            resolution=1,
                            orientation="h",
                            key=PREPARE_PREVIEW_TARGET_KEY,
                            expand_x=True,
                            disable_number_display=False,
                            enable_events=False,
                            disabled=True,
                        ),
                    ],
                    [sg.Text("Load a project to enable preview.", key=PREPARE_PREVIEW_META_KEY)],
                    [
                        sg.Text("Active zone", size=(16, 1)),
                        sg.Combo(
                            ("0", "1"),
                            default_value="0",
                            readonly=True,
                            key=PREPARE_ACTIVE_CROP_ZONE_KEY,
                            size=(6, 1),
                        ),
                        sg.Text("Mode", size=(6, 1)),
                        sg.Combo(
                            _CROP_EDIT_MODE_OPTIONS,
                            default_value="create",
                            readonly=True,
                            key=PREPARE_CROP_EDIT_MODE_KEY,
                            size=(18, 1),
                        ),
                    ],
                    [
                        sg.Button(
                            "Stage Active Zone",
                            key="-STAGE-PREPARE-ACTIVE-ZONE-",
                            disabled=True,
                        ),
                        sg.Button(
                            "Apply Drag To Zone",
                            key="-APPLY-PREPARE-CROP-SELECTION-",
                            disabled=True,
                        ),
                        sg.Button(
                            "Clear Drag",
                            key="-CLEAR-PREPARE-CROP-SELECTION-",
                            disabled=True,
                        ),
                    ],
                    [
                        sg.Text(
                            "Load a preview, then drag inside it to stage a crop selection.",
                            key=PREPARE_SELECTION_META_KEY,
                            expand_x=True,
                        )
                    ],
                    [
                        sg.Button("Load Preview Frame", key="-LOAD-PREPARE-PREVIEW-", disabled=True),
                        sg.Button("Use Start Time", key="-USE-PREPARE-START-TIME-", disabled=True),
                    ],
                ],
                expand_x=True,
            )
        ],
        [
            sg.Frame(
                "Crop Zones",
                [
                    [
                        sg.Text("Zone 0", size=(14, 1)),
                        sg.Input("", key=PREPARE_CROP_ZONE0_KEY, expand_x=True),
                    ],
                    [
                        sg.Text("Zone 1", size=(14, 1)),
                        sg.Input("", key=PREPARE_CROP_ZONE1_KEY, expand_x=True),
                    ],
                    [sg.Text("", key=PREPARE_CROP_META_KEY, expand_x=True)],
                    [
                        sg.Button("Save Crop Zones", key="-SAVE-PREPARE-CROP-ZONES-"),
                        sg.Button("Reload Crop Zones", key="-RELOAD-PREPARE-CROP-ZONES-"),
                        sg.Button("Clear Crop Zones", key="-CLEAR-PREPARE-CROP-ZONES-"),
                    ],
                ],
                expand_x=True,
            )
        ],
        [
            sg.Frame(
                "Prepare Config",
                [
                    [
                        sg.Text("Start ms", size=(14, 1)),
                        sg.Input("", key=PREPARE_TIME_START_KEY, size=(12, 1)),
                        sg.Text("End ms", size=(10, 1)),
                        sg.Input("", key=PREPARE_TIME_END_KEY, size=(12, 1)),
                    ],
                    [
                        sg.Text("Frames to skip", size=(14, 1)),
                        sg.Input("", key=PREPARE_FRAMES_TO_SKIP_KEY, size=(12, 1)),
                        sg.Text("SSIM", size=(10, 1)),
                        sg.Input("", key=PREPARE_SSIM_KEY, size=(12, 1)),
                    ],
                    [
                        sg.Text("Tight SSIM", size=(14, 1)),
                        sg.Input("", key=PREPARE_TIGHT_SSIM_KEY, size=(12, 1)),
                        sg.Text("Max width", size=(10, 1)),
                        sg.Input("", key=PREPARE_MAX_WIDTH_KEY, size=(12, 1)),
                    ],
                    [
                        sg.Text("Brightness", size=(14, 1)),
                        sg.Input("", key=PREPARE_BRIGHTNESS_KEY, size=(12, 1)),
                        sg.Text("Subtitle pos", size=(10, 1)),
                        sg.Combo(
                            _SUBTITLE_POSITION_OPTIONS,
                            default_value="center",
                            readonly=True,
                            key=PREPARE_SUBTITLE_POSITION_KEY,
                            size=(12, 1),
                        ),
                    ],
                    [
                        sg.Text("Detector", size=(14, 1)),
                        sg.Input("", key=PREPARE_DETECTOR_NAME_KEY, size=(38, 1)),
                    ],
                    [
                        sg.Checkbox(
                            "Use full frame",
                            key=PREPARE_USE_FULLFRAME_KEY,
                            default=False,
                        ),
                        sg.Checkbox(
                            "Debug mode",
                            key=PREPARE_DEBUG_MODE_KEY,
                            default=False,
                        ),
                    ],
                    [sg.Text("", key=PREPARE_CONFIG_META_KEY, expand_x=True)],
                    [
                        sg.Button("Save Prepare Config", key="-SAVE-PREPARE-CONFIG-"),
                        sg.Button("Reload Prepare Config", key="-RELOAD-PREPARE-CONFIG-"),
                        sg.Button("Run Prepare", key="-RUN-PREPARE-"),
                        sg.Button("Stop Prepare", key="-STOP-PREPARE-", disabled=True),
                    ],
                    [sg.Text("Prepare run is idle.", key=PREPARE_RUN_STATUS_KEY, expand_x=True)],
                    [
                        sg.Multiline(
                            "",
                            key=PREPARE_RUN_LOG_KEY,
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
                "Prepare Summary",
                [
                    [
                        sg.Multiline(
                            "",
                            key=PREPARE_SUMMARY_KEY,
                            expand_x=True,
                            expand_y=True,
                            disabled=True,
                            size=(88, 16),
                        )
                    ]
                ],
                expand_x=True,
                expand_y=True,
            )
        ],
        [
            sg.Button("Refresh Prepare Summary", key="-REFRESH-PREPARE-"),
            sg.Button("Open Prepare Folder", key="-OPEN-PREPARE-FOLDER-"),
            sg.Button("Open Prepared Images", key="-OPEN-PREPARED-IMAGES-"),
            sg.Button("Open Prepare Config", key="-OPEN-PREPARE-CONFIG-"),
            sg.Button("Open Segment Manifest", key="-OPEN-SEGMENT-MANIFEST-"),
        ],
        [
            sg.Text(
                "Prepare tab now supports preview, visual crop editing, persisted config, and Prepare run controls.",
            )
        ],
    ]


def set_empty_prepare_tab(window: sg.Window) -> None:
    _update_prepare_config_form(window, _empty_prepare_config_form())
    update_prepare_crop_zones_form(window, _empty_prepare_crop_zones_form())
    set_prepare_preview_context(window, duration_ms=0, target_ms=0, source_available=False)
    set_prepare_selection_state(window, "Load a preview to start interactive crop selection.")
    set_prepare_run_state(window, "Prepare run is idle.")
    reset_prepare_run_log(window)
    window[PREPARE_SUMMARY_KEY].update(
        "Load a project to inspect Prepare artifacts and summary information."
    )


def update_prepare_tab(window: sg.Window, summary: PrepareStageSummary) -> None:
    window[PREPARE_SUMMARY_KEY].update(render_prepare_stage_text(summary))


def update_prepare_config_form(window: sg.Window, form: PrepareConfigForm) -> None:
    _update_prepare_config_form(window, form)


def update_prepare_crop_zones_form(window: sg.Window, form: PrepareCropZonesForm) -> None:
    window[PREPARE_CROP_ZONE0_KEY].update(form.zone_specs[0])
    window[PREPARE_CROP_ZONE1_KEY].update(form.zone_specs[1])
    mode = "full-frame" if form.use_fullframe else "crop-zones"
    window[PREPARE_CROP_META_KEY].update(
        f"Persisted zones: {form.persisted_zone_count} | Mode: {mode} | Format: x,y,width,height"
    )


def set_prepare_preview_context(
    window: sg.Window,
    *,
    duration_ms: int,
    target_ms: int,
    source_available: bool,
) -> None:
    maximum = max(int(duration_ms), 0)
    clamped_target = min(max(int(target_ms), 0), maximum)
    window[PREPARE_PREVIEW_TARGET_KEY].update(
        range=(0, maximum),
        value=clamped_target,
        disabled=not source_available,
    )
    window["-LOAD-PREPARE-PREVIEW-"].update(disabled=not source_available)
    window["-USE-PREPARE-START-TIME-"].update(disabled=not source_available)
    if source_available:
        window[PREPARE_PREVIEW_META_KEY].update(
            f"Preview ready. Duration: {maximum} ms | Target: {clamped_target} ms"
        )
    else:
        window[PREPARE_PREVIEW_META_KEY].update("Load a project to enable preview.")


def update_prepare_preview(window: sg.Window, preview: PreparePreviewFrame) -> None:
    render_prepare_preview_graph(window[PREPARE_PREVIEW_GRAPH_KEY], preview)
    window[PREPARE_PREVIEW_TARGET_KEY].update(value=preview.requested_ms)
    window[PREPARE_PREVIEW_META_KEY].update(
        "Target: "
        f"{preview.requested_ms} ms | Actual: {preview.actual_ms} ms | "
        f"Source: {preview.source_width}x{preview.source_height} | "
        f"Preview: {preview.display_width}x{preview.display_height}"
    )


def update_prepare_preview_selection(
    window: sg.Window,
    preview: PreparePreviewFrame | None,
    selection: tuple[int, int, int, int] | None,
) -> None:
    render_prepare_preview_graph(window[PREPARE_PREVIEW_GRAPH_KEY], preview, selection=selection)


def set_prepare_selection_state(
    window: sg.Window,
    message: str,
    *,
    can_apply: bool = False,
    can_clear: bool = False,
    can_stage: bool = False,
) -> None:
    window[PREPARE_SELECTION_META_KEY].update(message)
    window["-APPLY-PREPARE-CROP-SELECTION-"].update(disabled=not can_apply)
    window["-CLEAR-PREPARE-CROP-SELECTION-"].update(disabled=not can_clear)
    window["-STAGE-PREPARE-ACTIVE-ZONE-"].update(disabled=not can_stage)


def set_prepare_run_state(
    window: sg.Window,
    message: str,
    *,
    running: bool = False,
) -> None:
    window[PREPARE_RUN_STATUS_KEY].update(message)
    window["-RUN-PREPARE-"].update(disabled=running)
    window["-STOP-PREPARE-"].update(disabled=not running)


def reset_prepare_run_log(window: sg.Window) -> None:
    window[PREPARE_RUN_LOG_KEY].update("")


def append_prepare_run_log(window: sg.Window, line: str) -> None:
    current = window[PREPARE_RUN_LOG_KEY].get() or ""
    next_value = f"{current}\n{line}".strip() if current else line
    window[PREPARE_RUN_LOG_KEY].update(next_value)


def build_prepare_crop_zones_form(
    values: dict[str, Any],
    *,
    use_fullframe: bool,
) -> PrepareCropZonesForm:
    return PrepareCropZonesForm(
        zone_specs=(
            str(values.get(PREPARE_CROP_ZONE0_KEY, "")),
            str(values.get(PREPARE_CROP_ZONE1_KEY, "")),
        ),
        persisted_zone_count=0,
        use_fullframe=use_fullframe,
    )


def build_prepare_config_form(values: dict[str, Any]) -> PrepareConfigForm:
    return PrepareConfigForm(
        time_start_ms=str(values.get(PREPARE_TIME_START_KEY, "")),
        time_end_ms=str(values.get(PREPARE_TIME_END_KEY, "")),
        frames_to_skip=str(values.get(PREPARE_FRAMES_TO_SKIP_KEY, "")),
        ssim_threshold=str(values.get(PREPARE_SSIM_KEY, "")),
        tight_box_ssim_threshold=str(values.get(PREPARE_TIGHT_SSIM_KEY, "")),
        subtitle_position=str(values.get(PREPARE_SUBTITLE_POSITION_KEY, "center")),
        ocr_image_max_width=str(values.get(PREPARE_MAX_WIDTH_KEY, "")),
        brightness_threshold=str(values.get(PREPARE_BRIGHTNESS_KEY, "")),
        use_fullframe=bool(values.get(PREPARE_USE_FULLFRAME_KEY, False)),
        detector_name=str(values.get(PREPARE_DETECTOR_NAME_KEY, "")),
        debug_mode=bool(values.get(PREPARE_DEBUG_MODE_KEY, False)),
        crop_zone_count=0,
        detector_config_keys=(),
    )


def _empty_prepare_config_form() -> PrepareConfigForm:
    return PrepareConfigForm(
        time_start_ms="0",
        time_end_ms="",
        frames_to_skip="1",
        ssim_threshold="0.92",
        tight_box_ssim_threshold="0.85",
        subtitle_position="center",
        ocr_image_max_width="720",
        brightness_threshold="",
        use_fullframe=False,
        detector_name="",
        debug_mode=False,
        crop_zone_count=0,
        detector_config_keys=(),
    )


def _empty_prepare_crop_zones_form() -> PrepareCropZonesForm:
    return PrepareCropZonesForm(
        zone_specs=("", ""),
        persisted_zone_count=0,
        use_fullframe=False,
    )


def _update_prepare_config_form(window: sg.Window, form: PrepareConfigForm) -> None:
    window[PREPARE_TIME_START_KEY].update(form.time_start_ms)
    window[PREPARE_TIME_END_KEY].update(form.time_end_ms)
    window[PREPARE_FRAMES_TO_SKIP_KEY].update(form.frames_to_skip)
    window[PREPARE_SSIM_KEY].update(form.ssim_threshold)
    window[PREPARE_TIGHT_SSIM_KEY].update(form.tight_box_ssim_threshold)
    window[PREPARE_SUBTITLE_POSITION_KEY].update(form.subtitle_position)
    window[PREPARE_MAX_WIDTH_KEY].update(form.ocr_image_max_width)
    window[PREPARE_BRIGHTNESS_KEY].update(form.brightness_threshold)
    window[PREPARE_USE_FULLFRAME_KEY].update(value=form.use_fullframe)
    window[PREPARE_DETECTOR_NAME_KEY].update(form.detector_name)
    window[PREPARE_DEBUG_MODE_KEY].update(value=form.debug_mode)
    detector_keys = ", ".join(form.detector_config_keys) if form.detector_config_keys else "none"
    window[PREPARE_CONFIG_META_KEY].update(
        f"Crop zones in config: {form.crop_zone_count} | Extra detector keys preserved: {detector_keys}"
    )
