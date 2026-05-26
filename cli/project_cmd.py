"""Project-related CLI commands for VOCra."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from vocra.core.project.workspace import (
    ProjectWorkspaceError,
    create_project,
    open_project,
    validate_project,
)


def configure_project_parser(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    project_parser = subparsers.add_parser(
        "project",
        help="Create, inspect, and validate VOCra projects.",
    )
    project_subparsers = project_parser.add_subparsers(dest="project_command")

    create_parser = project_subparsers.add_parser(
        "create",
        help="Create a new VOCra project workspace.",
    )
    create_parser.add_argument("--video", required=True, help="Path to the source video.")
    create_parser.add_argument(
        "--project",
        required=True,
        help="Path to the .vocra project directory to create.",
    )
    create_parser.set_defaults(func=_handle_project_create)

    inspect_parser = project_subparsers.add_parser(
        "inspect",
        help="Inspect an existing VOCra project manifest.",
    )
    inspect_parser.add_argument(
        "--project",
        required=True,
        help="Path to the .vocra project directory.",
    )
    inspect_parser.set_defaults(func=_handle_project_inspect)

    validate_parser = project_subparsers.add_parser(
        "validate",
        help="Validate the required files for an existing VOCra project.",
    )
    validate_parser.add_argument(
        "--project",
        required=True,
        help="Path to the .vocra project directory.",
    )
    validate_parser.set_defaults(func=_handle_project_validate)


def _handle_project_create(args: argparse.Namespace) -> int:
    try:
        project = create_project(Path(args.video), Path(args.project))
    except ProjectWorkspaceError as exc:
        raise SystemExit(f"Error: {exc}") from exc

    print(json.dumps(_project_to_cli_dict(project), indent=2))
    return 0


def _handle_project_inspect(args: argparse.Namespace) -> int:
    try:
        project = open_project(Path(args.project))
    except ProjectWorkspaceError as exc:
        raise SystemExit(f"Error: {exc}") from exc

    print(json.dumps(_project_to_cli_dict(project), indent=2))
    return 0


def _handle_project_validate(args: argparse.Namespace) -> int:
    try:
        validate_project(Path(args.project))
    except ProjectWorkspaceError as exc:
        raise SystemExit(f"Error: {exc}") from exc

    print(json.dumps({"project": str(Path(args.project).expanduser().resolve()), "status": "ok"}, indent=2))
    return 0


def _project_to_cli_dict(project) -> dict[str, object]:
    payload = project.to_dict()
    payload["root"] = str(project.root)
    return payload
