"""Prepare-stage models and services for VOCra."""

from vocra.core.prepare.config import PrepareConfig
from vocra.core.prepare.crop import CropBounds, CropRenderPlan
from vocra.core.prepare.detectors.base import DetectionGridResult
from vocra.core.prepare.errors import PrepareCancelledError
from vocra.core.prepare.frame_filter import (
    DetectionSamplingFilterResult,
    FrameFilterResult,
    RepresentativeFrame,
    filter_sampled_frames_for_detection,
)
from vocra.core.prepare.grids import (
    PreparedDetectionGrid,
    build_detection_grid_indexes,
    build_detection_grids,
)
from vocra.core.prepare.models import (
    CropZone,
    DetectionBox,
    PrepareRunSummary,
    PrepareSummary,
    SubtitleSegment,
)
from vocra.core.prepare.sampler import (
    SampledFrame,
    SampledZoneFrame,
    SyntheticVideoFrame,
    apply_brightness_threshold,
    sample_video_capture,
)
from vocra.core.prepare.segmenter import DetectedFrame, LayoutGroup
from vocra.core.prepare.segments import build_subtitle_segments
from vocra.core.prepare.service import (
    PrepareCandidateSelection,
    PrepareRunResult,
    PrepareSamplingResult,
    run_prepare,
    sample_project_video,
)
from vocra.core.prepare.similarity import compute_ssim_similarity
from vocra.core.prepare.stitch import (
    PolygonIntersection,
    StitchLayout,
    StitchTilePlacement,
)

__all__ = [
    "CropBounds",
    "CropRenderPlan",
    "CropZone",
    "DetectedFrame",
    "DetectionGridResult",
    "DetectionSamplingFilterResult",
    "DetectionBox",
    "FrameFilterResult",
    "LayoutGroup",
    "PolygonIntersection",
    "PreparedDetectionGrid",
    "PrepareCandidateSelection",
    "PrepareConfig",
    "PrepareCancelledError",
    "PrepareRunResult",
    "PrepareRunSummary",
    "PrepareSamplingResult",
    "PrepareSummary",
    "RepresentativeFrame",
    "SampledFrame",
    "SampledZoneFrame",
    "build_subtitle_segments",
    "build_detection_grid_indexes",
    "build_detection_grids",
    "apply_brightness_threshold",
    "compute_ssim_similarity",
    "filter_sampled_frames_for_detection",
    "run_prepare",
    "sample_project_video",
    "StitchLayout",
    "StitchTilePlacement",
    "SubtitleSegment",
    "SyntheticVideoFrame",
    "sample_video_capture",
]
