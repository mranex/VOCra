"""Review quality flags and filtering helpers for VOCra."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import replace

from vocra.core.review.models import ReviewItem

_SUSPICIOUS_FLAGS = {
    "mostly_punctuation",
    "repeated_text",
    "replacement_character",
    "too_long",
    "too_short",
}


def apply_quality_flags(items: Iterable[ReviewItem]) -> list[ReviewItem]:
    materialized = list(items)
    repeated_counts = Counter(
        item.original_text.strip()
        for item in materialized
        if item.original_text.strip()
    )
    enriched: list[ReviewItem] = []
    for item in materialized:
        flags = list(item.quality_flags)
        text = item.original_text.strip()
        if item.ocr_status == "error":
            flags.append("ocr_error")
        if not text:
            flags.append("empty_ocr_text")
        if item.review_status == "pending":
            flags.append("unreviewed")
        if text and len(text) <= 1:
            flags.append("too_short")
        if len(text) >= 120:
            flags.append("too_long")
        if "\ufffd" in text:
            flags.append("replacement_character")
        if text and _is_mostly_punctuation(text):
            flags.append("mostly_punctuation")
        if text and repeated_counts[text] > 1:
            flags.append("repeated_text")
        enriched.append(replace(item, quality_flags=tuple(dict.fromkeys(flags))))
    return enriched


def filter_review_items(
    items: Iterable[ReviewItem],
    filter_name: str,
) -> list[ReviewItem]:
    materialized = list(items)
    if filter_name == "all":
        return materialized
    if filter_name in {"pending", "accepted", "edited", "rejected"}:
        return [item for item in materialized if item.review_status == filter_name]
    if filter_name == "unreviewed":
        return [item for item in materialized if "unreviewed" in item.quality_flags]
    if filter_name == "errors":
        return [item for item in materialized if "ocr_error" in item.quality_flags]
    if filter_name == "empty":
        return [item for item in materialized if "empty_ocr_text" in item.quality_flags]
    if filter_name == "suspicious":
        return [
            item
            for item in materialized
            if any(flag in _SUSPICIOUS_FLAGS for flag in item.quality_flags)
        ]
    raise ValueError(f"Unsupported review filter: {filter_name}")


def _is_mostly_punctuation(text: str) -> bool:
    non_space = [char for char in text if not char.isspace()]
    if not non_space:
        return False
    punctuation_count = sum(
        1 for char in non_space if not char.isalnum() and char != "_"
    )
    return punctuation_count / len(non_space) >= 0.7
