"""Fake Prepare detector backend for tests and synthetic flows."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

from vocra.core.prepare.detectors.base import DetectionGridResult, DetectionPolygon


class FakeTextDetectorBackend:
    name = "fake-text-detector"

    def validate_config(self, config: dict[str, Any]) -> None:
        score = float(config.get("score", 0.95))
        if not 0.0 <= score <= 1.0:
            raise ValueError("Fake detector score must be between 0.0 and 1.0.")

    def detect_grids(
        self,
        image_dir: Path,
        output_dir: Path,
        config: dict[str, Any],
    ) -> tuple[DetectionGridResult, ...]:
        self.validate_config(config)
        output_dir.mkdir(parents=True, exist_ok=True)
        margin = int(config.get("box_margin", 8))
        score = float(config.get("score", 0.95))

        items: list[DetectionGridResult] = []
        for image_path in sorted(path for path in image_dir.iterdir() if path.is_file()):
            if image_path.name in set(config.get("empty_images", [])):
                items.append(
                    DetectionGridResult(
                        input_path=image_path,
                        polygons=(),
                        scores=(),
                        raw={"backend": self.name, "image": image_path.name, "empty": True},
                    )
                )
                continue

            right_x = 100.0 - float(margin)
            bottom_y = 40.0
            if bool(config.get("cover_full_image", False)):
                with Image.open(image_path) as image:
                    right_x = float(image.width) - float(margin)
                    bottom_y = float(image.height) - float(margin)

            polygon: DetectionPolygon = (
                (float(margin), float(margin)),
                (right_x, float(margin)),
                (right_x, bottom_y),
                (float(margin), bottom_y),
            )
            items.append(
                DetectionGridResult(
                    input_path=image_path,
                    polygons=(polygon,),
                    scores=(score,),
                    raw={"backend": self.name, "image": image_path.name},
                )
            )
        return tuple(items)
