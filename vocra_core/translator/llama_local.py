from __future__ import annotations

from vocra_core.translator.openai_compatible import OpenAICompatibleTranslator


class LlamaLocalTranslator(OpenAICompatibleTranslator):
    def __init__(self, *, server_url: str, model: str = "", **kwargs) -> None:
        super().__init__(
            base_url=server_url,
            api_key="",
            model=str(model or "").strip() or "local-model",
            **kwargs,
        )
