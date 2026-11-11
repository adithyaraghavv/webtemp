"""Tests for the ordering SQL, run against a throwaway Postgres (never Supabase).
Set QR_PSQL to a psql command that connects as a superuser to an empty database that already has the roles
anon/authenticated and the auth.uid() stub (see ordering/tests/boot.sql). Skipped when not set."""
import os, shlex, subprocess, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SQL = HERE.parent.parent / "webbuild" / "ordering_kit" / "supabase"
PSQL = os.environ.get("QR_PSQL")


def run(script: str):
    """Run a script in one transaction that is always rolled back. Returns (ok, stdout+stderr)."""
    full = "begin;\n" + script + "\nrollback;\n"
    p = subprocess.run(shlex.split(PSQL) + ["-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1"], input=full,
                       capture_output=True, text=True)
    return p.returncode == 0, (p.stdout + p.stderr).strip()


SEED = """
insert into settings(id, cafe_name, currency, upi_id, upi_name, google_place_id) values (1,'Test Cafe','Rs ','test@upi','Test Cafe','PLACE123');
insert into menu_categories(id, name, sort) values ('c0000000-0000-0000-0000-000000000001','Coffee',1),('c0000000-0000-0000-0000-000000000002','Bakes',2);
insert into menu_items(id, category_id, name, price_paise, options) values
 ('00000000-0000-0000-0000-000000000001','c0000000-0000-0000-0000-000000000001','Filter coffee',9000,
  '[{"name":"Size","choices":[{"label":"Regular","delta_paise":0},{"label":"Large","delta_paise":2000}]},{"name":"Sugar","choices":[{"label":"Normal"},{"label":"Less sugar"}]}]'),
 ('00000000-0000-0000-0000-000000000002','c0000000-0000-0000-0000-000000000001','Cold brew',14000,'[]'),
 ('00000000-0000-0000-0000-000000000004','c0000000-0000-0000-0000-000000000001','Latte',16000,
  '[{"name":"Size","required":true,"choices":[{"label":"Small","delta_paise":-1000},{"label":"Large","delta_paise":3000}]}]');
insert into menu_items(id, category_id, name, price_paise, available) values ('00000000-0000-0000-0000-000000000003','c0000000-0000-0000-0000-000000000002','Sold out',5000,false);
insert into cafe_tables(label, secret) values ('T1','s1'),('T2','s2');
insert into staff(user_id) values ('11111111-1111-1111-1111-111111111111');
"""
ITEMS = """'[{"id":"00000000-0000-0000-0000-000000000001","qty":2},{"id":"00000000-0000-0000-0000-000000000002","qty":1}]'::jsonb"""


@unittest.skipUnless(PSQL, "set QR_PSQL to run SQL tests")
class OrderingSql(unittest.TestCase):
    STAFF = "set local role authenticated; select set_config('request.jwt.claim.sub','11111111-1111-1111-1111-111111111111', true);\n"
    OTHER = "set local role authenticated; select set_config('request.jwt.claim.sub','22222222-2222-2222-2222-222222222222', true);\n"

    def ok(self, script):
        good, out = run(SEED + script)
        self.assertTrue(good, out)
        return out

    def bad(self, script, needle=""):
        good, out = run(SEED + script)
        self.assertFalse(good, "expected an error but it succeeded: " + out)
        self.assertIn(needle, out)

    def test_order_total_uses_stored_prices(self):
        out = self.ok(f"set local role anon; select (place_order('T1','s1',{ITEMS},'no sugar'))->>'order_total_paise';")
        self.assertEqual(out.splitlines()[-1], "32000")  # 2*90 + 140 rupees, in paise

    def test_client_cannot_set_prices(self):
        items = """'[{"id":"00000000-0000-0000-0000-000000000001","qty":1,"price_paise":1,"price":1}]'::jsonb"""
        out = self.ok(f"set local role anon; select (place_order('T1','s1',{items}))->>'order_total_paise';")
        self.assertEqual(out.splitlines()[-1], "9000")

    def test_wrong_or_missing_secret(self):
        self.bad(f"set local role anon; select place_order('T1','wrong',{ITEMS});", "unknown table")
        self.bad(f"set local role anon; select place_order('T1',null,{ITEMS});", "unknown table")
        self.bad(f"set local role anon; select place_order('T9','s1',{ITEMS});", "unknown table")

    def test_bad_quantities_and_items(self):
        for q in (0, 21, -1):
            it = f"""'[{{"id":"00000000-0000-0000-0000-000000000001","qty":{q}}}]'::jsonb"""
            self.bad(f"set local role anon; select place_order('T1','s1',{it});", "bad quantity")
        self.bad("""set local role anon; select place_order('T1','s1','[{"id":"00000000-0000-0000-0000-000000000003","qty":1}]'::jsonb);""", "not available")
        self.bad("""set local role anon; select place_order('T1','s1','[{"id":"not-a-uuid","qty":1}]'::jsonb);""", "bad item")
        self.bad("set local role anon; select place_order('T1','s1','[]'::jsonb);", "between 1 and 30")
        self.bad("""set local role anon; select place_order('T1','s1','{"a":1}'::jsonb);""", "must be a list")

    def test_order_flood_is_stopped(self):
        one = """'[{"id":"00000000-0000-0000-0000-000000000001","qty":1}]'::jsonb"""
        calls = "\n".join(f"select place_order('T1','s1',{one});" for _ in range(11))
        self.bad("set local role anon;\n" + calls, "too many orders")

    def test_anon_cannot_read_private_tables(self):
        for t in ("bills", "orders", "order_items", "cafe_tables", "settings", "staff"):
            self.bad(f"set local role anon; select * from {t};", "permission denied")
        self.bad("set local role anon; insert into menu_items(category_id,name,price_paise) values ('c0000000-0000-0000-0000-000000000001','y',1);", "permission denied")
        self.bad("set local role anon; update menu_items set price_paise = 1;", "permission denied")
        self.bad("set local role anon; insert into orders(bill_id) values (gen_random_uuid());", "permission denied")

    def test_anon_sees_the_menu_including_sold_out_and_public_cafe_info(self):
        out = self.ok("set local role anon; select count(*) from menu_items;")
        self.assertEqual(out.splitlines()[-1], "4")
        out = self.ok("set local role anon; select available from menu_items where name = 'Sold out';")
        self.assertEqual(out.splitlines()[-1], "f")
        out = self.ok("set local role anon; select get_cafe();")
        self.assertIn("Test Cafe", out)
        self.assertIn("PLACE123", out)
        self.assertNotIn("test@upi", out)  # the UPI id is not public until a bill is requested

    def test_bill_token_is_needed_and_isolated(self):
        one = """'[{"id":"00000000-0000-0000-0000-000000000001","qty":1}]'::jsonb"""
        out = self.ok(f"""set local role anon;
          select set_config('t.a', (place_order('T1','s1',{ITEMS}))->>'bill_token', false);
          select place_order('T2','s2',{one});
          select (get_bill(current_setting('t.a')))->>'total_paise';
          select count(*) from (select get_bill('deadbeef') g) q where g is not null;""").splitlines()
        self.assertEqual(out[-2], "32000")  # T1's bill only; T2's order is not mixed in
        self.assertEqual(out[-1], "0")      # an unknown token returns nothing

    def test_bill_flow_rating_and_payment(self):
        flow = f"""
        set local role anon;
        select set_config('t.tok', (place_order('T1','s1',{ITEMS}))->>'bill_token', false);
        select (get_bill(current_setting('t.tok')))->>'total_paise';
        select (request_bill(current_setting('t.tok')))->>'upi_id';
        select (request_bill(current_setting('t.tok')))->>'total_paise';
        select submit_rating(current_setting('t.tok'), 5, 'great');
        """
        out = self.ok(flow).splitlines()
        self.assertIn("32000", out)
        self.assertIn("test@upi", out)
        # rating only once
        self.bad(flow + f"select submit_rating(current_setting('t.tok'), 4);", "already rated")

    def test_rating_before_bill_and_bad_stars(self):
        pre = f"set local role anon; select set_config('t.tok', (place_order('T1','s1',{ITEMS}))->>'bill_token', false);\n"
        self.bad(pre + "select submit_rating(current_setting('t.tok'), 5);", "ask for the bill first")
        self.bad(pre + "select request_bill(current_setting('t.tok')); select submit_rating(current_setting('t.tok'), 6);", "1 to 5")

    def test_no_new_orders_while_bill_is_being_settled(self):
        self.bad(f"""set local role anon;
          select set_config('t.tok', (place_order('T1','s1',{ITEMS}))->>'bill_token', false);
          select request_bill(current_setting('t.tok'));
          select place_order('T1','s1',{ITEMS});""", "being settled")

    def test_request_bill_needs_something_to_pay(self):
        self.bad("set local role anon; select request_bill('nope');", "unknown bill")

    def test_two_tables_have_separate_bills(self):
        out = self.ok(f"""set local role anon;
          select (place_order('T1','s1',{ITEMS}))->>'bill_token' <> (place_order('T2','s2',{ITEMS}))->>'bill_token';""")
        self.assertEqual(out.splitlines()[-1], "t")

    def test_staff_rules(self):
        place = f"set local role anon; select place_order('T1','s1',{ITEMS});\nreset role;\n"
        staff = "set local role authenticated; select set_config('request.jwt.claim.sub','11111111-1111-1111-1111-111111111111', true);\n"
        other = "set local role authenticated; select set_config('request.jwt.claim.sub','22222222-2222-2222-2222-222222222222', true);\n"
        out = self.ok(place + staff + "select count(*) from staff_orders;")
        self.assertEqual(out.splitlines()[-1], "1")
        out = self.ok(place + other + "select count(*) from staff_orders;")
        self.assertEqual(out.splitlines()[-1], "0")  # logged in but not staff sees nothing
        # staff can change status only
        self.ok(place + staff + "update orders set status='preparing';")
        self.bad(place + staff + "update orders set bill_id = gen_random_uuid();", "permission denied")
        self.bad(place + staff + "delete from orders;", "permission denied")
        # anon cannot mark paid; non-staff cannot either
        self.bad(place + "set local role anon; select mark_paid(gen_random_uuid());", "permission denied")
        self.bad(place + other + "select mark_paid(gen_random_uuid());", "not allowed")
        out = self.ok(place + "reset role;\nselect id::text into temp b from bills;\n" + staff +
                      "select mark_paid((select id from public.bills limit 1))->>'status';")
        self.assertEqual(out.splitlines()[-1], "paid")

    def test_after_payment_table_can_start_a_new_bill(self):
        staff = "set local role authenticated; select set_config('request.jwt.claim.sub','11111111-1111-1111-1111-111111111111', true);\n"
        out = self.ok(f"""set local role anon; select place_order('T1','s1',{ITEMS});
          reset role;
          {staff}
          select mark_paid((select id from public.bills limit 1));
          reset role; set local role anon;
          select (place_order('T1','s1',{ITEMS}))->>'order_total_paise';""")
        self.assertEqual(out.splitlines()[-1], "32000")

    # ---- options, notes, customer details
    def test_option_prices_come_from_the_menu(self):
        it = """'[{"id":"00000000-0000-0000-0000-000000000001","qty":2,"options":{"Size":"Large","Sugar":"Less sugar"},"note":"extra hot","price_paise":1}]'::jsonb"""
        out = self.ok(f"set local role anon; select (place_order('T1','s1',{it}))->>'order_total_paise';")
        self.assertEqual(out.splitlines()[-1], "22000")  # (90 + 20) * 2 rupees

    def test_required_option_and_bad_options(self):
        lat = lambda o: f"""'[{{"id":"00000000-0000-0000-0000-000000000004","qty":1,"options":{o}}}]'::jsonb"""
        self.bad(f"set local role anon; select place_order('T1','s1',{lat('{}')});", "missing option")
        self.bad(f"set local role anon; select place_order('T1','s1',{lat(chr(123) + chr(34) + 'Size' + chr(34) + ':' + chr(34) + 'Huge' + chr(34) + chr(125))});", "bad option")
        self.bad(f"set local role anon; select place_order('T1','s1',{lat(chr(123) + chr(34) + 'Flavour' + chr(34) + ':' + chr(34) + 'x' + chr(34) + chr(125))});", "bad option")
        self.bad("""set local role anon; select place_order('T1','s1','[{"id":"00000000-0000-0000-0000-000000000002","qty":1,"options":{"Size":"Large"}}]'::jsonb);""", "bad option")
        self.bad(f"set local role anon; select place_order('T1','s1',{lat('[1]')});", "bad options")
        out = self.ok(f"set local role anon; select (place_order('T1','s1',{lat(chr(123) + chr(34) + 'Size' + chr(34) + ':' + chr(34) + 'Small' + chr(34) + chr(125))}))->>'order_total_paise';")
        self.assertEqual(out.splitlines()[-1], "15000")  # a negative price change is allowed

    def test_customer_name_phone_and_notes_are_validated_and_kept(self):
        place = f"set local role anon; select place_order('T1','s1',{ITEMS},'note', 'Asha', '+91 98765 43210');\nreset role;\n"
        out = self.ok(place + "select customer_name || '|' || customer_phone || '|' || note from orders;")
        self.assertEqual(out.splitlines()[-1], "Asha|+91 98765 43210|note")
        self.bad(f"set local role anon; select place_order('T1','s1',{ITEMS},null,'x','abc');", "bad phone")
        self.bad(f"set local role anon; select place_order('T1','s1',{ITEMS},null,'x','12345');", "bad phone")

    def test_item_note_and_options_are_stored_on_the_line(self):
        it = """'[{"id":"00000000-0000-0000-0000-000000000001","qty":1,"options":{"Size":"Large"},"note":"less ice"}]'::jsonb"""
        out = self.ok(f"set local role anon; select place_order('T1','s1',{it});\nreset role;\nselect note || '|' || (options->0->>'choice') || '|' || price_paise from order_items;")
        self.assertEqual(out.splitlines()[-1], "less ice|Large|11000")

    # ---- status flow
    def test_status_flow_is_enforced(self):
        place = f"set local role anon; select place_order('T1','s1',{ITEMS});\nreset role;\n" + self.STAFF
        for steps in (["preparing", "ready", "completed"], ["preparing", "cancelled"], ["cancelled"]):
            self.ok(place + "\n".join(f"update orders set status='{x}';" for x in steps))
        self.bad(place + "update orders set status='ready';", "invalid status change")
        self.bad(place + "update orders set status='completed';", "invalid status change")
        self.bad(place + "update orders set status='preparing'; update orders set status='new';", "invalid status change")
        self.bad(place + "update orders set status='cancelled'; update orders set status='preparing';", "invalid status change")
        self.bad(place + "update orders set status='whatever';", "invalid status change")

    # ---- menu management
    def test_menu_management_is_staff_only(self):
        for role in ("set local role anon;", self.OTHER):
            self.bad(role + "insert into menu_categories(name) values ('Hack');", "permission denied" if "anon" in role else "row-level security")
        self.ok(self.STAFF + "insert into menu_categories(name) values ('Tea');")
        self.ok(self.STAFF + "update menu_items set price_paise = 9500, available = false where name = 'Cold brew';")
        self.ok(self.STAFF + "delete from menu_items where name = 'Cold brew';")
        out = self.ok("set local role anon; select count(*) from menu_categories;")
        self.assertEqual(out.splitlines()[-1], "2")
        # a non-staff signed-in user changes nothing (RLS filters the rows)
        out = self.ok(self.OTHER + "update menu_items set price_paise = 1; select count(*) from menu_items where price_paise = 1;")
        self.assertEqual(out.splitlines()[-1], "0")

    def test_deleting_an_item_keeps_past_orders(self):
        out = self.ok(f"set local role anon; select place_order('T1','s1',{ITEMS});\nreset role;\n" + self.STAFF +
                      "delete from menu_items where name = 'Cold brew';\nreset role;\nselect count(*) from order_items where name = 'Cold brew' and menu_item_id is null;")
        self.assertEqual(out.splitlines()[-1], "1")

    def test_category_with_items_cannot_be_deleted(self):
        self.bad(self.STAFF + "delete from menu_categories where name = 'Coffee';", "violates foreign key")

    def test_bad_option_definitions_are_rejected(self):
        cat = "(select id from menu_categories limit 1)"
        def ins(opts):
            return self.STAFF + f"insert into menu_items(category_id, name, price_paise, options) values ({cat}, 'x', 1, '{opts}'::jsonb);"
        self.ok(ins('[{"name":"Size","choices":[{"label":"S","delta_paise":0}]}]'))
        self.bad(ins('{"a":1}'), "options must be a list")
        self.bad(ins('[{"name":"","choices":[{"label":"S"}]}]'), "bad option group name")
        self.bad(ins('[{"name":"A","choices":[]}]'), "1 to 10 choices")
        self.bad(ins('[{"name":"A","choices":[{"label":"S"},{"label":"S"}]}]'), "duplicate choice")
        self.bad(ins('[{"name":"A","choices":[{"label":"S"}]},{"name":"A","choices":[{"label":"S"}]}]'), "duplicate option group")
        self.bad(ins('[{"name":"A","choices":[{"label":"S","delta_paise":1.5}]}]'), "bad price change")
        self.bad(ins('[{"name":"A","choices":[{"label":"S","delta_paise":"1"}]}]'), "bad price change")

    # ---- analytics
    def test_analytics_numbers_and_permissions(self):
        orders = (f"set local role anon; select place_order('T1','s1',{ITEMS});\n"          # 320
                  f"""select place_order('T2','s2','[{{"id":"00000000-0000-0000-0000-000000000002","qty":3}}]'::jsonb);\n"""  # 420
                  "reset role;\n")
        q = "select analytics(now() - interval '1 day', now() + interval '1 day', 'day')"
        out = self.ok(orders + self.STAFF + f"select ({q})->'overview'->>'revenue_paise';")
        self.assertEqual(out.splitlines()[-1], "74000")
        out = self.ok(orders + self.STAFF + f"select ({q})->'overview'->>'orders';")
        self.assertEqual(out.splitlines()[-1], "2")
        out = self.ok(orders + self.STAFF + f"select ({q})->'overview'->>'avg_order_paise';")
        self.assertEqual(out.splitlines()[-1], "37000")
        out = self.ok(orders + self.STAFF + f"select ({q})->'top'->0->>'name' || '|' || (({q})->'top'->0->>'qty');")
        self.assertEqual(out.splitlines()[-1], "Cold brew|4")  # 4 cold brews (1 + 3) beat 2 filter coffees
        out = self.ok(orders + self.STAFF + f"select ({q})->'least'->0->>'name';")
        self.assertEqual(out.splitlines()[-1], "Latte")        # never ordered, available
        out = self.ok(orders + self.STAFF + f"select jsonb_array_length(({q})->'hours');")
        self.assertEqual(out.splitlines()[-1], "24")
        out = self.ok(orders + self.STAFF + f"select sum((x->>'orders')::int) from jsonb_array_elements(({q})->'series') x;")
        self.assertEqual(out.splitlines()[-1], "2")
        # cancelled orders do not count
        out = self.ok(orders + self.STAFF + "update orders set status = 'cancelled' where id = (select id from orders order by created_at limit 1);\n"
                      f"select ({q})->'overview'->>'orders';")
        self.assertEqual(out.splitlines()[-1], "1")
        for who in ("set local role anon;", self.OTHER):
            self.bad(orders + who + f"{q};", "permission denied" if "anon" in who else "not allowed")
        self.bad(orders + self.STAFF + "select analytics(now(), now() - interval '1 day', 'day');", "bad range")
        self.bad(orders + self.STAFF + "select analytics(now() - interval '1 day', now(), 'year');", "bucket must be")

    def test_analytics_weeks_and_months_run(self):
        for b in ("week", "month"):
            self.ok(self.STAFF + f"select analytics(now() - interval '90 days', now() + interval '1 day', '{b}');")

    def test_storage_policies_exist_and_only_staff_write(self):
        out = self.ok("select count(*) from pg_policies where schemaname = 'storage' and policyname like 'menu_images_staff_%';")
        self.assertEqual(out.splitlines()[-1], "3")


if __name__ == "__main__":
    unittest.main()
