"""Prepare configuration contracts for VOCra."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vocra.core.prepare.models import CropZone

PREPARE_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class PrepareConfig:
    time_start_ms: int = 0
    time_end_ms: int | None = None
    frames_to_skip: int = 1
    ssim_threshold: float = 0.92
    tight_box_ssim_threshold: float = 0.85
    subtitle_position: str = "center"
    ocr_image_max_width: int = 720
    brightness_threshold: int | None = None
    use_fullframe: bool = False
    crop_zones: tuple[CropZone, ...] = ()
    detector: dict[str, Any] = field(default_factory=dict)
    debug_mode: bool = False
    schema_version: int = PREPARE_SCHEMA_VERSION

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> PrepareConfig:
        return cls(
            time_start_ms=int(payload.get("time_start_ms", 0)),
            time_end_ms=_to_optional_int(payload.get("time_end_ms")),
            frames_to_skip=int(payload.get("frames_to_skip", 1)),
            ssim_threshold=float(payload.get("ssim_threshold", 0.92)),
            tight_box_ssim_threshold=float(payload.get("tight_box_ssim_threshold", 0.85)),
            subtitle_position=str(payload.get("subtitle_position", "center")),
            ocr_image_max_width=int(payload.get("ocr_image_max_width", 720)),
            brightness_threshold=_to_optional_int(payload.get("brightness_threshold")),
            use_fullframe=bool(payload.get("use_fullframe", False)),
            crop_zones=tuple(
                CropZone(
                    zone_idx=int(item["zone_idx"]),
                    x=int(item["x"]),
                    y=int(item["y"]),
                    width=int(item["width"]),
                    height=int(item["height"]),
                )
                for item in payload.get("crop_zones", [])
            ),
            detector=dict(payload.get("detector", {})),
            debug_mode=bool(payload.get("debug_mode", False)),
            schema_version=int(payload.get("schema_version", PREPARE_SCHEMA_VERSION)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "time_start_ms": self.time_start_ms,
            "time_end_ms": self.time_end_ms,
            "frames_to_skip": self.frames_to_skip,
            "ssim_threshold": self.ssim_threshold,
            "tight_box_ssim_threshold": self.tight_box_ssim_threshold,
            "subtitle_position": self.subtitle_position,
            "ocr_image_max_width": self.ocr_image_max_width,
            "brightness_threshold": self.brightness_threshold,
            "use_fullframe": self.use_fullframe,
            "crop_zones": [
                {
                    "zone_idx": zone.zone_idx,
                    "x": zone.x,
                    "y": zone.y,
                    "width": zone.width,
                    "height": zone.height,
                }
                for zone in self.crop_zones
            ],
            "detector": dict(self.detector),
            "debug_mode": self.debug_mode,
        }


def _to_optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)
