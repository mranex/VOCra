"""OpenAI-compatible vision OCR backend for VOCra."""

from __future__ import annotations

import base64
import json
import mimetypes
from collections.abc import Iterable
from pathlib import Path
from typing import Any
from urllib import request

from vocra.core.ocr.backends.base import BackendTestResult
from vocra.core.ocr.models import OcrInput, OcrOutput


class OpenAICompatibleVisionBackend:
    name = "openai-compatible-vision"

    def validate_config(self, config: dict[str, Any]) -> None:
        required_fields = ("endpoint", "model", "prompt_template")
        missing = [field for field in required_fields if not str(config.get(field, "")).strip()]
        if missing:
            missing_text = ", ".join(sorted(missing))
            raise ValueError(f"Missing required OpenAI-compatible config fields: {missing_text}")

    def test_connection(self, config: dict[str, Any]) -> BackendTestResult:
        self.validate_config(config)
        timeout_sec = float(config.get("timeout_sec", 30))
        url = _build_models_url(str(config["endpoint"]))
        headers = _build_headers(config)
        req = request.Request(url, method="GET", headers=headers)
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
        url = _build_chat_completions_url(str(config["endpoint"]))
        headers = _build_headers(config)

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


def _build_headers(config: dict[str, Any]) -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
    }
    api_key = str(config.get("api_key", "")).strip()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _build_models_url(endpoint: str) -> str:
    normalized = endpoint.rstrip("/")
    if normalized.endswith("/models"):
        return normalized
    if normalized.endswith("/v1"):
        return f"{normalized}/models"
    return f"{normalized}/v1/models"


def _build_chat_completions_url(endpoint: str) -> str:
    normalized = endpoint.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    if normalized.endswith("/v1"):
        return f"{normalized}/chat/completions"
    return f"{normalized}/v1/chat/completions"


def _build_request_payload(item: OcrInput, config: dict[str, Any]) -> dict[str, Any]:
    data_url = _build_image_data_url(item.image_path)
    prompt = str(config["prompt_template"])
    return {
        "model": str(config["model"]),
        "temperature": float(config.get("temperature", 0)),
        "max_tokens": int(config.get("max_tokens", 256)),
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": data_url,
                        },
                    },
                ],
            }
        ],
    }


def _build_image_data_url(image_path: Path) -> str:
    mime_type = mimetypes.guess_type(image_path.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _extract_text(raw_response: dict[str, Any]) -> str:
    try:
        content = raw_response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("Response did not contain a valid choices[0].message.content payload.") from exc

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            text = item.get("text")
            if isinstance(text, str):
                parts.append(text.strip())
        return "\n".join(part for part in parts if part).strip()

    raise ValueError("Unsupported message.content format returned by backend.")
