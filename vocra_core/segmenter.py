from __future__ import annotations

import difflib
import json
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Callable

import cv2

from vocra_core.project_manager import load_project, save_progress, update_status
from vocra_core.ssim_filter import _compute_ssim


ProgressCallback = Callable[[int, int | None, str], None]


def build_segments(
    project_dir: str,
    similarity_threshold: float | None = None,
    blank_tolerance: int | None = None,
    ssim_cross_check: bool | None = None,
    ssim_same_threshold: float | None = None,
    ssim_override_threshold: float | None = None,
    use_sharpness_representative: bool | None = None,
    use_text_voting: bool | None = None,
    callback: ProgressCallback | None = None,
) -> int:
    progress = load_project(project_dir)
    project_path = Path(project_dir).expanduser().resolve()
    segments_path = project_path / progress["cache_files"]["segments"]
    ocr_path = project_path / progress["cache_files"]["ocr_origin"]
    cropped_dir = project_path / progress["frame_extract"]["cropped_dir"]
    segmenter_config = progress.get("segmenter", {})
    resolved_similarity_threshold = float(
        similarity_threshold if similarity_threshold is not None else segmenter_config.get("similarity_threshold", 0.5)
    )
    resolved_blank_tolerance = max(
        0,
        int(blank_tolerance if blank_tolerance is not None else segmenter_config.get("blank_tolerance", 1)),
    )
    resolved_ssim_cross_check = bool(
        ssim_cross_check if ssim_cross_check is not None else segmenter_config.get("ssim_cross_check", True)
    )
    resolved_ssim_same_threshold = float(
        ssim_same_threshold
        if ssim_same_threshold is not None
        else segmenter_config.get("ssim_same_threshold", 0.7)
    )
    resolved_ssim_override_threshold = float(
        ssim_override_threshold
        if ssim_override_threshold is not None
        else segmenter_config.get("ssim_override_threshold", 0.9)
    )
    resolved_use_sharpness_representative = bool(
        use_sharpness_representative
        if use_sharpness_representative is not None
        else segmenter_config.get("use_sharpness_representative", True)
    )
    resolved_use_text_voting = bool(
        use_text_voting if use_text_voting is not None else segmenter_config.get("use_text_voting", True)
    )

    previous_payload = None
    if segments_path.exists() and progress["status"].get("segments_done", False):
        with segments_path.open("r", encoding="utf-8") as handle:
            previous_payload = json.load(handle)
        if _segments_cache_matches(
            previous_payload,
            similarity_threshold=resolved_similarity_threshold,
            blank_tolerance=resolved_blank_tolerance,
            ssim_cross_check=resolved_ssim_cross_check,
            ssim_same_threshold=resolved_ssim_same_threshold,
            ssim_override_threshold=resolved_ssim_override_threshold,
            use_sharpness_representative=resolved_use_sharpness_representative,
            use_text_voting=resolved_use_text_voting,
        ):
            segments = previous_payload.get("segments", [])
            if callback:
                callback(len(segments), len(segments), "segments already built")
            return len(segments)

    with ocr_path.open("r", encoding="utf-8") as handle:
        ocr_payload = json.load(handle)

    items = sorted(ocr_payload.get("items", []), key=lambda item: item["image"])
    segments: list[dict] = []
    current_group: list[dict] = []
    pending_blanks: list[dict] = []
    blank_streak = 0
    total = len(items)
    image_cache = _ImageCache(max_items=20)

    for index, item in enumerate(items, start=1):
        text = _normalize_text(item.get("text", ""))
        if not text:
            blank_streak += 1
            pending_blanks.append(item)
            if blank_streak > resolved_blank_tolerance:
                if current_group:
                    segments.append(
                        _build_segment(
                            len(segments) + 1,
                            current_group,
                            cropped_dir=cropped_dir,
                            use_sharpness=resolved_use_sharpness_representative,
                            use_text_voting=resolved_use_text_voting,
                        )
                    )
                    current_group = []
                pending_blanks = []
                blank_streak = 0
            if callback:
                callback(index, total, f"blank {item['image']} ({len(pending_blanks)})")
            continue

        if blank_streak > 0:
            if blank_streak <= resolved_blank_tolerance and current_group:
                current_group.extend(pending_blanks)
            blank_streak = 0
            pending_blanks = []

        if not current_group:
            current_group = [item]
            if callback:
                callback(index, total, f"start {item['image']}")
            continue

        previous_item = _last_non_blank_item(current_group)
        previous_text = _normalize_text(previous_item.get("text", ""))
        similarity = difflib.SequenceMatcher(None, previous_text, text).ratio() if previous_text else 0.0
        image_ssim = None
        if resolved_ssim_cross_check:
            image_ssim = _get_crop_ssim(cropped_dir, previous_item["image"], item["image"], image_cache)
            decision = _decide_grouping(
                text_sim=similarity,
                img_ssim=image_ssim,
                text_threshold=resolved_similarity_threshold,
                ssim_same=resolved_ssim_same_threshold,
                ssim_override=resolved_ssim_override_threshold,
            )
        else:
            decision = "same" if previous_text and similarity >= resolved_similarity_threshold else "different"

        if decision == "same":
            current_group.append(item)
            if callback:
                if image_ssim is None:
                    callback(index, total, f"group {item['image']} ({similarity:.2f})")
                else:
                    callback(index, total, f"group {item['image']} (text={similarity:.2f}, ssim={image_ssim:.2f})")
            continue

        segments.append(
            _build_segment(
                len(segments) + 1,
                current_group,
                cropped_dir=cropped_dir,
                use_sharpness=resolved_use_sharpness_representative,
                use_text_voting=resolved_use_text_voting,
            )
        )
        current_group = [item]
        if callback:
            if image_ssim is None:
                callback(index, total, f"new {item['image']} ({similarity:.2f})")
            else:
                callback(index, total, f"new {item['image']} (text={similarity:.2f}, ssim={image_ssim:.2f})")

    if pending_blanks and current_group and blank_streak <= resolved_blank_tolerance:
        current_group.extend(pending_blanks)

    if current_group:
        segments.append(
            _build_segment(
                len(segments) + 1,
                current_group,
                cropped_dir=cropped_dir,
                use_sharpness=resolved_use_sharpness_representative,
                use_text_voting=resolved_use_text_voting,
            )
        )

    payload = {
        "config": {
            "similarity_threshold": resolved_similarity_threshold,
            "blank_tolerance": resolved_blank_tolerance,
            "ssim_cross_check": resolved_ssim_cross_check,
            "ssim_same_threshold": resolved_ssim_same_threshold,
            "ssim_override_threshold": resolved_ssim_override_threshold,
            "use_sharpness_representative": resolved_use_sharpness_representative,
            "use_text_voting": resolved_use_text_voting,
        },
        "segments": segments,
    }
    with segments_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")

    if previous_payload is not None and _segments_structure_changed(previous_payload, payload):
        _invalidate_downstream_outputs(project_dir, progress, project_path)
    update_status(project_dir, "segments_done", True)
    if callback:
        callback(len(segments), len(segments), "segments built")
    return len(segments)


def _build_segment(
    segment_id: int,
    group_items: list[dict],
    *,
    cropped_dir: Path,
    use_sharpness: bool,
    use_text_voting: bool,
) -> dict:
    represent_image, sharpness_score = _pick_representative(
        group_items,
        cropped_dir=cropped_dir,
        use_sharpness=use_sharpness,
    )
    voted_text, vote_count = _vote_group_text(group_items, enabled=use_text_voting)
    return {
        "id": segment_id,
        "start_image": group_items[0]["image"],
        "end_image": group_items[-1]["image"],
        "represent_image": represent_image,
        "sharpness_selected": represent_image != group_items[0]["image"],
        "sharpness_score": sharpness_score,
        "source": "ocr_og",
        "voted_draft_text": voted_text,
        "vote_count": vote_count,
        "total_frames": len(group_items),
    }


def _pick_representative(
    group_items: list[dict],
    *,
    cropped_dir: Path,
    use_sharpness: bool,
) -> tuple[str, float]:
    if not group_items:
        raise ValueError("group_items cannot be empty")

    if not use_sharpness or len(group_items) <= 1:
        image_name = group_items[0]["image"]
        return image_name, _sharpness_score(cropped_dir / image_name)

    candidates = group_items[:-1] if len(group_items) > 2 else list(group_items)
    non_blank_candidates = [item for item in candidates if _normalize_text(item.get("text", ""))]
    effective_candidates = non_blank_candidates or candidates

    best_item = effective_candidates[0]
    best_score = _sharpness_score(cropped_dir / best_item["image"])
    for item in effective_candidates[1:]:
        score = _sharpness_score(cropped_dir / item["image"])
        if score > best_score:
            best_item = item
            best_score = score
    return best_item["image"], best_score


def _last_non_blank_item(group_items: list[dict]) -> dict:
    for item in reversed(group_items):
        if _normalize_text(item.get("text", "")):
            return item
    return group_items[-1]


def _segments_cache_matches(
    payload: dict,
    *,
    similarity_threshold: float,
    blank_tolerance: int,
    ssim_cross_check: bool,
    ssim_same_threshold: float,
    ssim_override_threshold: float,
    use_sharpness_representative: bool,
    use_text_voting: bool,
) -> bool:
    config = payload.get("config", {})
    if not isinstance(config, dict):
        return False
    cached_similarity = float(config.get("similarity_threshold", -1))
    cached_blank_tolerance = int(config.get("blank_tolerance", -1))
    cached_ssim_cross_check = bool(config.get("ssim_cross_check", False))
    cached_ssim_same_threshold = float(config.get("ssim_same_threshold", -1))
    cached_ssim_override_threshold = float(config.get("ssim_override_threshold", -1))
    cached_use_sharpness_representative = bool(config.get("use_sharpness_representative", False))
    cached_use_text_voting = bool(config.get("use_text_voting", True))
    return (
        abs(cached_similarity - similarity_threshold) <= 1e-9
        and cached_blank_tolerance == blank_tolerance
        and cached_ssim_cross_check == ssim_cross_check
        and abs(cached_ssim_same_threshold - ssim_same_threshold) <= 1e-9
        and abs(cached_ssim_override_threshold - ssim_override_threshold) <= 1e-9
        and cached_use_sharpness_representative == use_sharpness_representative
        and cached_use_text_voting == use_text_voting
    )


def _segments_structure_changed(previous_payload: dict, current_payload: dict) -> bool:
    previous_segments = previous_payload.get("segments", [])
    current_segments = current_payload.get("segments", [])
    previous_structure = [
        (
            int(segment.get("id", 0)),
            str(segment.get("start_image", "")),
            str(segment.get("end_image", "")),
            str(segment.get("represent_image", "")),
        )
        for segment in previous_segments
    ]
    current_structure = [
        (
            int(segment.get("id", 0)),
            str(segment.get("start_image", "")),
            str(segment.get("end_image", "")),
            str(segment.get("represent_image", "")),
        )
        for segment in current_segments
    ]
    return previous_structure != current_structure


def _decide_grouping(
    *,
    text_sim: float,
    img_ssim: float,
    text_threshold: float,
    ssim_same: float,
    ssim_override: float,
) -> str:
    if text_sim >= text_threshold:
        return "same" if img_ssim >= ssim_same else "different"
    return "same" if img_ssim >= ssim_override else "different"


def _get_crop_ssim(cropped_dir: Path, image_a: str, image_b: str, cache: "_ImageCache") -> float:
    img_a = cache.get(cropped_dir / image_a)
    img_b = cache.get(cropped_dir / image_b)
    if img_a is None or img_b is None:
        return 0.0
    return _compute_ssim(img_a, img_b)


def _sharpness_score(image_path: Path) -> float:
    image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        return 0.0
    return float(cv2.Laplacian(image, cv2.CV_64F).var())


def _vote_group_text(group_items: list[dict], *, enabled: bool) -> tuple[str, int]:
    if not enabled:
        return "", 0

    candidates: list[tuple[str, float, int]] = []
    for index, item in enumerate(group_items):
        normalized = _normalize_text(item.get("text", ""))
        if not normalized:
            continue
        candidates.append((normalized, _confidence_value(item.get("confidence", 0.0)), index))

    if not candidates:
        return "", 0

    counter = Counter(text for text, _confidence, _index in candidates)
    max_count = max(counter.values())
    best_text = ""
    best_avg_conf = -1.0
    best_index = len(group_items) + 1

    for text, count in counter.items():
        if count != max_count:
            continue
        matches = [entry for entry in candidates if entry[0] == text]
        avg_conf = sum(entry[1] for entry in matches) / len(matches)
        first_index = min(entry[2] for entry in matches)
        if avg_conf > best_avg_conf or (abs(avg_conf - best_avg_conf) <= 1e-9 and first_index < best_index):
            best_text = text
            best_avg_conf = avg_conf
            best_index = first_index

    return best_text, int(counter.get(best_text, 0))


def _confidence_value(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _invalidate_downstream_outputs(project_dir: str, progress: dict, project_path: Path) -> None:
    for cache_key in ("ocr_final", "translation"):
        relative_path = str(progress.get("cache_files", {}).get(cache_key, "") or "").strip()
        if not relative_path:
            continue
        cache_path = project_path / relative_path
        if cache_path.exists():
            cache_path.unlink()

    updated_progress = load_project(project_dir)
    status = updated_progress.get("status", {})
    status["preprocessed_done"] = False
    status["ocr_final_done"] = False
    status["translation_done"] = False
    status["export_done"] = False
    save_progress(project_dir, updated_progress)


class _ImageCache:
    def __init__(self, max_items: int = 20) -> None:
        self.max_items = max(1, int(max_items))
        self._cache: OrderedDict[str, object] = OrderedDict()

    def get(self, image_path: Path):
        key = str(image_path)
        if key in self._cache:
            value = self._cache.pop(key)
            self._cache[key] = value
            return value

        image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        self._cache[key] = image
        if len(self._cache) > self.max_items:
            self._cache.popitem(last=False)
        return image


def _normalize_text(text: str) -> str:
    return " ".join(str(text).split()).strip()
