"""PaddleOCR text-detection backend for VOCra Prepare."""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from vocra.core.prepare.detectors.base import DetectionGridResult, DetectionPolygon


class PaddleTextDetectorBackend:
    name = "paddleocr-text-detection"

    def validate_config(self, config: dict[str, Any]) -> None:
        command_prefix = config.get("paddleocr_path")
        if isinstance(command_prefix, str):
            if not command_prefix.strip():
                raise ValueError("Paddle detector requires a non-empty paddleocr_path.")
        elif isinstance(command_prefix, list):
            if not command_prefix or not all(isinstance(item, str) and item for item in command_prefix):
                raise ValueError("Paddle detector paddleocr_path lists must contain strings.")
        else:
            raise ValueError(
                "Paddle detector requires paddleocr_path as a string or a list of strings."
            )

        model_dir = str(config.get("model_dir", "")).strip()
        if not model_dir:
            raise ValueError("Paddle detector requires a model_dir.")

    def detect_grids(
        self,
        image_dir: Path,
        output_dir: Path,
        config: dict[str, Any],
    ) -> tuple[DetectionGridResult, ...]:
        self.validate_config(config)
        output_dir.mkdir(parents=True, exist_ok=True)
        timeout_sec = float(config.get("timeout_sec", 120))
        command = build_paddle_text_detection_command(
            image_dir=image_dir,
            output_dir=output_dir,
            config=config,
        )

        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
            check=False,
            shell=False,
        )
        if completed.returncode != 0:
            message = completed.stderr.strip() or completed.stdout.strip() or "command failed"
            raise RuntimeError(
                f"Paddle text detection exited with code {completed.returncode}: {message}"
            )

        return parse_paddle_text_detection_lines(completed.stdout.splitlines())


def build_paddle_text_detection_command(
    *,
    image_dir: Path,
    output_dir: Path,
    config: dict[str, Any],
) -> list[str]:
    command_prefix = config["paddleocr_path"]
    if isinstance(command_prefix, list):
        command = list(command_prefix)
    else:
        command = [str(command_prefix)]

    model_dir = str(config["model_dir"])
    subcommand = str(config.get("subcommand", "text_detection"))
    command.extend(
        [
            subcommand,
            "--input",
            str(image_dir),
            "--model_dir",
            model_dir,
            "--model_name",
            os.path.basename(model_dir.rstrip("/\\")),
            "--save_path",
            str(output_dir),
        ]
    )
    return command


def parse_paddle_text_detection_lines(lines: Iterable[str]) -> tuple[DetectionGridResult, ...]:
    results: list[DetectionGridResult] = []
    for raw_line in lines:
        line = raw_line.strip()
        if not line or not line.startswith("{"):
            continue
        payload = json.loads(line)
        if "input_path" not in payload:
            continue
        results.append(_parse_paddle_detection_payload(payload))
    return tuple(results)


def _parse_paddle_detection_payload(payload: dict[str, Any]) -> DetectionGridResult:
    polygons = tuple(_parse_polygon(item) for item in payload.get("dt_polys", []))
    scores = tuple(float(value) for value in payload.get("dt_scores", []))
    return DetectionGridResult(
        input_path=Path(str(payload["input_path"])),
        polygons=polygons,
        scores=scores,
        raw=payload,
    )


def _parse_polygon(raw_polygon: Any) -> DetectionPolygon:
    points = tuple((float(point[0]), float(point[1])) for point in raw_polygon)
    if len(points) != 4:
        raise ValueError("Detection polygons must contain exactly 4 points.")
    return points  # type: ignore[return-value]
