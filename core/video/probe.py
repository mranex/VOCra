"""Source video probing for VOCra projects."""

from __future__ import annotations

import hashlib
from pathlib import Path

from vocra.core.project.schema import SourceVideo


class VideoProbeError(RuntimeError):
    """Raised when VOCra cannot inspect the source video."""


def probe_video(video_path: Path) -> SourceVideo:
    path = video_path.expanduser().resolve()
    if not path.exists():
        raise VideoProbeError(f"Source video does not exist: {path}")
    if not path.is_file():
        raise VideoProbeError(f"Source video is not a file: {path}")

    fingerprint = _compute_fingerprint(path)
    try:
        import av
    except ImportError as exc:
        raise VideoProbeError(
            "PyAV is required to probe video metadata in VOCra."
        ) from exc

    try:
        with av.open(str(path)) as container:
            stream = next((item for item in container.streams if item.type == "video"), None)
            if stream is None:
                raise VideoProbeError(f"No video stream found in source file: {path}")

            width = int(stream.width or 0)
            height = int(stream.height or 0)
            fps = _probe_fps(stream)
            duration_ms = _probe_duration_ms(container, stream)
            start_time_offset_ms = _probe_start_time_offset_ms(stream)
    except VideoProbeError:
        raise
    except Exception as exc:
        raise VideoProbeError(f"Failed to probe video metadata for {path}: {exc}") from exc

    return SourceVideo(
        path=path,
        fingerprint=fingerprint,
        duration_ms=duration_ms,
        width=width,
        height=height,
        fps=fps,
        start_time_offset_ms=start_time_offset_ms,
    )


def _compute_fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    stat = path.stat()
    digest.update(str(path).encode("utf-8"))
    digest.update(str(stat.st_size).encode("utf-8"))
    digest.update(str(stat.st_mtime_ns).encode("utf-8"))

    with path.open("rb") as handle:
        first_chunk = handle.read(65536)
        digest.update(first_chunk)
        if stat.st_size > 65536:
            handle.seek(max(stat.st_size - 65536, 0))
            digest.update(handle.read(65536))

    return digest.hexdigest()


def _probe_duration_ms(container, stream) -> int:
    if stream.duration is not None and stream.time_base is not None:
        return int(float(stream.duration * stream.time_base) * 1000)
    if container.duration is not None:
        return int(container.duration / 1000)
    return 0


def _probe_fps(stream) -> float:
    if stream.average_rate is not None:
        return float(stream.average_rate)
    if stream.base_rate is not None:
        return float(stream.base_rate)
    return 0.0


def _probe_start_time_offset_ms(stream) -> float:
    if stream.start_time is None or stream.time_base is None:
        return 0.0
    return float(stream.start_time * stream.time_base) * 1000.0
