from __future__ import annotations

from typing import Dict


class BaseTranslator:
    LANG_NAMES: Dict[str, str] = {
        "auto": "Auto-detect",
        "ja": "Japanese",
        "zh": "Chinese",
        "ko": "Korean",
        "en": "English",
        "vi": "Vietnamese",
        "th": "Thai",
        "id": "Indonesian",
        "fr": "French",
        "de": "German",
        "es": "Spanish",
        "ru": "Russian",
    }

    STYLE_PRESETS: Dict[str, str] = {
        "default": "",
        "formal": "Use formal, polite language.",
        "casual": "Use casual, natural everyday language.",
        "keep_honorifics": "Keep honorifics untranslated.",
        "literal": "Translate meaning accurately.",
    }

    def __init__(self, custom_prompt: str | None = None, style: str = "default") -> None:
        preset_prompt = self.STYLE_PRESETS.get(style, "")
        self.custom_prompt = str(custom_prompt or "").strip() or preset_prompt
        self.style = style

    def set_custom_prompt(self, prompt: str) -> None:
        self.custom_prompt = str(prompt or "").strip()

    def get_lang_name(self, code: str, default: str = "Auto-detect") -> str:
        return self.LANG_NAMES.get(code, default)

    def build_style_instructions(self) -> str:
        if self.custom_prompt:
            return f"\nStyle instructions: {self.custom_prompt}"
        return ""
