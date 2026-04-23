FROM python:3.11-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir \
    "fastapi>=0.115" \
    "uvicorn[standard]>=0.32" \
    "sse-starlette>=2.1" \
    "pydantic>=2.9" \
    "httpx>=0.27" \
    "python-dotenv>=1.0" \
    "langgraph>=0.2.50" \
    "langchain-core>=0.3" \
    "youtube-transcript-api>=0.6.2,<1.0" \
    "yt-dlp>=2024.10.7" \
    "anthropic>=0.39" \
    "openai>=1.54" \
    "google-genai>=0.3" \
    "Pillow>=10.4"

COPY . .

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
