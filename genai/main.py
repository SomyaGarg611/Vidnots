from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from pathlib import Path
from typing import AsyncIterator

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sse_starlette.sse import EventSourceResponse

from graph import compiled_graph
from providers import get as get_provider
from providers import listed as list_providers
from state import Event, GraphState

# ─── logging (scrubbed — never log api_key) ──────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("vidnots")


def scrub(payload: dict) -> dict:
    return {k: ("***" if k == "api_key" else v) for k, v in payload.items()}


# ─── app ─────────────────────────────────────────────────────────────────
FRAME_DIR = Path(os.environ.get("FRAME_DIR", "/app/frames"))
FRAME_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Vidnots", version="0.2.0")

# Per-IP rate limiter. Browsers share an origin with the API in both dev
# (via Vite proxy) and prod (single container), so get_remote_address sees
# real client IPs. Applied only to /api/jobs — providers and healthz are
# cheap.
_rate = os.environ.get("RATE_LIMIT_PER_MIN", "10")
limiter = Limiter(key_func=get_remote_address, default_limits=[])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Kept permissive for now — could tighten once we know the production origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/frames", StaticFiles(directory=str(FRAME_DIR)), name="frames")

_job_semaphore = asyncio.Semaphore(int(os.environ.get("MAX_CONCURRENT_JOBS", "2")))


class JobRequest(BaseModel):
    url: str = Field(..., description="YouTube video URL")
    provider: str = Field(..., description="provider name: gemini | anthropic | openai")
    model: str | None = Field(None, description="model id; defaults to provider default")
    api_key: str = Field(..., description="BYOK — held in memory for job duration only")


@app.get("/healthz")
async def healthz() -> dict:
    return {"ok": True}


# Routes the browser calls live under /api/* so frontend and backend share
# a single origin in dev (via Vite proxy) and prod (single container).
api = APIRouter(prefix="/api")


@api.get("/providers")
async def providers() -> list[dict]:
    return list_providers()


def _sse_payload(evt: Event) -> dict:
    return {"event": evt.type, "data": json.dumps(evt.data, default=str)}


async def _run_graph(req: JobRequest, queue: asyncio.Queue) -> None:
    try:
        get_provider(req.provider)
    except ValueError as exc:
        await queue.put(Event(type="error", data={"message": str(exc)}))
        await queue.put(Event(type="done", data={}))
        return

    model = req.model or get_provider(req.provider).default_model
    job_id = uuid.uuid4().hex[:12]
    log.info("job %s start %s", job_id, scrub(req.model_dump()))

    state: GraphState = {
        "url": req.url,
        "provider": req.provider,
        "model": model,
        "api_key": req.api_key,
        "job_id": job_id,
        "events": queue,
    }

    try:
        async with _job_semaphore:
            await compiled_graph.ainvoke(state)
    except Exception as exc:
        log.exception("job %s failed", job_id)
        await queue.put(Event(type="error", data={"message": str(exc)}))
    finally:
        await queue.put(Event(type="done", data={"job_id": job_id}))
        log.info("job %s end", job_id)


async def _stream(req: JobRequest) -> AsyncIterator[dict]:
    queue: asyncio.Queue[Event] = asyncio.Queue()
    task = asyncio.create_task(_run_graph(req, queue))
    try:
        while True:
            evt = await queue.get()
            yield _sse_payload(evt)
            if evt.type == "done":
                break
    finally:
        if not task.done():
            task.cancel()


@api.post("/jobs")
@limiter.limit(f"{_rate}/minute")
async def create_job(request: Request, req: JobRequest):
    if not req.url.startswith(("http://", "https://")):
        raise HTTPException(400, "url must be http(s)")
    if not req.api_key:
        raise HTTPException(400, "api_key is required (BYOK)")
    return EventSourceResponse(_stream(req))


app.include_router(api)


# Serve the built SPA at / when the static dir exists (populated by the
# Dockerfile's frontend build stage). Skipped in local dev so pathing stays
# clean when running uvicorn + vite side-by-side. Mounted LAST so /api/*,
# /healthz, /frames are matched first.
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="spa")
