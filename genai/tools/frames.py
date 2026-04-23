from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class ExtractedFrame:
    ts: float
    path: Path


async def _run(cmd: list[str]) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    return proc.returncode or 0, out.decode(errors="ignore"), err.decode(errors="ignore")


async def detect_scenes(video_path: Path, threshold: float = 0.3) -> list[float]:
    """Return timestamps (seconds) of scene changes via ffmpeg's scene filter."""
    code, _out, err = await _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(video_path),
            "-filter:v",
            f"select='gt(scene,{threshold})',showinfo",
            "-f",
            "null",
            "-",
        ]
    )
    if code != 0:
        return []
    times: list[float] = []
    for m in re.finditer(r"pts_time:([0-9.]+)", err):
        try:
            times.append(float(m.group(1)))
        except ValueError:
            continue
    return sorted(set(round(t, 2) for t in times))


async def even_timestamps(duration_s: float, count: int) -> list[float]:
    if duration_s <= 0 or count <= 0:
        return []
    step = duration_s / (count + 1)
    return [round(step * (i + 1), 2) for i in range(count)]


async def extract_frame(video_path: Path, ts: float, out_path: Path) -> bool:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    code, _out, _err = await _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{ts:.2f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-q:v",
            "3",
            "-y",
            str(out_path),
        ]
    )
    return code == 0 and out_path.exists()


async def extract_many(
    video_path: Path, timestamps: list[float], out_dir: Path
) -> list[ExtractedFrame]:
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[ExtractedFrame] = []
    # serial extraction — ffmpeg is CPU-heavy, parallelism on free tier hurts
    for ts in timestamps:
        safe = f"{int(ts * 1000):08d}.jpg"
        out = out_dir / safe
        if await extract_frame(video_path, ts, out):
            results.append(ExtractedFrame(ts=ts, path=out))
    return results


async def probe_duration(video_path: Path) -> float:
    code, out, _err = await _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(video_path),
        ]
    )
    if code != 0:
        return 0.0
    try:
        return float(json.loads(out)["format"]["duration"])
    except (KeyError, ValueError, json.JSONDecodeError):
        return 0.0
