# webbuild

Your own website and landing-page builder for Claude Code. Type `/webbuild`, answer one intake
message about the business, and it builds a premium static site: a full-screen hero that plays
a filmed video as you scroll, about, menu, gallery, hours, map and call/WhatsApp buttons.

## Install (one time)
Add this to the setup script of your Claude Code cloud environment (after the guard line):

    pip install git+https://github.com/adithyaraghavv/webtemp.git && webbuild setup

## Use
1. New session, environment with the setup script, any repo or an empty one.
2. Type `/webbuild`. Answer the intake. Give it a 10-25 second phone video if you have one.
3. It writes `brief.json`, extracts frames, builds `site/`, screenshots it on phone and desktop, fixes issues.
4. Deploy: drag `site/` into Netlify.

## Design layer (our own, original code)
Five presets (`webbuild presets`): ember, paper, street, quiet, diner. Each is a different material
(palette, type pairing, corner shape, borders). `webbuild lint site` fails the build on common
machine-made tells: colours outside tokens, pure black/white, missing focus styles, no reduced-motion
fallback, purple-blue gradients, emoji icons, low contrast (WCAG), missing alt text, filler copy,
invented "trusted by" claims. Idea credit: the anti-AI-slop approach popularised by Hallmark (MIT);
none of its code or text is used here.

## Commands
- `webbuild example` prints a full example brief
- `webbuild check brief.json` validates it
- `webbuild frames video.mp4 --out site/frames --count 120` needs ffmpeg
- `webbuild lint site` design and quality checks (exit 1 on any FAIL)
- `webbuild presets` lists presets
- `webbuild build brief.json --out site` writes `site/index.html` (counts the real frames itself)

Standard library only. Output is plain HTML, CSS and JS with no build step. All text from the
brief is HTML-escaped; colours and font names are validated.

## Not built yet
Cafe QR ordering (table QR, live orders dashboard, bill, payment) needs a backend and is a separate module.
