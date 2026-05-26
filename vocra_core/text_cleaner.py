from __future__ import annotations

import json
import re


PREFIXES = (
    "OCR:",
    "Text:",
    "Recognized text:",
    "Recognized Text:",
    "Output:",
)

META_RESPONSE_PATTERNS = (
    re.compile(r"^the image is too blurry to recognize any text content\.?$", re.IGNORECASE),
    re.compile(r"^the image is too blurry.*recognize.*text.*$", re.IGNORECASE),
    re.compile(r"^unable to recognize any text.*$", re.IGNORECASE),
    re.compile(r"^cannot recognize any text.*$", re.IGNORECASE),
    re.compile(r"^no text can be recognized.*$", re.IGNORECASE),
    re.compile(r"^no readable text.*$", re.IGNORECASE),
    re.compile(r"^text is not legible.*$", re.IGNORECASE),
    re.compile(r"^the text in the image is not clear enough.*$", re.IGNORECASE),
)


def clean_ocr_text(text: str) -> str:
    cleaned = str(text or "").strip()
    if not cleaned:
        return ""

    cleaned = cleaned.replace("\r\n", "\n").replace("\r", "\n").strip()
    cleaned = _strip_code_fences(cleaned)

    parsed = _try_parse_json(cleaned)
    extracted = _extract_text_from_json(parsed)
    if extracted is not None:
        cleaned = extracted

    for prefix in PREFIXES:
        if cleaned.lower().startswith(prefix.lower()):
            cleaned = cleaned[len(prefix) :].lstrip()
            break

    return cleaned.replace("\r\n", "\n").replace("\r", "\n").strip()


def is_meta_ocr_response(text: str) -> bool:
    cleaned = clean_ocr_text(text)
    if not cleaned:
        return False
    normalized = " ".join(cleaned.split())
    return any(pattern.match(normalized) for pattern in META_RESPONSE_PATTERNS)


def sanitize_ocr_text(text: str) -> tuple[str, str]:
    cleaned = clean_ocr_text(text)
    if not cleaned:
        return "", ""
    if is_meta_ocr_response(cleaned):
        return "", "meta_response"
    return cleaned, ""


def _strip_code_fences(text: str) -> str:
    cleaned = str(text or "").strip()
    if cleaned.startswith("```") and cleaned.endswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 2:
            cleaned = "\n".join(lines[1:-1]).strip()
    return cleaned


def _try_parse_json(text: str):
    try:
        return json.loads(text)
    except Exception:
        return None


def _extract_text_from_json(value) -> str | None:
    if isinstance(value, dict):
        for key in ("text", "ocr", "content", "result"):
            text = value.get(key)
            if isinstance(text, str):
                return text
    if isinstance(value, list):
        text_parts = [item for item in value if isinstance(item, str)]
        if text_parts:
            return "\n".join(text_parts)
    return None
