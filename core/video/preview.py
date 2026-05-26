"""Read-only source-video preview helpers for VOCra."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, Callable

from PIL import Image

from vocra.core.video.capture import VideoCaptureError, open_video_capture


@dataclass(frozen=True)
class VideoPreviewFrame:
    requested_ms: int
    actual_ms: int
    source_width: int
    source_height: int
    display_width: int
    display_height: int
    png_bytes: bytes


def load_video_preview_frame(
    video_path: Path,
    target_ms: int,
    *,
    max_width: int = 640,
    max_height: int = 360,
    capture_factory: Callable[[Path], Any] = open_video_capture,
    frame_to_image: Callable[[Any], Any] | None = None,
) -> VideoPreviewFrame:
    requested_ms = max(int(target_ms), 0)
    converter = frame_to_image or _default_frame_to_image
    try:
        with capture_factory(video_path) as capture:
            capture.seek(float(requested_ms))
            ok, frame, timestamp_ms = capture.read()
    except VideoCaptureError:
        raise
    except Exception as exc:
        raise VideoCaptureError(f"Failed to load preview frame from {video_path}.") from exc

    if not ok or frame is None:
        raise VideoCaptureError(f"No preview frame could be decoded from {video_path}.")

    image = Image.fromarray(converter(frame))
    source_width, source_height = image.size
    display_width, display_height = _fit_size(
        source_width,
        source_height,
        max_width=max_width,
        max_height=max_height,
    )
    if (display_width, display_height) != image.size:
        image = image.resize((display_width, display_height))
    return VideoPreviewFrame(
        requested_ms=requested_ms,
        actual_ms=max(int(round(timestamp_ms)), 0),
        source_width=source_width,
        source_height=source_height,
        display_width=display_width,
        display_height=display_height,
        png_bytes=_encode_png(image),
    )


def _default_frame_to_image(frame: Any) -> Any:
    if hasattr(frame, "to_ndarray"):
        return frame.to_ndarray(format="rgb24")
    return frame


def _fit_size(
    source_width: int,
    source_height: int,
    *,
    max_width: int,
    max_height: int,
) -> tuple[int, int]:
    if source_width <= 0 or source_height <= 0:
        raise VideoCaptureError("Preview frame has invalid image dimensions.")
    width_scale = max_width / source_width
    height_scale = max_height / source_height
    scale = min(width_scale, height_scale, 1.0)
    return (
        max(int(round(source_width * scale)), 1),
        max(int(round(source_height * scale)), 1),
    )


def _encode_png(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
