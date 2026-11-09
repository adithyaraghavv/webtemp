"""Tests for the ordering SQL, run against a throwaway Postgres (never Supabase).
Set QR_PSQL to a psql command that connects as a superuser to an empty database that already has the roles
anon/authenticated and the auth.uid() stub (see ordering/tests/boot.sql). Skipped when not set."""
import os, shlex, subprocess, unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
SQL = HERE.parent / "supabase"
PSQL = os.environ.get("QR_PSQL")


def run(script: str):
    """Run a script in one transaction that is always rolled back. Returns (ok, stdout+stderr)."""
    full = "begin;\n" + script + "\nrollback;\n"
    p = subprocess.run(shlex.split(PSQL) + ["-X", "-q", "-A", "-t", "-v", "ON_ERROR_STOP=1"], input=full,
                       capture_output=True, text=True)
    return p.returncode == 0, (p.stdout + p.stderr).strip()


SEED = """
insert into settings(id, cafe_name, currency, upi_id, upi_name, google_place_id) values (1,'Test Cafe','Rs ','test@upi','Test Cafe','PLACE123');
insert into menu_items(id, category, name, price_paise) values
 ('00000000-0000-0000-0000-000000000001','Coffee','Filter coffee',9000),
 ('00000000-0000-0000-0000-000000000002','Coffee','Cold brew',14000);
insert into menu_items(id, category, name, price_paise, available) values ('00000000-0000-0000-0000-000000000003','Bakes','Sold out',5000,false);
insert into cafe_tables(label, secret) values ('T1','s1'),('T2','s2');
insert into staff(user_id) values ('11111111-1111-1111-1111-111111111111');
"""
ITEMS = """'[{"id":"00000000-0000-0000-0000-000000000001","qty":2},{"id":"00000000-0000-0000-0000-000000000002","qty":1}]'::jsonb"""


@unittest.skipUnless(PSQL, "set QR_PSQL to run SQL tests")
class OrderingSql(unittest.TestCase):
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
        self.bad("set local role anon; insert into menu_items(category,name,price_paise) values ('x','y',1);", "permission denied")
        self.bad("set local role anon; update menu_items set price_paise = 1;", "permission denied")
        self.bad("set local role anon; insert into orders(bill_id) values (gen_random_uuid());", "permission denied")

    def test_anon_sees_only_available_menu_and_public_cafe_info(self):
        out = self.ok("set local role anon; select count(*) from menu_items;")
        self.assertEqual(out.splitlines()[-1], "2")
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


if __name__ == "__main__":
    unittest.main()
