from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

import requests

from vocra_core.text_cleaner import sanitize_ocr_text


class OpenAICompatibleOCRProvider:
    def __init__(self, config: dict):
        self._config = dict(config)
        self.provider_key = str(config.get("provider", "openai_compatible") or "openai_compatible")
        self.server_url = str(config.get("server_url", "") or "").strip().rstrip("/")
        if not self.server_url:
            raise ValueError("final_ocr.server_url is required.")

        configured_model = str(config.get("model", "") or "").strip()
        if not configured_model and self.provider_key == "openai_compatible":
            raise ValueError("final_ocr.model is required for openai_compatible OCR.")
        self.model = configured_model or "local-model"
        self.timeout = float(config.get("timeout", 120) or 120)
        self.max_tokens = max(1, int(config.get("max_tokens", 512) or 512))
        self.temperature = float(config.get("temperature", 0) or 0)
        self.prompt = (
            str(config.get("prompt", "") or "").strip()
            or "OCR:"
        )

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

        raise RuntimeError(f"Final OCR server validation failed: {last_error}")

    def recognize_image(self, image_path: str) -> dict[str, Any]:
        image_file = Path(image_path).expanduser().resolve()
        if not image_file.exists():
            raise FileNotFoundError(f"Preprocessed image not found: {image_file}")

        image_b64 = base64.b64encode(image_file.read_bytes()).decode("ascii")
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
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
            raise RuntimeError(f"Final OCR request timed out: {exc}") from exc
        except requests.RequestException as exc:
            raise RuntimeError(f"Final OCR request failed: {exc}") from exc

        if int(response.status_code) >= 400:
            raise RuntimeError(
                f"Final OCR server returned HTTP {response.status_code}: {response.text[:400]}"
            )

        try:
            response_data = response.json()
        except Exception as exc:
            raise RuntimeError("Final OCR server returned invalid JSON.") from exc

        raw_text = self._extract_message_text(response_data)
        cleaned_text, rejection_reason = sanitize_ocr_text(raw_text)
        return {
            "text": cleaned_text,
            "confidence": None,
            "provider": self.provider_key,
            "raw": response_data,
            "raw_text": raw_text,
            "rejection_reason": rejection_reason,
        }

    def close(self) -> None:
        return None

    def metadata(self) -> dict[str, Any]:
        return {
            "provider": self.provider_key,
            "server_url": self.server_url,
            "model": self.model,
        }

    def _extract_message_text(self, response_data: dict[str, Any]) -> str:
        try:
            content = response_data["choices"][0]["message"]["content"]
        except Exception as exc:
            raise RuntimeError("Final OCR response missing message content.") from exc

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
