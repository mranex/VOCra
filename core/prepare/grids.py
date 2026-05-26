"""Helpers for detector-ready stitched grid images."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from vocra.core.prepare.sampler import SampledFrame, SampledZoneFrame
from vocra.core.prepare.stitch import (
    StitchLayout,
    build_stitch_layout,
    compute_batch_limit,
)


@dataclass(frozen=True)
class PreparedDetectionGrid:
    layout: StitchLayout
    image: Any


def build_detection_grids(
    sampled_frames: tuple[SampledFrame, ...],
    *,
    out_dir: Path,
    prefix: str = "det_stitched",
    max_width: int = 1500,
    max_height: int = 1500,
    grid_spacing: int = 10,
    zero_pad_length: int = 8,
) -> tuple[PreparedDetectionGrid, ...]:
    """Batch sampled zone crops into stitched detector grid images."""
    frames_by_zone: dict[int, list[SampledZoneFrame]] = defaultdict(list)
    for sampled_frame in sorted(sampled_frames, key=lambda frame: frame.frame_idx):
        for zone_frame in sampled_frame.zones:
            frames_by_zone[zone_frame.zone_idx].append(zone_frame)

    prepared_grids: list[PreparedDetectionGrid] = []
    counter = 0

    for zone_idx in sorted(frames_by_zone):
        zone_frames = frames_by_zone[zone_idx]
        if not zone_frames:
            continue

        tile_height, tile_width = _image_shape(zone_frames[0].image)
        batch_limit = compute_batch_limit(
            tile_width,
            tile_height,
            max_width=max_width,
            max_height=max_height,
            grid_spacing=grid_spacing,
        )

        for batch_start in range(0, len(zone_frames), batch_limit):
            batch = zone_frames[batch_start : batch_start + batch_limit]
            _validate_batch_shapes(batch, tile_height=tile_height, tile_width=tile_width)

            layout = build_stitch_layout(
                [frame.frame_idx for frame in batch],
                zone_idx=zone_idx,
                counter=counter,
                prefix=prefix,
                out_dir=out_dir,
                tile_width=tile_width,
                tile_height=tile_height,
                max_width=max_width,
                grid_spacing=grid_spacing,
                zero_pad_length=zero_pad_length,
                source_frame_indices_by_frame={
                    frame.frame_idx: frame.source_frame_indices or (frame.frame_idx,)
                    for frame in batch
                },
            )
            prepared_grids.append(
                PreparedDetectionGrid(
                    layout=layout,
                    image=_render_grid_image(layout, batch),
                )
            )
            counter += 1

    return tuple(prepared_grids)


def build_detection_grid_indexes(
    prepared_grids: tuple[PreparedDetectionGrid, ...],
) -> tuple[dict[str, StitchLayout], dict[Path, Any]]:
    """Build layout and image lookups for detector/parsing orchestration."""
    return (
        {grid.layout.file_name: grid.layout for grid in prepared_grids},
        {grid.layout.file_path: grid.image for grid in prepared_grids},
    )


def write_detection_grid_images(
    prepared_grids: tuple[PreparedDetectionGrid, ...],
) -> tuple[Path, ...]:
    """Persist prepared detection-grid images to their target file paths."""
    written_paths: list[Path] = []
    for grid in prepared_grids:
        grid.layout.file_path.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(grid.image).save(grid.layout.file_path, quality=80)
        written_paths.append(grid.layout.file_path)
    return tuple(written_paths)


def _render_grid_image(
    layout: StitchLayout,
    zone_frames: list[SampledZoneFrame],
) -> Any:
    first_image = zone_frames[0].image
    canvas = _build_canvas(
        first_image,
        canvas_height=layout.canvas_height,
        canvas_width=layout.canvas_width,
    )

    for placement, zone_frame in zip(layout.placements, zone_frames):
        image = zone_frame.image
        canvas[
            placement.y : placement.y + placement.height,
            placement.x : placement.x + placement.width,
        ] = image

    return canvas


def _build_canvas(
    source_image: Any,
    *,
    canvas_height: int,
    canvas_width: int,
) -> Any:
    if source_image.ndim == 2:
        return np.zeros(
            (canvas_height, canvas_width),
            dtype=source_image.dtype,
        )
    return np.zeros(
        (canvas_height, canvas_width, source_image.shape[2]),
        dtype=source_image.dtype,
    )


def _image_shape(image: Any) -> tuple[int, int]:
    height, width = image.shape[:2]
    return int(height), int(width)


def _validate_batch_shapes(
    zone_frames: list[SampledZoneFrame],
    *,
    tile_height: int,
    tile_width: int,
) -> None:
    for zone_frame in zone_frames:
        current_height, current_width = _image_shape(zone_frame.image)
        if current_height != tile_height or current_width != tile_width:
            raise ValueError(
                "All sampled zone images in a stitched grid batch must share the same size."
            )
