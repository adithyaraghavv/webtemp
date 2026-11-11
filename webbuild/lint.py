"""Our own design/quality linter for generated sites. Standard library only.

Grades: FAIL (never ship), WARN (fix or explain). Rules are original; they encode general
web-quality and anti-template principles (WCAG contrast, focus states, motion safety,
token discipline, no invented content, no filler copy)."""
from __future__ import annotations

import colorsys
import re
from html.parser import HTMLParser
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


OVERUSED_FONTS = {"inter", "roboto", "open sans", "arial", "helvetica", "helvetica neue", "lato", "montserrat",
                  "poppins", "system-ui", "sans-serif", "segoe ui"}


def _first_family(v: str) -> str:
    return v.split(",")[0].strip().strip("'\"").lower()


def _sat(hexc: str) -> float:
    h = hexc.lstrip("#")
    if len(h) in (3, 4):
        h = "".join(c * 2 for c in h[:3])
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return colorsys.rgb_to_hsv(r, g, b)[1]


class _Cards(HTMLParser):
    """Finds nested cards and runs of identical cards that are not priced menu items."""

    def __init__(self):
        super().__init__()
        self.stack = []      # (tag, is_card)
        self.nested = 0
        self.plain_cards = 0
        self._card_open = []  # per open card: has price

    def handle_starttag(self, tag, attrs):
        if tag in ("br", "img", "input", "meta", "link", "hr"):
            return
        cls = (dict(attrs).get("class") or "").split()
        is_card = any(c == "card" or c.endswith("-card") or c.startswith("card-") for c in cls)
        if is_card and any(c for _, c in self.stack):
            self.nested += 1
        if self._card_open and "price" in cls:
            self._card_open[-1] = True
        if is_card:
            self._card_open.append(False)
        self.stack.append((tag, is_card))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                is_card = self.stack[i][1]
                del self.stack[i:]
                if is_card and self._card_open and not self._card_open.pop():
                    self.plain_cards += 1
                break


def _ai_tells(css_nc: str, htm: str, tok: dict) -> list[Issue]:
    """Original checks for the look that makes a page read as machine-made."""
    out: list[Issue] = []
    # type: overused families, or no pairing at all
    fams = {k: _first_family(v) for k, v in tok.items() if k.startswith("font-")}
    for k, f in fams.items():
        if f in OVERUSED_FONTS:
            out.append(Issue("WARN", "overused-font", f"--{k} is {f!r}, the default of most generated sites",
                             "pick a distinctive family that suits the business (see `webbuild presets`)"))
    heads = fams.get("font-head")
    if heads and heads == fams.get("font-body"):
        out.append(Issue("WARN", "no-pairing", "heading and body use the same family", "pair a display face with a quiet text face"))
    # neutrals: untinted greys read as unfinished
    for k in ("bg", "card", "fg", "muted"):
        v = tok.get(k, "")
        if HEX.fullmatch(v) and _sat(v) < 0.01 and v.lower() not in ("#fff", "#ffffff", "#000", "#000000"):
            out.append(Issue("WARN", "untinted-neutral", f"--{k} {v} is a pure grey", "tint toward the palette's hue"))
    # grey text sitting on a coloured surface
    for t, surf in (("muted", "bg"), ("muted", "card")):
        a, b = tok.get(t, ""), tok.get(surf, "")
        if HEX.fullmatch(a) and HEX.fullmatch(b) and _sat(a) < 0.06 and _sat(b) > 0.35:
            out.append(Issue("WARN", "grey-on-colour", f"grey --{t} on the coloured --{surf}", "use a tint of the background hue"))
    # motion that feels bouncy or springy
    for m in re.finditer(r"cubic-bezier\(\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\)", css_nc):
        y1, y2 = float(m.group(2)), float(m.group(4))
        if y1 < 0 or y1 > 1 or y2 < 0 or y2 > 1:
            out.append(Issue("WARN", "bounce-easing", f"overshooting easing {m.group(0)}", "use an ease-out curve that settles"))
    if re.search(r"\b(bounce|elastic|spring)\b", css_nc, re.I):
        out.append(Issue("WARN", "bounce-easing", "bounce/elastic/spring motion", "use a short ease-out"))
    # glass everywhere
    if len(re.findall(r"backdrop-filter\s*:", css_nc)) > 1:
        out.append(Issue("WARN", "glass", "backdrop-filter on several elements", "one blurred bar at most; elsewhere use solid surfaces"))
    # layout monotony
    cp = _Cards()
    try:
        cp.feed(htm)
    except Exception:
        pass
    if cp.nested:
        out.append(Issue("WARN", "nested-cards", f"{cp.nested} card(s) inside another card", "flatten: one surface per idea"))
    if cp.plain_cards >= 3:
        out.append(Issue("WARN", "card-grid", f"{cp.plain_cards} identical unpriced cards in a row",
                         "vary the layout: one large, one wide, or plain text with rules"))
    # decorative data
    if re.search(r'class="[^"]*\bspark', htm, re.I):
        out.append(Issue("WARN", "sparkline", "decorative sparkline", "remove it unless it shows real data"))
    return out


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

    out += _ai_tells(css_nc, htm, tok)

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
    page = idx.read_text()
    out += lint_html(page)
    # every local file the page points to must exist next to index.html
    refs = set(re.findall(r'(?:src|href)="([^"#?:]+?\.(?:jpg|jpeg|png|webp|gif|svg|mp4|webm|css|js|ico))"', page, re.I))
    for r in sorted(refs):
        if not (root / r).exists():
            out.append(Issue("FAIL", "missing-file", f"page references {r} but it is not in {root}",
                             "run: webbuild ordering init " + str(root) + " --url ... --key ..." if r.startswith("order/")
                             else "copy it next to index.html, or fix the path in brief.json"))
    m = re.search(r"var n=(\d+),dir=\"([^\"]*)\",ext=\"([^\"]*)\"", page)
    if m and int(m.group(1)) > 0:
        d = root / m.group(2)
        have = len(list(d.glob("*" + m.group(3)))) if d.is_dir() else 0
        if have < int(m.group(1)):
            out.append(Issue("FAIL", "missing-frames", f"hero expects {m.group(1)} frames in {m.group(2)}, found {have}"))
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
