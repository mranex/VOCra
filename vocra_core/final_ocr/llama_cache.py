from __future__ import annotations

from typing import Any, Callable
from urllib.parse import urlparse

import requests


def clear_llama_server_slots(
    server_url: str,
    *,
    timeout: float = 10.0,
    logger: Callable[[str], None] | None = None,
    label: str = "Local OCR",
) -> dict[str, Any]:
    normalized_url = _normalize_server_url(server_url)
    result: dict[str, Any] = {
        "supported": False,
        "cleared": 0,
        "skipped_processing": 0,
        "errors": [],
        "reason": "",
    }

    try:
        response = requests.get(f"{normalized_url}/slots", timeout=float(timeout))
    except requests.RequestException as exc:
        result["reason"] = "request_failed"
        result["errors"].append(f"Unable to query llama.cpp slots: {exc}")
        _log(logger, f"{label} slot cache clear skipped because /slots could not be queried.")
        return result

    status_code = int(response.status_code)
    if status_code in {404, 405}:
        result["reason"] = "unsupported"
        return result
    if status_code >= 400:
        result["reason"] = "http_error"
        result["errors"].append(f"GET /slots returned HTTP {status_code}.")
        _log(logger, f"{label} slot cache clear skipped because /slots returned HTTP {status_code}.")
        return result

    try:
        slots_payload = response.json()
    except Exception:
        result["reason"] = "invalid_response"
        result["errors"].append("GET /slots returned invalid JSON.")
        _log(logger, f"{label} slot cache clear skipped because /slots returned invalid JSON.")
        return result

    if not isinstance(slots_payload, list):
        result["reason"] = "invalid_response"
        result["errors"].append("GET /slots did not return a slot list.")
        _log(logger, f"{label} slot cache clear skipped because /slots returned an invalid payload.")
        return result

    result["supported"] = True

    for slot in slots_payload:
        if not isinstance(slot, dict):
            result["errors"].append("Skipped malformed slot payload.")
            continue

        raw_slot_id = slot.get("id", slot.get("id_slot"))
        try:
            slot_id = int(raw_slot_id)
        except Exception:
            continue

        if bool(slot.get("is_processing")):
            result["skipped_processing"] += 1
            continue

        try:
            erase_response = requests.post(
                f"{normalized_url}/slots/{slot_id}?action=erase",
                timeout=float(timeout),
            )
        except requests.RequestException as exc:
            result["errors"].append(f"Slot {slot_id} erase failed: {exc}")
            continue

        erase_status = int(erase_response.status_code)
        if erase_status in {404, 405}:
            result["supported"] = False
            result["reason"] = "unsupported"
            result["errors"].append(f"Slot {slot_id} erase returned HTTP {erase_status}.")
            break
        if erase_status >= 400:
            result["errors"].append(f"Slot {slot_id} erase returned HTTP {erase_status}.")
            continue

        result["cleared"] += 1

    return result


def _normalize_server_url(raw_url: str) -> str:
    normalized_input = str(raw_url or "").strip()
    if not normalized_input:
        raise ValueError("A valid llama.cpp server URL is required.")
    if "://" not in normalized_input:
        normalized_input = f"http://{normalized_input}"
    parsed = urlparse(normalized_input)
    host = parsed.hostname or "127.0.0.1"
    port = int(parsed.port or 8080)
    scheme = parsed.scheme or "http"
    return f"{scheme}://{host}:{port}".rstrip("/")


def _log(logger: Callable[[str], None] | None, message: str) -> None:
    if logger is not None:
        logger(message)
