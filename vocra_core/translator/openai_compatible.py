from __future__ import annotations

import json
from typing import Any

import requests

from vocra_core.translator.base import BaseTranslator


class OpenAICompatibleTranslator(BaseTranslator):
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str = "",
        model: str,
        custom_prompt: str = "",
        style: str = "default",
        temperature: float = 0.3,
        max_tokens: int = 4096,
        timeout: int = 120,
        json_mode: bool = True,
        max_retries: int = 2,
    ) -> None:
        super().__init__(custom_prompt=custom_prompt, style=style)
        self.base_url = str(base_url or "").strip().rstrip("/")
        if not self.base_url:
            raise ValueError("translator.base_url is required.")
        self.model = str(model or "").strip()
        if not self.model:
            raise ValueError("translator.model is required.")
        self.api_key = str(api_key or "").strip()
        self.temperature = float(temperature)
        self.max_tokens = max(1, int(max_tokens or 4096))
        self.timeout = max(1, int(timeout or 120))
        self.json_mode = bool(json_mode)
        self.max_retries = max(0, int(max_retries or 0))
        self.endpoint = self._normalize_endpoint(self.base_url)

    def translate_batch(
        self,
        texts: list[str],
        source: str = "auto",
        target: str = "vi",
    ) -> list[str]:
        if not texts:
            return []

        messages = self._build_messages(texts, source=source, target=target)
        last_error: Exception | None = None
        for _attempt in range(self.max_retries + 1):
            try:
                content = self._post(messages)
                parsed = self._parse_json(content)
                return self._extract_items_result(parsed, texts)
            except Exception as exc:
                last_error = exc

        raise RuntimeError(f"Translator response could not be parsed after retries: {last_error}")

    def _build_messages(self, texts: list[str], *, source: str, target: str) -> list[dict[str, str]]:
        source_name = self.get_lang_name(source, source or "Auto-detect")
        target_name = self.get_lang_name(target, target or "Vietnamese")
        system_prompt = (
            f"You are a subtitle translator. Translate from {source_name} to {target_name}."
            f"{self.build_style_instructions()}"
        ).strip()
        request_payload = {
            "items": [{"index": index, "text": str(text or "")} for index, text in enumerate(texts)]
        }
        user_prompt = "\n\n".join(
            [
                "Return ONLY valid JSON with this exact shape:",
                json.dumps(
                    {"items": [{"index": 0, "translation": "..."}]},
                    ensure_ascii=False,
                    indent=2,
                ),
                "Input JSON:",
                json.dumps(request_payload, ensure_ascii=False, indent=2),
            ]
        )
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def _post(self, messages: list[dict[str, str]]) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if self.json_mode:
            payload["response_format"] = {"type": "json_object"}

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        try:
            response = requests.post(
                self.endpoint,
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.Timeout as exc:
            raise RuntimeError("Translator request timed out.") from exc
        except requests.RequestException as exc:
            raise RuntimeError(f"Translator request failed: {exc}") from exc

        try:
            data = response.json()
        except Exception as exc:
            raise RuntimeError("Translator response is not valid JSON.") from exc

        try:
            content = data["choices"][0]["message"]["content"]
        except Exception as exc:
            raise RuntimeError("Translator response missing message content.") from exc

        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts: list[str] = []
            for part in content:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    parts.append(part["text"])
                elif isinstance(part, str):
                    parts.append(part)
            return "".join(parts).strip()
        return str(content or "").strip()

    def _parse_json(self, text: str):
        cleaned = self._strip_code_fence(text)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            extracted = self._extract_first_json(cleaned)
            return json.loads(extracted)

    def _strip_code_fence(self, text: str) -> str:
        cleaned = str(text or "").strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:].strip()
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:].strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
        return cleaned

    def _extract_first_json(self, text: str) -> str:
        text = str(text or "").strip()
        object_start = text.find("{")
        array_start = text.find("[")
        starts = [index for index in (object_start, array_start) if index != -1]
        if not starts:
            raise ValueError("Translator response did not contain a JSON object or array.")
        start = min(starts)
        end = text.rfind("}" if text[start] == "{" else "]")
        if end == -1 or end <= start:
            raise ValueError("Translator response JSON was incomplete.")
        return text[start : end + 1]

    def _extract_items_result(self, parsed: Any, originals: list[str]) -> list[str]:
        if not isinstance(parsed, dict):
            raise ValueError("Translator response must be a JSON object.")
        items = parsed.get("items")
        if not isinstance(items, list):
            raise ValueError("Translator response is missing an 'items' list.")
        if len(items) != len(originals):
            raise ValueError(f"Translator returned {len(items)} items; expected {len(originals)}.")

        translations: list[str] = []
        for expected_index, item in enumerate(items):
            if not isinstance(item, dict):
                raise ValueError("Translator response items must be objects.")
            if int(item.get("index", -1)) != expected_index:
                raise ValueError(f"Translator item index mismatch at position {expected_index}.")
            translations.append(str(item.get("translation", "") or ""))
        return translations

    def _normalize_endpoint(self, base_url: str) -> str:
        if base_url.endswith("/v1"):
            return f"{base_url}/chat/completions"
        return f"{base_url}/v1/chat/completions"
