from __future__ import annotations

import asyncio
import inspect
from pathlib import Path
from typing import Any

from vocra_core.text_cleaner import sanitize_ocr_text


class ChromeLensOCRProvider:
    def __init__(self, config: dict):
        self._config = dict(config)
        self.provider_key = "chrome_lens"
        self.language = str(config.get("chrome_lens_language", "auto") or "auto")
        self.headless = bool(config.get("chrome_lens_headless", True))
        self.chrome_path = str(config.get("chrome_path", "") or "").strip()
        self.user_data_dir = str(config.get("user_data_dir", "") or "").strip()
        self.max_retries = int(config.get("chrome_lens_max_retries", 3) or 3)
        self.timeout = float(config.get("timeout", 120) or 120)
        self._module: Any = None

    def validate(self) -> None:
        self._module = self._import_module()

    def recognize_image(self, image_path: str) -> dict[str, Any]:
        image_file = Path(image_path).expanduser().resolve()
        if not image_file.exists():
            raise FileNotFoundError(f"Preprocessed image not found: {image_file}")
        module = self._module or self._import_module()
        raw_result = self._invoke_backend(module, image_file)
        raw_text = self._normalize_result(raw_result)
        cleaned_text, rejection_reason = sanitize_ocr_text(raw_text)
        return {
            "text": cleaned_text,
            "confidence": None,
            "provider": self.provider_key,
            "raw": raw_result,
            "raw_text": raw_text,
            "rejection_reason": rejection_reason,
        }

    def close(self) -> None:
        return None

    def metadata(self) -> dict[str, Any]:
        return {
            "provider": self.provider_key,
            "language": self.language,
            "headless": self.headless,
        }

    def _import_module(self):
        candidates = ("chrome_lens_py", "chrome_lens")
        last_error: Exception | None = None
        for module_name in candidates:
            try:
                return __import__(module_name)
            except Exception as exc:
                last_error = exc
        raise RuntimeError(
            "chrome-lens-py is not installed or could not be imported. "
            "Install it before using the Chrome Lens OCR backend."
        ) from last_error

    def _invoke_backend(self, module: Any, image_file: Path):
        kwargs = {
            "language": self.language,
            "headless": self.headless,
            "chrome_path": self.chrome_path or None,
            "user_data_dir": self.user_data_dir or None,
            "max_retries": self.max_retries,
            "timeout": self.timeout,
        }

        for attr_name in ("recognize_image", "ocr_image"):
            backend = getattr(module, attr_name, None)
            if backend is not None:
                return self._call_backend(backend, str(image_file), kwargs)

        client_class = getattr(module, "ChromeLensClient", None) or getattr(module, "ChromeLens", None)
        if client_class is not None:
            client = client_class(**{k: v for k, v in kwargs.items() if v is not None})
            backend = getattr(client, "recognize_image", None) or getattr(client, "ocr_image", None)
            if backend is None:
                raise RuntimeError("chrome-lens-py client does not expose recognize_image().")
            return self._call_backend(backend, str(image_file), kwargs=None)

        raise RuntimeError(
            "chrome-lens-py was imported, but no compatible recognize_image API was found."
        )

    def _call_backend(self, backend, image_path: str, kwargs: dict | None):
        if kwargs is None:
            kwargs = {}
        result = backend(image_path, **{k: v for k, v in kwargs.items() if v is not None})
        if inspect.isawaitable(result):
            try:
                return asyncio.run(result)
            except RuntimeError:
                loop = asyncio.new_event_loop()
                try:
                    return loop.run_until_complete(result)
                finally:
                    loop.close()
        return result

    def _normalize_result(self, raw_result: Any) -> str:
        if isinstance(raw_result, str):
            return raw_result
        if isinstance(raw_result, dict):
            for key in ("text", "ocr", "content", "result"):
                value = raw_result.get(key)
                if isinstance(value, str):
                    return value
        return str(raw_result or "")
