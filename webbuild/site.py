"""Renders a complete static website (one HTML file) from a brief. Standard library only."""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

from . import restaurant

PRESETS = {
    # Each preset is a different material: palette, type pairing, corner shape, borders.
    "ember": {"bg": "#100d0c", "fg": "#f3ece4", "muted": "#b3a89d", "card": "#1b1715", "accent": "#e0475a",
              "on_accent": "#1a0a0c", "line": "#3a312c", "scrim": "#0b0908", "hero_fg": "#f7f1ea",
              "heading_font": "Fraunces", "body_font": "DM Sans", "heading_axis": ":opsz,wght@9..144,600;9..144,700",
              "radius": "14px", "btn_radius": "999px", "bw": "0px"},
    "paper": {"bg": "#f4ede0", "fg": "#231c16", "muted": "#5e5348", "card": "#fbf6ec", "accent": "#a8431f",
              "on_accent": "#fdf6ea", "line": "#cdbfa6", "scrim": "#1c1612", "hero_fg": "#f8f1e6",
              "heading_font": "Newsreader", "body_font": "Work Sans", "heading_axis": ":opsz,wght@6..72,500;6..72,700",
              "radius": "2px", "btn_radius": "2px", "bw": "1px"},
    "street": {"bg": "#f2c230", "fg": "#14110f", "muted": "#3d3426", "card": "#fff1b8", "accent": "#b3142b",
               "on_accent": "#fff4e0", "line": "#14110f", "scrim": "#14110f", "hero_fg": "#fff4d6",
               "heading_font": "Archivo Black", "body_font": "Work Sans", "heading_axis": "",
               "radius": "0px", "btn_radius": "0px", "bw": "3px"},
    "quiet": {"bg": "#e9eee8", "fg": "#1d2a24", "muted": "#4d5d54", "card": "#f4f7f3", "accent": "#2f6b52",
              "on_accent": "#f2f7f3", "line": "#c0cec4", "scrim": "#14201a", "hero_fg": "#eef3ee",
              "heading_font": "Cormorant Garamond", "body_font": "Jost", "heading_axis": ":wght@500;700",
              "radius": "18px", "btn_radius": "999px", "bw": "0px"},
    "diner": {"bg": "#f6e9cf", "fg": "#2a1d17", "muted": "#5f4a3c", "card": "#fff6df", "accent": "#0f6f78",
              "on_accent": "#f6efe0", "line": "#2a1d17", "scrim": "#1f1612", "hero_fg": "#fbf0d8",
              "heading_font": "Bricolage Grotesque", "body_font": "Manrope", "heading_axis": ":wght@600;800",
              "radius": "10px", "btn_radius": "8px", "bw": "2px"},
    "cantina": {"bg": "#150c0b", "fg": "#f2e7e1", "muted": "#bfa9a1", "card": "#1f1210", "accent": "#c9302a",
                "on_accent": "#fff0ea", "line": "#40241f", "scrim": "#0d0605", "hero_fg": "#fbeee8",
                "heading_font": "Anton", "body_font": "Barlow", "heading_axis": "",
                "radius": "4px", "btn_radius": "2px", "bw": "0px"},
}
DEFAULT_THEME = PRESETS["ember"]
COLOR_KEYS = ("bg", "fg", "muted", "card", "accent", "on_accent", "line", "scrim", "hero_fg")
SIZE = re.compile(r"^\d{1,3}px$")
AXIS = re.compile(r"^(:[A-Za-z0-9@;,.]+)?$")

REQUIRED = ("name",)
HEX = re.compile(r"^#[0-9a-fA-F]{3,8}$")
FONT = re.compile(r"^[A-Za-z0-9 ]{1,40}$")


def theme_of(brief: dict) -> dict:
    t = dict(brief.get("theme") or {})
    base = PRESETS.get(t.pop("preset", "ember"))
    return {**(base or DEFAULT_THEME), **t}


def e(v) -> str:
    return html.escape(str(v if v is not None else ""), quote=True)


def validate(brief: dict) -> list[str]:
    errs = [f"missing required field: {k}" for k in REQUIRED if not brief.get(k)]
    if brief.get("template", "classic") not in ("classic", "restaurant"):
        errs.append("template must be classic or restaurant")
    raw = brief.get("theme") or {}
    if "preset" in raw and raw["preset"] not in PRESETS:
        errs.append(f"theme.preset must be one of: {', '.join(PRESETS)}")
    for k, v in theme_of(brief).items():
        if k in COLOR_KEYS and not HEX.match(str(v)):
            errs.append(f"theme.{k} must be a hex colour like #112233")
        elif k.endswith("_font") and not FONT.match(str(v)):
            errs.append(f"theme.{k} may only contain letters, numbers and spaces")
        elif k in ("radius", "btn_radius", "bw") and not SIZE.match(str(v)):
            errs.append(f"theme.{k} must look like 12px")
        elif k == "heading_axis" and not AXIS.match(str(v)):
            errs.append("theme.heading_axis has invalid characters")
    for k in ("phone", "whatsapp"):
        v = brief.get(k)
        if v and not re.match(r"^\+?[0-9 \-]{6,20}$", str(v)):
            errs.append(f"{k} must look like +919876543210")
    return errs


def advice(brief: dict) -> list[str]:
    """Non-blocking notes on the brief: the design direction is what keeps a site from reading as generic."""
    out = []
    d = str(brief.get("direction") or "").strip()
    if not d:
        out.append('no "direction": write one line naming the single look (e.g. "dark and cinematic, heavy condensed type, '
                   'one red accent"). Mixed or safe looks read as generic.')
    elif len(d.split()) > 25:
        out.append('"direction" is long; reduce it to one look')
    if brief.get("register", "brand") not in ("brand", "product"):
        out.append('"register" must be "brand" (marketing, bold) or "product" (app UI, restrained)')
    return out


def _digits(v: str) -> str:
    return re.sub(r"\D", "", v or "")


def _menu(brief: dict) -> str:
    cats = brief.get("menu") or []
    if not cats:
        return ""
    cur = e(brief.get("currency", ""))
    out = ['<section id="menu" class="sec"><h2>Menu</h2>']
    for c in cats:
        out.append(f'<h3>{e(c.get("category"))}</h3><div class="grid">')
        for it in c.get("items", []):
            img = f'<img loading="lazy" src="{e(it["image"])}" alt="{e(it.get("name"))}">' if it.get("image") else ""
            price = f'<span class="price">{cur}{e(it["price"])}</span>' if it.get("price") not in (None, "") else ""
            out.append(f'<article class="card">{img}<div class="cb"><div class="row"><h4>{e(it.get("name"))}</h4>{price}</div>'
                       f'<p>{e(it.get("desc", ""))}</p></div></article>')
        out.append("</div>")
    out.append("</section>")
    return "".join(out)


def _gallery(brief: dict) -> str:
    imgs = brief.get("gallery") or []
    if not imgs:
        return ""
    return ('<section id="gallery" class="sec"><h2>Gallery</h2><div class="gal">'
            + "".join(f'<img loading="lazy" src="{e(i)}" alt="{e(brief["name"])} photo {n}">' for n, i in enumerate(imgs, 1))
            + "</div></section>")


def _visit(brief: dict) -> str:
    hours = brief.get("hours") or []
    rows = "".join(f'<li><span>{e(h.get("days"))}</span><span>{e(h.get("time"))}</span></li>' for h in hours)
    addr = e(brief.get("address", ""))
    btns = []
    if brief.get("map_url"):
        btns.append(f'<a class="btn" href="{e(brief["map_url"])}" rel="noopener">Get directions</a>')
    if brief.get("phone"):
        btns.append(f'<a class="btn ghost" href="tel:{e(_digits(brief["phone"]))}">Call</a>')
    if brief.get("whatsapp"):
        msg = "Hi, I would like to book a table"
        btns.append(f'<a class="btn ghost" href="https://wa.me/{_digits(brief["whatsapp"])}?text={e(msg.replace(" ", "%20"))}" rel="noopener">WhatsApp</a>')
    return (f'<section id="visit" class="sec"><h2>{e(brief.get("cta_title", "Visit us"))}</h2>'
            f'<div class="visit"><div><p class="addr">{addr}</p><ul class="hours">{rows}</ul></div>'
            f'<div class="btns">{"".join(btns)}</div></div></section>')


CSS = """
:root{--bg:%(bg)s;--fg:%(fg)s;--accent:%(accent)s;--muted:%(muted)s;--card:%(card)s;--on-accent:%(on_accent)s;
--line:%(line)s;--scrim:%(scrim)s;--hero-fg:%(hero_fg)s;--radius:%(radius)s;--btn-radius:%(btn_radius)s;--bw:%(bw)s;
--font-head:'%(heading_font)s',Georgia,serif;--font-body:'%(body_font)s',system-ui,sans-serif}
*{box-sizing:border-box;margin:0}html{scroll-behavior:smooth;overflow-x:clip}
body{background:var(--bg);color:var(--fg);font-family:var(--font-body);line-height:1.6;overflow-x:clip}
h1,h2,h3{font-family:var(--font-head);line-height:1.12;text-wrap:balance}
a{color:inherit}
:focus-visible{outline:3px solid var(--accent);outline-offset:3px}
nav :focus-visible,.hero-copy :focus-visible{outline-color:var(--hero-fg)}
nav{position:fixed;inset:0 0 auto 0;z-index:10;display:flex;justify-content:space-between;align-items:center;padding:12px 20px;
background:color-mix(in srgb,var(--scrim) 88%%,transparent);color:var(--hero-fg)}
nav b{font-family:var(--font-head);font-size:1.15rem}nav a{color:var(--hero-fg);text-decoration:none;margin-left:16px;font-size:.9rem}
nav a:hover{text-decoration:underline}
.btn{display:inline-block;background:var(--accent);color:var(--on-accent);padding:12px 24px;border-radius:var(--btn-radius);
text-decoration:none;font-weight:600;margin:8px 8px 8px 0;transition:transform .15s ease,opacity .15s ease}
.btn:hover{opacity:.9}.btn:active{transform:translateY(1px)}
.btn.ghost{background:transparent;border:2px solid var(--line);color:var(--fg)}
#hero{position:relative;height:%(hero_vh)ssvh}
#stage{position:sticky;top:0;height:100svh;overflow:hidden;background:var(--scrim)}
#stage canvas,#stage img.poster{position:absolute;inset:0;width:100%%;height:100%%;object-fit:cover}
#stage:after{content:"";position:absolute;inset:0;background:linear-gradient(color-mix(in srgb,var(--scrim) 55%%,transparent),color-mix(in srgb,var(--scrim) 15%%,transparent) 40%%,color-mix(in srgb,var(--scrim) 72%%,transparent))}
.hero-copy{position:absolute;z-index:2;left:0;right:0;bottom:12svh;padding:0 24px;max-width:900px;color:var(--hero-fg)}
.hero-copy h1{font-size:clamp(2.4rem,9vw,5.5rem)}.hero-copy p{font-size:clamp(1rem,2.6vw,1.35rem);margin:12px 0 20px;max-width:34em}
.hero-copy .btn:hover{opacity:.9}
.sec{padding:80px 24px;max-width:1100px;margin:auto}.sec h2{font-size:clamp(1.8rem,5vw,3rem);margin-bottom:24px}
.sec h3{margin:32px 0 16px;color:var(--accent);font-size:1.3rem}.about{font-size:1.15rem;color:var(--muted);max-width:720px}
.grid{display:grid;gap:20px;grid-template-columns:repeat(auto-fill,minmax(240px,1fr))}
.card{background:var(--card);border-radius:var(--radius);overflow:hidden;border:var(--bw) solid var(--line)}
.card img{width:100%%;aspect-ratio:4/3;object-fit:cover;display:block}
.cb{padding:16px}.row{display:flex;justify-content:space-between;gap:8px}.row h4{font-size:1.02rem}.price{color:var(--accent);font-weight:700}
.card p{color:var(--muted);font-size:.9rem;margin-top:4px}
.gal{display:grid;gap:8px;grid-template-columns:repeat(auto-fill,minmax(200px,1fr))}.gal img{width:100%%;aspect-ratio:1;object-fit:cover;border-radius:var(--radius)}
.visit{display:grid;gap:24px}.addr{font-size:1.2rem}.hours{list-style:none;padding:0;margin-top:16px;color:var(--muted)}
.hours li{display:flex;justify-content:space-between;max-width:360px;padding:8px 0;border-bottom:1px solid var(--line)}
footer{padding:32px 24px;text-align:center;color:var(--muted);font-size:.85rem}
@media(min-width:760px){.visit{grid-template-columns:1fr 1fr;align-items:center}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}.btn{transition:none}#hero{height:100svh}}
"""

JS = """
(function(){
var n=%(count)d,dir=%(dir)s,ext=%(ext)s,pad=%(pad)d,fx=%(fx)d;
var hero=document.getElementById('hero'),cv=document.getElementById('cv');
if(!n||!cv)return;
if(window.matchMedia('(prefers-reduced-motion: reduce)').matches){return;}
var root=document.documentElement.style,ctx=cv.getContext('2d'),imgs=new Array(n),cur=-1,loaded=0;
function size(){var r=window.devicePixelRatio>2?2:window.devicePixelRatio||1;cv.width=innerWidth*r;cv.height=innerHeight*r;draw(cur<0?0:cur,true)}
function name(i){return dir+String(i+1).padStart(pad,'0')+ext}
function draw(i,force){var im=imgs[i];if(!im||!im.complete||!im.naturalWidth)return;if(i===cur&&!force)return;cur=i;
 var cw=cv.width,ch=cv.height,s=Math.max(cw/im.naturalWidth,ch/im.naturalHeight),w=im.naturalWidth*s,h=im.naturalHeight*s;
 ctx.drawImage(im,(cw-w)/2,(ch-h)/2,w,h)}
function load(i){var im=new Image();im.onload=function(){loaded++;if(i===0||i===cur)draw(i,true)};im.src=name(i);imgs[i]=im}
load(0);for(var i=1;i<n;i+=1){(function(k){setTimeout(function(){load(k)},k*12)})(i)}
var raf=0;function onScroll(){if(raf)return;raf=requestAnimationFrame(function(){raf=0;
 var r=hero.getBoundingClientRect(),p=Math.min(1,Math.max(0,-r.top/(hero.offsetHeight-innerHeight)));
 if(fx){var c=function(v){return Math.min(1,Math.max(0,v))};root.setProperty('--reveal',c((p-.74)/.16));root.setProperty('--leave',c((p-.9)/.1))}
 var i=Math.min(n-1,Math.floor(p*(n-1)));
 if(!imgs[i]||!imgs[i].complete){for(var d=1;d<n;d++){if(imgs[i-d]&&imgs[i-d].complete){i=i-d;break}}}
 draw(i)})}
if(fx){root.setProperty('--reveal',0)}
addEventListener('scroll',onScroll,{passive:true});addEventListener('resize',size);size();onScroll();
})();
"""


def render(brief: dict) -> str:
    errs = validate(brief)
    if errs:
        raise ValueError("; ".join(errs))
    t = theme_of(brief)
    hero = brief.get("hero") or {}
    count = int(hero.get("frames", 0) or 0)
    frames_dir = hero.get("dir", "frames/")
    if not frames_dir.endswith("/"):
        frames_dir += "/"
    ext = hero.get("ext", ".jpg")
    rest = brief.get("template") == "restaurant"
    css = CSS % {**t, "hero_vh": 100 + min(max(count, 0), 240) * 3 if count else 100}
    if rest:
        css += restaurant.CSS % {}
    js = JS % {"fx": 1 if rest else 0, "count": count, "dir": json.dumps(frames_dir), "ext": json.dumps(ext), "pad": int(hero.get("pad", 4))}
    poster = f'<img class="poster" src="{e(hero["poster"])}" alt="">' if hero.get("poster") else ""
    fonts = ("family=" + t["heading_font"].replace(" ", "+") + t["heading_axis"] +
             "&family=" + t["body_font"].replace(" ", "+") + ":wght@400;600")
    nav = "".join(f'<a href="#{i}">{l}</a>' for i, l, k in
                  (("menu", "Menu", "menu"), ("gallery", "Gallery", "gallery"), ("visit", "Visit", "x")) if k == "x" or brief.get(k))
    cta = (f'<a class="btn" href="#visit">{e(brief.get("cta_label", "Find us"))}</a>')
    about = (f'<section id="about" class="sec"><h2>{e(brief.get("about_title", "Our story"))}</h2>'
             f'<p class="about">{e(brief.get("about", ""))}</p></section>') if brief.get("about") else ""
    desc = e(brief.get("description") or brief.get("tagline") or brief["name"])
    if rest:
        body = (restaurant.nav(brief) + restaurant.hero(brief, poster) + restaurant.ready(brief) + about
                + restaurant.menu(brief) + _gallery(brief) + restaurant.find(brief))
    else:
        body = (f'<nav><b>{e(brief["name"])}</b><div>{nav}</div></nav>'
                f'<header id="hero"><div id="stage">{poster}<canvas id="cv" aria-hidden="true"></canvas>'
                f'<div class="hero-copy"><h1>{e(brief["name"])}</h1><p>{e(brief.get("tagline", ""))}</p>{cta}</div></div></header>'
                f'{about}{_menu(brief)}{_gallery(brief)}{_visit(brief)}')
    return f"""<!doctype html>
<html lang="{e(brief.get('lang', 'en'))}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(brief['name'])}{(' | ' + e(brief['tagline'])) if brief.get('tagline') else ''}</title>
<meta name="description" content="{desc}"><meta name="theme-color" content="{e(t['bg'])}">
<meta property="og:title" content="{e(brief['name'])}"><meta property="og:description" content="{desc}">
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?{fonts}&display=swap" rel="stylesheet">
<style>{css}</style></head><body{' class="rest"' if rest else ''} id="top">
{body}
<footer>&copy; {e(brief['name'])}</footer>
<script>{js}</script></body></html>
"""


def build(brief_path: str, out_dir: str) -> Path:
    brief = json.loads(Path(brief_path).read_text())
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    hero = brief.setdefault("hero", {}) if brief.get("hero") else None
    if hero is not None:
        # trust the files on disk, not the number in the brief
        d = out / hero.get("dir", "frames/")
        found = sorted(d.glob("*" + hero.get("ext", ".jpg"))) if d.is_dir() else []
        hero["frames"] = len(found)
    (out / "index.html").write_text(render(brief))
    return out / "index.html"
