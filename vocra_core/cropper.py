from __future__ import annotations

from pathlib import Path
from typing import Callable

import cv2

from vocra_core.project_manager import load_project, update_status


ProgressCallback = Callable[[int, int | None, str], None]


def crop_frames(project_dir: str, callback: ProgressCallback | None = None) -> int:
    progress = load_project(project_dir)
    project_path = Path(project_dir).expanduser().resolve()
    crop_box = progress["subtitle_crop"]
    frames_dir = project_path / progress["frame_extract"]["frames_dir"]
    cropped_dir = project_path / progress["frame_extract"]["cropped_dir"]

    cropped_dir.mkdir(parents=True, exist_ok=True)
    frame_files = sorted(frames_dir.glob("*.png"))
    total = len(frame_files)
    if total == 0:
        raise RuntimeError("No extracted frames found to crop")

    x = int(crop_box["x"])
    y = int(crop_box["y"])
    width = int(crop_box["width"])
    height = int(crop_box["height"])

    for index, frame_path in enumerate(frame_files, start=1):
        output_path = cropped_dir / frame_path.name
        if output_path.exists():
            if callback:
                callback(index, total, f"skip {frame_path.name}")
            continue

        image = cv2.imread(str(frame_path))
        if image is None:
            raise RuntimeError(f"Failed to read frame image: {frame_path}")

        image_height, image_width = image.shape[:2]
        if x < 0 or y < 0 or width <= 0 or height <= 0 or x + width > image_width or y + height > image_height:
            raise ValueError(
                f"Invalid subtitle crop {crop_box} for image size {image_width}x{image_height}"
            )

        cropped = image[y : y + height, x : x + width]
        if not cv2.imwrite(str(output_path), cropped):
            raise RuntimeError(f"Failed to write cropped image: {output_path}")

        if callback:
            callback(index, total, frame_path.name)

    update_status(project_dir, "cropped_done", True)
    return len(sorted(cropped_dir.glob("*.png")))
