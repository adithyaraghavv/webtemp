# QR table ordering (module for webbuild sites)

Customer scans the QR on a table, picks items, sends the order. Staff see it live, mark it served. The customer asks
for the bill, optionally rates the visit (Skip is always there), then pays by UPI QR. Staff confirm the payment.

No libraries and no build step: plain HTML and JS, our own QR encoder (`ordering_kit/web/qr.js`), `fetch` for the Supabase REST API.

## Parts
- `webbuild/ordering_kit/supabase/001_schema.sql`, `002_bill_rating_staff.sql`: tables, row-level security and the only functions customers can call.
- `webbuild/ordering_kit/web/`: `order.html` customer page, `staff.html` kitchen and bills, `tables.html` printable table QR codes.
- `config.js`: Supabase URL and the publishable key (never the service key).
- `dev/`: local test server and seed data. It runs the real SQL against a throwaway local Postgres, never Supabase.
- `tests/`: SQL tests (attacks included), QR encoder test, browser test of the whole flow.

## Rules the database enforces
- Customers cannot read or write any table. They call `place_order`, `get_bill`, `request_bill`, `submit_rating`, `get_cafe`.
- A table is identified by its label and a secret in the QR. Wrong secret, no order.
- Prices come from `menu_items`, never from the phone. Quantity 1 to 20, up to 30 lines, 10 orders per bill per 10 minutes.
- A bill is found only by its random token. The UPI id is released only after a bill is requested.
- Staff are users listed in `public.staff`. Being signed in is not enough. Staff can change an order's status, nothing else.
- Payment is confirmed by a person (`mark_paid`). Nothing here confirms a UPI payment automatically.

## Setting up a cafe (when a Supabase project is available)
1. New Supabase project for the cafe. Run the two SQL files in order.
2. Insert one `settings` row (`id = 1`), menu items, tables. Create a staff user in Supabase Auth, then insert their id into `public.staff`.
3. Put the URL and publishable key in `config.js`. Sign in at `staff.html`, open `tables.html`, print the codes.
4. Run guard against it before real use.

## Local test
```
createdb qrunit; psql -d qrunit -f ordering/tests/boot.sql; psql -d qrunit -f webbuild/ordering_kit/supabase/001_schema.sql; psql -d qrunit -f webbuild/ordering_kit/supabase/002_bill_rating_staff.sql
QR_PSQL="psql -d qrunit" python3 -m unittest tests.test_sql tests.test_qr
```
For the browser test use a second database with `dev/seed.sql` and `python3 dev/mock_server.py 8780`, then `python3 tests/e2e_browser.py`.

## Known limits (v1)
- Not yet applied to a real Supabase project; tested locally only. Supabase's own security advisor has not been run.
- The orders list refreshes every 4 seconds (polling), not Realtime.
- After the bill is requested, the table cannot add orders until staff mark it paid.
- Menu and table edits are done in the Supabase dashboard; there is no admin screen yet.
- The table secret is fixed per table; change the row to rotate it.
- If the phone is closed mid-meal the customer re-scans and sees a new bill; staff can still see the old one.
- Google review link is shown to everyone after payment, never filtered by rating.

## Using it from a site
`webbuild ordering init site --url https://<project>.supabase.co --key <publishable key>` copies the pages into `site/order/`
and the SQL into `../ordering-sql/` (outside the site, so it is never published). Secret keys are refused.
