"""Video capture helpers for VOCra."""

from __future__ import annotations

from pathlib import Path
from types import TracebackType
from typing import Any, Protocol


class VideoCaptureError(RuntimeError):
    """Raised when VOCra cannot open or decode video frames."""


class VideoCapture(Protocol):
    """Small capture protocol used by Prepare sampling code."""

    def read(self) -> tuple[bool, Any | None, float]:
        """Return success flag, frame object, and timestamp in milliseconds."""

    def seek(self, target_ms: float) -> None:
        """Move decode position to the requested timestamp when supported."""


class PyAvVideoCapture:
    """Thin PyAV-backed capture adapter extracted from legacy VideOCR semantics."""

    def __init__(self, video_path: Path) -> None:
        self.path = video_path.expanduser().resolve()
        self.container: Any | None = None
        self.stream: Any | None = None
        self.frame_iterator: Any | None = None

    def __enter__(self) -> PyAvVideoCapture:
        try:
            import av
        except ImportError as exc:
            raise VideoCaptureError(
                "PyAV is required to decode video frames in VOCra."
            ) from exc

        try:
            self.container = av.open(str(self.path))
            self.stream = next(
                (item for item in self.container.streams if item.type == "video"),
                None,
            )
            if self.stream is None:
                raise VideoCaptureError(f"No video stream found in source file: {self.path}")
            self.stream.thread_type = "FRAME"
            self.frame_iterator = self.container.decode(self.stream)
            return self
        except VideoCaptureError:
            raise
        except Exception as exc:
            raise VideoCaptureError(f"Can not open video {self.path}.") from exc

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self.container is not None:
            self.container.close()

    def read(self) -> tuple[bool, Any | None, float]:
        try:
            if self.frame_iterator is None or self.stream is None or self.stream.time_base is None:
                return False, None, 0.0

            frame = next(self.frame_iterator)
            timestamp_ms = (
                float(frame.pts * self.stream.time_base * 1000)
                if frame.pts is not None
                else 0.0
            )
            return True, frame, timestamp_ms
        except StopIteration:
            return False, None, 0.0

    def seek(self, target_ms: float) -> None:
        if self.container is None or self.stream is None or self.stream.time_base is None:
            return

        target_pts = int((target_ms / 1000.0) / float(self.stream.time_base))
        self.container.seek(target_pts, stream=self.stream)
        self.frame_iterator = self.container.decode(self.stream)


def open_video_capture(video_path: Path) -> PyAvVideoCapture:
    """Create a PyAV-backed capture object for a source video."""
    return PyAvVideoCapture(video_path)
