from __future__ import annotations

import base64
from typing import AsyncIterator

from anthropic import AsyncAnthropic

from .base import register


class AnthropicProvider:
    name = "anthropic"
    default_model = "claude-sonnet-4-6"
    supports_vision = True
    supports_native_video = False

    async def stream_text(
        self, *, model: str, system: str, user: str, api_key: str
    ) -> AsyncIterator[str]:
        client = AsyncAnthropic(api_key=api_key)
        async with client.messages.stream(
            model=model,
            system=system,
            max_tokens=8000,
            messages=[{"role": "user", "content": user}],
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def caption_image(
        self, *, model: str, image_bytes: bytes, prompt: str, api_key: str
    ) -> str:
        client = AsyncAnthropic(api_key=api_key)
        b64 = base64.standard_b64encode(image_bytes).decode("ascii")
        resp = await client.messages.create(
            model=model,
            max_tokens=800,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": b64,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        return "".join(
            block.text for block in resp.content if getattr(block, "type", "") == "text"
        )


register(AnthropicProvider())
