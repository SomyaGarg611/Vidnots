from __future__ import annotations

import base64
from typing import AsyncIterator

from openai import AsyncOpenAI

from .base import register


class OpenAIProvider:
    name = "openai"
    default_model = "gpt-4o-mini"
    supports_vision = True
    supports_native_video = False

    async def stream_text(
        self, *, model: str, system: str, user: str, api_key: str
    ) -> AsyncIterator[str]:
        client = AsyncOpenAI(api_key=api_key)
        stream = await client.chat.completions.create(
            model=model,
            stream=True,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta

    async def caption_image(
        self, *, model: str, image_bytes: bytes, prompt: str, api_key: str
    ) -> str:
        client = AsyncOpenAI(api_key=api_key)
        b64 = base64.standard_b64encode(image_bytes).decode("ascii")
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                        },
                    ],
                }
            ],
        )
        return resp.choices[0].message.content or ""


register(OpenAIProvider())
