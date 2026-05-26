from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
from typing import Callable

from vocra_core.final_ocr.provider_factory import create_final_ocr_provider
from vocra_core.project_manager import load_project, update_status


ProgressCallback = Callable[[int, int | None, str], None]


def run_final_ocr(
    project_dir: str,
    force: bool = False,
    callback: ProgressCallback | None = None,
) -> int:
    progress = load_project(project_dir)
    project_path = Path(project_dir).expanduser().resolve()
    segments_path = project_path / progress["cache_files"]["segments"]
    ocr_final_path = project_path / progress["cache_files"]["ocr_final"]
    preprocessed_dir = project_path / progress["frame_extract"]["preprocessed_dir"]

    with segments_path.open("r", encoding="utf-8") as handle:
        segments_payload = json.load(handle)
    segments = segments_payload.get("segments", [])
    total = len(segments)
    if total == 0:
        raise RuntimeError("No segments found for final OCR")

    payload = _load_items_payload(ocr_final_path)
    items_by_image = {item["image"]: item for item in payload["items"]}
    provider = create_final_ocr_provider(progress["final_ocr"])
    clear_cache_interval = _coerce_clear_cache_interval(progress.get("final_ocr", {}).get("clear_cache_interval", 1))
    parallel_slots = _coerce_parallel_slots(progress.get("final_ocr", {}).get("parallel_slots", 1))
    provider.validate()

    try:
        processed_since_clear = 0
        completed_count = 0
        pending_segments: list[dict] = []

        for segment in segments:
            image_name = segment["represent_image"]
            existing_item = items_by_image.get(image_name)
            if existing_item and existing_item.get("status") == "done" and not force:
                completed_count += 1
                if callback:
                    callback(completed_count, total, f"skip {image_name}")
                continue
            pending_segments.append(segment)

        for wave in _chunked(pending_segments, parallel_slots):
            with ThreadPoolExecutor(max_workers=parallel_slots) as executor:
                future_to_segment = {
                    executor.submit(_recognize_segment, provider, preprocessed_dir, segment): segment
                    for segment in wave
                }
                for future in as_completed(future_to_segment):
                    segment = future_to_segment[future]
                    image_name = segment["represent_image"]
                    try:
                        result = future.result()
                        raw_text = str(result.get("raw_text", "") or "")
                        items_by_image[image_name] = {
                            "image": image_name,
                            "segment_id": int(segment["id"]),
                            "text": str(result.get("text", "") or ""),
                            "confidence": result.get("confidence"),
                            "status": "done",
                            "error": "",
                            "raw_ocr_text": raw_text if raw_text != str(result.get("text", "") or "") else "",
                            "provider": str(result.get("provider", provider.provider_key)),
                            "rejection_reason": str(result.get("rejection_reason", "") or ""),
                            "edited": False,
                        }
                        preview = str(result.get("text", "") or "")[:50] or "(empty)"
                    except Exception as exc:
                        items_by_image[image_name] = {
                            "image": image_name,
                            "segment_id": int(segment["id"]),
                            "text": "",
                            "confidence": None,
                            "status": "error",
                            "error": str(exc),
                            "raw_ocr_text": "",
                            "provider": provider.provider_key,
                            "edited": False,
                        }
                        preview = f"error: {exc}"

                    _save_items_payload(ocr_final_path, items_by_image)
                    completed_count += 1
                    processed_since_clear += 1
                    if callback:
                        callback(completed_count, total, preview)

            if clear_cache_interval > 0 and processed_since_clear >= clear_cache_interval:
                _clear_provider_runtime_cache(provider)
                processed_since_clear = 0

        if processed_since_clear > 0:
            _clear_provider_runtime_cache(provider)
    finally:
        provider.close()

    all_done = all(item.get("status") == "done" for item in items_by_image.values()) and len(items_by_image) >= total
    update_status(project_dir, "ocr_final_done", all_done)
    return len(items_by_image)


def _load_items_payload(payload_path: Path) -> dict:
    if not payload_path.exists():
        return {"items": []}
    with payload_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    items = data.get("items", [])
    if not isinstance(items, list):
        raise ValueError(f"Invalid payload format in {payload_path}")
    return {"items": items}


def _save_items_payload(payload_path: Path, items_by_image: dict[str, dict]) -> None:
    payload_path.parent.mkdir(parents=True, exist_ok=True)
    items = [items_by_image[name] for name in sorted(items_by_image)]
    with payload_path.open("w", encoding="utf-8") as handle:
        json.dump({"items": items}, handle, indent=2)
        handle.write("\n")


def _clear_provider_runtime_cache(provider) -> None:
    clear_runtime_cache = getattr(provider, "clear_runtime_cache", None)
    if not callable(clear_runtime_cache):
        return
    try:
        clear_runtime_cache()
    except Exception:
        return


def _coerce_clear_cache_interval(value) -> int:
    try:
        parsed = int(value)
    except Exception:
        return 1
    return max(0, parsed)


def _coerce_parallel_slots(value) -> int:
    try:
        parsed = int(value)
    except Exception:
        return 1
    return max(1, parsed)


def _chunked(items: list[dict], chunk_size: int) -> list[list[dict]]:
    return [items[index:index + chunk_size] for index in range(0, len(items), chunk_size)]


def _recognize_segment(provider, preprocessed_dir: Path, segment: dict) -> dict:
    image_name = str(segment["represent_image"])
    image_path = preprocessed_dir / image_name
    return provider.recognize_image(str(image_path))
