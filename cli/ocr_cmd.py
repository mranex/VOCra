"""OCR-related CLI commands for VOCra."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from vocra.core.ocr.registry import create_backend
from vocra.core.ocr.service import run_ocr
from vocra.core.project.manifest import read_json_file


def configure_ocr_parser(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    ocr_parser = subparsers.add_parser(
        "ocr",
        help="Run OCR backends against prepared artifacts.",
    )
    ocr_subparsers = ocr_parser.add_subparsers(dest="ocr_command")

    run_parser = ocr_subparsers.add_parser(
        "run",
        help="Run an OCR backend over prepared subtitle segments.",
    )
    _configure_ocr_run_parser(run_parser, require_run_id=False, include_force=True)
    run_parser.set_defaults(func=_handle_ocr_run)

    resume_failed_parser = ocr_subparsers.add_parser(
        "resume-failed",
        help="Resume an existing OCR run by processing only segments whose latest status is error.",
    )
    _configure_ocr_run_parser(
        resume_failed_parser,
        require_run_id=True,
        include_force=False,
    )
    resume_failed_parser.set_defaults(func=_handle_ocr_resume_failed)

    rerun_empty_parser = ocr_subparsers.add_parser(
        "rerun-empty",
        help="Rerun only segments whose latest OCR text is empty in an existing OCR run.",
    )
    _configure_ocr_run_parser(
        rerun_empty_parser,
        require_run_id=True,
        include_force=False,
    )
    rerun_empty_parser.set_defaults(func=_handle_ocr_rerun_empty)

    test_backend_parser = ocr_subparsers.add_parser(
        "test-backend",
        help="Validate OCR backend connectivity/config without running subtitle OCR.",
    )
    _add_ocr_config_arguments(test_backend_parser)
    test_backend_parser.set_defaults(func=_handle_ocr_test_backend)


def _configure_ocr_run_parser(
    parser: argparse.ArgumentParser,
    *,
    require_run_id: bool,
    include_force: bool,
) -> None:
    parser.add_argument(
        "--project",
        required=True,
        help="Path to the .vocra project directory.",
    )
    parser.add_argument(
        "--prepare-run",
        default="prepare_default",
        help="Prepare run identifier. Use `prepare_default` for top-level prepare artifacts.",
    )
    parser.add_argument(
        "--run-id",
        required=require_run_id,
        help="Existing OCR run directory name to resume into.",
    )
    if include_force:
        parser.add_argument(
            "--force",
            action="store_true",
            help="Reprocess segments even if normalized outputs already exist in the target run.",
        )
    _add_ocr_config_arguments(parser)


def _add_ocr_config_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--backend", help="OCR backend name.")
    parser.add_argument(
        "--config",
        help="Path to an OCR config JSON file. CLI flags override values from the file.",
    )
    parser.add_argument(
        "--text-template",
        help="Fake backend only: template used to generate text.",
    )
    parser.add_argument(
        "--command-template",
        help="Local-command backend only: command template using fields like {image} and {segment_id}.",
    )
    parser.add_argument(
        "--stdout-format",
        help="Local-command backend only: one of plain_text or json.",
    )
    parser.add_argument(
        "--working-dir",
        help="Local-command backend only: working directory for command execution.",
    )
    parser.add_argument(
        "--fail-segment-id",
        action="append",
        default=[],
        help="Fake backend only: segment_id to simulate as an OCR error. May be provided multiple times.",
    )
    parser.add_argument(
        "--empty-segment-id",
        action="append",
        default=[],
        help="Fake backend only: segment_id to simulate as empty text. May be provided multiple times.",
    )
    parser.add_argument(
        "--endpoint",
        help="Backend endpoint base URL for HTTP OCR backends such as OpenAI-compatible or Ollama.",
    )
    parser.add_argument("--api-key", help="OpenAI-compatible API key, if required.")
    parser.add_argument("--model", help="OCR model identifier for the selected backend.")
    parser.add_argument(
        "--prompt-template",
        help="Prompt sent with each prepared subtitle image.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        help="Sampling temperature for the OCR backend, when supported.",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        help="Maximum completion tokens for the OCR backend, when supported.",
    )
    parser.add_argument(
        "--timeout-sec",
        type=float,
        help="HTTP timeout in seconds for backend calls.",
    )


def _handle_ocr_run(args: argparse.Namespace) -> int:
    return _run_ocr_command(
        args,
        rerun_empty=False,
    )


def _handle_ocr_resume_failed(args: argparse.Namespace) -> int:
    return _run_ocr_command(
        args,
        rerun_empty=False,
    )


def _handle_ocr_rerun_empty(args: argparse.Namespace) -> int:
    return _run_ocr_command(
        args,
        rerun_empty=True,
    )


def _run_ocr_command(
    args: argparse.Namespace,
    *,
    rerun_empty: bool,
) -> int:
    config = _build_ocr_config(args)

    result = run_ocr(
        Path(args.project),
        prepare_run=args.prepare_run,
        config=config,
        run_id=args.run_id,
        force=bool(getattr(args, "force", False)),
        rerun_empty=rerun_empty,
    )
    print(
        json.dumps(
            {
                "run_dir": str(result.run_dir),
                "ocr_config_path": str(result.config_path),
                "raw_outputs_path": str(result.raw_outputs_path),
                "normalized_text_path": str(result.normalized_text_path),
                "errors_path": str(result.errors_path),
                "report_path": str(result.report_path),
                "summary": {
                    "run_id": result.summary.run_id,
                    "ok_count": result.summary.ok_count,
                    "error_count": result.summary.error_count,
                    "empty_count": result.summary.empty_count,
                },
            },
            indent=2,
        )
    )
    return 0


def _handle_ocr_test_backend(args: argparse.Namespace) -> int:
    config = _build_ocr_config(args)
    try:
        backend = create_backend(config)
        result = backend.test_connection(config)
    except ValueError as exc:
        raise SystemExit(f"Error: {exc}") from exc

    print(
        json.dumps(
            {
                "backend": str(config["backend"]),
                "ok": result.ok,
                "message": result.message,
            },
            indent=2,
        )
    )
    return 0 if result.ok else 1


def _build_ocr_config(args: argparse.Namespace) -> dict[str, object]:
    config: dict[str, object] = {}
    config_path = getattr(args, "config", None)
    if config_path is not None:
        config.update(read_json_file(Path(config_path)))

    backend_name = getattr(args, "backend", None)
    if backend_name is not None:
        config["backend"] = backend_name
    if "backend" not in config:
        raise SystemExit(
            "Error: OCR config must provide a backend via --backend or --config."
        )
    text_template = getattr(args, "text_template", None)
    if text_template is not None:
        config["text_template"] = text_template
    command_template = getattr(args, "command_template", None)
    if command_template is not None:
        config["command_template"] = command_template
    stdout_format = getattr(args, "stdout_format", None)
    if stdout_format is not None:
        config["stdout_format"] = stdout_format
    working_dir = getattr(args, "working_dir", None)
    if working_dir is not None:
        config["working_dir"] = working_dir
    fail_segment_ids = getattr(args, "fail_segment_id", [])
    if fail_segment_ids:
        config["fail_segment_ids"] = list(fail_segment_ids)
    empty_segment_ids = getattr(args, "empty_segment_id", [])
    if empty_segment_ids:
        config["empty_segment_ids"] = list(empty_segment_ids)
    endpoint = getattr(args, "endpoint", None)
    if endpoint is not None:
        config["endpoint"] = endpoint
    api_key = getattr(args, "api_key", None)
    if api_key is not None:
        config["api_key"] = api_key
    model = getattr(args, "model", None)
    if model is not None:
        config["model"] = model
    prompt_template = getattr(args, "prompt_template", None)
    if prompt_template is not None:
        config["prompt_template"] = prompt_template
    temperature = getattr(args, "temperature", None)
    if temperature is not None:
        config["temperature"] = temperature
    max_tokens = getattr(args, "max_tokens", None)
    if max_tokens is not None:
        config["max_tokens"] = max_tokens
    timeout_sec = getattr(args, "timeout_sec", None)
    if timeout_sec is not None:
        config["timeout_sec"] = timeout_sec
    return config
