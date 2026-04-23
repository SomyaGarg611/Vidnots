from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from pathlib import Path

from youtube_transcript_api import (
    NoTranscriptFound,
    TranscriptsDisabled,
    YouTubeTranscriptApi,
)

_VIDEO_ID_RE = re.compile(r"(?:v=|/shorts/|/embed/|youtu\.be/)([A-Za-z0-9_-]{11})")

# YouTube aggressively blocks the default `web` player_client on datacenter
# IPs (HF Spaces, etc.) — the symptom is [SSL: UNEXPECTED_EOF_WHILE_READING]
# mid-handshake. Safari / iOS / tv_embedded clients are challenged far less.
_YTDLP_EXTRACTOR_ARGS = {
    "youtube": {"player_client": ["web_safari", "ios", "tv_embedded", "web"]},
}


def extract_video_id(url: str) -> str:
    m = _VIDEO_ID_RE.search(url)
    if not m:
        raise ValueError(f"could not extract YouTube video id from: {url!r}")
    return m.group(1)


@dataclass
class CaptionChunk:
    start: float
    end: float
    text: str


async def fetch_captions(video_id: str) -> list[CaptionChunk] | None:
    """Pull YouTube auto/manual captions. Returns None when the video has none
    OR when YouTube refuses (anti-bot / empty XML). Transcription is best-effort;
    a missing transcript is never fatal — the graph falls back to visuals."""

    def _sync() -> list[CaptionChunk] | None:
        try:
            raw = YouTubeTranscriptApi.get_transcript(video_id)
        except Exception:
            # covers NoTranscriptFound, TranscriptsDisabled, VideoUnavailable,
            # xml.etree.ElementTree.ParseError from YouTube returning empty
            # body under anti-bot, connection errors, etc.
            return None
        return [
            CaptionChunk(
                start=float(r["start"]),
                end=float(r["start"]) + float(r.get("duration", 0.0)),
                text=r["text"].replace("\n", " ").strip(),
            )
            for r in raw
            if r.get("text", "").strip()
        ]

    return await asyncio.to_thread(_sync)


@dataclass
class VideoMeta:
    duration_s: float
    title: str
    chapters: list[dict] | None  # [{start_time, end_time, title}]


async def fetch_metadata(url: str) -> VideoMeta:
    """Use yt-dlp in metadata-only mode — does not download the video."""

    def _sync() -> VideoMeta:
        import yt_dlp

        with yt_dlp.YoutubeDL(
            {
                "quiet": True,
                "no_warnings": True,
                "skip_download": True,
                "extractor_args": _YTDLP_EXTRACTOR_ARGS,
            }
        ) as ydl:
            info = ydl.extract_info(url, download=False)
        return VideoMeta(
            duration_s=float(info.get("duration") or 0.0),
            title=info.get("title") or "",
            chapters=info.get("chapters"),
        )

    return await asyncio.to_thread(_sync)


async def download_video(url: str, out_dir: Path) -> Path:
    """Download the video (lowest reasonable quality) for frame extraction.
    Returns the path to the downloaded file."""

    out_dir.mkdir(parents=True, exist_ok=True)

    def _sync() -> Path:
        import yt_dlp

        out_tmpl = str(out_dir / "%(id)s.%(ext)s")
        opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "worst[ext=mp4]/worst",
            "outtmpl": out_tmpl,
            "noplaylist": True,
            "extractor_args": _YTDLP_EXTRACTOR_ARGS,
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            return Path(ydl.prepare_filename(info))

    return await asyncio.to_thread(_sync)
