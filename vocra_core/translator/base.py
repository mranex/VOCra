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
        "default": (
            "Translate like polished subtitle dialogue: natural, clear, easy to read quickly, "
            "and faithful to the scene's intent, tone, and subtext."
        ),
        "subtitle_balanced": (
            "Prioritize natural subtitle dialogue. Keep lines concise, smooth, and emotionally accurate "
            "without sounding too literal or too loose."
        ),
        "comedy_punchy": (
            "Optimize for comedy timing. Preserve punchlines, awkward pauses, irony, wordplay, and banter. "
            "If a joke cannot be translated literally, adapt it into a target-language line that lands the same effect."
        ),
        "faithful_natural": (
            "Stay close to the original meaning, relationships, and tone, but still write like real spoken dialogue "
            "instead of stiff prose."
        ),
        "short_readable": (
            "Keep subtitles short, fast to read, and clean on screen. Remove redundancy when safe, but preserve the key meaning."
        ),
        "dramatic_cinematic": (
            "Preserve dramatic weight, tension, and character voice. Keep lines cinematic, emotionally sharp, and not overly wordy."
        ),
        "honorifics_cultural": (
            "Preserve culturally meaningful honorifics, social hierarchy, and relationship cues when they matter to the scene."
        ),
        "custom": "",
        "formal": "Use formal, polite language.",
        "casual": "Use casual, natural everyday language.",
        "keep_honorifics": "Keep honorifics untranslated.",
        "literal": "Translate meaning accurately and stay close to the wording where possible.",
    }

    def __init__(
        self,
        custom_prompt: str | None = None,
        style: str = "default",
        video_context: str | None = None,
    ) -> None:
        self.custom_prompt = str(custom_prompt or "").strip()
        self.style = str(style or "default").strip() or "default"
        self.video_context = str(video_context or "").strip()

    def set_custom_prompt(self, prompt: str) -> None:
        self.custom_prompt = str(prompt or "").strip()

    def set_video_context(self, context: str) -> None:
        self.video_context = str(context or "").strip()

    def get_lang_name(self, code: str, default: str = "Auto-detect") -> str:
        return self.LANG_NAMES.get(code, default)

    def build_system_prompt(self, *, source_lang: str, target_lang: str) -> str:
        directive = self._resolve_prompt_directive()
        parts = [
            f"You are a professional subtitle translator. Translate from {source_lang} to {target_lang}.",
            "Requirements:",
            "- Preserve meaning, tone, pacing, subtext, and character relationships.",
            "- Write natural spoken dialogue suitable for on-screen subtitles.",
            "- Keep lines concise and readable; avoid bloated or bookish wording.",
            "- Do not add explanations, translator notes, or commentary.",
            "- Keep names, recurring terms, and catchphrases consistent.",
        ]
        if directive:
            heading = "Custom instructions:" if self.style == "custom" else "Style guide:"
            parts.extend([heading, directive])
        if self.video_context:
            parts.extend(["Video context:", self.video_context])
        return "\n".join(parts).strip()

    def _resolve_prompt_directive(self) -> str:
        if self.style == "custom":
            return self.custom_prompt
        return self.STYLE_PRESETS.get(self.style, self.STYLE_PRESETS["default"])
