"""Renders a complete static website (one HTML file) from a brief. Standard library only."""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

DEFAULT_THEME = {"bg": "#0e0c0b", "fg": "#f4efe9", "accent": "#d7263d", "muted": "#a89f96",
                 "card": "#1a1715", "heading_font": "Playfair Display", "body_font": "Inter"}

REQUIRED = ("name",)
HEX = re.compile(r"^#[0-9a-fA-F]{3,8}$")
FONT = re.compile(r"^[A-Za-z0-9 ]{1,40}$")


def e(v) -> str:
    return html.escape(str(v if v is not None else ""), quote=True)


def validate(brief: dict) -> list[str]:
    errs = [f"missing required field: {k}" for k in REQUIRED if not brief.get(k)]
    for k, v in {**DEFAULT_THEME, **brief.get("theme", {})}.items():
        if k in ("bg", "fg", "accent", "muted", "card") and not HEX.match(str(v)):
            errs.append(f"theme.{k} must be a hex colour like #112233")
        if k.endswith("_font") and not FONT.match(str(v)):
            errs.append(f"theme.{k} may only contain letters, numbers and spaces")
    for k in ("phone", "whatsapp"):
        v = brief.get(k)
        if v and not re.match(r"^\+?[0-9 \-]{6,20}$", str(v)):
            errs.append(f"{k} must look like +919876543210")
    return errs


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
:root{--bg:%(bg)s;--fg:%(fg)s;--accent:%(accent)s;--muted:%(muted)s;--card:%(card)s}
*{box-sizing:border-box;margin:0}html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--fg);font-family:'%(body_font)s',system-ui,sans-serif;line-height:1.6}
h1,h2,h3{font-family:'%(heading_font)s',Georgia,serif;line-height:1.15}
nav{position:fixed;inset:0 0 auto 0;z-index:10;display:flex;justify-content:space-between;align-items:center;padding:14px 20px;background:linear-gradient(#000a,#0000)}
nav b{font-family:'%(heading_font)s',serif;font-size:1.15rem}nav a{color:var(--fg);text-decoration:none;margin-left:16px;font-size:.9rem}
.btn{display:inline-block;background:var(--accent);color:#fff;padding:12px 22px;border-radius:999px;text-decoration:none;font-weight:600;margin:6px 8px 6px 0}
.btn.ghost{background:transparent;border:1px solid var(--muted);color:var(--fg)}
#hero{position:relative;height:%(hero_vh)svh}
#stage{position:sticky;top:0;height:100svh;overflow:hidden;background:#000}
#stage canvas,#stage img.poster{position:absolute;inset:0;width:100%%;height:100%%;object-fit:cover}
#stage:after{content:"";position:absolute;inset:0;background:linear-gradient(#0008,#0003 40%%,#000a)}
.hero-copy{position:absolute;z-index:2;left:0;right:0;bottom:12svh;padding:0 24px;max-width:900px}
.hero-copy h1{font-size:clamp(2.4rem,9vw,5.5rem)}.hero-copy p{color:#e9e2da;font-size:clamp(1rem,2.6vw,1.35rem);margin:12px 0 18px}
.sec{padding:84px 22px;max-width:1100px;margin:auto}.sec h2{font-size:clamp(1.8rem,5vw,3rem);margin-bottom:26px}
.sec h3{margin:34px 0 14px;color:var(--accent);font-size:1.3rem}.about{font-size:1.15rem;color:var(--muted);max-width:720px}
.grid{display:grid;gap:18px;grid-template-columns:repeat(auto-fill,minmax(240px,1fr))}
.card{background:var(--card);border-radius:16px;overflow:hidden}.card img{width:100%%;aspect-ratio:4/3;object-fit:cover;display:block}
.cb{padding:14px 16px}.row{display:flex;justify-content:space-between;gap:10px}.row h4{font-size:1.02rem}.price{color:var(--accent);font-weight:700}
.card p{color:var(--muted);font-size:.9rem;margin-top:4px}
.gal{display:grid;gap:10px;grid-template-columns:repeat(auto-fill,minmax(200px,1fr))}.gal img{width:100%%;aspect-ratio:1;object-fit:cover;border-radius:12px}
.visit{display:grid;gap:26px}.addr{font-size:1.2rem}.hours{list-style:none;padding:0;margin-top:14px;color:var(--muted)}
.hours li{display:flex;justify-content:space-between;max-width:360px;padding:6px 0;border-bottom:1px solid #fff2}
footer{padding:30px 22px;text-align:center;color:var(--muted);font-size:.85rem}
@media(min-width:760px){.visit{grid-template-columns:1fr 1fr;align-items:center}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
"""

JS = """
(function(){
var n=%(count)d,dir=%(dir)s,ext=%(ext)s,pad=%(pad)d;
var hero=document.getElementById('hero'),cv=document.getElementById('cv');
if(!n||!cv)return;
if(window.matchMedia('(prefers-reduced-motion: reduce)').matches){return;}
var ctx=cv.getContext('2d'),imgs=new Array(n),cur=-1,loaded=0;
function size(){var r=window.devicePixelRatio>2?2:window.devicePixelRatio||1;cv.width=innerWidth*r;cv.height=innerHeight*r;draw(cur<0?0:cur,true)}
function name(i){return dir+String(i+1).padStart(pad,'0')+ext}
function draw(i,force){var im=imgs[i];if(!im||!im.complete||!im.naturalWidth)return;if(i===cur&&!force)return;cur=i;
 var cw=cv.width,ch=cv.height,s=Math.max(cw/im.naturalWidth,ch/im.naturalHeight),w=im.naturalWidth*s,h=im.naturalHeight*s;
 ctx.drawImage(im,(cw-w)/2,(ch-h)/2,w,h)}
function load(i){var im=new Image();im.onload=function(){loaded++;if(i===0||i===cur)draw(i,true)};im.src=name(i);imgs[i]=im}
load(0);for(var i=1;i<n;i+=1){(function(k){setTimeout(function(){load(k)},k*12)})(i)}
var raf=0;function onScroll(){if(raf)return;raf=requestAnimationFrame(function(){raf=0;
 var r=hero.getBoundingClientRect(),p=Math.min(1,Math.max(0,-r.top/(hero.offsetHeight-innerHeight)));
 var i=Math.min(n-1,Math.floor(p*(n-1)));
 if(!imgs[i]||!imgs[i].complete){for(var d=1;d<n;d++){if(imgs[i-d]&&imgs[i-d].complete){i=i-d;break}}}
 draw(i)})}
addEventListener('scroll',onScroll,{passive:true});addEventListener('resize',size);size();
})();
"""


def render(brief: dict) -> str:
    errs = validate(brief)
    if errs:
        raise ValueError("; ".join(errs))
    t = {**DEFAULT_THEME, **brief.get("theme", {})}
    hero = brief.get("hero") or {}
    count = int(hero.get("frames", 0) or 0)
    frames_dir = hero.get("dir", "frames/")
    if not frames_dir.endswith("/"):
        frames_dir += "/"
    ext = hero.get("ext", ".jpg")
    css = CSS % {**t, "hero_vh": 100 + min(max(count, 0), 240) * 3 if count else 100}
    js = JS % {"count": count, "dir": json.dumps(frames_dir), "ext": json.dumps(ext), "pad": int(hero.get("pad", 4))}
    poster = f'<img class="poster" src="{e(hero["poster"])}" alt="">' if hero.get("poster") else ""
    fonts = "family=" + t["heading_font"].replace(" ", "+") + ":wght@600;700&family=" + t["body_font"].replace(" ", "+") + ":wght@400;600"
    nav = "".join(f'<a href="#{i}">{l}</a>' for i, l, k in
                  (("menu", "Menu", "menu"), ("gallery", "Gallery", "gallery"), ("visit", "Visit", "x")) if k == "x" or brief.get(k))
    cta = (f'<a class="btn" href="#visit">{e(brief.get("cta_label", "Find us"))}</a>')
    about = (f'<section id="about" class="sec"><h2>{e(brief.get("about_title", "Our story"))}</h2>'
             f'<p class="about">{e(brief.get("about", ""))}</p></section>') if brief.get("about") else ""
    desc = e(brief.get("description") or brief.get("tagline") or brief["name"])
    return f"""<!doctype html>
<html lang="{e(brief.get('lang', 'en'))}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(brief['name'])}{(' | ' + e(brief['tagline'])) if brief.get('tagline') else ''}</title>
<meta name="description" content="{desc}"><meta name="theme-color" content="{e(t['bg'])}">
<meta property="og:title" content="{e(brief['name'])}"><meta property="og:description" content="{desc}">
<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?{fonts}&display=swap" rel="stylesheet">
<style>{css}</style></head><body>
<nav><b>{e(brief['name'])}</b><div>{nav}</div></nav>
<header id="hero"><div id="stage">{poster}<canvas id="cv"></canvas>
<div class="hero-copy"><h1>{e(brief['name'])}</h1><p>{e(brief.get('tagline', ''))}</p>{cta}</div></div></header>
{about}{_menu(brief)}{_gallery(brief)}{_visit(brief)}
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
