"""Small Prepare-side orchestration helpers for detector output."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from vocra.core.prepare.config import PrepareConfig
from vocra.core.prepare.crop import (
    CropRenderPlan,
    build_crop_render_plan,
    resolve_crop_zones,
)
from vocra.core.prepare.detectors.base import DetectionGridResult
from vocra.core.prepare.errors import PrepareCancelledError
from vocra.core.prepare.frame_filter import (
    CropSimilarityFn,
    FrameFilterResult,
    filter_sampled_frames_for_detection,
    select_representative_frames,
)
from vocra.core.prepare.grids import (
    PreparedDetectionGrid,
    build_detection_grid_indexes,
    build_detection_grids,
    write_detection_grid_images,
)
from vocra.core.prepare.models import PrepareRunSummary
from vocra.core.prepare.sampler import (
    SampledFrame,
    build_frame_timestamp_map,
    compute_average_frame_duration_ms,
    sample_video_capture,
)
from vocra.core.prepare.segmenter import (
    DetectedFrame,
    LayoutGroup,
    Rect,
    group_frames_by_layout,
)
from vocra.core.prepare.segments import build_subtitle_segments
from vocra.core.prepare.stitch import StitchLayout, unstitch_polygon
from vocra.core.prepare.writer import PrepareArtifacts, write_prepare_run_artifacts
from vocra.core.progress import ProgressEvent
from vocra.core.project.runs import create_prepare_run
from vocra.core.project.workspace import open_project
from vocra.core.video.capture import open_video_capture


@dataclass(frozen=True)
class PrepareCandidateSelection:
    detected_frames: tuple[DetectedFrame, ...]
    layout_groups: tuple[LayoutGroup, ...]
    filter_result: FrameFilterResult


@dataclass(frozen=True)
class PrepareRunResult:
    run_dir: Path
    artifacts: PrepareArtifacts
    summary: PrepareRunSummary


@dataclass(frozen=True)
class PrepareSamplingResult:
    sampled_frames: tuple[SampledFrame, ...]
    crop_plans: tuple[CropRenderPlan, ...]


def run_prepare(
    project_root: Path,
    *,
    config: PrepareConfig,
    detector_backend,
    similarity_fn: CropSimilarityFn,
    capture_factory=open_video_capture,
    frame_to_image=None,
    run_name: str | None = None,
    layout_tolerance: float = 0.05,
    ssim_threshold: float | None = None,
    progress=None,
    cancel_requested=None,
) -> PrepareRunResult:
    """Run the current end-to-end Prepare orchestration slice."""
    _emit_progress(
        progress,
        stage="prepare.sample",
        message="Sampling source video frames for Prepare.",
    )
    sampling = sample_project_video(
        project_root,
        config=config,
        capture_factory=capture_factory,
        frame_to_image=frame_to_image,
        cancel_requested=cancel_requested,
    )
    _raise_if_cancelled(cancel_requested)
    _emit_progress(
        progress,
        stage="prepare.sample",
        message=f"Sampled {len(sampling.sampled_frames)} frames across {len(sampling.crop_plans)} crop plan(s).",
        current=len(sampling.sampled_frames),
        total=len(sampling.sampled_frames),
        percent=100.0,
    )
    _emit_progress(
        progress,
        stage="prepare.filter",
        message="Applying coarse SSIM filtering before text detection.",
    )
    filtered_sampling = filter_sampled_frames_for_detection(
        sampling.sampled_frames,
        similarity_fn=similarity_fn,
        ssim_threshold=config.ssim_threshold,
    )
    _raise_if_cancelled(cancel_requested)
    _emit_progress(
        progress,
        stage="prepare.filter",
        message=(
            f"Kept {len(filtered_sampling.sampled_frames)} sampled frames for detection "
            f"after coarse filtering."
        ),
        current=len(filtered_sampling.sampled_frames),
        total=len(sampling.sampled_frames),
    )

    with TemporaryDirectory() as temp_dir:
        detection_image_dir = Path(temp_dir) / "detection_grids"
        detection_output_dir = Path(temp_dir) / "detector_output"
        _emit_progress(
            progress,
            stage="prepare.detect",
            message="Building stitched detection grids.",
        )
        prepared_grids = build_detection_grids(
            filtered_sampling.sampled_frames,
            out_dir=detection_image_dir,
            prefix=str(config.detector.get("grid_prefix", "det_stitched")),
            max_width=int(config.detector.get("grid_max_width", 1500)),
            max_height=int(config.detector.get("grid_max_height", 1500)),
            grid_spacing=int(config.detector.get("grid_spacing", 10)),
            zero_pad_length=int(config.detector.get("grid_zero_pad_length", 8)),
        )
        write_detection_grid_images(prepared_grids)
        _raise_if_cancelled(cancel_requested)
        _emit_progress(
            progress,
            stage="prepare.detect",
            message=f"Prepared {len(prepared_grids)} detection grid image(s).",
            current=len(prepared_grids),
            total=len(prepared_grids),
            percent=100.0 if prepared_grids else 0.0,
        )

        if prepared_grids:
            _emit_progress(
                progress,
                stage="prepare.detect",
                message="Running text detector on stitched grids.",
            )
            detector_results = detector_backend.detect_grids(
                detection_image_dir,
                detection_output_dir,
                dict(config.detector),
            )
        else:
            detector_results = ()
        _raise_if_cancelled(cancel_requested)
        _emit_progress(
            progress,
            stage="prepare.detect",
            message=f"Detector returned {len(detector_results)} grid result(s).",
            current=len(detector_results),
            total=len(prepared_grids),
        )

        layouts_by_name, grid_images = build_detection_grid_indexes(prepared_grids)
        _emit_progress(
            progress,
            stage="prepare.segment",
            message="Grouping detected frames and building subtitle segments.",
        )
        return run_prepare_candidate_selection(
            project_root,
            config=config,
            detector_results=detector_results,
            layouts_by_name=layouts_by_name,
            grid_images=grid_images,
            similarity_fn=similarity_fn,
            sampled_frames=sampling.sampled_frames,
            prepared_grids=prepared_grids,
            run_name=run_name,
            layout_tolerance=layout_tolerance,
            ssim_threshold=ssim_threshold,
            progress=progress,
            cancel_requested=cancel_requested,
        )


def map_detector_results_to_frames(
    detector_results: tuple[DetectionGridResult, ...],
    layouts_by_name: Mapping[str, StitchLayout],
) -> tuple[DetectedFrame, ...]:
    """Join detector grid outputs back to per-frame local polygons."""
    detected_frames: list[DetectedFrame] = []

    for result in detector_results:
        layout = layouts_by_name.get(result.input_path.name)
        if layout is None:
            continue

        polygons_by_frame: dict[int, list[tuple[Any, float]]] = {
            placement.frame_idx: [] for placement in layout.placements
        }
        placements_by_frame = {
            placement.frame_idx: placement for placement in layout.placements
        }

        for polygon, score in zip(result.polygons, result.scores):
            for intersection in unstitch_polygon(polygon, layout.placements):
                polygons_by_frame[intersection.placement.frame_idx].append(
                    (intersection.polygon, score)
                )

        for frame_idx, polygon_rows in polygons_by_frame.items():
            if not polygon_rows:
                continue

            placement = placements_by_frame[frame_idx]
            polygons = tuple(row[0] for row in polygon_rows)
            average_score = sum(row[1] for row in polygon_rows) / len(polygon_rows)
            detected_frames.append(
                DetectedFrame(
                    frame_idx=frame_idx,
                    zone_idx=placement.zone_idx,
                    polygons=polygons,
                    detection_score=average_score,
                    grid_file=result.input_path,
                    placement=placement,
                    source_frame_indices=placement.source_frame_indices or (frame_idx,),
                )
            )

    return tuple(sorted(detected_frames, key=lambda frame: (frame.zone_idx, frame.frame_idx)))


def build_grid_crop_provider(
    grid_images: Mapping[str | Path, Any],
):
    """Build a crop provider that slices crops from stitched grid images."""

    def crop_provider(frame: DetectedFrame, rect: Rect) -> Any:
        grid_image = _resolve_grid_image(grid_images, frame.grid_file)
        placement = frame.placement
        tile = grid_image[
            placement.y : placement.y + placement.height,
            placement.x : placement.x + placement.width,
        ]
        height, width = tile.shape[:2]
        crop_x1 = max(0, int(rect[0]))
        crop_y1 = max(0, int(rect[1]))
        crop_x2 = min(width, int(rect[2]))
        crop_y2 = min(height, int(rect[3]))
        return tile[crop_y1:crop_y2, crop_x1:crop_x2]

    return crop_provider


def select_representatives_from_detector_results(
    detector_results: tuple[DetectionGridResult, ...],
    layouts_by_name: Mapping[str, StitchLayout],
    grid_images: Mapping[str | Path, Any],
    *,
    similarity_fn: CropSimilarityFn,
    layout_tolerance: float = 0.05,
    ssim_threshold: float = 0.85,
) -> FrameFilterResult:
    """Map detector outputs to frames, group by layout, and select representatives."""
    selection = build_prepare_candidate_selection(
        detector_results,
        layouts_by_name,
        grid_images,
        similarity_fn=similarity_fn,
        layout_tolerance=layout_tolerance,
        ssim_threshold=ssim_threshold,
    )
    return selection.filter_result


def build_prepare_candidate_selection(
    detector_results: tuple[DetectionGridResult, ...],
    layouts_by_name: Mapping[str, StitchLayout],
    grid_images: Mapping[str | Path, Any],
    *,
    similarity_fn: CropSimilarityFn,
    layout_tolerance: float = 0.05,
    ssim_threshold: float = 0.85,
) -> PrepareCandidateSelection:
    """Build the first durable Prepare candidate slice from detector outputs."""
    detected_frames = map_detector_results_to_frames(detector_results, layouts_by_name)
    layout_groups = group_frames_by_layout(detected_frames, tolerance=layout_tolerance)
    filter_result = select_representative_frames(
        layout_groups,
        crop_provider=build_grid_crop_provider(grid_images),
        similarity_fn=similarity_fn,
        ssim_threshold=ssim_threshold,
    )
    return PrepareCandidateSelection(
        detected_frames=detected_frames,
        layout_groups=layout_groups,
        filter_result=filter_result,
    )


def run_prepare_candidate_selection(
    project_root: Path,
    *,
    config: PrepareConfig,
    detector_results: tuple[DetectionGridResult, ...],
    layouts_by_name: Mapping[str, StitchLayout],
    grid_images: Mapping[str | Path, Any],
    similarity_fn: CropSimilarityFn,
    sampled_frames: tuple[SampledFrame, ...] = (),
    prepared_grids: tuple[PreparedDetectionGrid, ...] = (),
    run_name: str | None = None,
    layout_tolerance: float = 0.05,
    ssim_threshold: float | None = None,
    progress=None,
    cancel_requested=None,
) -> PrepareRunResult:
    """Persist representative-frame candidates into a prepare run folder."""
    project = open_project(project_root)
    selection = build_prepare_candidate_selection(
        detector_results,
        layouts_by_name,
        grid_images,
        similarity_fn=similarity_fn,
        layout_tolerance=layout_tolerance,
        ssim_threshold=(
            config.tight_box_ssim_threshold if ssim_threshold is None else ssim_threshold
        ),
    )
    _raise_if_cancelled(cancel_requested)
    frame_timestamps = build_frame_timestamp_map(sampled_frames)
    subtitle_segments = (
        build_subtitle_segments(
            selection.filter_result.representatives,
            frame_timestamps,
            start_time_offset_ms=project.source.start_time_offset_ms,
            avg_frame_duration_ms=compute_average_frame_duration_ms(frame_timestamps),
        )
        if frame_timestamps
        else ()
    )
    _emit_progress(
        progress,
        stage="prepare.segment",
        message=(
            f"Prepared {len(selection.layout_groups)} layout group(s), "
            f"{len(selection.filter_result.representatives)} representative candidate(s), "
            f"and {len(subtitle_segments)} subtitle segment(s)."
        ),
    )
    run_dir = create_prepare_run(
        project,
        run_name or str(config.detector.get("name", "prepare")),
    )
    _raise_if_cancelled(cancel_requested)
    _emit_progress(
        progress,
        stage="prepare.write",
        message=f"Writing Prepare artifacts into {run_dir.name}.",
    )
    artifacts = write_prepare_run_artifacts(
        run_dir,
        config=config,
        sampled_frames=sampled_frames,
        detected_frames=selection.detected_frames,
        layout_groups=selection.layout_groups,
        filter_result=selection.filter_result,
        prepared_grids=prepared_grids,
        subtitle_segments=subtitle_segments,
    )
    summary = PrepareRunSummary(
        run_id=run_dir.name,
        sampled_frame_count=len(sampled_frames),
        detected_frame_count=len(selection.detected_frames),
        layout_group_count=len(selection.layout_groups),
        representative_candidate_count=len(selection.filter_result.representatives),
        deleted_duplicate_count=selection.filter_result.deleted_count,
        segment_count=len(subtitle_segments),
    )
    _emit_progress(
        progress,
        stage="prepare.write",
        message=(
            f"Prepare artifacts written for run {summary.run_id}: "
            f"{summary.segment_count} segment(s), {summary.detected_frame_count} detected frame(s)."
        ),
        current=summary.segment_count,
        total=summary.segment_count,
        percent=100.0,
    )
    return PrepareRunResult(
        run_dir=run_dir,
        artifacts=artifacts,
        summary=summary,
    )


def sample_project_video(
    project_root: Path,
    *,
    config: PrepareConfig,
    capture_factory=open_video_capture,
    frame_to_image=None,
    cancel_requested=None,
) -> PrepareSamplingResult:
    """Sample a project's source video using the decoder-backed capture boundary."""
    project = open_project(project_root)
    crop_bounds = resolve_crop_zones(
        project.source.width,
        project.source.height,
        list(config.crop_zones),
        use_fullframe=config.use_fullframe,
    )
    crop_plans = tuple(
        build_crop_render_plan(
            bounds,
            video_width=project.source.width,
            video_height=project.source.height,
            ocr_image_max_width=config.ocr_image_max_width,
        )
        for bounds in crop_bounds
    )

    with capture_factory(project.source.path) as capture:
        sampled_frames = sample_video_capture(
            capture,
            crop_plans,
            time_start_ms=float(config.time_start_ms),
            time_end_ms=(
                None if config.time_end_ms is None else float(config.time_end_ms)
            ),
            start_time_offset_ms=project.source.start_time_offset_ms,
            brightness_threshold=config.brightness_threshold,
            frames_to_skip=config.frames_to_skip,
            subtitle_position=config.subtitle_position,
            frame_to_image=frame_to_image,
            cancel_requested=cancel_requested,
        )

    return PrepareSamplingResult(
        sampled_frames=sampled_frames,
        crop_plans=crop_plans,
    )


def _resolve_grid_image(grid_images: Mapping[str | Path, Any], grid_file: Path) -> Any:
    for key in (grid_file, grid_file.name, str(grid_file)):
        if key in grid_images:
            return grid_images[key]
    raise KeyError(f"Grid image was not provided for {grid_file}")


def _emit_progress(
    progress,
    *,
    stage: str,
    message: str,
    current: int | float | None = None,
    total: int | float | None = None,
    percent: float | None = None,
    segment_id: str | None = None,
) -> None:
    if progress is None:
        return
    progress(
        ProgressEvent(
            stage=stage,
            message=message,
            current=current,
            total=total,
            percent=percent,
            segment_id=segment_id,
        )
    )


def _raise_if_cancelled(cancel_requested) -> None:
    if cancel_requested is None:
        return
    if cancel_requested():
        raise PrepareCancelledError("Prepare run was cancelled by the user.")
