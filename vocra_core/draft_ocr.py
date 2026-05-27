from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable

from vocra_core.draft_ocr_providers import create_draft_provider
from vocra_core.project_manager import load_project, update_status


ProgressCallback = Callable[[int, int | None, str], None]


def run_draft_ocr(project_dir: str, callback: ProgressCallback | None = None) -> int:
    try:
        if callback:
            callback(0, 1, "Draft OCR: starting helper process...")
        return _run_draft_ocr_via_subprocess(project_dir, callback=callback)
    except Exception as exc:
        if callback:
            callback(0, 1, f"Draft OCR helper unavailable, falling back to in-process OCR: {exc}")
        try:
            return _run_draft_ocr_internal(project_dir, callback=callback)
        except Exception as inner_exc:
            if _exception_contains(inner_exc, "No module named 'paddle'") or _exception_contains(exc, "No module named 'paddle'"):
                raise inner_exc
            if callback:
                callback(0, 1, f"Draft OCR in-process path also failed: {inner_exc}")
            raise inner_exc


def _run_draft_ocr_internal(project_dir: str, callback: ProgressCallback | None = None) -> int:
    progress = load_project(project_dir)
    project_path = Path(project_dir).expanduser().resolve()
    cropped_dir = project_path / progress["frame_extract"]["cropped_dir"]
    ocr_path = project_path / progress["cache_files"]["ocr_origin"]
    image_files = sorted(cropped_dir.glob("*.png"))
    total = len(image_files)
    if total == 0:
        raise RuntimeError("No cropped images found for draft OCR")

    payload = _load_ocr_payload(ocr_path)
    items_by_image = {item["image"]: item for item in payload["items"]}
    unique_frames, frame_map = _load_ssim_filter_plan(progress, project_path)
    provider = create_draft_provider(progress["draft_ocr"])

    new_items = 0
    provider.initialize()
    try:
        for index, image_path in enumerate(image_files, start=1):
            image_name = image_path.name
            if image_name in items_by_image:
                if callback:
                    callback(index, total, f"skip {image_name}")
                continue

            if unique_frames is not None and image_name not in unique_frames:
                leader = frame_map.get(image_name, "")
                leader_item = items_by_image.get(leader)
                if leader_item:
                    items_by_image[image_name] = {
                        "image": image_name,
                        "text": leader_item.get("text", ""),
                        "confidence": float(leader_item.get("confidence", 0.0) or 0.0),
                        "inherited_from": leader,
                    }
                    new_items += 1
                    if new_items % 50 == 0:
                        _save_ocr_payload(ocr_path, items_by_image)
                    if callback:
                        callback(index, total, f"inherit {image_name} <= {leader}")
                    continue

            text, confidence = provider.recognize(str(image_path))
            items_by_image[image_name] = {
                "image": image_name,
                "text": text,
                "confidence": confidence,
            }
            new_items += 1

            if new_items % 50 == 0:
                _save_ocr_payload(ocr_path, items_by_image)

            if callback:
                preview = text[:60] if text else "(empty)"
                callback(index, total, preview)
    finally:
        provider.close()

    _save_ocr_payload(ocr_path, items_by_image)
    update_status(project_dir, "ocr_origin_done", True)
    return len(items_by_image)


def _run_draft_ocr_via_subprocess(project_dir: str, callback: ProgressCallback | None = None) -> int:
    interpreter_cmd = _find_python_with_paddle()
    workspace_root = Path(__file__).resolve().parents[1]
    command = [*interpreter_cmd, "-u", "-m", "vocra_core.draft_ocr_cli", str(Path(project_dir).resolve())]
    process = subprocess.Popen(
        command,
        cwd=str(workspace_root),
        env={**os.environ, "PYTHONUTF8": "1"},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    result_count: int | None = None
    assert process.stdout is not None
    for raw_line in process.stdout:
        line = raw_line.rstrip("\r\n")
        if line.startswith("PROGRESS\t"):
            parts = line.split("\t", 3)
            if len(parts) == 4 and callback:
                current = int(parts[1])
                total = int(parts[2])
                callback(current, total, parts[3])
        elif line.startswith("RESULT\t"):
            parts = line.split("\t", 1)
            if len(parts) == 2:
                result_count = int(parts[1])
        elif callback and line.strip():
            callback(0, 1, line)

    return_code = process.wait()
    if return_code != 0:
        raise RuntimeError(f"Draft OCR helper process failed with exit code {return_code}.")
    if result_count is None:
        raise RuntimeError("Draft OCR helper process finished without returning a result count.")
    return result_count


def _load_ocr_payload(ocr_path: Path) -> dict:
    if not ocr_path.exists():
        return {"items": []}

    with ocr_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    items = data.get("items", [])
    if not isinstance(items, list):
        raise ValueError(f"Invalid OCR payload format in {ocr_path}")
    return {"items": items}


def _load_ssim_filter_plan(progress: dict, project_path: Path) -> tuple[set[str] | None, dict[str, str]]:
    if not progress.get("status", {}).get("ssim_filtered", False):
        return None, {}

    current_config = progress.get("ssim_filter", {})
    current_enabled = bool(current_config.get("enabled", True))
    current_threshold = float(current_config.get("threshold", 0.95))
    if not current_enabled:
        return None, {}

    cache_key = progress.get("cache_files", {}).get("ssim_filter", "cache/ssim_filter.json")
    ssim_filter_path = project_path / cache_key
    if not ssim_filter_path.exists():
        return None, {}

    try:
        with ssim_filter_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception:
        return None, {}

    unique_frames = payload.get("unique_frames", [])
    frame_map = payload.get("frame_map", {})
    payload_enabled = bool(payload.get("enabled", True))
    payload_threshold = float(payload.get("threshold", 0.95))
    if not isinstance(unique_frames, list) or not isinstance(frame_map, dict):
        return None, {}
    if not payload_enabled:
        return None, {}
    if abs(payload_threshold - current_threshold) > 1e-9:
        return None, {}

    return set(str(name) for name in unique_frames), {str(key): str(value) for key, value in frame_map.items()}


def _save_ocr_payload(ocr_path: Path, items_by_image: dict[str, dict]) -> None:
    ocr_path.parent.mkdir(parents=True, exist_ok=True)
    items = [items_by_image[name] for name in sorted(items_by_image)]
    payload = {"items": items}
    with ocr_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")


def _find_python_with_paddle() -> list[str]:
    candidates: list[list[str]] = []
    if sys.executable:
        candidates.append([sys.executable])

    python_path = shutil.which("python")
    if python_path:
        candidates.append([python_path])

    py_launcher = shutil.which("py")
    if py_launcher:
        candidates.append([py_launcher, "-3.11"])
        candidates.append([py_launcher, "-3"])

    seen: set[tuple[str, ...]] = set()
    probe_code = "import paddle, paddleocr; print('ok')"
    for candidate in candidates:
        key = tuple(candidate)
        if key in seen:
            continue
        seen.add(key)
        try:
            result = subprocess.run(
                [*candidate, "-c", probe_code],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=30,
            )
        except Exception:
            continue
        if result.returncode == 0 and "ok" in result.stdout:
            return candidate

    raise RuntimeError("Could not find a Python interpreter that can import both paddle and paddleocr.")


def _exception_contains(exc: BaseException, needle: str) -> bool:
    current: BaseException | None = exc
    needle_lower = needle.lower()
    while current is not None:
        if needle_lower in str(current).lower():
            return True
        current = current.__cause__ or current.__context__
    return False
