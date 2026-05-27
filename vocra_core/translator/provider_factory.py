from __future__ import annotations

from vocra_core.app_config import load_global_config
from vocra_core.translator.base import BaseTranslator
from vocra_core.translator.llama_local import LlamaLocalTranslator
from vocra_core.translator.openai_compatible import OpenAICompatibleTranslator


def create_translator(config: dict, *, video_context: str = "") -> BaseTranslator:
    provider = str(config.get("provider", "openai_compatible") or "openai_compatible")
    if provider == "openai_compatible":
        api_key = str(config.get("api_key", "") or "")
        if not api_key:
            api_key = str(load_global_config().get("translator", {}).get("api_key", "") or "")
        return OpenAICompatibleTranslator(
            base_url=str(config.get("base_url", "") or ""),
            api_key=api_key,
            model=str(config.get("model", "") or ""),
            custom_prompt=str(config.get("custom_prompt", "") or ""),
            style=str(config.get("style", "default") or "default"),
            video_context=video_context,
            temperature=float(config.get("temperature", 0.3) or 0.3),
            max_tokens=int(config.get("max_tokens", 4096) or 4096),
            timeout=int(config.get("timeout", 120) or 120),
            json_mode=bool(config.get("json_mode", True)),
            max_retries=int(config.get("max_retries", 2) or 2),
        )
    if provider == "llama_local":
        server_url = str(config.get("server_url", "") or config.get("base_url", "") or "").strip()
        return LlamaLocalTranslator(
            server_url=server_url,
            model=str(config.get("model", "") or ""),
            custom_prompt=str(config.get("custom_prompt", "") or ""),
            style=str(config.get("style", "default") or "default"),
            video_context=video_context,
            temperature=float(config.get("temperature", 0.3) or 0.3),
            max_tokens=int(config.get("max_tokens", 4096) or 4096),
            timeout=int(config.get("timeout", 120) or 120),
            json_mode=bool(config.get("json_mode", True)),
            max_retries=int(config.get("max_retries", 2) or 2),
        )
    raise ValueError(f"Unknown translator provider: {provider}")
