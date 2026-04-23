from __future__ import annotations

from providers import get as get_provider
from state import Chapter, GraphState, TranscriptChunk
from tools.youtube import extract_video_id, fetch_captions, fetch_metadata

from ._util import emit, resilient

_NATIVE_TRANSCRIBE_PROMPT = (
    "Transcribe the full audio of this video from start to finish. "
    "Output plain text only — no commentary, no section headings, no summary. "
    "Every ~30 seconds, prefix the next line with a rough timestamp in the "
    "form [MM:SS]. Preserve speaker disfluencies only when meaningful."
)


@resilient(
    "transcriber",
    fallback={
        "transcript": [],
        "duration_s": 0.0,
        "chapters": None,
        "transcript_source": "none",
    },
)
async def transcriber_node(state: GraphState) -> dict:
    """Pull YouTube captions + metadata. When captions are missing and the
    chosen provider supports native video (Gemini), defer transcription to
    the provider's native YouTube ingestion — works even from datacenter IPs
    where yt-dlp is TLS-blocked."""
    url = state["url"]
    video_id = extract_video_id(url)
    await emit(state, "progress", agent="transcriber", status="start")

    # Metadata is best-effort. yt-dlp is often blocked on datacenter IPs
    # (e.g., HF Spaces) — losing duration/chapters must not abort the node.
    meta = None
    try:
        meta = await fetch_metadata(url)
    except Exception as exc:
        await emit(
            state,
            "progress",
            agent="transcriber",
            status="warn",
            message=f"metadata unavailable ({exc.__class__.__name__}); continuing",
        )

    captions = await fetch_captions(video_id)

    transcript: list[TranscriptChunk] = []
    source = "none"

    if captions:
        transcript = [
            TranscriptChunk(start=c.start, end=c.end, text=c.text) for c in captions
        ]
        source = "captions"
    else:
        # Fallback: ask the provider to ingest the YouTube URL natively.
        # Gemini's backend reaches YouTube directly; our datacenter may not.
        provider = get_provider(state["provider"])
        if provider.supports_native_video:
            try:
                buf: list[str] = []
                async for tok in provider.process_video_native(
                    model=state["model"],
                    youtube_url=url,
                    prompt=_NATIVE_TRANSCRIBE_PROMPT,
                    api_key=state["api_key"],
                ):
                    buf.append(tok)
                text = "".join(buf).strip()
                if text:
                    duration = meta.duration_s if meta else 0.0
                    transcript = [TranscriptChunk(start=0.0, end=duration, text=text)]
                    source = "gemini_native"
            except Exception as exc:
                await emit(
                    state,
                    "progress",
                    agent="transcriber",
                    status="warn",
                    message=f"native transcription failed: {exc!s}",
                )

    chapters = None
    if meta and meta.chapters:
        chapters = [
            Chapter(
                start=float(c.get("start_time") or 0),
                end=float(c.get("end_time") or 0),
                title=(c.get("title") or "").strip(),
            )
            for c in meta.chapters
        ]

    duration_s = meta.duration_s if meta else 0.0

    await emit(
        state,
        "progress",
        agent="transcriber",
        status="done",
        message=f"{len(transcript)} chunks, source={source}, duration={duration_s:.0f}s",
    )

    return {
        "video_id": video_id,
        "transcript": transcript,
        "duration_s": duration_s,
        "chapters": chapters,
        "transcript_source": source,
    }
