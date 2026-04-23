# syntax=docker/dockerfile:1.7

# ─── Stage 1: build the Vite + React frontend ────────────────────────────
FROM node:20-alpine AS web

WORKDIR /w

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./

# Empty API_URL → all calls are same-origin relative (/api/*, /frames/*).
# FastAPI serves both the SPA and those endpoints in production.
ENV VITE_API_URL=""
RUN npm run build

# ─── Stage 2: Python runtime (FastAPI + LangGraph + ffmpeg + yt-dlp) ─────
FROM python:3.11-slim

# ffmpeg + yt-dlp's runtime deps. yt-dlp itself comes in via pip.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY genai/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY genai/ ./
# Drop the built SPA next to main.py; main.py mounts it at /.
COPY --from=web /w/dist ./static

ENV PYTHONUNBUFFERED=1
ENV FRAME_DIR=/app/frames

# HF Spaces expects the app on port 7860 by convention.
EXPOSE 7860

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]
