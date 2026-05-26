"""Prepare frame filtering helpers extracted from legacy VideOCR."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vocra.core.prepare.detectors.base import DetectionPolygon
from vocra.core.prepare.sampler import SampledFrame, SampledZoneFrame
from vocra.core.prepare.segmenter import DetectedFrame, LayoutGroup, Rect
from vocra.core.prepare.stitch import StitchTilePlacement

CropProvider = Callable[[DetectedFrame, Rect], Any]
CropSimilarityFn = Callable[[Any, Any], float]


@dataclass(frozen=True)
class RepresentativeFrame:
    frame_idx: int
    end_frame_idx: int
    source_frame_idx: int
    zone_idx: int
    detection_score: float
    grid_file: Path
    placement: StitchTilePlacement
    source_frame_indices: tuple[int, ...]
    source_polygons: tuple[DetectionPolygon, ...]
    union_rects: tuple[Rect, ...]


@dataclass(frozen=True)
class FrameFilterResult:
    representatives: tuple[RepresentativeFrame, ...]
    deleted_count: int


@dataclass(frozen=True)
class DetectionSamplingFilterResult:
    sampled_frames: tuple[SampledFrame, ...]
    skipped_zone_count: int


def filter_sampled_frames_for_detection(
    sampled_frames: tuple[SampledFrame, ...],
    *,
    similarity_fn: CropSimilarityFn,
    ssim_threshold: float,
) -> DetectionSamplingFilterResult:
    """Apply the legacy coarse SSIM skip before the text detector pass."""
    if ssim_threshold >= 1.0:
        return DetectionSamplingFilterResult(
            sampled_frames=sampled_frames,
            skipped_zone_count=0,
        )

    previous_samples: dict[int, Any] = {}
    filtered_frames: list[dict[str, Any]] = []
    last_kept_positions: dict[int, tuple[int, int]] = {}
    skipped_zone_count = 0

    for sampled_frame in sampled_frames:
        kept_zones: list[SampledZoneFrame] = []
        for zone_frame in sampled_frame.zones:
            sample = zone_frame.ssim_sample
            if sample is None:
                kept_zones.append(zone_frame)
                continue

            previous_sample = previous_samples.get(zone_frame.zone_idx)
            previous_samples[zone_frame.zone_idx] = sample
            if previous_sample is None:
                kept_zones.append(zone_frame)
                continue

            if _is_empty_crop(previous_sample) or _is_empty_crop(sample):
                kept_zones.append(zone_frame)
                continue

            score = similarity_fn(previous_sample, sample)
            if score > ssim_threshold:
                skipped_zone_count += 1
                frame_pos, zone_pos = last_kept_positions[zone_frame.zone_idx]
                existing_zone = filtered_frames[frame_pos]["zones"][zone_pos]
                filtered_frames[frame_pos]["zones"][zone_pos] = SampledZoneFrame(
                    frame_idx=existing_zone.frame_idx,
                    zone_idx=existing_zone.zone_idx,
                    timestamp_ms=existing_zone.timestamp_ms,
                    image=existing_zone.image,
                    ssim_sample=existing_zone.ssim_sample,
                    source_frame_indices=(
                        existing_zone.source_frame_indices
                        + zone_frame.source_frame_indices
                    ),
                )
                continue
            kept_zones.append(zone_frame)

        if kept_zones:
            frame_pos = len(filtered_frames)
            filtered_frames.append(
                {
                    "frame_idx": sampled_frame.frame_idx,
                    "timestamp_ms": sampled_frame.timestamp_ms,
                    "zones": kept_zones,
                }
            )
            for zone_pos, zone_frame in enumerate(kept_zones):
                last_kept_positions[zone_frame.zone_idx] = (frame_pos, zone_pos)

    return DetectionSamplingFilterResult(
        sampled_frames=tuple(
            SampledFrame(
                frame_idx=int(item["frame_idx"]),
                timestamp_ms=float(item["timestamp_ms"]),
                zones=tuple(item["zones"]),
            )
            for item in filtered_frames
        ),
        skipped_zone_count=skipped_zone_count,
    )


def select_representative_frames(
    groups: tuple[LayoutGroup, ...],
    *,
    crop_provider: CropProvider,
    similarity_fn: CropSimilarityFn,
    ssim_threshold: float,
) -> FrameFilterResult:
    """Keep the best detection-score frame per contiguous similar block."""
    representatives: list[RepresentativeFrame] = []
    deleted_count = 0

    for group in groups:
        current_batch: list[tuple[DetectedFrame, tuple[Any, ...]]] = []
        previous_crops: tuple[Any, ...] = ()

        for index, frame in enumerate(group.frames):
            current_crops = tuple(
                crop_provider(frame, rect) for rect in group.union_rects
            )

            if index == 0:
                current_batch = [(frame, current_crops)]
                previous_crops = current_crops
                continue

            all_lines_match = True
            for previous_crop, current_crop in zip(previous_crops, current_crops):
                if _is_empty_crop(previous_crop) or _is_empty_crop(current_crop):
                    all_lines_match = False
                    break
                score = similarity_fn(previous_crop, current_crop)
                if score <= ssim_threshold:
                    all_lines_match = False
                    break

            if all_lines_match:
                current_batch.append((frame, current_crops))
                continue

            representatives.append(_pick_representative(current_batch, group.union_rects))
            deleted_count += len(current_batch) - 1
            current_batch = [(frame, current_crops)]
            previous_crops = current_crops

        if current_batch:
            representatives.append(_pick_representative(current_batch, group.union_rects))
            deleted_count += len(current_batch) - 1

    return FrameFilterResult(
        representatives=tuple(representatives),
        deleted_count=deleted_count,
    )


def _pick_representative(
    batch: list[tuple[DetectedFrame, tuple[Any, ...]]],
    union_rects: tuple[Rect, ...],
) -> RepresentativeFrame:
    anchor_frame = batch[0][0]
    end_frame = batch[-1][0]
    best_frame = max(batch, key=lambda item: item[0].detection_score)[0]
    source_frame_indices = tuple(
        frame_idx
        for frame, _ in batch
        for frame_idx in (
            frame.source_frame_indices or (frame.frame_idx,)
        )
    )
    return RepresentativeFrame(
        frame_idx=anchor_frame.frame_idx,
        end_frame_idx=(source_frame_indices[-1] if source_frame_indices else end_frame.frame_idx),
        source_frame_idx=best_frame.frame_idx,
        zone_idx=best_frame.zone_idx,
        detection_score=best_frame.detection_score,
        grid_file=best_frame.grid_file,
        placement=best_frame.placement,
        source_frame_indices=source_frame_indices,
        source_polygons=best_frame.polygons,
        union_rects=union_rects,
    )


def _is_empty_crop(crop: Any) -> bool:
    if crop is None:
        return True
    size = getattr(crop, "size", None)
    if size is not None:
        return bool(size == 0)
    try:
        return len(crop) == 0  # type: ignore[arg-type]
    except Exception:
        return False
