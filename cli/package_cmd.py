"""Package-related CLI commands for VOCra."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from vocra.core.package.service import PackageOptions, package_srt
from vocra.core.project.workspace import ProjectWorkspaceError


def configure_package_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    package_parser = subparsers.add_parser(
        "package",
        help="Package prepared and OCR artifacts into subtitle files.",
    )
    package_subparsers = package_parser.add_subparsers(dest="package_command")

    srt_parser = package_subparsers.add_parser(
        "srt",
        help="Build an SRT file from prepared and OCR artifacts.",
    )
    srt_parser.add_argument("--project", required=True, help="Path to the .vocra project directory.")
    srt_parser.add_argument(
        "--prepare-run",
        default="prepare_default",
        help="Prepare run identifier. Use `prepare_default` for top-level prepare artifacts.",
    )
    srt_parser.add_argument("--ocr-run", required=True, help="OCR run identifier.")
    srt_parser.add_argument("--output", help="Optional explicit output .srt path.")
    srt_parser.add_argument(
        "--min-subtitle-duration-ms",
        type=int,
        default=0,
        help="Minimum subtitle duration in milliseconds.",
    )
    srt_parser.add_argument(
        "--empty-text-policy",
        default="skip",
        choices=("skip", "keep"),
        help="How to handle empty OCR text.",
    )
    srt_parser.add_argument(
        "--review-state-policy",
        default="auto",
        choices=("auto", "ignore", "require"),
        help="Whether to auto-use, ignore, or require review_state.jsonl for the selected OCR run.",
    )
    srt_parser.set_defaults(func=_handle_package_srt)


def _handle_package_srt(args: argparse.Namespace) -> int:
    options = PackageOptions(
        format="srt",
        empty_text_policy=args.empty_text_policy,
        min_subtitle_duration_ms=args.min_subtitle_duration_ms,
        review_state_policy=args.review_state_policy,
    )
    try:
        result = package_srt(
            Path(args.project),
            prepare_run=args.prepare_run,
            ocr_run=args.ocr_run,
            options=options,
            output_path=None if args.output is None else Path(args.output),
        )
    except (ProjectWorkspaceError, ValueError) as exc:
        raise SystemExit(f"Error: {exc}") from exc

    print(
        json.dumps(
            {
                "run_dir": str(result.run_dir),
                "output_path": str(result.output_path),
                "package_report_path": str(result.package_report_path),
                "subtitle_count": result.subtitle_count,
            },
            indent=2,
        )
    )
    return 0
