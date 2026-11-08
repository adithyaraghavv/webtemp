"""Turn a video into numbered frames for the scroll-scrub hero (needs ffmpeg)."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def extract(video: str, out_dir: str, count: int = 120, width: int = 1280, quality: int = 4) -> dict:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("ffmpeg/ffprobe not found. Install ffmpeg first.")
    if not Path(video).is_file():
        raise FileNotFoundError(video)
    if not 2 <= count <= 300:
        raise ValueError("count must be between 2 and 300")
    p = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                        "default=nw=1:nk=1", video], capture_output=True, text=True, timeout=60)
    try:
        dur = float(p.stdout.strip())
    except ValueError:
        raise RuntimeError(f"could not read video duration: {p.stderr.strip()[:200]}")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.jpg"):
        old.unlink()
    fps = count / dur
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-vf", f"fps={fps:.5f},scale={width}:-2",
                        "-q:v", str(quality), str(out / "%04d.jpg")], capture_output=True, text=True, timeout=900)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {r.stderr.strip()[:300]}")
    files = sorted(out.glob("*.jpg"))
    # keep exactly `count` frames (fps rounding can add one)
    for extra in files[count:]:
        extra.unlink()
    files = files[:count]
    size = sum(f.stat().st_size for f in files)
    return {"frames": len(files), "dir": out_dir, "total_mb": round(size / 1e6, 1), "seconds": round(dur, 1)}
