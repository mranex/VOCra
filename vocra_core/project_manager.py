from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path


PROGRESS_FILENAME = "progress.json"


def create_project(
    video_path: str,
    project_dir: str,
    subtitle_crop: dict,
    frame_interval: float,
) -> dict:
    project_path = Path(project_dir).expanduser().resolve()
    video_file = Path(video_path).expanduser().resolve()

    project_path.mkdir(parents=True, exist_ok=True)
    for relative_dir in ("cache/frames", "cache/cropped", "cache/preprocessed"):
        (project_path / relative_dir).mkdir(parents=True, exist_ok=True)

    defaults = _load_default_config()
    progress = {
        "project_name": project_path.name,
        "video_path": str(video_file),
        "project_dir": str(project_path),
        "video_context": "",
        "subtitle_crop": _normalize_crop(subtitle_crop),
        "frame_extract": {
            "interval_sec": float(frame_interval),
            "frames_dir": "cache/frames",
            "cropped_dir": "cache/cropped",
            "preprocessed_dir": "cache/preprocessed",
        },
        "cache_files": {
            "timestamp": "cache/timestamp.json",
            "ssim_filter": "cache/ssim_filter.json",
            "ocr_origin": "cache/ocr_og.json",
            "segments": "cache/segments.json",
            "ocr_final": "cache/ocr_fn.json",
            "translation": "cache/translation.json",
        },
        "status": {
            "setup_done": True,
            "frames_extracted": False,
            "cropped_done": False,
            "ssim_filtered": False,
            "ocr_origin_done": False,
            "segments_done": False,
            "preprocessed_done": False,
            "ocr_final_done": False,
            "translation_done": False,
            "export_done": False,
        },
        "draft_ocr": {
            "provider": "paddleocr",
            "language": "auto",
        },
        "ssim_filter": deepcopy(defaults.get("ssim_filter", {"enabled": True, "threshold": 0.95})),
        "segmenter": deepcopy(defaults.get("segmenter", {"similarity_threshold": 0.5, "blank_tolerance": 1})),
        "final_ocr": deepcopy(defaults["final_ocr"]),
        "translator": deepcopy(defaults["translator"]),
    }

    save_progress(str(project_path), progress)
    return load_project(str(project_path))


def load_project(project_dir: str) -> dict:
    progress_path = _progress_path(project_dir)
    if not progress_path.exists():
        raise FileNotFoundError(f"progress.json not found in {progress_path.parent}")

    with progress_path.open("r", encoding="utf-8") as handle:
        progress = json.load(handle)
    return _normalize_progress_schema(progress)


def update_status(project_dir: str, step: str, value: bool) -> None:
    progress = load_project(project_dir)
    status = progress.get("status", {})
    if step not in status:
        raise KeyError(f"Unknown status step: {step}")

    status[step] = bool(value)
    save_progress(project_dir, progress)


def get_cache_path(project_dir: str, cache_key: str) -> str:
    progress = load_project(project_dir)
    cache_files = progress.get("cache_files", {})
    if cache_key not in cache_files:
        raise KeyError(f"Unknown cache key: {cache_key}")

    return str(_project_path(project_dir) / cache_files[cache_key])


def save_progress(project_dir: str, progress: dict) -> None:
    project_path = _project_path(project_dir)
    project_path.mkdir(parents=True, exist_ok=True)

    normalized = _normalize_progress_schema(progress)
    progress_path = project_path / PROGRESS_FILENAME
    with progress_path.open("w", encoding="utf-8") as handle:
        json.dump(normalized, handle, indent=2)
        handle.write("\n")


def _load_default_config() -> dict:
    config_path = Path(__file__).with_name("default_config.json")
    with config_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _normalize_progress_schema(progress: dict) -> dict:
    normalized = deepcopy(progress)
    defaults = _load_default_config()
    normalized.setdefault("video_context", "")

    cache_files = normalized.setdefault("cache_files", {})
    cache_files.setdefault("timestamp", "cache/timestamp.json")
    cache_files.setdefault("ssim_filter", "cache/ssim_filter.json")
    cache_files.setdefault("ocr_origin", "cache/ocr_og.json")
    cache_files.setdefault("segments", "cache/segments.json")
    cache_files.setdefault("ocr_final", "cache/ocr_fn.json")
    cache_files.setdefault("translation", "cache/translation.json")

    status = normalized.setdefault("status", {})
    status.setdefault("setup_done", True)
    status.setdefault("frames_extracted", False)
    status.setdefault("cropped_done", False)
    status.setdefault("ssim_filtered", False)
    status.setdefault("ocr_origin_done", False)
    status.setdefault("segments_done", False)
    status.setdefault("preprocessed_done", False)
    status.setdefault("ocr_final_done", False)
    status.setdefault("translation_done", False)
    status.setdefault("export_done", False)

    draft_ocr = normalized.setdefault("draft_ocr", {})
    draft_ocr.setdefault("provider", "paddleocr")
    draft_ocr.setdefault("language", "auto")

    ssim_filter = normalized.setdefault("ssim_filter", {})
    for key, value in defaults.get("ssim_filter", {}).items():
        ssim_filter.setdefault(key, deepcopy(value))

    segmenter = normalized.setdefault("segmenter", {})
    for key, value in defaults.get("segmenter", {}).items():
        segmenter.setdefault(key, deepcopy(value))

    final_ocr = normalized.setdefault("final_ocr", {})
    for key, value in defaults.get("final_ocr", {}).items():
        final_ocr.setdefault(key, deepcopy(value))

    translator = normalized.setdefault("translator", {})
    for key, value in defaults.get("translator", {}).items():
        translator.setdefault(key, deepcopy(value))

    return normalized


def _normalize_crop(subtitle_crop: dict) -> dict:
    required_keys = ("x", "y", "width", "height")
    missing_keys = [key for key in required_keys if key not in subtitle_crop]
    if missing_keys:
        missing = ", ".join(missing_keys)
        raise KeyError(f"Missing subtitle crop keys: {missing}")

    return {key: int(subtitle_crop[key]) for key in required_keys}


def _project_path(project_dir: str) -> Path:
    return Path(project_dir).expanduser().resolve()


def _progress_path(project_dir: str) -> Path:
    return _project_path(project_dir) / PROGRESS_FILENAME
