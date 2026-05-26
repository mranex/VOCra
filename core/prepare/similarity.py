"""Similarity helpers for Prepare-stage image filtering."""

from __future__ import annotations

from typing import Any

import numpy as np

try:
    import fast_ssim  # type: ignore
except ImportError:  # pragma: no cover - optional at runtime
    fast_ssim = None


def compute_ssim_similarity(left: Any, right: Any) -> float:
    """Compute legacy-style SSIM with a deterministic fallback."""
    if _is_empty_image(left) or _is_empty_image(right):
        return 0.0
    if getattr(left, "shape", None) != getattr(right, "shape", None):
        return 0.0

    if fast_ssim is not None:
        return float(fast_ssim.ssim(left, right, data_range=255))

    left_arr = np.asarray(left, dtype=np.float32)
    right_arr = np.asarray(right, dtype=np.float32)
    delta = np.abs(left_arr - right_arr)
    return max(0.0, 1.0 - float(delta.mean() / 255.0))


def _is_empty_image(image: Any) -> bool:
    if image is None:
        return True
    size = getattr(image, "size", None)
    if isinstance(size, int):
        return size == 0
    try:
        return len(image) == 0  # type: ignore[arg-type]
    except Exception:
        return False
