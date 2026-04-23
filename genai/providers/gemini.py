from __future__ import annotations

from typing import AsyncIterator

from google import genai
from google.genai import types

from .base import register


class GeminiProvider:
    name = "gemini"
    default_model = "gemini-2.5-flash"
    supports_vision = True
    supports_native_video = True

    async def stream_text(
        self, *, model: str, system: str, user: str, api_key: str
    ) -> AsyncIterator[str]:
        client = genai.Client(api_key=api_key)
        stream = await client.aio.models.generate_content_stream(
            model=model,
            contents=user,
            config=types.GenerateContentConfig(system_instruction=system),
        )
        async for chunk in stream:
            if getattr(chunk, "text", None):
                yield chunk.text

    async def caption_image(
        self, *, model: str, image_bytes: bytes, prompt: str, api_key: str
    ) -> str:
        client = genai.Client(api_key=api_key)
        resp = await client.aio.models.generate_content(
            model=model,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                prompt,
            ],
        )
        return resp.text or ""

    async def process_video_native(
        self,
        *,
        model: str,
        youtube_url: str,
        prompt: str,
        api_key: str,
        start_s: float | None = None,
        end_s: float | None = None,
    ) -> AsyncIterator[str]:
        """Gemini-only: send the YouTube URL directly. Use start/end to window
        past the per-video duration ceiling for 1h+ content."""
        client = genai.Client(api_key=api_key)
        video_meta = None
        if start_s is not None or end_s is not None:
            video_meta = types.VideoMetadata(
                start_offset=f"{int(start_s or 0)}s",
                end_offset=f"{int(end_s)}s" if end_s is not None else None,
            )
        part = types.Part(
            file_data=types.FileData(file_uri=youtube_url, mime_type="video/*"),
            video_metadata=video_meta,
        )
        stream = await client.aio.models.generate_content_stream(
            model=model,
            contents=[part, prompt],
        )
        async for chunk in stream:
            if getattr(chunk, "text", None):
                yield chunk.text


register(GeminiProvider())
