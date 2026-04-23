from __future__ import annotations

from typing import AsyncIterator, Protocol, runtime_checkable


@runtime_checkable
class Provider(Protocol):
    """Common interface for any LLM backend. All methods accept a BYOK `api_key`
    passed per call — providers must never persist or log it."""

    name: str
    default_model: str
    supports_vision: bool
    supports_native_video: bool

    async def stream_text(
        self,
        *,
        model: str,
        system: str,
        user: str,
        api_key: str,
    ) -> AsyncIterator[str]:
        """Stream plain-text completion chunks."""
        ...

    async def caption_image(
        self,
        *,
        model: str,
        image_bytes: bytes,
        prompt: str,
        api_key: str,
    ) -> str:
        """Single-shot image -> caption. Raises if provider lacks vision."""
        ...


PROVIDERS: dict[str, Provider] = {}


def register(provider: Provider) -> Provider:
    PROVIDERS[provider.name] = provider
    return provider


def get(name: str) -> Provider:
    if name not in PROVIDERS:
        raise ValueError(f"unknown provider: {name!r}. known: {list(PROVIDERS)}")
    return PROVIDERS[name]


def listed() -> list[dict]:
    return [
        {
            "name": p.name,
            "default_model": p.default_model,
            "supports_vision": p.supports_vision,
            "supports_native_video": p.supports_native_video,
        }
        for p in PROVIDERS.values()
    ]
