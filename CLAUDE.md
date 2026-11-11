# Project handoff: cafe-site-kit (webbuild)

Owner: Adi (solo founder, Bengaluru). Repo: github.com/adithyaraghavv/cafe-site-kit (main). Older copy: webtemp.

## What this is
`webbuild` is a reusable kit that generates a premium, non-"AI-looking" static website for a cafe or restaurant, plus table-QR ordering
and an owner dashboard. Each client gets their own generated site, their own Supabase project and their own owner login.
The cafe "Brew House" is only a demo with placeholder art.

## Standing rules from Adi (follow these)
- Do not install anything, and do not clone or run third-party code, without his explicit approval first. Reading is fine.
- Supabase actions are ON HOLD (free plan limit of 2 projects). Build and test on the local Postgres only. Never create or change a Supabase project without his explicit yes.
- Never apply database migrations or push to GitHub as part of a guard check unless he asks.
- Design must not look AI-made: run `webbuild lint`; keep one design direction per site.
- Plain-English summaries for him; he is not reading code line by line.

## Layout
- `webbuild/` Python package (stdlib only): `site.py` (render), `restaurant.py` (restaurant template), `lint.py`, `theme.py`, `ordering.py`, `cli.py`, `assets.py` (the /webbuild command text), `frames.py` (video to scroll-hero frames, needs ffmpeg).
- `webbuild/ordering_kit/web/`: `site.js` + `site.css` (customer ordering on the landing page, active only with `?t=<table>&k=<secret>`), `staff.html` + `staff.js` (owner dashboard: Orders, Kitchen, Analytics, Menu, Tables, Settings), `api.js`, `qr.js` (own QR encoder), `ui.css`, `config.js` (URL + PUBLISHABLE key only).
- `webbuild/ordering_kit/supabase/001..004_*.sql`: schema + RLS, bills/ratings/staff, analytics, storage. Prices and totals are computed server-side. Customers (anon) can only read the menu and call SECURITY DEFINER functions.
- `ordering/dev/`: local test server `mock_server.py` (mimics the Supabase endpoints, runs the real SQL on a throwaway Postgres), `seed.sql`, `run_e2e.sh`.
- `ordering/tests/`: `test_sql.py` (security and rule tests), `test_qr.py`, `e2e_browser.py` (Playwright end-to-end).
- `tests/test_webbuild.py`: unit tests.

## Commands
- `python3 -m unittest discover -s tests` (31 tests)
- SQL tests need Postgres 16: see `ordering/README.md`.
- `ordering/dev/run_e2e.sh SITE_DIR [photo.jpg] [shots_dir]` rebuilds a throwaway DB, starts the mock server and runs the browser test (needs Playwright, Postgres, Linux-style shell).
- `webbuild build brief.json --out site`, then `webbuild ordering init site --url ... --key <publishable key>`.
- `webbuild theme photo1.jpg photo2.jpg` prints a theme block from the cafe's own photos.

## State on 2026-11-11 (v0.5.0)
Done and proven locally: landing page (Hero, About, Menu, Gallery, Location/Hours, Contact), live menu from the database, table-QR-only ordering with options and notes, bill, UPI QR payment confirmed manually by staff, optional rating, Google review link; dashboard with all tabs; analytics from real test orders. The browser test passes: a test order shows in the dashboard, a menu edit shows on the site, analytics numbers match.
Guard (`guard scan --no-live`): 2 HIGH findings, both false positives (public menu read policies are intentional).

## Not done / next
- Real Supabase not tried; needs a free slot (upgrade or pause a project). Then run the SQL files in order, create the owner user, add to `public.staff`, run guard and the Supabase security advisor.
- Real cafe photos and walk-in video: run `webbuild theme` on the photos, build the fly-through hero from the video. Compare the layout and motion against the El Chavocho reference recording (only partly checked so far).
- Hero scroll smoothness on a real phone is unverified. Fonts Anton and Barlow looked right on Adi's machine but never loaded in the cloud sandbox.
- Adi wants to run it locally with `npm run dev`; the repo is Python plus static files today, so a dev wrapper is still to be decided.
- Add `# refresh N` and `pip install --upgrade git+https://github.com/adithyaraghavv/cafe-site-kit.git && webbuild setup` to his Claude environment setup script (he does this himself).
