from __future__ import annotations

import base64
import json
import re
from pathlib import Path
from typing import Any, Callable

import requests

from vocra_core.final_ocr.llama_cache import clear_llama_server_slots
from vocra_core.text_cleaner import sanitize_ocr_text


DEFAULT_PROMPT = "OCR:"
DEFAULT_MAX_RETRIES = 3
OCR_REPEAT_MAX_UNIT_CHARS = 12
OCR_REPEAT_MIN_REPETITIONS = 4
OCR_REPEAT_MIN_TOTAL_CHARS = 12
OCR_LIST_MARKER_CHARS = r"\-\*\u2022\u30fb"
OCR_CIRCLED_NUMBER_CHARS = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
LINE_LIST_MARKER_RE = re.compile(
    rf"^\s*(?:(?:\((?:\d{{1,2}})\)|(?:\d{{1,2}}(?:[.):]|\s+)|[{OCR_CIRCLED_NUMBER_CHARS}]))|[{OCR_LIST_MARKER_CHARS}])\s*"
)
INLINE_NUMBERED_MARKER_RE = re.compile(
    rf"(?:(?<=^)|(?<=\s))(?:\((?:\d{{1,2}})\)|(?:\d{{1,2}}[.):]|[{OCR_CIRCLED_NUMBER_CHARS}]))(?=\s*\S)"
)
INLINE_BULLET_MARKER_RE = re.compile(
    rf"(?:(?<=^)|(?<=\s))(?:[{OCR_LIST_MARKER_CHARS}])(?=\s*\S)"
)


class PaddleOCRVLLocalProvider:
    def __init__(self, config: dict):
        self._config = dict(config)
        self.provider_key = "llama_cpp"
        self.provider_name = "PaddleOCR-VL"
        self.server_url = str(config.get("server_url", "") or "").strip().rstrip("/")
        if not self.server_url:
            raise ValueError("final_ocr.server_url is required.")

        self.model = str(config.get("model", "") or "paddleocr-vl").strip() or "paddleocr-vl"
        self.timeout = float(config.get("timeout", 120) or 120)
        self.max_tokens = max(1, int(config.get("max_tokens", 512) or 512))
        self.temperature = 0.0
        self.prompt = str(config.get("prompt", "") or "").strip() or DEFAULT_PROMPT
        self.repeat_penalty = float(config.get("repeat_penalty", 1.2) or 1.2)
        self.repeat_last_n = int(config.get("repeat_last_n", -1))
        self.max_retries = max(1, int(config.get("max_retries", DEFAULT_MAX_RETRIES) or DEFAULT_MAX_RETRIES))

    def validate(self) -> None:
        endpoints = (
            f"{self.server_url}/health",
            f"{self.server_url}/v1/models",
        )
        last_error = "No health endpoint responded."
        for endpoint in endpoints:
            try:
                response = requests.get(endpoint, timeout=min(self.timeout, 10.0))
            except requests.RequestException as exc:
                last_error = str(exc)
                continue
            if 200 <= int(response.status_code) < 400:
                return
            last_error = f"{endpoint} returned HTTP {response.status_code}"

        raise RuntimeError(f"PaddleOCR-VL server validation failed: {last_error}")

    def recognize_image(self, image_path: str) -> dict[str, Any]:
        image_file = Path(image_path).expanduser().resolve()
        if not image_file.exists():
            raise FileNotFoundError(f"Preprocessed image not found: {image_file}")

        image_b64 = base64.b64encode(image_file.read_bytes()).decode("ascii")
        raw_text = self._recognize_with_retries(image_b64)
        cleaned_text, rejection_reason = sanitize_ocr_text(clean_paddleocr_vl_output(raw_text))
        return {
            "text": cleaned_text,
            "confidence": None,
            "provider": self.provider_key,
            "raw": None,
            "raw_text": raw_text,
            "rejection_reason": rejection_reason,
        }

    def clear_runtime_cache(self, logger: Callable[[str], None] | None = None) -> dict[str, Any]:
        return clear_llama_server_slots(
            self.server_url,
            timeout=min(self.timeout, 10.0),
            logger=logger,
            label=self.provider_name,
        )

    def close(self) -> None:
        return None

    def metadata(self) -> dict[str, Any]:
        return {
            "provider": self.provider_key,
            "server_url": self.server_url,
            "model": self.model,
            "prompt": self.prompt,
        }

    def _recognize_with_retries(self, image_b64: str) -> str:
        best_trimmed_candidate = ""
        best_fallback_candidate = ""

        for attempt in range(1, self.max_retries + 1):
            request_max_tokens = self.max_tokens if attempt == 1 else min(self.max_tokens, 128)
            raw_text = self._chat_completion(image_b64, max_tokens=request_max_tokens)
            cleaned = clean_paddleocr_vl_output(raw_text)
            trimmed, had_repeat = trim_repeated_ocr_output(cleaned)
            degenerate = is_degenerate_ocr_output(cleaned)

            if cleaned:
                best_fallback_candidate = _prefer_candidate(best_fallback_candidate, cleaned)
            if had_repeat and trimmed:
                best_trimmed_candidate = _prefer_candidate(best_trimmed_candidate, trimmed)

            if cleaned and not had_repeat and not degenerate:
                return raw_text

        if best_trimmed_candidate:
            return best_trimmed_candidate
        if best_fallback_candidate:
            return best_fallback_candidate
        return ""

    def _chat_completion(self, image_b64: str, *, max_tokens: int | None = None) -> str:
        token_limit = int(max_tokens if max_tokens is not None else self.max_tokens)
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": token_limit,
            "repeat_penalty": self.repeat_penalty,
            "repeat_last_n": self.repeat_last_n,
            "repetition_penalty": self.repeat_penalty,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_b64}"},
                        },
                        {"type": "text", "text": self.prompt},
                    ],
                }
            ],
        }

        try:
            response = requests.post(
                f"{self.server_url}/v1/chat/completions",
                json=payload,
                timeout=self.timeout,
            )
        except requests.Timeout as exc:
            raise RuntimeError(f"PaddleOCR-VL request timed out: {exc}") from exc
        except requests.RequestException as exc:
            raise RuntimeError(
                "PaddleOCR-VL server is not reachable. Start run_server.bat and check health first. "
                f"{exc}"
            ) from exc

        if int(response.status_code) == 404:
            return self._legacy_completion(image_b64, max_tokens=token_limit)
        if int(response.status_code) >= 400:
            raise RuntimeError(
                f"PaddleOCR-VL server returned HTTP {response.status_code}: {response.text[:400]}"
            )

        try:
            response_data = response.json()
        except Exception as exc:
            raise RuntimeError("PaddleOCR-VL server returned invalid JSON.") from exc

        return self._extract_message_text(response_data)

    def _legacy_completion(self, image_b64: str, *, max_tokens: int) -> str:
        payload = {
            "prompt": self.prompt,
            "image_data": image_b64,
            "n_predict": int(max_tokens),
            "temperature": self.temperature,
            "repeat_penalty": self.repeat_penalty,
            "repeat_last_n": self.repeat_last_n,
        }

        try:
            response = requests.post(
                f"{self.server_url}/completion",
                json=payload,
                timeout=self.timeout,
            )
        except requests.Timeout as exc:
            raise RuntimeError(f"PaddleOCR-VL legacy request timed out: {exc}") from exc
        except requests.RequestException as exc:
            raise RuntimeError(f"PaddleOCR-VL legacy request failed: {exc}") from exc

        if int(response.status_code) >= 400:
            raise RuntimeError(
                "PaddleOCR-VL server did not expose a compatible endpoint. "
                f"HTTP {response.status_code}: {response.text[:400]}"
            )

        try:
            response_data = response.json()
        except Exception as exc:
            raise RuntimeError("PaddleOCR-VL legacy endpoint returned invalid JSON.") from exc

        content = response_data.get("content") or response_data.get("text") or ""
        if not isinstance(content, str):
            raise RuntimeError("Invalid legacy PaddleOCR-VL response payload.")
        return content

    def _extract_message_text(self, response_data: dict[str, Any]) -> str:
        try:
            content = response_data["choices"][0]["message"]["content"]
        except Exception as exc:
            raise RuntimeError("PaddleOCR-VL response missing message content.") from exc

        if isinstance(content, str):
            return content
        if isinstance(content, list):
            text_parts: list[str] = []
            for part in content:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    text_parts.append(part["text"])
                elif isinstance(part, str):
                    text_parts.append(part)
            return "\n".join(text_parts).strip()
        return str(content or "").strip()


def clean_paddleocr_vl_output(text: str) -> str:
    cleaned = str(text or "").strip()
    if not cleaned:
        return ""

    if cleaned.startswith("```") and cleaned.endswith("```"):
        lines = cleaned.splitlines()
        if len(lines) >= 2:
            cleaned = "\n".join(lines[1:-1]).strip()

    try:
        parsed = json.loads(cleaned)
    except Exception:
        parsed = None

    if isinstance(parsed, dict):
        for key in ("text", "ocr", "content", "result"):
            value = parsed.get(key)
            if isinstance(value, str):
                cleaned = value.strip()
                break
    elif isinstance(parsed, list):
        text_parts = [value for value in parsed if isinstance(value, str)]
        if text_parts:
            cleaned = "\n".join(text_parts).strip()

    for prefix in ("OCR:", "Text:", "Recognized text:", "Recognized Text:", "Output:"):
        if cleaned.lower().startswith(prefix.lower()):
            cleaned = cleaned[len(prefix) :].strip()
            break

    cleaned = strip_ocr_list_markers(cleaned)
    lines = [line.strip() for line in cleaned.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    lines = [" ".join(line.split()) for line in lines if line.strip()]
    return "\n".join(lines).strip()


def strip_ocr_list_markers(text: str) -> str:
    cleaned = str(text or "").strip()
    if not cleaned:
        return ""

    lines = cleaned.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    non_empty_lines = [line for line in lines if line.strip()]
    marker_count = sum(1 for line in non_empty_lines if LINE_LIST_MARKER_RE.match(line))
    if len(non_empty_lines) >= 2 and marker_count >= 2 and marker_count >= max(2, len(non_empty_lines) - 1):
        stripped_lines = [LINE_LIST_MARKER_RE.sub("", line, count=1).strip() for line in lines]
        return _join_ocr_lines(stripped_lines)

    inline_cleaned = INLINE_NUMBERED_MARKER_RE.sub("", cleaned)
    inline_cleaned = INLINE_BULLET_MARKER_RE.sub("", inline_cleaned)
    if inline_cleaned != cleaned:
        return _join_ocr_lines(inline_cleaned.replace("\r\n", "\n").replace("\r", "\n").split("\n"))
    return cleaned


def _join_ocr_lines(lines: list[str]) -> str:
    joined = " ".join(line.strip() for line in lines if line and line.strip())
    joined = re.sub(r"\s+", " ", joined)
    joined = re.sub(r"\s+([,.;:!?])", r"\1", joined)
    return joined.strip()


def repeated_ocr_suffix_start(text: str) -> int | None:
    cleaned = str(text or "")
    non_space_chars: list[str] = []
    non_space_indices: list[int] = []
    for index, char in enumerate(cleaned):
        if char.isspace():
            continue
        non_space_chars.append(char)
        non_space_indices.append(index)

    condensed = "".join(non_space_chars)
    if len(condensed) < OCR_REPEAT_MIN_TOTAL_CHARS:
        return None

    best_start = None
    max_unit = min(OCR_REPEAT_MAX_UNIT_CHARS, len(condensed) // OCR_REPEAT_MIN_REPETITIONS)
    for unit_length in range(1, max_unit + 1):
        unit = condensed[-unit_length:]
        repetitions = 1
        start_index = len(condensed) - unit_length

        while start_index - unit_length >= 0:
            candidate = condensed[start_index - unit_length:start_index]
            if candidate != unit:
                break
            repetitions += 1
            start_index -= unit_length

        total_chars = repetitions * unit_length
        if repetitions < OCR_REPEAT_MIN_REPETITIONS or total_chars < OCR_REPEAT_MIN_TOTAL_CHARS:
            continue

        original_start = non_space_indices[start_index]
        if best_start is None or original_start < best_start:
            best_start = original_start

    return best_start


def trim_repeated_ocr_output(text: str) -> tuple[str, bool]:
    cleaned = str(text or "").strip()
    if not cleaned:
        return "", False

    repeat_start = repeated_ocr_suffix_start(cleaned)
    if repeat_start is None:
        return cleaned, False

    trimmed = cleaned[:repeat_start].strip()
    return trimmed, True


def is_degenerate_ocr_output(text: str) -> bool:
    cleaned = str(text or "").strip()
    if not cleaned:
        return False

    compact = "".join(char for char in cleaned if not char.isspace())
    if len(compact) < OCR_REPEAT_MIN_TOTAL_CHARS:
        return False

    unique_chars = set(compact)
    if len(unique_chars) <= 2:
        return True

    trimmed, had_repeat = trim_repeated_ocr_output(cleaned)
    if had_repeat and not trimmed:
        return True
    if had_repeat and len(compact) >= 18:
        return True

    diversity = len(unique_chars) / max(1, len(compact))
    return len(compact) >= 24 and diversity < 0.18


def _candidate_score(text: str) -> tuple[int, int]:
    compact = "".join(char for char in str(text or "") if not char.isspace())
    return (len(compact), len(set(compact)))


def _prefer_candidate(current: str, candidate: str) -> str:
    if not candidate:
        return current
    if not current:
        return candidate
    return candidate if _candidate_score(candidate) > _candidate_score(current) else current
