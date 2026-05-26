"""Prepare-related CLI commands for VOCra."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from vocra.core.prepare.config import PrepareConfig
from vocra.core.prepare.detectors import (
    create_text_detector_backend,
    normalize_detector_name,
)
from vocra.core.prepare.models import CropZone
from vocra.core.prepare.service import run_prepare
from vocra.core.prepare.similarity import compute_ssim_similarity
from vocra.core.project.manifest import read_json_file
from vocra.core.video.timestamps import parse_time_str_to_ms


def configure_prepare_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    prepare_parser = subparsers.add_parser(
        "prepare",
        help="Prepare subtitle evidence from a project video.",
    )
    prepare_subparsers = prepare_parser.add_subparsers(dest="prepare_command")

    run_parser = prepare_subparsers.add_parser(
        "run",
        help="Run the Prepare stage and persist subtitle evidence artifacts.",
    )
    run_parser.add_argument("--project", required=True, help="Path to the .vocra project directory.")
    run_parser.add_argument(
        "--config",
        help="Path to a prepare config JSON file. CLI flags override values from the file.",
    )
    run_parser.add_argument(
        "--run-name",
        help="Optional human-readable suffix for the prepare run directory.",
    )
    run_parser.add_argument(
        "--time-start",
        help="Start time in MM:SS or HH:MM:SS format.",
    )
    run_parser.add_argument(
        "--time-end",
        help="Optional end time in MM:SS or HH:MM:SS format.",
    )
    run_parser.add_argument(
        "--time-start-ms",
        type=int,
        help="Start time in milliseconds. Overrides --time-start when both are given.",
    )
    run_parser.add_argument(
        "--time-end-ms",
        type=int,
        help="End time in milliseconds. Overrides --time-end when both are given.",
    )
    run_parser.add_argument(
        "--crop-zone",
        action="append",
        default=[],
        help="Crop zone in x,y,width,height form. May be provided multiple times.",
    )
    run_parser.add_argument(
        "--frames-to-skip",
        type=int,
        help="Legacy-style frame skip count; keep every N+1th frame.",
    )
    run_parser.add_argument(
        "--ssim-threshold",
        type=float,
        help="Coarse SSIM threshold applied before text detection.",
    )
    run_parser.add_argument(
        "--tight-box-ssim-threshold",
        type=float,
        help="Tight-box SSIM threshold used when de-duplicating detected subtitles.",
    )
    run_parser.add_argument(
        "--subtitle-position",
        choices=("left", "center", "right", "any"),
        help="Region used for coarse SSIM sampling.",
    )
    run_parser.add_argument(
        "--ocr-image-max-width",
        type=int,
        help="Maximum width for cropped subtitle images.",
    )
    run_parser.add_argument(
        "--brightness-threshold",
        type=int,
        help="Optional brightness threshold mask applied before SSIM/detection.",
    )
    run_parser.add_argument(
        "--use-fullframe",
        action="store_true",
        help="Ignore crop zones and use the full video frame.",
    )
    run_parser.add_argument(
        "--debug-mode",
        action="store_true",
        help="Record debug-oriented prepare artifacts when available.",
    )
    run_parser.add_argument(
        "--detector",
        help="Detector backend name. Supported: paddleocr-text-detection, fake.",
    )
    run_parser.add_argument(
        "--paddleocr-path",
        help="Paddle detector executable path or launcher command.",
    )
    run_parser.add_argument(
        "--model-dir",
        help="Paddle detector model directory.",
    )
    run_parser.add_argument(
        "--timeout-sec",
        type=float,
        help="Detector timeout in seconds.",
    )
    run_parser.add_argument(
        "--detector-score",
        type=float,
        help="Fake detector only: confidence score for generated boxes.",
    )
    run_parser.add_argument(
        "--detector-box-margin",
        type=int,
        help="Fake detector only: inset margin for generated boxes.",
    )
    run_parser.add_argument(
        "--detector-cover-full-image",
        action="store_true",
        help="Fake detector only: size synthetic boxes from the saved grid image dimensions.",
    )
    run_parser.set_defaults(func=_handle_prepare_run)


def _handle_prepare_run(args: argparse.Namespace) -> int:
    config = _build_prepare_config(args)
    try:
        detector_backend = create_text_detector_backend(config.detector)
    except ValueError as exc:
        raise SystemExit(f"Error: {exc}") from exc
    result = run_prepare(
        Path(args.project),
        config=config,
        detector_backend=detector_backend,
        similarity_fn=compute_ssim_similarity,
        run_name=args.run_name,
    )
    print(
        json.dumps(
            {
                "run_dir": str(result.run_dir),
                "prepare_config_path": str(result.artifacts.config_path),
                "timeline_path": str(result.artifacts.timeline_path),
                "detection_boxes_path": str(result.artifacts.detection_boxes_path),
                "frame_index_path": str(result.artifacts.frame_index_path),
                "subtitle_segments_path": (
                    None
                    if result.artifacts.subtitle_segments_path is None
                    else str(result.artifacts.subtitle_segments_path)
                ),
                "report_path": str(result.artifacts.report_path),
                "summary": {
                    "run_id": result.summary.run_id,
                    "sampled_frame_count": result.summary.sampled_frame_count,
                    "detected_frame_count": result.summary.detected_frame_count,
                    "representative_candidate_count": result.summary.representative_candidate_count,
                    "deleted_duplicate_count": result.summary.deleted_duplicate_count,
                    "segment_count": result.summary.segment_count,
                },
            },
            indent=2,
        )
    )
    return 0


def _build_prepare_config(args: argparse.Namespace) -> PrepareConfig:
    payload: dict[str, Any] = {}
    if args.config is not None:
        payload.update(read_json_file(Path(args.config)))

    if args.time_start is not None:
        payload["time_start_ms"] = int(parse_time_str_to_ms(args.time_start))
    if args.time_end is not None:
        payload["time_end_ms"] = int(parse_time_str_to_ms(args.time_end))
    if args.time_start_ms is not None:
        payload["time_start_ms"] = args.time_start_ms
    if args.time_end_ms is not None:
        payload["time_end_ms"] = args.time_end_ms
    if args.frames_to_skip is not None:
        payload["frames_to_skip"] = args.frames_to_skip
    if args.ssim_threshold is not None:
        payload["ssim_threshold"] = args.ssim_threshold
    if args.tight_box_ssim_threshold is not None:
        payload["tight_box_ssim_threshold"] = args.tight_box_ssim_threshold
    if args.subtitle_position is not None:
        payload["subtitle_position"] = args.subtitle_position
    if args.ocr_image_max_width is not None:
        payload["ocr_image_max_width"] = args.ocr_image_max_width
    if args.brightness_threshold is not None:
        payload["brightness_threshold"] = args.brightness_threshold
    if args.use_fullframe:
        payload["use_fullframe"] = True
    if args.debug_mode:
        payload["debug_mode"] = True
    if args.crop_zone:
        payload["crop_zones"] = [
            _parse_crop_zone(index, value) for index, value in enumerate(args.crop_zone)
        ]

    detector_payload = dict(payload.get("detector", {}))
    if args.detector is not None:
        detector_payload["name"] = normalize_detector_name(args.detector)
    if args.paddleocr_path is not None:
        detector_payload["paddleocr_path"] = args.paddleocr_path
    if args.model_dir is not None:
        detector_payload["model_dir"] = args.model_dir
    if args.timeout_sec is not None:
        detector_payload["timeout_sec"] = args.timeout_sec
    if args.detector_score is not None:
        detector_payload["score"] = args.detector_score
    if args.detector_box_margin is not None:
        detector_payload["box_margin"] = args.detector_box_margin
    if args.detector_cover_full_image:
        detector_payload["cover_full_image"] = True
    if detector_payload:
        payload["detector"] = detector_payload

    config = PrepareConfig.from_dict(payload)
    if not config.use_fullframe and not config.crop_zones:
        raise SystemExit(
            "Error: Prepare config must provide at least one --crop-zone unless --use-fullframe is enabled."
        )
    if not config.detector:
        raise SystemExit(
            "Error: Prepare config must provide a detector via --detector or --config."
        )
    return config


def _parse_crop_zone(zone_idx: int, value: str) -> dict[str, int]:
    pieces = [part.strip() for part in value.split(",")]
    if len(pieces) != 4:
        raise SystemExit(
            f"Error: invalid --crop-zone '{value}'. Expected x,y,width,height."
        )
    try:
        x, y, width, height = (int(piece) for piece in pieces)
    except ValueError as exc:
        raise SystemExit(
            f"Error: invalid --crop-zone '{value}'. Expected integer x,y,width,height."
        ) from exc

    zone = CropZone(zone_idx=zone_idx, x=x, y=y, width=width, height=height)
    return {
        "zone_idx": zone.zone_idx,
        "x": zone.x,
        "y": zone.y,
        "width": zone.width,
        "height": zone.height,
    }
