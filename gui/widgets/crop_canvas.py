"""Helpers for the interactive Prepare preview canvas."""

from __future__ import annotations

from typing import Any

import PySimpleGUI as sg

from vocra.app.models import PreparePreviewFrame

PREPARE_PREVIEW_GRAPH_KEY = "-PREPARE-PREVIEW-GRAPH-"
PREPARE_ACTIVE_CROP_ZONE_KEY = "-PREPARE-ACTIVE-CROP-ZONE-"
PREPARE_CROP_EDIT_MODE_KEY = "-PREPARE-CROP-EDIT-MODE-"
PREPARE_PREVIEW_CANVAS_SIZE = (640, 360)


def build_prepare_preview_graph() -> Any:
    width, height = PREPARE_PREVIEW_CANVAS_SIZE
    return sg.Graph(
        canvas_size=(width, height),
        graph_bottom_left=(0, height),
        graph_top_right=(width, 0),
        background_color="black",
        key=PREPARE_PREVIEW_GRAPH_KEY,
        enable_events=True,
        drag_submits=True,
        border_width=1,
    )


def render_prepare_preview_graph(
    graph: sg.Graph,
    preview: PreparePreviewFrame | None,
    *,
    selection: tuple[int, int, int, int] | None = None,
) -> None:
    graph.erase()
    if preview is None:
        return
    graph.draw_image(data=preview.png_bytes, location=(0, 0))
    if selection is None:
        return
    x0, y0, x1, y1 = selection
    graph.draw_rectangle(
        (x0, y0),
        (x1, y1),
        line_color="#00E5FF",
        line_width=2,
    )


def normalize_preview_selection(
    start_xy: tuple[float, float] | None,
    end_xy: tuple[float, float] | None,
    *,
    display_width: int,
    display_height: int,
) -> tuple[int, int, int, int] | None:
    if start_xy is None or end_xy is None:
        return None
    if display_width <= 0 or display_height <= 0:
        return None

    x0 = _clamp_coordinate(start_xy[0], 0, display_width)
    y0 = _clamp_coordinate(start_xy[1], 0, display_height)
    x1 = _clamp_coordinate(end_xy[0], 0, display_width)
    y1 = _clamp_coordinate(end_xy[1], 0, display_height)

    left = min(x0, x1)
    top = min(y0, y1)
    right = max(x0, x1)
    bottom = max(y0, y1)
    if right - left < 2 or bottom - top < 2:
        return None
    return (left, top, right, bottom)


def move_preview_selection(
    selection: tuple[int, int, int, int],
    *,
    delta_x: float,
    delta_y: float,
    display_width: int,
    display_height: int,
) -> tuple[int, int, int, int]:
    left, top, right, bottom = selection
    width = max(right - left, 1)
    height = max(bottom - top, 1)
    moved_left = _clamp_coordinate(left + delta_x, 0, max(display_width - width, 0))
    moved_top = _clamp_coordinate(top + delta_y, 0, max(display_height - height, 0))
    return (
        moved_left,
        moved_top,
        moved_left + width,
        moved_top + height,
    )


def resize_preview_selection(
    selection: tuple[int, int, int, int],
    *,
    handle: str,
    target_xy: tuple[float, float],
    display_width: int,
    display_height: int,
) -> tuple[int, int, int, int] | None:
    left, top, right, bottom = selection
    target_x = _clamp_coordinate(target_xy[0], 0, display_width)
    target_y = _clamp_coordinate(target_xy[1], 0, display_height)
    minimum_size = 2

    if handle == "top-left":
        updated = (min(target_x, right - minimum_size), min(target_y, bottom - minimum_size), right, bottom)
    elif handle == "top-right":
        updated = (left, min(target_y, bottom - minimum_size), max(target_x, left + minimum_size), bottom)
    elif handle == "bottom-left":
        updated = (min(target_x, right - minimum_size), top, right, max(target_y, top + minimum_size))
    elif handle == "bottom-right":
        updated = (left, top, max(target_x, left + minimum_size), max(target_y, top + minimum_size))
    else:
        raise ValueError(f"Unsupported resize handle: {handle}")

    if updated[2] - updated[0] < minimum_size or updated[3] - updated[1] < minimum_size:
        return None
    return updated


def _clamp_coordinate(value: float, minimum: int, maximum: int) -> int:
    integer_value = int(round(float(value)))
    return min(max(integer_value, minimum), maximum)
