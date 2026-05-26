"""Video utilities for VOCra."""

from __future__ import annotations


def __getattr__(name: str):
    if name in {"PyAvVideoCapture", "VideoCapture", "VideoCaptureError", "open_video_capture"}:
        from vocra.core.video.capture import (
            PyAvVideoCapture,
            VideoCapture,
            VideoCaptureError,
            open_video_capture,
        )

        return {
            "PyAvVideoCapture": PyAvVideoCapture,
            "VideoCapture": VideoCapture,
            "VideoCaptureError": VideoCaptureError,
            "open_video_capture": open_video_capture,
        }[name]

    if name in {"VideoProbeError", "probe_video"}:
        from vocra.core.video.probe import VideoProbeError, probe_video

        return {
            "VideoProbeError": VideoProbeError,
            "probe_video": probe_video,
        }[name]

    if name in {"VideoPreviewFrame", "load_video_preview_frame"}:
        from vocra.core.video.preview import VideoPreviewFrame, load_video_preview_frame

        return {
            "VideoPreviewFrame": VideoPreviewFrame,
            "load_video_preview_frame": load_video_preview_frame,
        }[name]

    if name in {
        "compute_subtitle_ms_range",
        "format_srt_timestamp",
        "format_srt_timestamp_from_ms",
        "parse_time_str_to_ms",
    }:
        from vocra.core.video.timestamps import (
            compute_subtitle_ms_range,
            format_srt_timestamp,
            format_srt_timestamp_from_ms,
            parse_time_str_to_ms,
        )

        return {
            "compute_subtitle_ms_range": compute_subtitle_ms_range,
            "format_srt_timestamp": format_srt_timestamp,
            "format_srt_timestamp_from_ms": format_srt_timestamp_from_ms,
            "parse_time_str_to_ms": parse_time_str_to_ms,
        }[name]

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
