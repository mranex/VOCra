"""Synthetic-friendly sampling helpers for VOCra Prepare."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from vocra.core.prepare.crop import CropRenderPlan
from vocra.core.prepare.errors import PrepareCancelledError
from vocra.core.video.capture import VideoCapture


@dataclass(frozen=True)
class SyntheticVideoFrame:
    frame_idx: int
    timestamp_ms: float
    image: Any


@dataclass(frozen=True)
class SampledZoneFrame:
    frame_idx: int
    zone_idx: int
    timestamp_ms: float
    image: Any
    ssim_sample: Any | None
    source_frame_indices: tuple[int, ...] = ()


@dataclass(frozen=True)
class SampledFrame:
    frame_idx: int
    timestamp_ms: float
    zones: tuple[SampledZoneFrame, ...]


def compute_sampling_modulo(frames_to_skip: int) -> int:
    """Match the legacy frame-skip rule of keeping every N+1th frame."""
    if frames_to_skip < 0:
        raise ValueError("frames_to_skip must be greater than or equal to zero.")
    return frames_to_skip + 1


def build_ssim_sample(image: Any, subtitle_position: str) -> Any:
    """Extract the legacy coarse-SSIM region for a cropped subtitle image."""
    width = image.shape[1]
    if subtitle_position == "center":
        margin = int(width * 0.35)
        return image[:, margin : width - margin]
    if subtitle_position == "left":
        return image[:, : int(width * 0.3)]
    if subtitle_position == "right":
        return image[:, int(width * 0.7) :]
    if subtitle_position == "any":
        return image
    raise ValueError(f"Invalid subtitle_position: {subtitle_position}")


def sample_synthetic_frames(
    frames: Iterable[SyntheticVideoFrame],
    crop_plans: tuple[CropRenderPlan, ...],
    *,
    brightness_threshold: int | None = None,
    frames_to_skip: int,
    subtitle_position: str,
) -> tuple[SampledFrame, ...]:
    """Build cropped sampled frames without depending on a real decoder."""
    modulo = compute_sampling_modulo(frames_to_skip)
    sampled_frames: list[SampledFrame] = []

    for stream_index, frame in enumerate(frames):
        if stream_index % modulo != 0:
            continue

        sampled_frames.append(
            _build_sampled_frame(
                frame_idx=frame.frame_idx,
                timestamp_ms=frame.timestamp_ms,
                image=frame.image,
                brightness_threshold=brightness_threshold,
                crop_plans=crop_plans,
                subtitle_position=subtitle_position,
            )
        )

    return tuple(sampled_frames)


def sample_video_capture(
    capture: VideoCapture,
    crop_plans: tuple[CropRenderPlan, ...],
    *,
    time_start_ms: float = 0.0,
    time_end_ms: float | None = None,
    start_time_offset_ms: float = 0.0,
    brightness_threshold: int | None = None,
    frames_to_skip: int,
    subtitle_position: str,
    frame_to_image=None,
    cancel_requested=None,
) -> tuple[SampledFrame, ...]:
    """Sample frames from a decoder-backed capture while preserving legacy timing semantics."""
    effective_start_ms = time_start_ms + start_time_offset_ms
    effective_end_ms = (
        None if time_end_ms is None else time_end_ms + start_time_offset_ms
    )
    modulo = compute_sampling_modulo(frames_to_skip)
    sampled_frames: list[SampledFrame] = []
    image_loader = frame_to_image or _frame_to_image

    if effective_start_ms > 0:
        capture.seek(effective_start_ms)

    current_index = 0
    while True:
        _raise_if_cancelled(cancel_requested)
        success, frame, timestamp_ms = capture.read()
        if not success or frame is None:
            break

        if timestamp_ms < effective_start_ms:
            continue
        if effective_end_ms is not None and timestamp_ms > effective_end_ms:
            break

        if current_index % modulo == 0:
            sampled_frames.append(
                _build_sampled_frame(
                    frame_idx=current_index,
                    timestamp_ms=timestamp_ms,
                    image=image_loader(frame),
                    brightness_threshold=brightness_threshold,
                    crop_plans=crop_plans,
                    subtitle_position=subtitle_position,
                )
            )

        current_index += 1

    return tuple(sampled_frames)


def build_frame_timestamp_map(
    sampled_frames: Iterable[SampledFrame],
) -> dict[int, float]:
    """Collect a stable frame-index-to-timestamp mapping."""
    return {frame.frame_idx: frame.timestamp_ms for frame in sampled_frames}


def compute_average_frame_duration_ms(
    frame_timestamps: Mapping[int, float],
) -> float:
    """Recreate the legacy average-frame-duration fallback."""
    if len(frame_timestamps) <= 1:
        return 0.0

    min_idx = min(frame_timestamps)
    max_idx = max(frame_timestamps)
    if max_idx <= min_idx:
        return 0.0

    total_duration = frame_timestamps[max_idx] - frame_timestamps[min_idx]
    return total_duration / (max_idx - min_idx)


def _build_sampled_frame(
    *,
    frame_idx: int,
    timestamp_ms: float,
    image: Any,
    brightness_threshold: int | None,
    crop_plans: tuple[CropRenderPlan, ...],
    subtitle_position: str,
) -> SampledFrame:
    zones: list[SampledZoneFrame] = []
    for plan in crop_plans:
        cropped = image[
            plan.crop_y : plan.crop_y + plan.crop_height,
            plan.crop_x : plan.crop_x + plan.crop_width,
        ]
        prepared_image = apply_brightness_threshold(cropped, brightness_threshold)
        zones.append(
            SampledZoneFrame(
                frame_idx=frame_idx,
                zone_idx=plan.zone_idx,
                timestamp_ms=timestamp_ms,
                image=prepared_image,
                ssim_sample=build_ssim_sample(prepared_image, subtitle_position),
                source_frame_indices=(frame_idx,),
            )
        )
    return SampledFrame(
        frame_idx=frame_idx,
        timestamp_ms=timestamp_ms,
        zones=tuple(zones),
    )


def _frame_to_image(frame: Any) -> Any:
    if hasattr(frame, "to_ndarray"):
        return frame.to_ndarray(format="rgb24")
    return frame


def apply_brightness_threshold(image: Any, brightness_threshold: int | None) -> Any:
    """Apply the legacy brightness mask to a cropped subtitle zone."""
    if brightness_threshold is None:
        return image

    if image.ndim == 2:
        mask = image > brightness_threshold
        return (image * mask).astype(image.dtype, copy=False)

    red = image[..., 0].astype("uint16")
    green = image[..., 1].astype("uint16")
    blue = image[..., 2].astype("uint16")
    gray = ((red * 77 + green * 150 + blue * 29) >> 8).astype("uint8")
    mask = gray > brightness_threshold
    return (image * mask[..., None]).astype(image.dtype, copy=False)


def _raise_if_cancelled(cancel_requested) -> None:
    if cancel_requested is None:
        return
    if cancel_requested():
        raise PrepareCancelledError("Prepare run was cancelled by the user.")
