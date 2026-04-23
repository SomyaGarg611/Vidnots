from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict


@dataclass
class TranscriptChunk:
    start: float
    end: float
    text: str

    def to_dict(self) -> dict[str, Any]:
        return {"start": self.start, "end": self.end, "text": self.text}


@dataclass
class Chapter:
    start: float
    end: float
    title: str


@dataclass
class Frame:
    ts: float
    path: str
    url: str
    caption: str = ""
    is_slide: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ts": self.ts,
            "url": self.url,
            "caption": self.caption,
            "is_slide": self.is_slide,
        }


@dataclass
class OCRBlock:
    ts: float
    frame_url: str
    kind: Literal["code", "slide", "equation", "other"]
    text: str


EventType = Literal["progress", "frame", "token", "error", "done"]


@dataclass
class Event:
    type: EventType
    data: dict[str, Any] = field(default_factory=dict)


class GraphState(TypedDict, total=False):
    # inputs
    url: str
    video_id: str
    provider: str
    model: str
    api_key: str  # SCRUBBED — never log this field
    job_id: str

    # Transcriber outputs
    transcript: list[TranscriptChunk]
    duration_s: float
    chapters: list[Chapter] | None
    transcript_source: Literal["captions", "whisper", "gemini_native", "none"]

    # Visual-Analyst outputs
    frames: list[Frame]

    # OCR-Extractor outputs
    ocr_blocks: list[OCRBlock]

    # Synthesizer output
    notes_markdown: str

    # streaming channel (not serialized)
    events: asyncio.Queue
