from __future__ import annotations

from pathlib import Path

from providers import get as get_provider
from state import Frame, GraphState, OCRBlock

from ._util import emit, resilient

OCR_PROMPT = (
    "You are the OCR-Extractor agent. This frame contains a slide, code, "
    "equation, chart, or diagram. Output ONLY the structured text content, "
    "no prose. Rules:\n"
    "- Code → fenced ```lang code block```\n"
    "- Equations → inline LaTeX wrapped in $$ … $$\n"
    "- Slide bullets → markdown list\n"
    "- Chart/diagram → one sentence describing axes + trend, then any "
    "  visible labels as a list\n"
    "If you cannot read the content, output the single line: (unreadable)."
)


def _classify(caption: str) -> str:
    lower = caption.lower()
    if "```" in caption or "def " in lower or "function" in lower:
        return "code"
    if "$$" in caption or "equation" in lower:
        return "equation"
    if "chart" in lower or "graph" in lower or "axis" in lower:
        return "other"
    return "slide"


@resilient("ocr_extractor", fallback={"ocr_blocks": []})
async def ocr_extractor_node(state: GraphState) -> dict:
    frames: list[Frame] = state.get("frames") or []
    slide_frames = [f for f in frames if f.is_slide]

    await emit(
        state,
        "progress",
        agent="ocr_extractor",
        status="start",
        message=f"{len(slide_frames)} slide-like frames",
    )

    if not slide_frames:
        await emit(state, "progress", agent="ocr_extractor", status="done", message="no slides")
        return {"ocr_blocks": []}

    provider = get_provider(state["provider"])
    if not provider.supports_vision:
        await emit(
            state,
            "progress",
            agent="ocr_extractor",
            status="done",
            message="provider has no vision — skipping",
        )
        return {"ocr_blocks": []}

    blocks: list[OCRBlock] = []
    for f in slide_frames:
        try:
            img = Path(f.path).read_bytes()
            text = await provider.caption_image(
                model=state["model"],
                image_bytes=img,
                prompt=OCR_PROMPT,
                api_key=state["api_key"],
            )
        except Exception as exc:
            text = f"(ocr failed: {exc!s})"

        if text.strip() and text.strip() != "(unreadable)":
            blocks.append(
                OCRBlock(
                    ts=f.ts,
                    frame_url=f.url,
                    kind=_classify(text),  # type: ignore[arg-type]
                    text=text.strip(),
                )
            )

    await emit(
        state,
        "progress",
        agent="ocr_extractor",
        status="done",
        message=f"{len(blocks)} ocr blocks",
    )
    return {"ocr_blocks": blocks}
