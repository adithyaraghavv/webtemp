# Cafe ordering and owner dashboard

One database (Supabase Postgres) behind two things: the cafe's landing page and an owner dashboard.

- Landing page (`index.html`, built by webbuild with `"ordering": true`): menu read live from the database. A plain visit is
  read-only. Opened from a table QR (`?t=<table>&k=<secret>`) it also lets guests pick options and notes, order, follow the
  bill, pay by UPI QR and (optionally) rate. Staff confirm payment by hand.
- Dashboard (`order/staff.html`, owner login): Orders (New, Preparing, Ready, Completed), Kitchen, Analytics, Menu management
  (items, categories, photos, options, availability), Tables (QR codes), Settings.

## Parts
- `webbuild/ordering_kit/supabase/001..004_*.sql`: tables, row-level security, the only functions customers can call, analytics, photo storage.
- `webbuild/ordering_kit/web/`: `site.js`/`site.css` (landing ordering layer), `staff.html`/`staff.js`, `api.js`, `qr.js` (own QR encoder), `ui.css`, `config.js`.
- `ordering/tests/`: SQL attack and rule tests, QR decoding test, full browser test.
- `ordering/dev/`: local test server (real SQL on a throwaway Postgres, mimics the Supabase endpoints), seed data, `run_e2e.sh`.

## Go live (when the Supabase project is ready)
1. `webbuild build brief.json --out site` (brief has `"ordering": true`), then
   `webbuild ordering init site --url https://<project>.supabase.co --key <publishable key>`.
2. Run `ordering-sql/001..004` in order in the Supabase SQL editor. Create the owner user (Authentication) and add the id to `public.staff`.
3. Sign in at `/order/staff.html`, fill Settings (cafe name, UPI id), add categories and items, add tables, print the QR codes.
4. Run guard and the Supabase security advisor before real customers.

## Tests
```
createdb qrunit; psql -d qrunit -f ordering/tests/boot.sql; for f in webbuild/ordering_kit/supabase/00*.sql; do psql -d qrunit -f $f; done
QR_PSQL="psql -d qrunit" python3 -m unittest ordering.tests.test_sql ordering.tests.test_qr
ordering/dev/run_e2e.sh SITE_DIR [photo.jpg] [shots_dir]    # browser test, needs Playwright
```
