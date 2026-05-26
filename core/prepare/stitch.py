"""Stitch-grid helpers extracted from legacy VideOCR prepare logic."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

Polygon: TypeAlias = tuple[tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]]


@dataclass(frozen=True)
class StitchTilePlacement:
    frame_idx: int
    zone_idx: int
    x: int
    y: int
    width: int
    height: int
    source_frame_indices: tuple[int, ...] = ()


@dataclass(frozen=True)
class StitchLayout:
    file_name: str
    file_path: Path
    canvas_width: int
    canvas_height: int
    placements: tuple[StitchTilePlacement, ...]


@dataclass(frozen=True)
class PolygonIntersection:
    polygon: Polygon
    placement: StitchTilePlacement


def compute_batch_limit(
    tile_width: int,
    tile_height: int,
    *,
    max_width: int,
    max_height: int,
    grid_spacing: int,
) -> int:
    """Calculate how many crops fit inside a stitched grid."""
    cols = max(1, (max_width + grid_spacing) // (tile_width + grid_spacing))
    rows = max(1, (max_height + grid_spacing) // (tile_height + grid_spacing))
    return cols * rows


def build_stitch_layout(
    frame_indices: list[int],
    *,
    zone_idx: int,
    counter: int,
    prefix: str,
    out_dir: Path,
    tile_width: int,
    tile_height: int,
    max_width: int,
    grid_spacing: int,
    zero_pad_length: int,
    source_frame_indices_by_frame: dict[int, tuple[int, ...]] | None = None,
) -> StitchLayout:
    """Map frame indices into deterministic stitched-grid positions."""
    cols = max(1, (max_width + grid_spacing) // (tile_width + grid_spacing))
    actual_cols = min(len(frame_indices), cols)
    actual_rows = (len(frame_indices) + cols - 1) // cols
    canvas_width = actual_cols * tile_width + (actual_cols - 1) * grid_spacing
    canvas_height = actual_rows * tile_height + (actual_rows - 1) * grid_spacing

    file_name = f"{prefix}_{counter:0{zero_pad_length}d}_zone{zone_idx}.jpg"
    placements: list[StitchTilePlacement] = []
    for index, frame_idx in enumerate(frame_indices):
        row_idx = index // cols
        col_idx = index % cols
        x_offset = col_idx * (tile_width + grid_spacing)
        y_offset = row_idx * (tile_height + grid_spacing)
        placements.append(
            StitchTilePlacement(
                frame_idx=frame_idx,
                zone_idx=zone_idx,
                x=x_offset,
                y=y_offset,
                width=tile_width,
                height=tile_height,
                source_frame_indices=(
                    (frame_idx,)
                    if source_frame_indices_by_frame is None
                    else source_frame_indices_by_frame.get(frame_idx, (frame_idx,))
                ),
            )
        )

    return StitchLayout(
        file_name=file_name,
        file_path=out_dir / file_name,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        placements=tuple(placements),
    )


def unstitch_polygon(
    polygon: Polygon,
    placements: tuple[StitchTilePlacement, ...],
) -> tuple[PolygonIntersection, ...]:
    """Map a stitched-grid polygon back into one or more tile-local polygons."""
    poly_min_x = min(point[0] for point in polygon)
    poly_max_x = max(point[0] for point in polygon)
    poly_min_y = min(point[1] for point in polygon)
    poly_max_y = max(point[1] for point in polygon)

    intersections: list[PolygonIntersection] = []
    for placement in placements:
        cell_min_x = placement.x
        cell_max_x = placement.x + placement.width
        cell_min_y = placement.y
        cell_max_y = placement.y + placement.height

        if (
            poly_min_x < cell_max_x
            and poly_max_x > cell_min_x
            and poly_min_y < cell_max_y
            and poly_max_y > cell_min_y
        ):
            inter_min_x = max(poly_min_x, cell_min_x)
            inter_max_x = min(poly_max_x, cell_max_x)
            inter_min_y = max(poly_min_y, cell_min_y)
            inter_max_y = min(poly_max_y, cell_max_y)

            if inter_max_x - inter_min_x < 5 or inter_max_y - inter_min_y < 5:
                continue

            local_polygon: Polygon = (
                (inter_min_x - placement.x, inter_min_y - placement.y),
                (inter_max_x - placement.x, inter_min_y - placement.y),
                (inter_max_x - placement.x, inter_max_y - placement.y),
                (inter_min_x - placement.x, inter_max_y - placement.y),
            )
            intersections.append(
                PolygonIntersection(polygon=local_polygon, placement=placement)
            )

    if intersections:
        return tuple(intersections)

    centroid_x = sum(point[0] for point in polygon) / 4.0
    centroid_y = sum(point[1] for point in polygon) / 4.0
    nearest = min(
        placements,
        key=lambda placement: (
            (centroid_x - (placement.x + placement.width / 2.0)) ** 2
            + (centroid_y - (placement.y + placement.height / 2.0)) ** 2
        ),
    )
    local_polygon = tuple(
        (point[0] - nearest.x, point[1] - nearest.y) for point in polygon
    )
    return (PolygonIntersection(polygon=local_polygon, placement=nearest),)
