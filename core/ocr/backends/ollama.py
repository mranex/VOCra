"""Ollama OCR backend for VOCra."""

from __future__ import annotations

import base64
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from urllib import request

from vocra.core.ocr.backends.base import BackendTestResult
from vocra.core.ocr.models import OcrInput, OcrOutput

_DEFAULT_ENDPOINT = "http://127.0.0.1:11434"


class OllamaOcrBackend:
    name = "ollama"

    def validate_config(self, config: dict[str, Any]) -> None:
        required_fields = ("model", "prompt_template")
        missing = [field for field in required_fields if not str(config.get(field, "")).strip()]
        if missing:
            missing_text = ", ".join(sorted(missing))
            raise ValueError(f"Missing required Ollama config fields: {missing_text}")

    def test_connection(self, config: dict[str, Any]) -> BackendTestResult:
        self.validate_config(config)
        timeout_sec = float(config.get("timeout_sec", 30))
        url = _build_tags_url(_get_endpoint(config))
        req = request.Request(url, method="GET")
        try:
            with request.urlopen(req, timeout=timeout_sec) as response:
                if 200 <= response.status < 300:
                    return BackendTestResult(ok=True, message=f"Connected to {url}")
                return BackendTestResult(
                    ok=False,
                    message=f"Unexpected status {response.status} from {url}",
                )
        except Exception as exc:
            return BackendTestResult(ok=False, message=str(exc))

    def run(
        self,
        inputs: Iterable[OcrInput],
        config: dict[str, Any],
    ) -> Iterable[OcrOutput]:
        self.validate_config(config)
        timeout_sec = float(config.get("timeout_sec", 120))
        url = _build_chat_url(_get_endpoint(config))
        headers = {"Content-Type": "application/json"}

        for item in inputs:
            request_payload = _build_request_payload(item, config)
            payload_bytes = json.dumps(request_payload).encode("utf-8")
            req = request.Request(
                url,
                data=payload_bytes,
                headers=headers,
                method="POST",
            )
            try:
                with request.urlopen(req, timeout=timeout_sec) as response:
                    raw_response = json.loads(response.read().decode("utf-8"))
                text = _extract_text(raw_response)
                yield OcrOutput(
                    segment_id=item.segment_id,
                    text=text,
                    confidence=None,
                    raw=raw_response,
                    status="ok",
                )
            except Exception as exc:
                yield OcrOutput(
                    segment_id=item.segment_id,
                    text="",
                    confidence=None,
                    raw={
                        "error": str(exc),
                        "request": request_payload,
                    },
                    status="error",
                    error=str(exc),
                )


def _get_endpoint(config: dict[str, Any]) -> str:
    endpoint = str(config.get("endpoint", _DEFAULT_ENDPOINT)).strip()
    return endpoint or _DEFAULT_ENDPOINT


def _build_tags_url(endpoint: str) -> str:
    return f"{endpoint.rstrip('/')}/api/tags"


def _build_chat_url(endpoint: str) -> str:
    return f"{endpoint.rstrip('/')}/api/chat"


def _build_request_payload(item: OcrInput, config: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": str(config["model"]),
        "stream": False,
        "messages": [
            {
                "role": "user",
                "content": str(config["prompt_template"]),
                "images": [_encode_image_base64(item.image_path)],
            }
        ],
    }
    if config.get("temperature") is not None:
        payload["options"] = {"temperature": float(config["temperature"])}
    return payload


def _encode_image_base64(image_path: Path) -> str:
    return base64.b64encode(image_path.read_bytes()).decode("ascii")


def _extract_text(raw_response: dict[str, Any]) -> str:
    try:
        content = raw_response["message"]["content"]
    except (KeyError, TypeError) as exc:
        raise ValueError("Response did not contain a valid message.content payload.") from exc

    if not isinstance(content, str):
        raise ValueError("Unsupported message.content format returned by backend.")
    return content.strip()
