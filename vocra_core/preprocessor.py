from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

from vocra_core.project_manager import load_project, update_status


ProgressCallback = Callable[[int, int | None, str], None]


def preprocess_representatives(
    project_dir: str,
    callback: ProgressCallback | None = None,
) -> int:
    progress = load_project(project_dir)
    project_path = Path(project_dir).expanduser().resolve()
    segments_path = project_path / progress["cache_files"]["segments"]
    cropped_dir = project_path / progress["frame_extract"]["cropped_dir"]
    preprocessed_dir = project_path / progress["frame_extract"]["preprocessed_dir"]

    with segments_path.open("r", encoding="utf-8") as handle:
        segments_payload = json.load(handle)

    represent_images = [segment["represent_image"] for segment in segments_payload.get("segments", [])]
    total = len(represent_images)
    if total == 0:
        raise RuntimeError("No segments found for preprocessing")

    preprocessed_dir.mkdir(parents=True, exist_ok=True)

    for index, image_name in enumerate(represent_images, start=1):
        source_path = cropped_dir / image_name
        output_path = preprocessed_dir / image_name

        if output_path.exists():
            if callback:
                callback(index, total, f"skip {image_name}")
            continue

        processed = _preprocess_single(str(source_path))
        if not cv2.imwrite(str(output_path), processed):
            raise RuntimeError(f"Failed to write preprocessed image: {output_path}")

        if callback:
            callback(index, total, image_name)

    update_status(project_dir, "preprocessed_done", True)
    return len(list(preprocessed_dir.glob("*.png")))


def _preprocess_single(image_path: str) -> np.ndarray:
    image = cv2.imread(image_path)
    if image is None:
        raise RuntimeError(f"Failed to read cropped image: {image_path}")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    height, width = enhanced.shape
    upscaled = cv2.resize(enhanced, (width * 2, height * 2), interpolation=cv2.INTER_CUBIC)

    if float(np.mean(upscaled)) <= 128.0:
        upscaled = cv2.bitwise_not(upscaled)

    return upscaled
