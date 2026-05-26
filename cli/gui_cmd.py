"""GUI command for the VOCra shell."""

from __future__ import annotations

import argparse


def configure_gui_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    parser = subparsers.add_parser(
        "gui",
        help="Open the VOCra GUI shell.",
    )
    parser.add_argument(
        "--project",
        help="Optional path to an existing .vocra project folder to open on launch.",
    )
    parser.set_defaults(func=_handle_gui_open)


def _handle_gui_open(args: argparse.Namespace) -> int:
    from vocra.gui.main_window import run_main_window

    return run_main_window(initial_project=args.project)
