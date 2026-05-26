"""Prepare-tab app services for crop-zone editing and preview overlays."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, ImageDraw

from vocra.app.models import PrepareCropZonesForm, PreparePreviewFrame
from vocra.core.prepare.config import PREPARE_SCHEMA_VERSION, PrepareConfig
from vocra.core.prepare.models import CropZone
from vocra.core.project.manifest import (
    ManifestValidationError,
    read_json_file,
    write_json_file_atomic,
)
from vocra.core.project.schema import ProjectPaths
from vocra.core.project.workspace import (
    ProjectWorkspaceError,
    open_project,
    resolve_paths,
)
from vocra.core.video.capture import VideoCaptureError, open_video_capture
from vocra.core.video.preview import load_video_preview_frame


def load_prepare_crop_zones_form(project_root: Path) -> PrepareCropZonesForm:
    project = open_project(project_root)
    paths = resolve_paths(project.root)
    config = _load_prepare_config(paths)
    crop_zones, use_fullframe = _load_crop_zone_state(paths, config)
    if len(crop_zones) > 2:
        raise ProjectWorkspaceError(
            "Prepare crop editor currently supports at most 2 crop zones."
        )
    zone_specs = tuple(_format_zone_spec(zone) for zone in crop_zones[:2])
    padded_specs = zone_specs + ("",) * (2 - len(zone_specs))
    return PrepareCropZonesForm(
        zone_specs=padded_specs,
        persisted_zone_count=len(crop_zones),
        use_fullframe=use_fullframe,
    )


def save_prepare_crop_zones_form(
    project_root: Path,
    form: PrepareCropZonesForm,
    *,
    use_fullframe: bool,
) -> PrepareCropZonesForm:
    project = open_project(project_root)
    paths = resolve_paths(project.root)
    config = _load_prepare_config(paths)
    crop_zones = _parse_zone_specs(form.zone_specs)
    saved_config = PrepareConfig.from_dict(
        {
            **config.to_dict(),
            "crop_zones": [
                {
                    "zone_idx": zone.zone_idx,
                    "x": zone.x,
                    "y": zone.y,
                    "width": zone.width,
                    "height": zone.height,
                }
                for zone in crop_zones
            ],
            "use_fullframe": bool(use_fullframe),
        }
    )
    write_json_file_atomic(paths.prepare_config_file, saved_config.to_dict())
    write_crop_zones_artifact(paths, saved_config)
    return load_prepare_crop_zones_form(project.root)


def load_prepare_preview_with_crop_overlay(
    project_root: Path,
    *,
    target_ms: int,
    form: PrepareCropZonesForm | None = None,
    use_fullframe: bool | None = None,
    max_width: int = 640,
    max_height: int = 360,
    capture_factory=open_video_capture,
) -> PreparePreviewFrame:
    project = open_project(project_root)
    source_path = project.source.path
    if not source_path.exists():
        raise ProjectWorkspaceError(f"Source video is missing: {source_path}")

    if form is None:
        form = load_prepare_crop_zones_form(project.root)
    overlay_use_fullframe = form.use_fullframe if use_fullframe is None else bool(use_fullframe)
    crop_zones = _parse_zone_specs(form.zone_specs)

    try:
        preview = load_video_preview_frame(
            source_path,
            target_ms=target_ms,
            max_width=max_width,
            max_height=max_height,
            capture_factory=capture_factory,
        )
    except VideoCaptureError as exc:
        raise ProjectWorkspaceError(str(exc)) from exc

    rendered_bytes = _render_overlay_png(
        png_bytes=preview.png_bytes,
        source_width=preview.source_width,
        source_height=preview.source_height,
        display_width=preview.display_width,
        display_height=preview.display_height,
        crop_zones=crop_zones,
        use_fullframe=overlay_use_fullframe,
    )
    return PreparePreviewFrame(
        requested_ms=preview.requested_ms,
        actual_ms=preview.actual_ms,
        source_width=preview.source_width,
        source_height=preview.source_height,
        display_width=preview.display_width,
        display_height=preview.display_height,
        png_bytes=rendered_bytes,
    )


def preview_selection_to_crop_zone(
    preview: PreparePreviewFrame,
    *,
    zone_idx: int,
    start_xy: tuple[float, float],
    end_xy: tuple[float, float],
) -> CropZone:
    display_rect = _normalize_preview_rect(
        start_xy=start_xy,
        end_xy=end_xy,
        display_width=preview.display_width,
        display_height=preview.display_height,
    )
    if display_rect is None:
        raise ProjectWorkspaceError(
            "Preview selection is too small. Drag a larger rectangle inside the preview image."
        )

    left, top, right, bottom = display_rect
    source_left = _scale_preview_coordinate(left, preview.source_width, preview.display_width)
    source_top = _scale_preview_coordinate(top, preview.source_height, preview.display_height)
    source_right = _scale_preview_coordinate(
        right, preview.source_width, preview.display_width
    )
    source_bottom = _scale_preview_coordinate(
        bottom, preview.source_height, preview.display_height
    )

    clamped_right = min(max(source_right, source_left + 1), preview.source_width)
    clamped_bottom = min(max(source_bottom, source_top + 1), preview.source_height)
    return CropZone(
        zone_idx=zone_idx,
        x=source_left,
        y=source_top,
        width=clamped_right - source_left,
        height=clamped_bottom - source_top,
    )


def preview_selection_for_zone_spec(
    preview: PreparePreviewFrame,
    zone_spec: str,
) -> tuple[int, int, int, int] | None:
    parsed = _parse_zone_specs((zone_spec, ""))
    if not parsed:
        return None
    zone = parsed[0]
    left = _source_to_preview_coordinate(zone.x, preview.source_width, preview.display_width)
    top = _source_to_preview_coordinate(zone.y, preview.source_height, preview.display_height)
    right = _source_to_preview_coordinate(
        zone.x + zone.width,
        preview.source_width,
        preview.display_width,
    )
    bottom = _source_to_preview_coordinate(
        zone.y + zone.height,
        preview.source_height,
        preview.display_height,
    )
    return (
        min(max(left, 0), preview.display_width),
        min(max(top, 0), preview.display_height),
        min(max(right, 0), preview.display_width),
        min(max(bottom, 0), preview.display_height),
    )


def format_crop_zone_spec(zone: CropZone) -> str:
    return _format_zone_spec(zone)


def write_crop_zones_artifact(paths: ProjectPaths, config: PrepareConfig) -> None:
    payload = {
        "schema_version": PREPARE_SCHEMA_VERSION,
        "use_fullframe": bool(config.use_fullframe),
        "crop_zones": [
            {
                "zone_idx": zone.zone_idx,
                "x": zone.x,
                "y": zone.y,
                "width": zone.width,
                "height": zone.height,
            }
            for zone in config.crop_zones
        ],
    }
    write_json_file_atomic(paths.crop_zones_file, payload)


def _load_prepare_config(paths: ProjectPaths) -> PrepareConfig:
    if not paths.prepare_config_file.exists():
        return PrepareConfig()
    try:
        payload = read_json_file(paths.prepare_config_file)
    except ManifestValidationError as exc:
        raise ProjectWorkspaceError(
            f"Prepare config is invalid: {paths.prepare_config_file}"
        ) from exc
    return PrepareConfig.from_dict(payload)


def _load_crop_zone_state(
    paths: ProjectPaths,
    config: PrepareConfig,
) -> tuple[tuple[CropZone, ...], bool]:
    if not paths.crop_zones_file.exists():
        return tuple(config.crop_zones), bool(config.use_fullframe)
    try:
        payload = read_json_file(paths.crop_zones_file, required_fields=("crop_zones",))
    except ManifestValidationError as exc:
        raise ProjectWorkspaceError(
            f"Prepare crop zones are invalid: {paths.crop_zones_file}"
        ) from exc
    crop_zones = tuple(
        CropZone(
            zone_idx=int(item["zone_idx"]),
            x=int(item["x"]),
            y=int(item["y"]),
            width=int(item["width"]),
            height=int(item["height"]),
        )
        for item in payload.get("crop_zones", [])
    )
    return crop_zones, bool(payload.get("use_fullframe", config.use_fullframe))


def _format_zone_spec(zone: CropZone) -> str:
    return f"{zone.x},{zone.y},{zone.width},{zone.height}"


def _parse_zone_specs(zone_specs: tuple[str, str]) -> tuple[CropZone, ...]:
    parsed: list[CropZone] = []
    for zone_idx, raw_spec in enumerate(zone_specs):
        spec = raw_spec.strip()
        if not spec:
            continue
        parts = [part.strip() for part in spec.split(",")]
        if len(parts) != 4:
            raise ProjectWorkspaceError(
                f"Crop zone {zone_idx} must use x,y,width,height format."
            )
        try:
            x, y, width, height = (int(part) for part in parts)
        except ValueError as exc:
            raise ProjectWorkspaceError(
                f"Crop zone {zone_idx} must contain integers only."
            ) from exc
        if x < 0 or y < 0 or width <= 0 or height <= 0:
            raise ProjectWorkspaceError(
                f"Crop zone {zone_idx} must have non-negative origin and positive size."
            )
        parsed.append(
            CropZone(
                zone_idx=zone_idx,
                x=x,
                y=y,
                width=width,
                height=height,
            )
        )
    return tuple(parsed)


def _render_overlay_png(
    *,
    png_bytes: bytes,
    source_width: int,
    source_height: int,
    display_width: int,
    display_height: int,
    crop_zones: tuple[CropZone, ...],
    use_fullframe: bool,
) -> bytes:
    image = Image.open(BytesIO(png_bytes)).convert("RGB")
    draw = ImageDraw.Draw(image)
    scale_x = display_width / source_width
    scale_y = display_height / source_height

    if use_fullframe:
        draw.rectangle(
            (0, 0, max(display_width - 1, 0), max(display_height - 1, 0)),
            outline=(255, 215, 0),
            width=3,
        )

    colors = ((255, 80, 80), (80, 220, 120))
    for zone in crop_zones:
        color = colors[zone.zone_idx % len(colors)]
        x0 = int(round(zone.x * scale_x))
        y0 = int(round(zone.y * scale_y))
        x1 = int(round((zone.x + zone.width) * scale_x))
        y1 = int(round((zone.y + zone.height) * scale_y))
        draw.rectangle((x0, y0, x1, y1), outline=color, width=3)
        draw.text((x0 + 4, max(y0 + 4, 0)), f"Z{zone.zone_idx}", fill=color)

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _normalize_preview_rect(
    *,
    start_xy: tuple[float, float],
    end_xy: tuple[float, float],
    display_width: int,
    display_height: int,
) -> tuple[int, int, int, int] | None:
    if display_width <= 0 or display_height <= 0:
        return None

    x0 = _clamp_preview_coordinate(start_xy[0], display_width)
    y0 = _clamp_preview_coordinate(start_xy[1], display_height)
    x1 = _clamp_preview_coordinate(end_xy[0], display_width)
    y1 = _clamp_preview_coordinate(end_xy[1], display_height)
    left = min(x0, x1)
    top = min(y0, y1)
    right = max(x0, x1)
    bottom = max(y0, y1)
    if right - left < 2 or bottom - top < 2:
        return None
    return (left, top, right, bottom)


def _clamp_preview_coordinate(value: float, maximum: int) -> int:
    return min(max(int(round(float(value))), 0), maximum)


def _scale_preview_coordinate(value: int, source_size: int, display_size: int) -> int:
    if display_size <= 0:
        return 0
    scaled = int(round((value / display_size) * source_size))
    return min(max(scaled, 0), source_size)


def _source_to_preview_coordinate(value: int, source_size: int, display_size: int) -> int:
    if source_size <= 0:
        return 0
    scaled = int(round((value / source_size) * display_size))
    return min(max(scaled, 0), display_size)
