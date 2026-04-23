from __future__ import annotations

import os
from pathlib import Path

from providers import get as get_provider
from state import Frame, GraphState
from tools.frames import detect_scenes, even_timestamps, extract_many, probe_duration
from tools.youtube import download_video

from ._util import emit, resilient

FRAME_CAPTION_PROMPT = (
    "You are the Visual-Analyst agent for a video-notes pipeline. Describe "
    "what is on screen in one or two sentences. If the frame shows a slide, "
    "code, an equation, a chart, or a diagram, start your answer with the "
    "word SLIDE: and then transcribe the visible content as faithfully as "
    "possible (code in a fenced block, equations as LaTeX, bullets as a "
    "list). Otherwise describe the scene factually — no speculation."
)


def _frame_dir(job_id: str) -> Path:
    return Path(os.environ.get("FRAME_DIR", "/app/frames")) / job_id


def _download_dir() -> Path:
    return Path(os.environ.get("FRAME_DIR", "/app/frames")) / "_downloads"


@resilient("visual_analyst", fallback={"frames": []})
async def visual_analyst_node(state: GraphState) -> dict:
    await emit(state, "progress", agent="visual_analyst", status="start")

    max_frames = int(os.environ.get("MAX_FRAMES", "48"))
    job_id = state["job_id"]
    out_dir = _frame_dir(job_id)

    # 1. download a low-quality copy for frame extraction
    try:
        video_path = await download_video(state["url"], _download_dir())
    except Exception as exc:
        await emit(
            state,
            "progress",
            agent="visual_analyst",
            status="error",
            message=f"download failed: {exc!s}",
        )
        return {"frames": []}

    await emit(state, "progress", agent="visual_analyst", status="downloaded")

    # 2. pick timestamps — scene detection preferred, even sampling as fallback.
    # Probe duration from the file (state["duration_s"] is set by Transcriber
    # in a parallel branch and isn't reliably visible here).
    duration = state.get("duration_s") or 0.0
    if duration <= 0:
        duration = await probe_duration(video_path)

    scene_times = await detect_scenes(video_path, threshold=0.25)
    if len(scene_times) < 8:
        scene_times = await even_timestamps(duration, max_frames)

    # cap to MAX_FRAMES, preserving spread
    if len(scene_times) > max_frames:
        stride = len(scene_times) / max_frames
        scene_times = [scene_times[int(i * stride)] for i in range(max_frames)]

    # 3. extract jpegs
    extracted = await extract_many(video_path, scene_times, out_dir)

    await emit(
        state,
        "progress",
        agent="visual_analyst",
        status="extracted",
        message=f"{len(extracted)} frames",
    )

    # 4. caption each via the chosen provider (if it supports vision)
    provider = get_provider(state["provider"])
    frames: list[Frame] = []
    for f in extracted:
        rel_url = f"/frames/{job_id}/{f.path.name}"
        caption = ""
        is_slide = False
        if provider.supports_vision:
            try:
                img = f.path.read_bytes()
                caption = await provider.caption_image(
                    model=state["model"],
                    image_bytes=img,
                    prompt=FRAME_CAPTION_PROMPT,
                    api_key=state["api_key"],
                )
                is_slide = caption.strip().upper().startswith("SLIDE:")
            except Exception as exc:
                caption = f"(caption failed: {exc!s})"
        frame = Frame(
            ts=f.ts, path=str(f.path), url=rel_url, caption=caption, is_slide=is_slide
        )
        frames.append(frame)
        await emit(
            state,
            "frame",
            ts=f.ts,
            url=rel_url,
            caption=caption,
            is_slide=is_slide,
        )

    await emit(
        state,
        "progress",
        agent="visual_analyst",
        status="done",
        message=f"{len(frames)} captioned",
    )
    return {"frames": frames}
