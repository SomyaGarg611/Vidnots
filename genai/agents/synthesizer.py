from __future__ import annotations

from providers import get as get_provider
from state import Frame, GraphState, OCRBlock, TranscriptChunk

from ._util import emit, resilient

SYNTHESIZER_SYSTEM = """\
You are the Synthesizer agent of Vidnots. You receive the transcript,
captioned keyframes, and OCR blocks from a YouTube video, and produce a
complete Markdown notes document that lets the reader skip the video.

Hard rules:
1. Start with: `# Notes: <title>` then a metadata line `**Source:** <url>  •  **Duration:** <m>m  •  **Generated:** <date>`.
2. Follow with a `## TL;DR` (3–5 bullets) and `## Key Takeaways` (5–10 bullets).
3. Then produce chaptered sections. Use YouTube chapters if supplied; otherwise segment by topic change using the transcript + visual flags.
4. Every section header includes its timestamp range: `## 1. <title> (mm:ss – mm:ss)`.
5. Embed frames inline as `![caption @ mm:ss](<url>)` using the frames you are given. Put a frame in every section that has one. Do NOT invent frame URLs — only use URLs from the provided list.
6. Timestamps in prose are markdown links back to the video: `[02:15](<youtube_url>&t=135s)`.
7. Reproduce OCR blocks as fenced code, LaTeX, or markdown lists — do not just describe them.
8. Close with a `## Glossary` of any domain terms introduced.
9. No preamble, no apologies, no meta-commentary — output only the Markdown document.
"""


def _fmt_transcript(chunks: list[TranscriptChunk], limit: int = 400) -> str:
    # naive token budget: keep every chunk but abbreviate if very long
    if not chunks:
        return "(no transcript available — rely on frame captions and OCR)"
    lines = [f"[{c.start:.0f}s] {c.text}" for c in chunks[:limit]]
    if len(chunks) > limit:
        lines.append(f"... ({len(chunks) - limit} more chunks truncated)")
    return "\n".join(lines)


def _fmt_frames(frames: list[Frame]) -> str:
    if not frames:
        return "(no frames extracted)"
    return "\n".join(
        f"- ts={f.ts:.0f}s  url={f.url}  slide={f.is_slide}  caption={f.caption!r}"
        for f in frames
    )


def _fmt_ocr(blocks: list[OCRBlock]) -> str:
    if not blocks:
        return "(no ocr blocks)"
    return "\n\n".join(
        f"[ts={b.ts:.0f}s kind={b.kind} frame={b.frame_url}]\n{b.text}" for b in blocks
    )


def _fmt_chapters(chapters) -> str:
    if not chapters:
        return "(no chapter metadata — segment by topic)"
    return "\n".join(
        f"- {c.start:.0f}s–{c.end:.0f}s: {c.title}" for c in chapters
    )


@resilient("synthesizer", fallback={"notes_markdown": ""})
async def synthesizer_node(state: GraphState) -> dict:
    # LangGraph fan-in guard. The synthesizer has two incoming edges
    # (transcriber and ocr_extractor) that complete in different super-steps,
    # so the node gets invoked twice by default. Skip the first invocation
    # quietly — it happens before OCR has landed — and let the second one
    # (with the full picture) actually run.
    if "transcript_source" not in state or "ocr_blocks" not in state:
        return {}

    await emit(state, "progress", agent="synthesizer", status="start")

    provider = get_provider(state["provider"])

    user_prompt = f"""\
VIDEO URL: {state["url"]}
DURATION: {state.get("duration_s") or 0:.0f} seconds
TRANSCRIPT SOURCE: {state.get("transcript_source", "unknown")}

CHAPTERS:
{_fmt_chapters(state.get("chapters"))}

TRANSCRIPT CHUNKS (timestamps in seconds):
{_fmt_transcript(state.get("transcript") or [])}

KEYFRAMES (use ONLY these URLs when embedding images):
{_fmt_frames(state.get("frames") or [])}

OCR BLOCKS (reproduce these verbatim in the right sections):
{_fmt_ocr(state.get("ocr_blocks") or [])}

Produce the notes document now, following every rule in the system message.
"""

    parts: list[str] = []
    async for chunk in provider.stream_text(
        model=state["model"],
        system=SYNTHESIZER_SYSTEM,
        user=user_prompt,
        api_key=state["api_key"],
    ):
        parts.append(chunk)
        await emit(state, "token", text=chunk)

    await emit(state, "progress", agent="synthesizer", status="done")
    return {"notes_markdown": "".join(parts)}
