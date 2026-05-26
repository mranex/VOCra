from __future__ import annotations

from typing import Any, Protocol


class FinalOCRProvider(Protocol):
    provider_key: str

    def validate(self) -> None:
        ...

    def recognize_image(self, image_path: str) -> dict[str, Any]:
        ...

    def close(self) -> None:
        ...

    def metadata(self) -> dict[str, Any]:
        ...
