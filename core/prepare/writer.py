"""Prepare artifact writers for VOCra."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from vocra.core.prepare.config import PrepareConfig
from vocra.core.prepare.frame_filter import FrameFilterResult, RepresentativeFrame
from vocra.core.prepare.grids import PreparedDetectionGrid
from vocra.core.prepare.models import SubtitleSegment
from vocra.core.prepare.sampler import SampledFrame, build_frame_timestamp_map
from vocra.core.prepare.segmenter import DetectedFrame, LayoutGroup
from vocra.core.project.jsonl import write_jsonl_atomic
from vocra.core.project.manifest import write_json_file_atomic


@dataclass(frozen=True)
class PrepareArtifacts:
    run_dir: Path
    config_path: Path
    timeline_path: Path
    detection_boxes_path: Path
    frame_index_path: Path
    representative_candidates_path: Path
    subtitle_segments_path: Path | None
    detection_grids_dir: Path
    representative_images_dir: Path
    report_path: Path


def write_prepare_run_artifacts(
    run_dir: Path,
    *,
    config: PrepareConfig,
    detected_frames: tuple[DetectedFrame, ...],
    layout_groups: tuple[LayoutGroup, ...],
    filter_result: FrameFilterResult,
    sampled_frames: tuple[SampledFrame, ...] = (),
    prepared_grids: tuple[PreparedDetectionGrid, ...] = (),
    subtitle_segments: tuple[SubtitleSegment, ...] = (),
) -> PrepareArtifacts:
    run_root = run_dir.expanduser().resolve()
    run_root.mkdir(parents=True, exist_ok=True)

    config_path = run_root / "prepare_config.json"
    timeline_path = run_root / "timeline.jsonl"
    detection_boxes_path = run_root / "detection_boxes.jsonl"
    frame_index_path = run_root / "frame_index.jsonl"
    representative_candidates_path = run_root / "representative_candidates.jsonl"
    subtitle_segments_path = run_root / "subtitle_segments.jsonl"
    detection_grids_dir = run_root / "debug" / "detection_grids"
    representative_images_dir = run_root / "representative_images"
    report_path = run_root / "run_report.json"
    frame_timestamps = build_frame_timestamp_map(sampled_frames)
    representative_image_paths = _write_prepare_image_artifacts(
        run_root,
        prepared_grids,
        filter_result.representatives,
        subtitle_segments=subtitle_segments,
        detection_grids_dir=detection_grids_dir,
        representative_images_dir=representative_images_dir,
    )

    write_json_file_atomic(config_path, config.to_dict())
    write_jsonl_atomic(
        timeline_path,
        (_build_timeline_row(frame) for frame in sampled_frames),
    )
    write_jsonl_atomic(
        detection_boxes_path,
        (_build_detection_boxes_row(frame) for frame in detected_frames),
    )
    write_jsonl_atomic(
        frame_index_path,
        (_build_frame_index_row(frame, frame_timestamps) for frame in detected_frames),
    )
    write_jsonl_atomic(
        representative_candidates_path,
        (
            _build_representative_row(
                index,
                representative,
                representative_image_paths.get(index),
                run_root,
            )
            for index, representative in enumerate(
                filter_result.representatives,
                start=1,
            )
        ),
    )
    if subtitle_segments:
        write_jsonl_atomic(
            subtitle_segments_path,
            (segment.to_dict() for segment in subtitle_segments),
        )
    write_json_file_atomic(
        report_path,
        {
            "schema_version": 1,
            "run_id": run_root.name,
            "sampled_frame_count": len(sampled_frames),
            "detected_frame_count": len(detected_frames),
            "layout_group_count": len(layout_groups),
            "representative_candidate_count": len(filter_result.representatives),
            "deleted_duplicate_count": filter_result.deleted_count,
            "segment_count": len(subtitle_segments),
        },
    )

    return PrepareArtifacts(
        run_dir=run_root,
        config_path=config_path,
        timeline_path=timeline_path,
        detection_boxes_path=detection_boxes_path,
        frame_index_path=frame_index_path,
        representative_candidates_path=representative_candidates_path,
        subtitle_segments_path=subtitle_segments_path if subtitle_segments else None,
        detection_grids_dir=detection_grids_dir,
        representative_images_dir=representative_images_dir,
        report_path=report_path,
    )


def _build_timeline_row(frame: SampledFrame) -> dict[str, object]:
    return {
        "frame_idx": frame.frame_idx,
        "timestamp_ms": frame.timestamp_ms,
        "zone_indices": [zone.zone_idx for zone in frame.zones],
    }


def _build_detection_boxes_row(frame: DetectedFrame) -> dict[str, object]:
    return {
        "frame_idx": frame.frame_idx,
        "zone_idx": frame.zone_idx,
        "grid_file": frame.grid_file.name,
        "detection_score": frame.detection_score,
        "detection_boxes": [
            [
                [_serialize_number(point[0]), _serialize_number(point[1])]
                for point in polygon
            ]
            for polygon in frame.polygons
        ],
    }


def _build_frame_index_row(
    frame: DetectedFrame,
    frame_timestamps: dict[int, float],
) -> dict[str, object]:
    placement = frame.placement
    row: dict[str, object] = {
        "frame_idx": frame.frame_idx,
        "zone_idx": frame.zone_idx,
        "grid_file": frame.grid_file.name,
        "placement": {
            "x": placement.x,
            "y": placement.y,
            "width": placement.width,
            "height": placement.height,
        },
    }
    if frame.frame_idx in frame_timestamps:
        row["timestamp_ms"] = frame_timestamps[frame.frame_idx]
    return row


def _build_representative_row(
    index: int,
    representative: RepresentativeFrame,
    representative_image_path: Path | None,
    run_root: Path,
) -> dict[str, object]:
    placement = representative.placement
    row: dict[str, object] = {
        "candidate_id": f"cand_{index:06d}",
        "frame_idx": representative.frame_idx,
        "source_frame_idx": representative.source_frame_idx,
        "zone_idx": representative.zone_idx,
        "grid_file": representative.grid_file.name,
        "detection_score": representative.detection_score,
        "placement": {
            "x": placement.x,
            "y": placement.y,
            "width": placement.width,
            "height": placement.height,
        },
    }
    if representative_image_path is not None:
        row["image_path"] = representative_image_path.relative_to(run_root).as_posix()
    return row


def _write_prepare_image_artifacts(
    run_root: Path,
    prepared_grids: tuple[PreparedDetectionGrid, ...],
    representatives: tuple[RepresentativeFrame, ...],
    *,
    subtitle_segments: tuple[SubtitleSegment, ...],
    detection_grids_dir: Path,
    representative_images_dir: Path,
) -> dict[int, Path]:
    detection_grids_dir.mkdir(parents=True, exist_ok=True)
    representative_images_dir.mkdir(parents=True, exist_ok=True)

    grids_by_name: dict[str, PreparedDetectionGrid] = {}
    for grid in prepared_grids:
        grids_by_name[grid.layout.file_name] = grid
        _save_image(detection_grids_dir / grid.layout.file_name, grid.image)

    representative_paths: dict[int, Path] = {}
    for index, representative in enumerate(representatives, start=1):
        grid = grids_by_name.get(representative.grid_file.name)
        if grid is None:
            continue

        placement = representative.placement
        tile = grid.image[
            placement.y : placement.y + placement.height,
            placement.x : placement.x + placement.width,
        ]
        image_path = (
            representative_images_dir
            / f"cand_{index:06d}_z{representative.zone_idx}.jpg"
        )
        _save_image(image_path, tile)
        representative_paths[index] = image_path
        if index <= len(subtitle_segments):
            segment_image_path = run_root / subtitle_segments[index - 1].representative_image
            segment_image_path.parent.mkdir(parents=True, exist_ok=True)
            _save_image(segment_image_path, tile)

    return representative_paths


def _save_image(path: Path, image: Any) -> None:
    Image.fromarray(image).save(path, quality=80)


def _serialize_number(value: float) -> int | float:
    integer_value = int(value)
    if integer_value == value:
        return integer_value
    return value
