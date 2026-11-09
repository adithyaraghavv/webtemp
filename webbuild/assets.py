"""The /webbuild command text installed into Claude Code."""
from __future__ import annotations

COMMAND_MD = """---
description: Interview me about a business, then build a premium, ready-to-deploy website from my templates
---

Build a website with webbuild. Do not start building until the brief is complete.

Setup (skip what is done):
1. Run `webbuild --version`. If it is missing, install it from my repo `{repo}` (public):
   `pip install git+https://github.com/{repo}.git` (add `--break-system-packages` if pip refuses).
2. Work in a new folder for this site (ask me for the name if I did not give one).

Step 1: intake. Ask me for everything below in ONE message, as a short list, and let me answer in
one go. Accept "skip" or "you decide" for anything optional. Do not guess facts.
- Business name, what it is (cafe, salon, clinic, gym, startup, portfolio...), city, language
- One-line tagline and who the customers are
- Look and feel: mood words, colours or a reference site, dark or light
- Real content: about text, menu or services with prices, opening hours, address, phone, WhatsApp, map link
- Media: a hero video (best: 10 to 25 seconds, filmed on a phone, steady) and photos, with permission to use them
- The one action visitors should take (call, book, order, directions, join waitlist)
Never invent prices, hours, addresses, awards or reviews. If something is missing, leave it out
or mark it clearly as a placeholder in my summary.

Design direction (do this before writing the brief; it is what stops the site looking machine-made):
- Commit to ONE look and write it as `direction` in the brief, one line, for example "dark and cinematic,
  heavy condensed type, one red accent" or "warm and editorial, serif headlines, paper tones". Safe,
  in-between looks are what make a site feel generic. Do not blend two directions.
- This is brand work (marketing, landing pages): use the bolder rules. Large display type, real asymmetry,
  scroll choreography, one strong accent. Set `register` to "brand". Use "product" only for app UI.
- Neutrals are tinted toward the palette hue, never pure grey, black or white. Pair a distinctive display
  face with a quiet text face. Avoid Inter, Roboto, Arial, Open Sans, Poppins, Montserrat and Lato as the look.
- Avoid the machine-made tells: identical card grids, cards inside cards, glass blur on many surfaces,
  grey text on coloured backgrounds, bounce or elastic easing, decorative sparklines, purple-blue gradients,
  emoji as icons, big-number stat rows with no real numbers behind them.
- Ask for 1 or 2 sites I like. Name what makes them work (grid, type scale, photo style, motion) and use
  the principles, never copy them.
- Pick ONE preset from `webbuild presets` (ember, paper, street, quiet, diner) that fits this business's
  mood and neighbourhood, and say why in one line. Override colours or fonts only with a reason.
- Real media comes first. If I gave no real photos or video, say so and ask before building. Never use
  stock-looking filler, emoji as icons, or purple-blue gradients.
- Write copy in the owner's voice: short, plain, specific (a street, a dish, a year, a name). Never use
  filler like "elevate your experience", "seamless", "crafted with passion", "world-class".
- Never invent customer counts, awards, reviews or "trusted by" claims.

Step 2: write `brief.json` (see `webbuild example` for every field; run `webbuild check brief.json` and act on its notes), then show me a 6-line summary
of what you will build and what is missing. Continue unless I object.

Step 3: build.
1. If I gave a video: `webbuild frames VIDEO --out site/frames --count 120` (use 60 if the site is mostly
   for phones on slow data). Put the best still as `site/poster.jpg` and set `hero.poster` in the brief.
2. Copy photos into `site/img/` and compress them (max 1600px wide) before using them.
3. `webbuild build brief.json --out site`
4. Open `site/index.html` through a local server, take screenshots at 390px and 1280px wide with
   Playwright, and look at them. Check: text readable over the hero, buttons work, nothing overflows
   sideways, images load, scroll animation plays forward and back.
5. Improve the copy and the design honestly: sharper headline, real section order for this kind of
   business, strong first screen on a phone. Edit `brief.json` or the generated HTML, but keep the
   result a plain static site that needs no build step.

Step 4: quality gate (loop, max 3 rounds). Run `webbuild lint site`. Fix every FAIL at the cause in
`brief.json` or the HTML. Never hide a FAIL by weakening the linter. Fix or explain every WARN. Then re-run.
Then do a design critique on the screenshots (390px and 1280px) and write down your answers:
1. What is the one memorable thing on the first screen?
2. Would a person guess an AI made this? Name every tell you see (default fonts, card grids, timid colour,
   generic hero, stock phrasing) and fix each one.
3. Does the page keep to the one `direction` from the brief, or did it drift into a mix?
4. Does it have a clear hierarchy: one big idea per screen, not many equal boxes?
Fix what is weak, rebuild, re-lint, and look again. Do not report done on a page you judged generic.
Also check:
- Lighthouse-style basics: page title, meta description, alt text, tap targets, contrast
- Total page weight under 12 MB; no single image over 400 KB unless it is the hero frames
- Works without JavaScript (poster and content still visible) and with reduced motion
- No broken links; phone and WhatsApp links are correct

Step 5: finish. Tell me in plain English what you built, what is placeholder, what I must confirm
with the client, and how to deploy (drag the `site` folder into Netlify, or `netlify deploy --dir site`).
Do not deploy or publish anything unless I ask.
"""


def command_md(repo: str = "adithyaraghavv/webtemp") -> str:
    return COMMAND_MD.replace("{repo}", repo)
