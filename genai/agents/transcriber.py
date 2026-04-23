from __future__ import annotations

from state import Chapter, GraphState, TranscriptChunk
from tools.youtube import extract_video_id, fetch_captions, fetch_metadata

from ._util import emit, resilient


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
    """Pull YouTube captions + metadata. Whisper fallback deferred to v1.1 —
    when captions are missing we mark the source as 'none' and let the
    Synthesizer lean on visual/OCR signal."""
    url = state["url"]
    video_id = extract_video_id(url)
    await emit(state, "progress", agent="transcriber", status="start")

    meta = await fetch_metadata(url)
    captions = await fetch_captions(video_id)

    if captions:
        transcript = [
            TranscriptChunk(start=c.start, end=c.end, text=c.text) for c in captions
        ]
        source = "captions"
    else:
        transcript = []
        source = "none"

    chapters = None
    if meta.chapters:
        chapters = [
            Chapter(
                start=float(c.get("start_time") or 0),
                end=float(c.get("end_time") or 0),
                title=(c.get("title") or "").strip(),
            )
            for c in meta.chapters
        ]

    await emit(
        state,
        "progress",
        agent="transcriber",
        status="done",
        message=f"{len(transcript)} caption chunks, source={source}, duration={meta.duration_s:.0f}s",
    )

    return {
        "video_id": video_id,
        "transcript": transcript,
        "duration_s": meta.duration_s,
        "chapters": chapters,
        "transcript_source": source,
    }
