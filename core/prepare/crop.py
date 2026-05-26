"""Crop-zone helpers extracted from legacy VideOCR prepare logic."""

from __future__ import annotations

from dataclasses import dataclass

from vocra.core.prepare.models import CropZone


@dataclass(frozen=True)
class CropBounds:
    zone_idx: int
    x_start: int
    y_start: int
    x_end: int
    y_end: int
    midpoint_y: float


@dataclass(frozen=True)
class CropRenderPlan:
    zone_idx: int
    crop_x: int
    crop_y: int
    crop_width: int
    crop_height: int
    target_width: int
    target_height: int
    crop_filter: str
    scale_filter: str


def resolve_crop_zones(
    video_width: int,
    video_height: int,
    crop_zones: list[CropZone],
    *,
    use_fullframe: bool = False,
) -> tuple[CropBounds, ...]:
    """Validate crop origins and apply full-frame/default fallbacks."""
    if use_fullframe:
        return (
            CropBounds(
                zone_idx=0,
                x_start=0,
                y_start=0,
                x_end=video_width,
                y_end=video_height,
                midpoint_y=video_height / 2,
            ),
        )

    if not crop_zones:
        default_y_start = 2 * video_height // 3
        return (
            CropBounds(
                zone_idx=0,
                x_start=0,
                y_start=default_y_start,
                x_end=video_width,
                y_end=video_height,
                midpoint_y=default_y_start + (video_height // 6),
            ),
        )

    resolved: list[CropBounds] = []
    for zone in crop_zones:
        if zone.y >= video_height:
            raise ValueError(
                f"Crop Y position ({zone.y}) is outside video height ({video_height})."
            )
        if zone.x >= video_width:
            raise ValueError(
                f"Crop X position ({zone.x}) is outside video width ({video_width})."
            )
        resolved.append(
            CropBounds(
                zone_idx=zone.zone_idx,
                x_start=zone.x,
                y_start=zone.y,
                x_end=zone.x + zone.width,
                y_end=zone.y + zone.height,
                midpoint_y=zone.y + (zone.height / 2),
            )
        )
    return tuple(resolved)


def build_crop_render_plan(
    bounds: CropBounds,
    *,
    video_width: int,
    video_height: int,
    ocr_image_max_width: int,
    min_side: int = 64,
) -> CropRenderPlan:
    """Compute clipped crop bounds and OCR resize plan for PyAV filter graphs."""
    clipped_x_start = max(0, bounds.x_start)
    clipped_y_start = max(0, bounds.y_start)
    clipped_x_end = min(video_width, bounds.x_end)
    clipped_y_end = min(video_height, bounds.y_end)

    crop_width = max(2, (clipped_x_end - clipped_x_start) & ~1)
    crop_height = max(2, (clipped_y_end - clipped_y_start) & ~1)
    crop_x = clipped_x_start & ~1
    crop_y = clipped_y_start & ~1

    scale_ratio = 1.0
    if ocr_image_max_width and crop_width > ocr_image_max_width:
        scale_ratio = ocr_image_max_width / crop_width

    min_required_ratio = min_side / min(crop_width, crop_height)
    if scale_ratio < min_required_ratio:
        scale_ratio = min_required_ratio

    target_width = max(2, int(crop_width * scale_ratio) & ~1)
    target_height = max(2, int(crop_height * scale_ratio) & ~1)

    return CropRenderPlan(
        zone_idx=bounds.zone_idx,
        crop_x=crop_x,
        crop_y=crop_y,
        crop_width=crop_width,
        crop_height=crop_height,
        target_width=target_width,
        target_height=target_height,
        crop_filter=f"{crop_width}:{crop_height}:{crop_x}:{crop_y}",
        scale_filter=f"{target_width}:{target_height}:flags=area:threads=1",
    )
