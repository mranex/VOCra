from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import textwrap
from pathlib import Path
from typing import Callable

from vocra_core.exporter import _build_export_entries, _escape_ass_text, _to_ass_timestamp
from vocra_core.project_manager import load_project, save_progress


ProgressCallback = Callable[[int, int | None, str], None]

NVENC_ENCODERS_BY_CODEC = {
    "h264": "h264_nvenc",
    "avc1": "h264_nvenc",
    "hevc": "hevc_nvenc",
    "h265": "hevc_nvenc",
    "av1": "av1_nvenc",
}

BURN_STYLE_PRESETS = {
    "balanced": {
        "label": "Balanced",
        "font": "Arial",
        "font_size": 42,
        "outline": 2,
        "shadow": 0,
        "margin_v": 40,
    },
    "large": {
        "label": "Large",
        "font": "Arial",
        "font_size": 52,
        "outline": 3,
        "shadow": 1,
        "margin_v": 48,
    },
    "compact": {
        "label": "Compact",
        "font": "Arial",
        "font_size": 34,
        "outline": 2,
        "shadow": 0,
        "margin_v": 32,
    },
}

ASS_ALIGNMENT = {
    "bottom_left": 1,
    "bottom_center": 2,
    "bottom_right": 3,
    "middle_left": 4,
    "middle_center": 5,
    "middle_right": 6,
    "top_left": 7,
    "top_center": 8,
    "top_right": 9,
}

DEFAULT_BURN_STYLE = {
    "font_family": "Arial",
    "font_size": 42,
    "bold": False,
    "italic": False,
    "primary_color": "#FFFFFF",
    "outline_color": "#000000",
    "shadow_color": "#000000",
    "opacity": 100,
    "outline_width": 2,
    "shadow_depth": 0,
    "alignment": "bottom_center",
    "margin_l": 40,
    "margin_r": 40,
    "margin_v": 40,
    "max_line_chars": 42,
    "position_mode": "screen",
}


def default_burn_config() -> dict:
    return {
        "ffmpeg_path": "",
        "blur_enabled": True,
        "blur_strength": 8,
        "style_preset": "balanced",
        "burn_style": dict(DEFAULT_BURN_STYLE),
    }


def build_default_output_path(project_dir: str, progress: dict | None = None) -> str:
    project_path = Path(project_dir).expanduser().resolve()
    manifest = progress or load_project(str(project_path))
    project_name = str(manifest.get("project_name") or project_path.name)
    return str(project_path / "exports" / f"{_safe_stem(project_name)}.burned.mp4")


def resolve_ffmpeg_path(configured_path: str | None = None) -> str:
    candidate = str(configured_path or "").strip().strip('"')
    if candidate:
        resolved = Path(candidate).expanduser()
        if resolved.exists():
            return str(resolved.resolve())
        found = shutil.which(candidate)
        if found:
            return found
        raise FileNotFoundError(f"FFmpeg not found: {candidate}")

    found = shutil.which("ffmpeg")
    if found:
        return found
    raise FileNotFoundError("FFmpeg not found in PATH. Set FFmpeg Path in Config.")


def resolve_ffprobe_path(ffmpeg_path: str) -> str:
    ffmpeg_file = Path(ffmpeg_path)
    suffix = ".exe" if ffmpeg_file.suffix.lower() == ".exe" else ""
    sibling = ffmpeg_file.with_name(f"ffprobe{suffix}")
    if sibling.exists():
        return str(sibling.resolve())
    found = shutil.which("ffprobe")
    if found:
        return found
    raise FileNotFoundError("ffprobe not found. Install it next to ffmpeg or in PATH.")


def probe_video(video_path: str, *, ffprobe_path: str) -> dict:
    command = [
        ffprobe_path,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=codec_name,width,height,duration:format=duration",
        "-of",
        "json",
        video_path,
    ]
    result = _run_capture(command, timeout=30)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffprobe failed")

    payload = json.loads(result.stdout or "{}")
    streams = payload.get("streams", [])
    if not streams:
        raise RuntimeError("No video stream found.")
    stream = streams[0]
    duration = stream.get("duration") or payload.get("format", {}).get("duration") or 0
    return {
        "codec_name": str(stream.get("codec_name", "") or "").lower(),
        "width": int(stream.get("width") or 0),
        "height": int(stream.get("height") or 0),
        "duration": float(duration or 0),
    }


def select_nvenc_encoder(codec_name: str, available_encoders: set[str] | None = None) -> str:
    normalized = str(codec_name or "").lower()
    preferred = NVENC_ENCODERS_BY_CODEC.get(normalized, "h264_nvenc")
    if available_encoders is None:
        return preferred
    if preferred in available_encoders:
        return preferred
    if "h264_nvenc" in available_encoders:
        return "h264_nvenc"
    raise RuntimeError("h264_nvenc is not available in this FFmpeg build.")


def build_burn_filter(
    *,
    subtitle_path: str,
    crop: dict,
    blur_enabled: bool,
    blur_strength: int | float,
) -> str:
    subtitle_filter = f"subtitles=filename='{_escape_filter_path(subtitle_path)}'"
    if not blur_enabled:
        return f"[0:v]{subtitle_filter}[v]"

    x = max(0, int(crop.get("x", 0) or 0))
    y = max(0, int(crop.get("y", 0) or 0))
    width = max(1, int(crop.get("width", 0) or 0))
    height = max(1, int(crop.get("height", 0) or 0))
    sigma = max(0.1, min(float(blur_strength or 8), 64.0))
    return (
        f"[0:v]split=2[base][blur_src];"
        f"[blur_src]crop={width}:{height}:{x}:{y},gblur=sigma={sigma:.1f}[blurred];"
        f"[base][blurred]overlay={x}:{y}[blurred_base];"
        f"[blurred_base]{subtitle_filter}[v]"
    )


def run_burn_video(
    project_dir: str,
    *,
    output_path: str,
    export_source: str,
    ffmpeg_path: str = "",
    blur_enabled: bool = True,
    blur_strength: int = 8,
    style_preset: str = "balanced",
    burn_style: dict | None = None,
    callback: ProgressCallback | None = None,
) -> str:
    progress = load_project(project_dir)
    project_path = Path(project_dir).expanduser().resolve()
    video_path = Path(str(progress.get("video_path", ""))).expanduser().resolve()
    if not video_path.exists():
        raise FileNotFoundError(f"Source video not found: {video_path}")

    resolved_ffmpeg = resolve_ffmpeg_path(ffmpeg_path)
    ffprobe_path = resolve_ffprobe_path(resolved_ffmpeg)
    video_info = probe_video(str(video_path), ffprobe_path=ffprobe_path)
    encoders = available_video_encoders(resolved_ffmpeg)
    encoder = select_nvenc_encoder(video_info.get("codec_name", ""), encoders)

    output_file = Path(output_path).expanduser().resolve()
    if output_file.suffix.lower() != ".mp4":
        output_file = output_file.with_suffix(".mp4")
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="vocra_burn_") as temp_dir:
        ass_path = Path(temp_dir) / "subtitle.ass"
        write_burn_ass(
            project_dir,
            str(ass_path),
            export_source=export_source,
            video_width=int(video_info.get("width") or 1920),
            video_height=int(video_info.get("height") or 1080),
            style_preset=style_preset,
            burn_style=burn_style,
        )
        filter_graph = build_burn_filter(
            subtitle_path=str(ass_path),
            crop=progress.get("subtitle_crop", {}),
            blur_enabled=blur_enabled,
            blur_strength=blur_strength,
        )
        command = [
            resolved_ffmpeg,
            "-y",
            "-hide_banner",
            "-i",
            str(video_path),
            "-filter_complex",
            filter_graph,
            "-map",
            "[v]",
            "-map",
            "0:a?",
            "-map_metadata",
            "0",
            "-c:v",
            encoder,
            "-preset",
            "p4",
            "-cq",
            "19",
            "-b:v",
            "0",
            "-c:a",
            "copy",
            "-movflags",
            "+faststart",
            str(output_file),
        ]
        _run_ffmpeg_stream(command, float(video_info.get("duration") or 0), callback)

    refreshed = load_project(project_dir)
    burn_status = refreshed.setdefault("burn_video", {})
    burn_status.update(
        {
            "last_output_path": str(output_file),
            "last_export_source": export_source,
            "last_encoder": encoder,
            "last_blur_enabled": bool(blur_enabled),
            "last_blur_strength": int(blur_strength),
            "last_style_preset": style_preset,
            "last_burn_style": normalize_burn_style(burn_style, style_preset=style_preset),
        }
    )
    save_progress(project_dir, refreshed)
    return str(output_file)


def write_burn_ass(
    project_dir: str,
    output_path: str,
    *,
    export_source: str,
    video_width: int,
    video_height: int,
    style_preset: str,
    burn_style: dict | None = None,
) -> str:
    entries = _build_export_entries(project_dir, export_source=export_source)
    progress = load_project(project_dir)
    style = normalize_burn_style(burn_style, style_preset=style_preset)
    crop = progress.get("subtitle_crop", {}) or {}
    header = "\n".join(
        [
            "[Script Info]",
            "ScriptType: v4.00+",
            "Collisions: Normal",
            "WrapStyle: 0",
            "ScaledBorderAndShadow: yes",
            f"PlayResX: {max(1, int(video_width or 1920))}",
            f"PlayResY: {max(1, int(video_height or 1080))}",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            _build_ass_style_line(style),
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
    )
    event_lines = [
        f"Dialogue: 0,{_to_ass_timestamp(entry['start'])},{_to_ass_timestamp(entry['end'])},Default,,0,0,0,,{render_ass_dialogue_text(entry['text'], style, crop)}"
        for entry in entries
    ]
    output_file = Path(output_path).expanduser().resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(header + "\n" + "\n".join(event_lines) + "\n", encoding="utf-8")
    return str(output_file)


def normalize_burn_style(style: dict | None = None, *, style_preset: str = "balanced") -> dict:
    normalized = dict(DEFAULT_BURN_STYLE)
    preset = BURN_STYLE_PRESETS.get(style_preset, BURN_STYLE_PRESETS["balanced"])
    normalized.update(
        {
            "font_family": preset.get("font", normalized["font_family"]),
            "font_size": preset.get("font_size", normalized["font_size"]),
            "outline_width": preset.get("outline", normalized["outline_width"]),
            "shadow_depth": preset.get("shadow", normalized["shadow_depth"]),
            "margin_v": preset.get("margin_v", normalized["margin_v"]),
        }
    )
    if isinstance(style, dict):
        normalized.update({key: value for key, value in style.items() if value is not None})

    normalized["font_family"] = str(normalized.get("font_family") or "Arial").replace(",", " ")
    normalized["font_size"] = max(1, int(normalized.get("font_size") or 42))
    normalized["bold"] = bool(normalized.get("bold", False))
    normalized["italic"] = bool(normalized.get("italic", False))
    normalized["primary_color"] = _normalize_hex_color(str(normalized.get("primary_color", "#FFFFFF")))
    normalized["outline_color"] = _normalize_hex_color(str(normalized.get("outline_color", "#000000")))
    normalized["shadow_color"] = _normalize_hex_color(str(normalized.get("shadow_color", "#000000")))
    normalized["opacity"] = max(0, min(100, int(normalized.get("opacity", 100) or 100)))
    normalized["outline_width"] = max(0, int(normalized.get("outline_width", 2) or 0))
    normalized["shadow_depth"] = max(0, int(normalized.get("shadow_depth", 0) or 0))
    alignment = str(normalized.get("alignment") or "bottom_center")
    normalized["alignment"] = alignment if alignment in ASS_ALIGNMENT else "bottom_center"
    normalized["margin_l"] = max(0, int(normalized.get("margin_l", 40) or 0))
    normalized["margin_r"] = max(0, int(normalized.get("margin_r", 40) or 0))
    normalized["margin_v"] = max(0, int(normalized.get("margin_v", 40) or 0))
    normalized["max_line_chars"] = max(8, min(120, int(normalized.get("max_line_chars", 42) or 42)))
    position_mode = str(normalized.get("position_mode") or "screen")
    normalized["position_mode"] = "crop_stamp" if position_mode == "crop_stamp" else "screen"
    return normalized


def render_ass_dialogue_text(text: str, style: dict, crop: dict | None = None) -> str:
    normalized = normalize_burn_style(style)
    content = _wrap_text_for_style(str(text or ""), normalized, crop or {})
    escaped = _escape_ass_text(content)
    if normalized["position_mode"] != "crop_stamp":
        return escaped
    x = int(crop.get("x", 0) or 0)
    y = int(crop.get("y", 0) or 0)
    width = int(crop.get("width", 0) or 0)
    height = int(crop.get("height", 0) or 0)
    cx = x + max(1, width) / 2.0
    cy = y + max(1, height) / 2.0
    return r"{\an5\pos(" + f"{cx:.1f},{cy:.1f}" + ")}" + escaped


def _build_ass_style_line(style: dict) -> str:
    normalized = normalize_burn_style(style)
    alpha = _opacity_to_ass_alpha(normalized["opacity"])
    primary = _hex_to_ass_color(normalized["primary_color"], alpha=alpha)
    outline = _hex_to_ass_color(normalized["outline_color"], alpha=0)
    shadow = _hex_to_ass_color(normalized["shadow_color"], alpha=0)
    bold = -1 if normalized["bold"] else 0
    italic = -1 if normalized["italic"] else 0
    alignment = ASS_ALIGNMENT[normalized["alignment"]]
    return (
        "Style: Default,"
        f"{normalized['font_family']},{normalized['font_size']},{primary},&H000000FF,{outline},{shadow},"
        f"{bold},{italic},0,0,100,100,0,0,1,{normalized['outline_width']},{normalized['shadow_depth']},"
        f"{alignment},{normalized['margin_l']},{normalized['margin_r']},{normalized['margin_v']},1"
    )


def _wrap_text_for_style(text: str, style: dict, crop: dict) -> str:
    normalized = normalize_burn_style(style)
    max_chars = int(normalized["max_line_chars"])
    if normalized["position_mode"] == "crop_stamp":
        crop_width = int(crop.get("width", 0) or 0)
        if crop_width > 0:
            estimated = int(crop_width / max(1.0, normalized["font_size"] * 0.55))
            max_chars = max(8, min(max_chars, estimated))
    wrapped_lines: list[str] = []
    for raw_line in str(text or "").replace("\r", "").split("\n"):
        if not raw_line:
            wrapped_lines.append("")
            continue
        wrapped = textwrap.wrap(raw_line, width=max_chars, break_long_words=False, break_on_hyphens=False)
        wrapped_lines.extend(wrapped or [raw_line])
    return "\n".join(wrapped_lines)


def available_video_encoders(ffmpeg_path: str) -> set[str]:
    result = _run_capture([ffmpeg_path, "-hide_banner", "-encoders"], timeout=30)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "Unable to list FFmpeg encoders")
    return parse_video_encoders(result.stdout)


def parse_video_encoders(output: str) -> set[str]:
    encoders: set[str] = set()
    for line in str(output or "").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0].startswith("V"):
            encoders.add(parts[1])
    return encoders


def check_ffmpeg(ffmpeg_path: str = "") -> dict:
    try:
        resolved = resolve_ffmpeg_path(ffmpeg_path)
        version = _run_capture([resolved, "-hide_banner", "-version"], timeout=15)
        if version.returncode != 0:
            return {"ok": False, "ffmpeg_path": resolved, "message": version.stderr.strip() or "FFmpeg failed"}
        encoders = available_video_encoders(resolved)
        return {
            "ok": True,
            "ffmpeg_path": resolved,
            "has_h264_nvenc": "h264_nvenc" in encoders,
            "has_hevc_nvenc": "hevc_nvenc" in encoders,
            "has_av1_nvenc": "av1_nvenc" in encoders,
            "message": "FFmpeg is available.",
        }
    except Exception as exc:
        return {"ok": False, "ffmpeg_path": "", "message": str(exc)}


def check_nvidia_encode(ffmpeg_path: str = "") -> dict:
    try:
        resolved = resolve_ffmpeg_path(ffmpeg_path)
        version = _run_capture([resolved, "-hide_banner", "-version"], timeout=15)
        ffmpeg_ok = version.returncode == 0
        hwaccels_result = _run_capture([resolved, "-hide_banner", "-hwaccels"], timeout=15)
        hwaccels = hwaccels_result.stdout.lower()
        cuda_ok = "cuda" in hwaccels
        encoders = available_video_encoders(resolved) if ffmpeg_ok else set()
        practical = _run_capture(
            [
                resolved,
                "-hide_banner",
                "-f",
                "lavfi",
                "-i",
                "testsrc2=size=640x360:rate=1",
                "-t",
                "1",
                "-c:v",
                "h264_nvenc",
                "-f",
                "null",
                os.devnull,
            ],
            timeout=30,
        )
        practical_ok = practical.returncode == 0
        return {
            "ok": bool(ffmpeg_ok and cuda_ok and "h264_nvenc" in encoders and practical_ok),
            "ffmpeg_path": resolved,
            "ffmpeg_ok": ffmpeg_ok,
            "cuda_ok": cuda_ok,
            "has_h264_nvenc": "h264_nvenc" in encoders,
            "has_hevc_nvenc": "hevc_nvenc" in encoders,
            "has_av1_nvenc": "av1_nvenc" in encoders,
            "practical_ok": practical_ok,
            "message": practical.stderr.strip() if not practical_ok else "NVIDIA NVENC encode test passed.",
        }
    except Exception as exc:
        return {
            "ok": False,
            "ffmpeg_path": "",
            "ffmpeg_ok": False,
            "cuda_ok": False,
            "has_h264_nvenc": False,
            "has_hevc_nvenc": False,
            "has_av1_nvenc": False,
            "practical_ok": False,
            "message": str(exc),
        }


def format_nvidia_check_report(result: dict) -> str:
    def yes(value: bool) -> str:
        return "OK" if value else "FAIL"

    encoders = []
    for key, label in (
        ("has_h264_nvenc", "h264_nvenc"),
        ("has_hevc_nvenc", "hevc_nvenc"),
        ("has_av1_nvenc", "av1_nvenc"),
    ):
        if result.get(key):
            encoders.append(label)
    encoder_text = ", ".join(encoders) if encoders else "none"
    return "\n".join(
        [
            f"FFmpeg: {yes(bool(result.get('ffmpeg_ok', result.get('ok'))))}",
            f"Path: {result.get('ffmpeg_path') or '(not found)'}",
            f"CUDA hwaccel: {yes(bool(result.get('cuda_ok')))}",
            f"NVENC encoders: {encoder_text}",
            f"Practical h264_nvenc encode: {yes(bool(result.get('practical_ok')))}",
            "",
            str(result.get("message", "") or ""),
        ]
    ).strip()


def _run_ffmpeg_stream(command: list[str], duration: float, callback: ProgressCallback | None) -> None:
    process = subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    last_message = ""
    try:
        assert process.stderr is not None
        for raw_line in process.stderr:
            line = raw_line.strip()
            if not line:
                continue
            last_message = line
            current = _progress_from_line(line, duration)
            if callback:
                callback(current, 100, line)
        return_code = process.wait()
        if return_code != 0:
            raise RuntimeError(last_message or f"FFmpeg failed with exit code {return_code}")
        if callback:
            callback(100, 100, "Burn video completed.")
    except Exception:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
        raise


def _progress_from_line(line: str, duration: float) -> int:
    if duration <= 0:
        return 0
    match = re.search(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)", line)
    if not match:
        return 0
    hours = int(match.group(1))
    minutes = int(match.group(2))
    seconds = float(match.group(3))
    current = hours * 3600 + minutes * 60 + seconds
    return max(0, min(99, int(current * 100 / duration)))


def _run_capture(command: list[str], *, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)


def _normalize_hex_color(value: str) -> str:
    text = str(value or "").strip()
    if not text.startswith("#"):
        text = f"#{text}"
    if re.fullmatch(r"#[0-9a-fA-F]{6}", text):
        return text.upper()
    return "#FFFFFF"


def _hex_to_ass_color(value: str, *, alpha: int = 0) -> str:
    text = _normalize_hex_color(value).lstrip("#")
    red = int(text[0:2], 16)
    green = int(text[2:4], 16)
    blue = int(text[4:6], 16)
    safe_alpha = max(0, min(255, int(alpha)))
    return f"&H{safe_alpha:02X}{blue:02X}{green:02X}{red:02X}"


def _opacity_to_ass_alpha(opacity: int) -> int:
    safe_opacity = max(0, min(100, int(opacity)))
    return int(round(255 * (100 - safe_opacity) / 100))


def _escape_filter_path(path: str) -> str:
    value = Path(path).expanduser().resolve().as_posix()
    return value.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def _safe_stem(value: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", str(value)).strip(" ._")
    return cleaned or "vocra"
