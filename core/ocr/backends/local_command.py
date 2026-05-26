"""Local-command OCR backend for VOCra."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
from collections.abc import Iterable
from pathlib import Path
from string import Formatter
from typing import Any

from vocra.core.ocr.backends.base import BackendTestResult
from vocra.core.ocr.models import OcrInput, OcrOutput

_ALLOWED_TEMPLATE_FIELDS = frozenset(
    {
        "image",
        "segment_id",
        "zone_idx",
        "start_ms",
        "end_ms",
    }
)
_VALID_STDOUT_FORMATS = frozenset({"plain_text", "json"})


class LocalCommandOcrBackend:
    name = "local-command"

    def validate_config(self, config: dict[str, Any]) -> None:
        template = config.get("command_template")
        if isinstance(template, str):
            if not template.strip():
                raise ValueError("Local-command backend requires a non-empty command_template.")
            _validate_template_fields(template)
        elif isinstance(template, list):
            if not template:
                raise ValueError("Local-command backend requires a non-empty command_template.")
            for token in template:
                if not isinstance(token, str) or not token:
                    raise ValueError("Local-command command_template lists must contain strings.")
                _validate_template_fields(token)
        else:
            raise ValueError(
                "Local-command backend requires command_template as a string or a list of strings."
            )

        stdout_format = str(config.get("stdout_format", "plain_text")).strip().lower()
        if stdout_format not in _VALID_STDOUT_FORMATS:
            allowed = ", ".join(sorted(_VALID_STDOUT_FORMATS))
            raise ValueError(f"Unsupported stdout_format: {stdout_format}. Expected one of: {allowed}.")

        working_dir = config.get("working_dir")
        if working_dir is not None and not Path(str(working_dir)).exists():
            raise ValueError(f"Configured working_dir does not exist: {working_dir}")

    def test_connection(self, config: dict[str, Any]) -> BackendTestResult:
        try:
            self.validate_config(config)
            executable = _resolve_executable_name(config)
            if _executable_exists(executable):
                return BackendTestResult(ok=True, message=f"Resolved executable: {executable}")
            return BackendTestResult(ok=False, message=f"Executable was not found: {executable}")
        except Exception as exc:
            return BackendTestResult(ok=False, message=str(exc))

    def run(
        self,
        inputs: Iterable[OcrInput],
        config: dict[str, Any],
    ) -> Iterable[OcrOutput]:
        self.validate_config(config)
        timeout_sec = float(config.get("timeout_sec", 120))
        stdout_format = str(config.get("stdout_format", "plain_text")).strip().lower()
        working_dir = None
        if config.get("working_dir") is not None:
            working_dir = str(Path(str(config["working_dir"])))

        for item in inputs:
            command = _render_command(config, item)
            try:
                completed = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    timeout=timeout_sec,
                    cwd=working_dir,
                    shell=False,
                    check=False,
                )
                raw_payload = {
                    "command": _serialize_command(command),
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                    "returncode": completed.returncode,
                }
                if completed.returncode != 0:
                    message = completed.stderr.strip() or completed.stdout.strip() or "command failed"
                    raise RuntimeError(f"Command exited with code {completed.returncode}: {message}")

                text, parsed_stdout = _normalize_stdout(completed.stdout, stdout_format)
                if parsed_stdout is not None:
                    raw_payload["parsed_stdout"] = parsed_stdout
                yield OcrOutput(
                    segment_id=item.segment_id,
                    text=text,
                    confidence=None,
                    raw=raw_payload,
                    status="ok",
                )
            except subprocess.TimeoutExpired as exc:
                yield OcrOutput(
                    segment_id=item.segment_id,
                    text="",
                    confidence=None,
                    raw={
                        "command": _serialize_command(command),
                        "stdout": exc.stdout,
                        "stderr": exc.stderr,
                        "timeout_sec": timeout_sec,
                    },
                    status="error",
                    error=f"Command timed out after {timeout_sec} seconds.",
                )
            except Exception as exc:
                yield OcrOutput(
                    segment_id=item.segment_id,
                    text="",
                    confidence=None,
                    raw={
                        "command": _serialize_command(command),
                        "error": str(exc),
                    },
                    status="error",
                    error=str(exc),
                )


def _validate_template_fields(template: str) -> None:
    for _, field_name, _, _ in Formatter().parse(template):
        if field_name is None:
            continue
        if field_name not in _ALLOWED_TEMPLATE_FIELDS:
            allowed = ", ".join(sorted(_ALLOWED_TEMPLATE_FIELDS))
            raise ValueError(
                f"Unsupported command_template field `{field_name}`. Allowed fields: {allowed}."
            )


def _build_template_context(item: OcrInput) -> dict[str, str | int]:
    return {
        "image": str(item.image_path),
        "segment_id": item.segment_id,
        "zone_idx": item.zone_idx,
        "start_ms": item.start_ms,
        "end_ms": item.end_ms,
    }


def _render_command(config: dict[str, Any], item: OcrInput) -> list[str] | str:
    template = config["command_template"]
    context = _build_template_context(item)
    if isinstance(template, list):
        return [token.format_map(context) for token in template]

    rendered = str(template).format_map(context)
    if os.name == "nt":
        return rendered
    return shlex.split(rendered)


def _resolve_executable_name(config: dict[str, Any]) -> str:
    dummy_input = OcrInput(
        segment_id="seg_test",
        image_path=Path("image.jpg"),
        zone_idx=0,
        start_ms=0,
        end_ms=1000,
        metadata={},
    )
    rendered = _render_command(config, dummy_input)
    if isinstance(rendered, list):
        if not rendered:
            raise ValueError("Rendered local-command command was empty.")
        return rendered[0]

    tokens = shlex.split(rendered, posix=False)
    if not tokens:
        raise ValueError("Rendered local-command command was empty.")
    return tokens[0].strip("\"'")


def _executable_exists(executable: str) -> bool:
    candidate = Path(executable)
    if candidate.exists():
        return True
    return shutil.which(executable) is not None


def _normalize_stdout(stdout: str, stdout_format: str) -> tuple[str, Any | None]:
    if stdout_format == "plain_text":
        return stdout.strip(), None

    parsed = json.loads(stdout)
    if isinstance(parsed, str):
        return parsed.strip(), parsed
    if isinstance(parsed, dict):
        if isinstance(parsed.get("text"), str):
            return parsed["text"].strip(), parsed
        message = parsed.get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return message["content"].strip(), parsed
    raise ValueError("JSON stdout did not contain a supported text payload.")


def _serialize_command(command: list[str] | str) -> list[str] | str:
    return command
