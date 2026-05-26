"""Minimal CLI entrypoint for the VOCra workbench."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from vocra import __version__
from vocra.cli.gui_cmd import configure_gui_parser
from vocra.cli.ocr_cmd import configure_ocr_parser
from vocra.cli.package_cmd import configure_package_parser
from vocra.cli.prepare_cmd import configure_prepare_parser
from vocra.cli.project_cmd import configure_project_parser
from vocra.cli.review_cmd import configure_review_parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vocra",
        description=(
            "VOCra is a staged, artifact-driven hardcoded subtitle OCR workbench."
        ),
    )
    parser.add_argument(
        "--version",
        action="store_true",
        help="Show the VOCra version and exit.",
    )
    subparsers = parser.add_subparsers(dest="command")
    configure_project_parser(subparsers)
    configure_prepare_parser(subparsers)
    configure_ocr_parser(subparsers)
    configure_review_parser(subparsers)
    configure_package_parser(subparsers)
    configure_gui_parser(subparsers)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version:
        print(f"VOCra {__version__}")
        return 0
    if hasattr(args, "func"):
        return args.func(args)

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
