"""Restaurant / bar template: fly-through hero over a transparent nav, logo reveal, shrink into content,
bold call-to-action band, menu as ruled lists (no identical card grid), and a split find-us section.
Standard library only; all colours come from the theme tokens."""
from __future__ import annotations

import re

CSS = """
.rest nav{background:linear-gradient(color-mix(in srgb,var(--scrim) 72%%,transparent),transparent);padding:16px 20px;gap:12px}
.rest nav:before{content:"";position:absolute;inset:0;z-index:-1;background:var(--scrim);opacity:calc(var(--leave,0) * .94)}
.rest nav>div{display:flex;align-items:center;white-space:nowrap}
.brand{font-family:var(--font-head);font-size:1.15rem;text-decoration:none;text-transform:uppercase;white-space:nowrap}
nav .btn.sm{padding:8px 18px;font-size:.85rem;margin:0 0 0 18px;color:var(--on-accent)}
.rest #stage{transform:scale(calc(1 - .1 * var(--leave,0)));border-radius:calc(var(--leave,0) * 36px);transform-origin:center top}
.reveal{position:absolute;z-index:2;inset:0;display:grid;place-content:center;text-align:center;padding:24px;color:var(--hero-fg);
opacity:var(--reveal,1);pointer-events:none}
.mark{font-size:clamp(3.4rem,17vw,12rem);line-height:.9;text-transform:uppercase}
.reveal p{font-size:clamp(.95rem,2.4vw,1.3rem);margin-top:14px;letter-spacing:0}
.hero-actions{position:absolute;z-index:3;left:20px;bottom:calc(20px + env(safe-area-inset-bottom,0px));display:flex;gap:8px;flex-wrap:wrap;
opacity:calc(1 - var(--leave,0))}
.hero-actions .btn{margin:0;padding:10px 18px;font-size:.85rem}
.hero-actions .btn.ghost{color:var(--hero-fg);border-color:var(--hero-fg)}
.ready{background:var(--accent);color:var(--on-accent);padding:clamp(64px,11vw,128px) 24px;text-align:center}
.ready h2{font-size:clamp(2.8rem,11vw,7.5rem);text-transform:uppercase;line-height:.92;margin-bottom:12px}
.ready p{max-width:32em;margin:0 auto 20px;font-size:1.1rem}
.ready .btn{background:var(--on-accent);color:var(--accent);margin:8px 6px}
.ready .btn.ghost{background:transparent;border-color:var(--on-accent);color:var(--on-accent)}
.menu-wrap{max-width:1100px;margin:auto;padding:clamp(64px,10vw,120px) 24px}
.menu-wrap>h2{font-size:clamp(2.4rem,8vw,5rem);text-transform:uppercase;margin-bottom:48px}
.mcat{display:grid;gap:28px;margin-bottom:72px}
.mcat h3{font-size:clamp(1.6rem,4vw,2.4rem);text-transform:uppercase;color:var(--accent);margin:0 0 8px}
.mfeat img{width:100%%;aspect-ratio:4/5;object-fit:cover;display:block;border-radius:var(--radius)}
.mrow{display:grid;grid-template-columns:1fr auto;gap:2px 16px;padding:14px 0;border-bottom:1px solid var(--line)}
.mrow h4{font-family:var(--font-body);font-size:1.1rem;font-weight:600}
.mrow p{grid-column:1;color:var(--muted);font-size:.93rem}
.mrow .price{grid-row:1;grid-column:2;color:var(--accent);font-weight:700}
.find{display:grid;border-top:1px solid var(--line)}
.find .photo img{width:100%%;height:100%%;min-height:46svh;object-fit:cover;display:block}
.find .info{padding:clamp(48px,8vw,96px) 24px;max-width:600px}
.find h2{font-size:clamp(2.4rem,8vw,4.8rem);text-transform:uppercase;margin-bottom:20px}
.gal-wrap{max-width:1200px;margin:auto;padding:clamp(56px,9vw,112px) 24px}.gal-wrap>h2{font-size:clamp(2.4rem,8vw,5rem);text-transform:uppercase;margin-bottom:32px}
.mosaic{display:grid;gap:10px;grid-template-columns:repeat(2,1fr);grid-auto-flow:dense}
.mosaic img{width:100%%;height:100%%;object-fit:cover;display:block;border-radius:var(--radius);aspect-ratio:1}
.mosaic img:nth-child(5n+1){grid-column:span 2;aspect-ratio:16/9}
@media(min-width:860px){.mosaic{grid-template-columns:repeat(4,1fr)}.mosaic img:nth-child(5n+1){grid-column:span 2;grid-row:span 2;aspect-ratio:auto}}
.about-wrap{display:grid;gap:28px;max-width:1100px;margin:auto;padding:clamp(56px,9vw,112px) 24px}
.about-wrap h2{font-size:clamp(2.4rem,8vw,5rem);text-transform:uppercase}.about-wrap p{font-size:1.2rem;color:var(--muted);max-width:34em}
.about-wrap img{width:100%%;aspect-ratio:4/5;object-fit:cover;border-radius:var(--radius);display:block}
@media(min-width:860px){.about-wrap.has-photo{grid-template-columns:7fr 5fr;align-items:center}}
.contact{background:var(--card);border-top:1px solid var(--line)}.contact .in{max-width:1100px;margin:auto;padding:clamp(48px,8vw,96px) 24px;display:grid;gap:24px}
.contact h2{font-size:clamp(2.4rem,8vw,4.8rem);text-transform:uppercase}.contact ul{list-style:none;padding:0;display:grid;gap:10px;font-size:1.15rem}
.contact li span{display:block;color:var(--muted);font-size:.85rem;text-transform:uppercase;letter-spacing:.06em}
@media(min-width:860px){.contact .in{grid-template-columns:1fr 1fr}}
.js .rv{opacity:0;transform:translateY(28px);transition:opacity .7s cubic-bezier(.2,.7,.2,1),transform .7s cubic-bezier(.2,.7,.2,1)}
.js .rv.in{opacity:1;transform:none}
@media(prefers-reduced-motion:reduce){.js .rv{opacity:1;transform:none;transition:none}}
section[id]{scroll-margin-top:64px}
.mfeat img{aspect-ratio:16/10}
@media(max-width:560px){.rest nav>div a:not(.btn){display:none}}
@media(min-width:860px){.mfeat img{aspect-ratio:4/5}.mcat{grid-template-columns:5fr 7fr;align-items:start}.mcat.flip .mfeat{order:2}
.mcat.nofeat{grid-template-columns:1fr}.find.has-photo{grid-template-columns:1fr 1fr;min-height:72svh}}
"""


def _e(v) -> str:
    import html
    return html.escape(str(v if v is not None else ""), quote=True)


def _digits(v: str) -> str:
    return re.sub(r"\D", "", v or "")


def order_href(b: dict) -> str:
    if b.get("order_url"):
        return _e(b["order_url"])
    if b.get("whatsapp"):
        return f'https://wa.me/{_digits(b["whatsapp"])}'
    if b.get("phone"):
        return "tel:" + _e(_digits(b["phone"]))
    return "#visit"


def _buttons(b: dict, ghost_first: bool = False) -> str:
    out = []
    if b.get("order_url"):
        out.append(f'<a class="btn" href="{_e(b["order_url"])}" rel="noopener">{_e(b.get("cta_label", "Order now"))}</a>')
    if b.get("phone"):
        out.append(f'<a class="btn ghost" href="tel:{_e(_digits(b["phone"]))}">Call us</a>')
    if b.get("whatsapp"):
        out.append(f'<a class="btn ghost" href="https://wa.me/{_digits(b["whatsapp"])}" rel="noopener">WhatsApp</a>')
    return "".join(out)


def nav(b: dict) -> str:
    links = ""
    if b.get("menu") or b.get("ordering"):
        links += '<a href="#menu">Menu</a>'
    links += '<a href="#visit">Visit</a>'
    if b.get("phone") or b.get("whatsapp") or b.get("email") or b.get("instagram"):
        links += '<a href="#contact">Contact</a>'
    return (f'<nav><a class="brand" href="#top">{_e(b["name"])}</a><div>{links}'
            f'<a class="btn sm" href="{order_href(b)}">{_e(b.get("cta_label", "Order now"))}</a></div></nav>')


def hero(b: dict, poster: str) -> str:
    tag = f'<p>{_e(b["tagline"])}</p>' if b.get("tagline") else ""
    second = (f'<a class="btn ghost" href="{order_href(b)}">{_e(b.get("cta_label", "Order now"))}</a>')
    first = '<a class="btn" href="#menu">Explore the menu</a>' if (b.get("menu") or b.get("ordering")) else ""
    return (f'<header id="hero" data-fx="1"><div id="stage">{poster}<canvas id="cv" aria-hidden="true"></canvas>'
            f'<div class="reveal"><h1 class="mark">{_e(b["name"])}</h1>{tag}</div>'
            f'<div class="hero-actions">{first}{second}</div></div></header>')


def ready(b: dict) -> str:
    btns = _buttons(b)
    text = f'<p>{_e(b["ready_text"])}</p>' if b.get("ready_text") else ""
    return (f'<section class="ready"><h2>{_e(b.get("ready_title", "Ready to eat?"))}</h2>{text}{btns}</section>')


def about(b: dict) -> str:
    if not b.get("about"):
        return ""
    img = (f'<img class="rv" loading="lazy" src="{_e(b["about_image"])}" alt="">' if b.get("about_image") else "")
    return (f'<section id="about" class="about-wrap{" has-photo" if img else ""}"><div class="rv"><h2>{_e(b.get("about_title", "Our story"))}</h2>'
            f'<p>{_e(b["about"])}</p></div>{img}</section>')


def gallery(b: dict) -> str:
    imgs = b.get("gallery") or []
    if not imgs:
        return ""
    return ('<section id="gallery" class="gal-wrap"><h2 class="rv">Gallery</h2><div class="mosaic">'
            + "".join(f'<img class="rv" loading="lazy" src="{_e(i)}" alt="{_e(b["name"])} photo {n}">' for n, i in enumerate(imgs, 1))
            + "</div></section>")


def contact(b: dict) -> str:
    rows = []
    if b.get("phone"):
        rows.append(f'<li><span>Call</span><a href="tel:{_e(_digits(b["phone"]))}">{_e(b["phone"])}</a></li>')
    if b.get("whatsapp"):
        rows.append(f'<li><span>WhatsApp</span><a href="https://wa.me/{_digits(b["whatsapp"])}" rel="noopener">{_e(b["whatsapp"])}</a></li>')
    if b.get("email"):
        rows.append(f'<li><span>Email</span><a href="mailto:{_e(b["email"])}">{_e(b["email"])}</a></li>')
    if b.get("instagram"):
        h = str(b["instagram"]).lstrip("@")
        rows.append(f'<li><span>Instagram</span><a href="https://instagram.com/{_e(h)}" rel="noopener">@{_e(h)}</a></li>')
    if not rows:
        return ""
    return (f'<section id="contact" class="contact"><div class="in"><h2 class="rv">{_e(b.get("contact_title", "Say hello"))}</h2>'
            f'<ul class="rv">{"".join(rows)}</ul></div></section>')


def menu(b: dict) -> str:
    cats = b.get("menu") or []
    if not cats and not b.get("ordering"):
        return ""
    cur = _e(b.get("currency", ""))
    live = b.get("ordering")
    out = ['<section id="menu" class="menu-wrap"><h2 class="rv">Menu</h2>' + (f'<div id="menu-live" data-currency="{cur}">' if live else "")]
    for n, c in enumerate(cats):
        items = c.get("items", [])
        feat = next((i for i in items if i.get("image")), None)
        cls = "mcat" + (" flip" if n % 2 else "") + ("" if feat else " nofeat")
        photo = (f'<div class="mfeat"><img loading="lazy" src="{_e(feat["image"])}" alt="{_e(feat.get("name"))}"></div>' if feat else "")
        rows = []
        for it in items:
            price = (f'<span class="price">{cur}{_e(it["price"])}</span>' if it.get("price") not in (None, "") else "")
            desc = f'<p>{_e(it["desc"])}</p>' if it.get("desc") else ""
            rows.append(f'<div class="mrow"><h4>{_e(it.get("name"))}</h4>{price}{desc}</div>')
        out.append(f'<div class="{cls}">{photo}<div><h3>{_e(c.get("category"))}</h3>{"".join(rows)}</div></div>')
    out.append("</div></section>" if live else "</section>")
    return "".join(out)


def find(b: dict) -> str:
    hours = b.get("hours") or []
    rows = "".join(f'<li><span>{_e(h.get("days"))}</span><span>{_e(h.get("time"))}</span></li>' for h in hours)
    btns = []
    if b.get("map_url"):
        btns.append(f'<a class="btn" href="{_e(b["map_url"])}" rel="noopener">Get directions</a>')
    if b.get("phone"):
        btns.append(f'<a class="btn ghost" href="tel:{_e(_digits(b["phone"]))}">Call</a>')
    photo = (f'<div class="photo"><img loading="lazy" src="{_e(b["visit_image"])}" alt="{_e(b["name"])} from the street"></div>'
             if b.get("visit_image") else "")
    addr = f'<p class="addr">{_e(b["address"])}</p>' if b.get("address") else ""
    return (f'<section id="visit" class="find{" has-photo" if photo else ""}">{photo}<div class="info">'
            f'<h2>{_e(b.get("visit_title", "Find us"))}</h2>{addr}<ul class="hours">{rows}</ul>{"".join(btns)}</div></section>')
