---
title: Vidnots
emoji: 🎬
colorFrom: indigo
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# Vidnots

Paste a YouTube URL → get exhaustive Markdown notes that cover **everything spoken and shown** in the video: narrative prose of the audio, embedded screenshots of the visuals, OCR'd code / slide / equation blocks, timestamped section headers. The goal is that the notes fully replace watching the video.

Bring your own key (Gemini / Claude / OpenAI). Nothing is persisted server-side.

> **About the hosted demo** — the live version at **[huggingface.co/spaces/somya-garg/Vidnots](https://huggingface.co/spaces/somya-garg/Vidnots)** produces **text-only notes**. Embedded screenshots are not available there because YouTube actively blocks video downloads from datacenter IPs — a universal 2026 anti-scraping measure that affects every free cloud host (HF Spaces, Fly.io, Render, etc.), so `yt-dlp` cannot fetch frames from inside the Space container. The notes themselves are still generated end-to-end via the multi-agent pipeline (Transcriber → Visual-Analyst → OCR-Extractor → Synthesizer), they just arrive without embedded images.
>
> **For the full experience** — live frame extraction, embedded screenshots, OCR of slides/code/equations — [run the project locally](#running-locally). `yt-dlp` traffic then originates from your home ISP rather than a blocklisted cloud range and everything works end-to-end. A cookies-based workaround to enable frames on the hosted demo is documented in [DEPLOY.md §7](DEPLOY.md).

## Features

- **Multi-agent LangGraph pipeline** — Transcriber, Visual-Analyst, OCR-Extractor, and a tool-using Synthesizer, with real parallel fan-out so long videos get genuine wall-clock wins.
- **Real-time streaming UI** — Server-Sent Events push agent progress, extracted frames, and notes tokens to the browser as they're produced. No waiting on a big final payload.
- **Live frame feed** — every keyframe the Visual-Analyst extracts appears instantly as a card with caption and timestamp. Click to open a full-screen lightbox (`←` / `→` to navigate, `Esc` to close).
- **Provider abstraction** — Gemini 2.5 Pro/Flash, Claude Opus 4.7 / Sonnet 4.6 / Haiku 4.5, GPT-4o / GPT-4o-mini. Adding a provider is one file in `genai/providers/`.
- **Gemini native-video path** — when Gemini is picked, the pipeline can send the YouTube URL straight to Gemini's video-capable endpoint (windowed via `videoMetadata` offsets for 1h+ content).
- **BYOK** — user-supplied API keys are held in memory for a single job and scrubbed from every log line. Never written to disk, never echoed.
- **Per-IP rate limiting** — `slowapi` guards `POST /api/jobs` against runaway clients.
- **Exports** — download notes as `.md`, print-to-PDF, or copy to clipboard. Last N completed jobs cached in `localStorage` keyed by video URL.

## Architecture

```
┌──────────────┐   URL + model + BYOK key    ┌───────────────────────────────────┐
│  React (Vite)│────────────────────────────▶│  Python / FastAPI                 │
│   frontend   │◀── SSE stream ──────────────│  + LangGraph orchestrator         │
│ (dropdown,   │   (progress / frame /       │  + slowapi per-IP rate limit      │
│  live render,│    token / done)            │                                   │
│  lightbox)   │                             │  ┌─ Transcriber ┐                 │
│              │                             │  │              ├── in parallel ──│
└──────────────┘                             │  └─ Visual-Analyst ─▶ OCR-Extract │
        │                                    │              │             │      │
        │ Vite proxy (dev)                   │              └──────┬──────┘      │
        │ or same origin (prod)              │                     ▼             │
        └──────────────▶ /api/*              │              Synthesizer          │
                       /frames/*             │              (tool-using agent)   │
                       /  (built SPA in      │                     │             │
                          the prod image)    │                     ▼             │
                                             │              Verifier (planned)   │
                                             └──────────────────┬────────────────┘
                                                                ▼
                                                 yt-dlp + ffmpeg + frame store
                                                 (served under /frames/*)
```

Two services, one deploy target:

- **frontend/** — React + Vite + TypeScript. Vite's dev proxy forwards `/api/*` and `/frames/*` to the backend so the browser sees a single origin in dev and prod alike.
- **genai/** — Python 3.11 + FastAPI + **LangGraph**. Serves REST + SSE under `/api/*`, extracted frames under `/frames/*`, and (in the production image) the built React SPA at `/`. Shells out to `yt-dlp` + `ffmpeg`.

There is no Node/Express middle layer. FastAPI handles CORS, SSE (`EventSourceResponse`), static files, log scrubbing, and rate limiting directly — one origin, one data-flow diagram.

## Running locally

Two terminals.

```bash
# terminal 1 — backend
cd genai
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
FRAME_DIR="$PWD/frames" MAX_CONCURRENT_JOBS=2 MAX_FRAMES=48 \
  .venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 --reload

# terminal 2 — frontend
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

Requires **Python 3.11+**, **Node 20+**, and **ffmpeg** (`brew install ffmpeg` on macOS, `apt install ffmpeg` on Debian/Ubuntu).

Or `docker compose up` if you have Docker — brings up both services on a shared network.

## Deploy

The repo root `Dockerfile` builds a single container that:

1. Compiles the Vite SPA in a Node build stage.
2. Installs `ffmpeg` + pip deps in a Python runtime stage.
3. Copies the built SPA into the Python image so FastAPI serves the API and the frontend from one origin.

For **Hugging Face Spaces** (free, always-on, 16 GB / 2 vCPU):

```bash
git init
git add .
git commit -m "initial deploy"
# create a Space at https://huggingface.co/new-space — SDK: Docker
git remote add space https://huggingface.co/spaces/<you>/vidnots
git push space main
```

First build is 5–8 min (ffmpeg + npm ci + pip install); subsequent pushes are fast thanks to Docker layer caching. Your app lives at `https://<you>-vidnots.hf.space`.

## Environment variables

All optional. No secrets ever live in env — every provider key is BYOK per request.

| Var | Default | Purpose |
|---|---|---|
| `MAX_CONCURRENT_JOBS` | `2` | Server-side semaphore capping parallel graph runs. |
| `MAX_FRAMES` | `48` | Upper bound on keyframes extracted per video. |
| `RATE_LIMIT_PER_MIN` | `10` | Per-IP rate limit on `POST /api/jobs`. |
| `FRAME_DIR` | `/app/frames` | Where extracted frames are written and served from. |
| `VITE_API_URL` | *(unset)* | Set only when pointing the frontend at a remote backend — leave unset for same-origin. |

## Known limits

- Gemini's native-YouTube endpoint has a per-video duration ceiling; 1h+ videos use windowed `videoMetadata` offsets.
- Frame extraction is CPU-bound — 5–15 minute videos are the sweet spot on the HF Spaces free tier (2 vCPU).
- Extracted frames accumulate on disk; GC is not yet implemented. `MAX_FRAMES=48` is the current safety valve.
- Transcription falls back to "frames-only" when YouTube captions are missing. A Whisper fallback is planned.

## License

Personal / demo use. Respect YouTube's Terms of Service and the copyright of any video content you process.
