"""Our own design/quality linter for generated sites. Standard library only.

Grades: FAIL (never ship), WARN (fix or explain). Rules are original; they encode general
web-quality and anti-template principles (WCAG contrast, focus states, motion safety,
token discipline, no invented content, no filler copy)."""
from __future__ import annotations

import colorsys
import re
from dataclasses import dataclass
from pathlib import Path

FILLER = ["elevate your", "seamless", "crafted with passion", "unleash", "game-changer", "game changer",
          "cutting-edge", "cutting edge", "world-class", "revolutioni", "next-level", "next level",
          "in today's fast-paced", "take it to the next", "state-of-the-art", "one-stop", "synergy",
          "unlock the power", "elevated experience", "passion for excellence", "tailored to your needs"]
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿⭐✅❌]")
HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
COLORFN = re.compile(r"\b(?:rgba?|hsla?|oklch|oklab|lab|lch)\([^)]*\)")


@dataclass
class Issue:
    grade: str
    rule: str
    msg: str
    fix: str = ""

    def __str__(self):
        return f"  {self.grade:4} {self.rule:<14} {self.msg}" + (f"\n       fix: {self.fix}" if self.fix else "")


def _lum(hexc: str) -> float:
    h = hexc.lstrip("#")
    if len(h) in (3, 4):
        h = "".join(c * 2 for c in h[:3])
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(a: str, b: str) -> float:
    la, lb = sorted((_lum(a), _lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def _hue(hexc: str) -> float:
    h = hexc.lstrip("#")
    if len(h) in (3, 4):
        h = "".join(c * 2 for c in h[:3])
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return colorsys.rgb_to_hsv(r, g, b)[0] * 360


def _tokens(css: str) -> dict[str, str]:
    m = re.search(r":root\s*\{([^}]*)\}", css)
    return dict(re.findall(r"--([\w-]+)\s*:\s*([^;]+?)\s*(?:;|$)", m.group(1))) if m else {}


def _text_of(htm: str) -> str:
    t = re.sub(r"<(script|style)\b.*?</\1>", " ", htm, flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t)


def lint_html(htm: str) -> list[Issue]:
    out: list[Issue] = []
    css = "\n".join(re.findall(r"<style[^>]*>(.*?)</style>", htm, flags=re.S | re.I))
    css_nc = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    root = re.search(r":root\s*\{[^}]*\}", css_nc)
    outside = css_nc.replace(root.group(0), "") if root else css_nc
    tok = _tokens(css_nc)
    low = htm.lower()

    # document basics
    if not re.search(r"<html[^>]*\blang=", htm, re.I):
        out.append(Issue("FAIL", "html-lang", "no lang on <html>", 'add lang="en"'))
    if not re.search(r"<title>\s*\S", htm, re.I):
        out.append(Issue("FAIL", "title", "missing page title"))
    if 'name="description"' not in low:
        out.append(Issue("WARN", "meta-desc", "no meta description"))
    if "viewport" not in low:
        out.append(Issue("FAIL", "viewport", "no viewport meta tag"))
    for m in re.finditer(r"<img\b[^>]*>", htm, re.I):
        if not re.search(r"\balt=", m.group(0), re.I):
            out.append(Issue("FAIL", "img-alt", f"image without alt: {m.group(0)[:70]}"))
    for m in re.finditer(r"<canvas\b[^>]*>", htm, re.I):
        if not re.search(r"aria-(hidden|label)", m.group(0), re.I):
            out.append(Issue("FAIL", "canvas-a11y", "canvas without aria-hidden or aria-label", 'add aria-hidden="true"'))

    # token discipline
    lits = HEX.findall(outside) + COLORFN.findall(outside)
    if lits:
        out.append(Issue("FAIL", "tokens-color", f"{len(lits)} colour literal(s) outside :root, e.g. {lits[0]}",
                         "declare the colour as a token in :root and use var(--name)"))
    fonts = re.findall(r"font-family\s*:\s*([^;}]+)", outside)
    if [f for f in fonts if "var(" not in f]:
        out.append(Issue("FAIL", "tokens-font", "font-family literal outside :root", "use var(--font-*)"))
    pure = [c for c in HEX.findall(css_nc) if c.lower() in ("#fff", "#ffffff", "#000", "#000000")]
    if pure:
        out.append(Issue("FAIL", "pure-bw", "pure #fff/#000 used", "tint toward the palette's hue"))

    # motion + interaction
    if re.search(r"transition\s*:\s*all\b", css_nc):
        out.append(Issue("FAIL", "transition-all", "transition: all", "list the exact properties"))
    if re.search(r"transition[^;}]*\b(width|height|top|left)\b", css_nc):
        out.append(Issue("FAIL", "layout-anim", "animating width/height/top/left", "animate transform/opacity"))
    if ":focus-visible" not in css_nc:
        out.append(Issue("FAIL", "focus", "no :focus-visible styles", "visible 2px outline, 3:1 contrast"))
    moves = re.search(r"transition|animation|scroll-behavior|<canvas", css_nc + low)
    if moves and "prefers-reduced-motion" not in css_nc:
        out.append(Issue("FAIL", "reduced-motion", "motion without a prefers-reduced-motion fallback"))
    if not re.search(r"overflow-x\s*:\s*clip", css_nc):
        out.append(Issue("FAIL", "overflow-x", "no overflow-x: clip on html/body", "prevents sideways scroll"))
    if re.search(r"height\s*:\s*\d+vh\b", css_nc) or re.search(r"min-height\s*:\s*\d+vh\b", css_nc):
        out.append(Issue("WARN", "vh-units", "vh units jump with phone toolbars", "use svh or dvh"))

    # look
    for g in re.findall(r"linear-gradient\(([^;]*)\)", css_nc):
        hs = [_hue(c) for c in HEX.findall(g)]
        if len(hs) >= 2 and any(250 <= h <= 295 for h in hs) and any(200 <= h <= 260 for h in hs):
            out.append(Issue("FAIL", "purple-blue", "purple-to-blue gradient", "the most common AI tell; pick a palette from the business"))
    for m in re.finditer(r"([^{}]+)\{([^}]*)\}", css_nc):
        body = m.group(2)
        if re.search(r"text-transform\s*:\s*uppercase", body) and re.search(r"letter-spacing\s*:\s*0?\.[1-9]", body):
            out.append(Issue("WARN", "tracked-caps", f"tracked capitals on {m.group(1).strip()[:40]}",
                             "labels in sentence case, untracked"))
    if not re.search(r"text-wrap\s*:\s*balance", css_nc):
        out.append(Issue("WARN", "text-wrap", "no text-wrap: balance on headings"))

    # contrast from tokens
    def pair(fg, bg, need, label):
        if fg in tok and bg in tok and HEX.fullmatch(tok[fg]) and HEX.fullmatch(tok[bg]):
            r = contrast(tok[fg], tok[bg])
            if r < need:
                out.append(Issue("FAIL", "contrast", f"{label}: {r:.1f}:1, needs {need}:1 ({fg} on {bg})"))
    pair("fg", "bg", 4.5, "body text")
    pair("muted", "bg", 4.5, "muted text on page")
    pair("muted", "card", 4.5, "muted text on cards")
    pair("on-accent", "accent", 4.5, "button text")
    pair("accent", "bg", 3.0, "accent on page (links, prices)")
    pair("accent", "card", 3.0, "accent on cards")

    # copy
    text = _text_of(htm)
    tl = text.lower()
    hits = [f for f in FILLER if f in tl]
    if hits:
        out.append(Issue("WARN", "filler-copy", "stock marketing phrases: " + ", ".join(hits[:5]), "say something specific"))
    if EMOJI.search(text):
        out.append(Issue("FAIL", "emoji", "emoji used as icon/text", "use real photos or drawn icons"))
    if re.search(r"\b(\d{2,}[,.]?\d*\+?)\s+(happy|satisfied)\s+(customers|clients)", tl) or "trusted by" in tl:
        out.append(Issue("WARN", "invented-proof", "customer-count / 'trusted by' claim", "only with real, supplied numbers"))
    if re.search(r"lorem ipsum|your text here|placeholder", tl):
        out.append(Issue("FAIL", "placeholder", "placeholder text still on the page"))
    return out


def lint_dir(site_dir: str) -> list[Issue]:
    root = Path(site_dir)
    out: list[Issue] = []
    idx = root / "index.html"
    if not idx.exists():
        return [Issue("FAIL", "no-index", f"{idx} not found")]
    out += lint_html(idx.read_text())
    total = 0
    for f in root.rglob("*"):
        if f.is_file():
            n = f.stat().st_size
            total += n
            if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp") and "frames" not in f.parts and n > 400_000:
                out.append(Issue("WARN", "image-size", f"{f.relative_to(root)} is {n // 1000} KB", "compress to under 400 KB"))
    if total > 12_000_000:
        out.append(Issue("WARN", "page-weight", f"site is {total / 1e6:.1f} MB", "fewer frames or smaller width"))
    return out


def report(issues: list[Issue]) -> str:
    if not issues:
        return "lint: clean"
    n_f = sum(i.grade == "FAIL" for i in issues)
    return "\n".join(str(i) for i in issues) + f"\nlint: {n_f} FAIL, {len(issues) - n_f} WARN"
