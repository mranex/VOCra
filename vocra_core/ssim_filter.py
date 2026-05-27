from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import cv2
import numpy as np

from vocra_core.project_manager import load_project, update_status

try:
    from skimage.metrics import structural_similarity as _skimage_ssim
except Exception:
    _skimage_ssim = None


ProgressCallback = Callable[[int, int | None, str], None]


def filter_frames_by_ssim(
    project_dir: str,
    ssim_threshold: float | None = None,
    callback: ProgressCallback | None = None,
) -> dict:
    progress = load_project(project_dir)
    project_path = Path(project_dir).expanduser().resolve()
    cropped_dir = project_path / progress["frame_extract"]["cropped_dir"]
    ssim_filter_path = project_path / progress["cache_files"]["ssim_filter"]
    image_files = sorted(cropped_dir.glob("*.png"))
    total = len(image_files)
    if total == 0:
        raise RuntimeError("No cropped images found for SSIM filtering")

    ssim_config = progress.get("ssim_filter", {})
    enabled = bool(ssim_config.get("enabled", True))
    threshold = float(ssim_threshold if ssim_threshold is not None else ssim_config.get("threshold", 0.95))
    image_names = [path.name for path in image_files]

    if progress["status"].get("ssim_filtered", False) and ssim_filter_path.exists():
        try:
            with ssim_filter_path.open("r", encoding="utf-8") as handle:
                existing_payload = json.load(handle)
            if _is_cache_compatible(existing_payload, enabled, threshold, image_names):
                if callback:
                    callback(total, total, "SSIM filter already prepared")
                return {
                    "unique_count": int(existing_payload.get("unique_count", total)),
                    "duplicate_count": int(existing_payload.get("duplicate_count", 0)),
                }
        except Exception:
            pass

    if not enabled:
        payload = _build_passthrough_payload(threshold, image_names)
        _write_payload(ssim_filter_path, payload)
        update_status(project_dir, "ssim_filtered", True)
        if callback:
            callback(total, total, "SSIM filter disabled, keeping all frames")
        return {
            "unique_count": total,
            "duplicate_count": 0,
        }

    first_image = _read_grayscale(image_files[0])
    unique_frames = [image_files[0].name]
    frame_map = {image_files[0].name: image_files[0].name}
    unique_count = 1
    duplicate_count = 0
    last_unique_name = image_files[0].name
    last_unique_image = first_image

    if callback:
        callback(1, total, f"unique {last_unique_name} (seed)")

    for index, image_path in enumerate(image_files[1:], start=2):
        current_image = _read_grayscale(image_path)
        score = _compute_ssim(last_unique_image, current_image)

        if score >= threshold:
            frame_map[image_path.name] = last_unique_name
            duplicate_count += 1
            message = f"duplicate {image_path.name} -> {last_unique_name} (ssim={score:.3f})"
        else:
            frame_map[image_path.name] = image_path.name
            unique_frames.append(image_path.name)
            unique_count += 1
            last_unique_name = image_path.name
            last_unique_image = current_image
            message = f"unique {image_path.name} (ssim={score:.3f})"

        if callback:
            callback(index, total, message)

    payload = {
        "enabled": True,
        "threshold": threshold,
        "total_frames": total,
        "unique_count": unique_count,
        "duplicate_count": duplicate_count,
        "unique_frames": unique_frames,
        "frame_map": frame_map,
    }
    _write_payload(ssim_filter_path, payload)
    update_status(project_dir, "ssim_filtered", True)
    if callback:
        callback(total, total, f"SSIM filter ready ({unique_count} unique / {duplicate_count} duplicates)")
    return {
        "unique_count": unique_count,
        "duplicate_count": duplicate_count,
    }


def _build_passthrough_payload(threshold: float, image_names: list[str]) -> dict:
    frame_map = {name: name for name in image_names}
    return {
        "enabled": False,
        "threshold": threshold,
        "total_frames": len(image_names),
        "unique_count": len(image_names),
        "duplicate_count": 0,
        "unique_frames": list(image_names),
        "frame_map": frame_map,
    }


def _write_payload(ssim_filter_path: Path, payload: dict) -> None:
    ssim_filter_path.parent.mkdir(parents=True, exist_ok=True)
    with ssim_filter_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def _is_cache_compatible(payload: dict, enabled: bool, threshold: float, image_names: list[str]) -> bool:
    payload_enabled = bool(payload.get("enabled", True))
    payload_threshold = float(payload.get("threshold", 0.95))
    payload_total = int(payload.get("total_frames", -1))
    payload_unique = payload.get("unique_frames", [])
    payload_map = payload.get("frame_map", {})
    if payload_enabled != enabled:
        return False
    if abs(payload_threshold - threshold) > 1e-9:
        return False
    if payload_total != len(image_names):
        return False
    if sorted(payload_map) != sorted(image_names):
        return False
    if not isinstance(payload_unique, list) or not payload_unique:
        return False
    return True


def _read_grayscale(image_path: Path) -> np.ndarray:
    image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"Failed to read cropped image: {image_path}")
    return image


def _compute_ssim(img_a: np.ndarray, img_b: np.ndarray) -> float:
    if img_a.shape != img_b.shape:
        img_b = cv2.resize(img_b, (img_a.shape[1], img_a.shape[0]))

    if np.array_equal(img_a, img_b):
        return 1.0

    if _skimage_ssim is not None:
        try:
            return float(_skimage_ssim(img_a, img_b, data_range=255))
        except Exception:
            pass

    return _compute_ssim_fallback(img_a, img_b)


def _compute_ssim_fallback(img_a: np.ndarray, img_b: np.ndarray) -> float:
    arr_a = img_a.astype(np.float64)
    arr_b = img_b.astype(np.float64)

    mean_a = float(arr_a.mean())
    mean_b = float(arr_b.mean())
    var_a = float(arr_a.var())
    var_b = float(arr_b.var())
    covariance = float(((arr_a - mean_a) * (arr_b - mean_b)).mean())

    c1 = (0.01 * 255) ** 2
    c2 = (0.03 * 255) ** 2
    denominator = (mean_a**2 + mean_b**2 + c1) * (var_a + var_b + c2)
    if denominator == 0:
        return 1.0

    numerator = (2 * mean_a * mean_b + c1) * (2 * covariance + c2)
    score = numerator / denominator
    return float(max(-1.0, min(1.0, score)))
