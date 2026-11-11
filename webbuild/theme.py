"""Derive a site theme (colour tokens plus a font pairing) from a cafe's own photos. Standard library plus ffmpeg
(already needed for hero frames). Every pair of colours that carries text is nudged until it passes WCAG contrast."""
from __future__ import annotations

import colorsys
import shutil
import subprocess

SIZE = 24


def _lum(c):
    def f(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2])


def contrast(a, b) -> float:
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _hex(c):
    return "#%02x%02x%02x" % tuple(max(0, min(255, round(v))) for v in c)


def _hls(h, l, s):
    r, g, b = colorsys.hls_to_rgb(h, l, s)
    return (r * 255, g * 255, b * 255)


def _fit(color, against, target):
    """Move lightness of color away from `against` until the contrast reaches target."""
    h, l, s = colorsys.rgb_to_hls(*(v / 255 for v in color))
    up = _lum(against) < 0.4
    for _ in range(60):
        c = _hls(h, l, s)
        if contrast(c, against) >= target:
            return c
        l = min(1.0, l + 0.02) if up else max(0.0, l - 0.02)
    return (255, 255, 255) if up else (0, 0, 0)


def read_pixels(path: str) -> list:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required to read photos")
    r = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-frames:v", "1", "-vf", f"scale={SIZE}:{SIZE}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                       capture_output=True, timeout=60)
    if r.returncode or len(r.stdout) < SIZE * SIZE * 3:
        raise ValueError(f"could not read {path}")
    d = r.stdout
    return [(d[i], d[i + 1], d[i + 2]) for i in range(0, SIZE * SIZE * 3, 3)]


def theme_from_pixels(px: list) -> dict:
    n = len(px)
    avg_l = sum(colorsys.rgb_to_hls(*(v / 255 for v in p))[1] for p in px) / n
    dark = avg_l < 0.5
    # accent: the hue bin carrying the most colourful, not-too-dark pixels
    bins = {}
    for p in px:
        h, l, s = colorsys.rgb_to_hls(*(v / 255 for v in p))
        if s < 0.25 or l < 0.18 or l > 0.9:
            continue
        k = int(h * 12) % 12
        w = s * (1 - abs(l - 0.5))
        t = bins.setdefault(k, [0, 0, 0, 0]); t[0] += w; t[1] += p[0] * w; t[2] += p[1] * w; t[3] += p[2] * w
    if bins:
        w = max(bins.values(), key=lambda t: t[0]); base = (w[1] / w[0], w[2] / w[0], w[3] / w[0])
    else:
        base = (176, 66, 38)
    ah, al, as_ = colorsys.rgb_to_hls(*(v / 255 for v in base))
    accent_raw = _hls(ah, min(max(al, 0.4), 0.6), max(as_, 0.55))
    # surfaces tinted with the accent hue, so the page feels like the photos
    if dark:
        bg = _hls(ah, 0.06, 0.28); fg = _hls(ah, 0.93, 0.18); card = _hls(ah, 0.10, 0.28); line = _hls(ah, 0.20, 0.25); scrim = _hls(ah, 0.04, 0.3)
        muted = _fit(_hls(ah, 0.68, 0.12), bg, 4.5)
    else:
        bg = _hls(ah, 0.92, 0.35); fg = _hls(ah, 0.10, 0.25); card = _hls(ah, 0.96, 0.35); line = _hls(ah, 0.76, 0.22); scrim = _hls(ah, 0.08, 0.3)
        muted = _fit(_hls(ah, 0.34, 0.12), bg, 4.5)
    accent = _fit(accent_raw, bg, 4.5)
    on_accent = (255, 255, 255) if contrast((255, 255, 255), accent) >= contrast((0, 0, 0), accent) else (0, 0, 0)
    on_accent = _fit(on_accent, accent, 4.5) if contrast(on_accent, accent) < 4.5 else on_accent
    hero_fg = _hls(ah, 0.95, 0.15)
    warm = ah < 0.17 or ah > 0.92
    if dark:
        fonts = ("Anton", "Barlow", "") if warm else ("Fraunces", "DM Sans", ":opsz,wght@9..144,600;9..144,700")
    else:
        fonts = ("Newsreader", "Work Sans", ":opsz,wght@6..72,500;6..72,700") if warm else ("Cormorant Garamond", "Jost", ":wght@500;700")
    return {"bg": _hex(bg), "fg": _hex(fg), "muted": _hex(muted), "card": _hex(card), "accent": _hex(accent), "on_accent": _hex(on_accent),
            "line": _hex(line), "scrim": _hex(scrim), "hero_fg": _hex(hero_fg),
            "heading_font": fonts[0], "body_font": fonts[1], "heading_axis": fonts[2],
            "radius": "4px" if dark else "2px", "btn_radius": "2px"}


def theme_from_photos(paths: list) -> dict:
    px = []
    for p in paths:
        px += read_pixels(p)
    if not px:
        raise ValueError("give at least one photo")
    t = theme_from_pixels(px)
    t["bw"] = "0px"
    return t
