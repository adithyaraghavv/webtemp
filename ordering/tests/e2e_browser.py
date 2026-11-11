"""End-to-end browser test: landing page + owner dashboard + one database, against dev/mock_server.py.
Setup (see ordering/README.md): build a site with ordering: true, run `webbuild ordering init SITE --url http://127.0.0.1:8780 --key sb_publishable_x`,
start the mock server with QR_SITE=SITE and QR_PSQL pointing at a seeded throwaway DB, then run:
  OUT=shots python3 ordering/tests/e2e_browser.py
Needs Playwright."""
import json, os, re, sys, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

B = os.environ.get("BASE", "http://127.0.0.1:8780"); OUT = Path(os.environ.get("OUT", ".")); OUT.mkdir(parents=True, exist_ok=True)
PHOTO = os.environ.get("PHOTO", "")  # a jpg to upload as a new item photo
bad = 0
badhttp = []
def check(name, cond, extra=""):
    global bad; bad += 0 if cond else 1; print(("PASS " if cond else "FAIL ") + name, extra)
def api(path, body=None, token=None):
    req = urllib.request.Request(B + path, data=json.dumps(body).encode() if body is not None else None, headers={"Content-Type": "application/json", "apikey": "x", "Authorization": "Bearer " + (token or "x")})
    return json.loads(urllib.request.urlopen(req).read() or b"null")

with sync_playwright() as p:
    br = p.chromium.launch(); errs = []
    def watch(pg):
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("response", lambda r: badhttp.append((r.status, r.url)) if r.status >= 400 else None)
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" and "ERR_" not in m.text and "fonts" not in m.text and "Failed to load resource" not in m.text else None)
    mob = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)

    # 1. plain visit: everything visible, menu from the database, no ordering controls
    pub = mob.new_page(); watch(pub); pub.goto(B + "/"); pub.wait_for_selector(".o-note"); pub.wait_for_timeout(300)
    txt = pub.inner_text("body")
    check("plain visit shows live menu", pub.locator("#menu-live .mrow").count() == 4 and "Filter coffee" in txt, str(pub.locator("#menu-live .mrow").count()))
    check("plain visit is read-only (no Add buttons, scan hint)", pub.locator(".o-add").count() == 0 and "scan the qr" in txt.lower(), repr(txt[:200]))
    for sec in ("about", "menu", "gallery", "visit", "contact"):
        check("section #" + sec + " present", pub.locator("#" + sec).count() == 1)
    pub.screenshot(path=str(OUT / "01_plain_menu.png"), full_page=False)

    # 2. wrong table secret is refused
    bd = mob.new_page(); watch(bd); bd.goto(B + "/?t=T1&k=wrong"); bd.wait_for_selector(".o-add")
    bd.get_by_role("button", name="Add Banana bread").click(); bd.get_by_role("button", name=re.compile("^Add 1")).click()
    bd.get_by_role("button", name="View order").click(); bd.fill("#cn", "Mallory"); bd.get_by_role("button", name="Send order").click(); bd.wait_for_timeout(800)
    check("wrong table secret refused", "not valid" in bd.inner_text("dialog"))

    # 3. real table QR: options and notes, then send
    c = mob.new_page(); watch(c); c.goto(B + "/?t=T1&k=demo-secret-t1"); c.wait_for_selector(".o-add")
    check("table QR shows Table T1 chip and Add buttons", "Table T1" in c.inner_text(".o-bar") and c.locator(".o-add").count() == 4)
    c.get_by_role("button", name="Add Filter coffee").click()
    c.get_by_label("Large").check(); c.get_by_label("Less sugar").check(); c.fill("#on", "extra hot please")
    for _ in range(1): c.get_by_role("button", name="More").click()
    c.screenshot(path=str(OUT / "02_item_sheet.png"))
    c.get_by_role("button", name=re.compile("^Add 2")).click()
    c.get_by_role("button", name="Add Cold brew").click()
    c.get_by_role("button", name=re.compile("^Add 1")).click()
    check("required-choice rule is not enforced for optional groups; bar totals Rs 360", "Rs 360" in c.inner_text(".o-bar"), c.inner_text(".o-bar"))
    c.get_by_role("button", name="View order").click(); c.fill("#cn", "Priya"); c.fill("#cp", "9876501234"); c.fill("#co", "bring together")
    c.screenshot(path=str(OUT / "03_cart.png"))
    c.get_by_role("button", name="Send order").click(); c.wait_for_selector("text=Order sent"); c.wait_for_selector("dialog .o-line")
    dt = c.inner_text("dialog")
    check("bill shows lines, options, note and total", "2 × Filter coffee" in dt and "Size: Large" in dt and "extra hot please" in dt and "Rs 360" in dt, repr(dt))
    c.screenshot(path=str(OUT / "04_bill.png"))
    c.get_by_role("button", name="Order more").click()

    # more orders straight to the database as other tables (for analytics)
    items = {i["name"]: i["id"] for i in api("/rest/v1/menu_items?select=id,name")}
    api("/rest/v1/rpc/place_order", {"p_table": "T2", "p_secret": "demo-secret-t2", "p_name": "Ravi", "p_items": [{"id": items["Masala chai"], "qty": 2, "options": {"Sugar": "No sugar"}}]})
    api("/rest/v1/rpc/place_order", {"p_table": "T3", "p_secret": "demo-secret-t3", "p_name": "Sam", "p_items": [{"id": items["Banana bread"], "qty": 1}]})

    # 4. owner dashboard
    sc = br.new_context(viewport={"width": 1280, "height": 900}); s = sc.new_page(); watch(s)
    s.goto(B + "/order/staff.html"); check("dashboard asks for sign in", "owner sign in" in s.inner_text("#app").lower())
    s.fill("#em", "staff@test.cafe"); s.fill("#pw", "nope"); s.get_by_role("button", name="Sign in").click(); s.wait_for_timeout(600)
    check("bad password refused", "Sign in failed" in s.inner_text("#app"))
    s.fill("#em", "staff@test.cafe"); s.fill("#pw", "test-pass"); s.get_by_role("button", name="Sign in").click(); s.wait_for_selector(".ord")
    st = s.inner_text("#view")
    check("test order appears in dashboard with customer, items, options and notes",
          all(x in st for x in ("Table T1", "Priya", "9876501234", "2 × Filter coffee", "Size: Large", "Sugar: Less sugar", "extra hot please", "bring together", "1 × Cold brew")), st[:400])
    check("other tables' orders appear too", "Table T2" in st and "Table T3" in st)
    s.screenshot(path=str(OUT / "05_dash_orders.png"))
    s.locator(".ord", has_text="Table T1").get_by_role("button", name="Start preparing").click(); s.wait_for_selector(".ord.preparing")
    s.get_by_role("link", name="Kitchen").click(); s.wait_for_selector(".kitchen .ord")
    check("kitchen view lists the order being prepared with notes", "extra hot please" in s.inner_text(".kitchen"))
    s.screenshot(path=str(OUT / "06_dash_kitchen.png"))
    s.get_by_role("button", name="Mark ready").click(); s.wait_for_timeout(700)
    c.get_by_role("button", name="My bill").click(); c.wait_for_timeout(300); c.wait_for_selector(".o-st.ready")
    check("customer sees status change to Ready", "Ready" in c.inner_text("dialog")); c.get_by_role("button", name="Order more").click()
    s.get_by_role("link", name="Orders").click(); s.wait_for_selector(".ord.ready"); s.locator(".ord.ready").get_by_role("button", name="Complete").click(); s.wait_for_timeout(700)
    check("completed order moves to Completed list", "table t1" in s.inner_text("#view").lower().split("completed recently")[1])
    # cancel T3
    s.locator(".ord", has_text="Table T3").get_by_role("button", name="Cancel").click(); s.get_by_role("button", name="Cancel order").click(); s.wait_for_timeout(700)
    check("cancelled order leaves the board", "table t3" not in s.inner_text("#view").lower().split("bills waiting")[0])
    # customer asks for the bill, skips the rating, sees UPI, staff confirms payment
    c.get_by_role("button", name="My bill").click(); c.get_by_role("button", name="Ask for the bill").click(); c.wait_for_selector("text=Pay your bill")
    href = c.locator("a:has-text('Open UPI app')").get_attribute("href")
    check("UPI link has exact amount and id", "pa=test.cafe%40upi" in href and "am=360.00" in href and "cu=INR" in href, href)
    c.screenshot(path=str(OUT / "07_pay.png")); c.get_by_role("button", name="Skip").click()
    s.get_by_role("link", name="Orders").click(); s.reload(); s.wait_for_selector("text=/bills waiting/i"); s.get_by_role("button", name="Payment received").first.click(); s.get_by_role("button", name="Payment received").last.click(); s.wait_for_timeout(900)
    c.wait_for_selector("text=Payment received. Thank you", timeout=9000); check("customer sees thanks after staff confirms payment", True)

    # 5. menu edits in dashboard show on the site
    s.get_by_role("link", name="Menu").click(); s.wait_for_selector(".mrowx")
    s.screenshot(path=str(OUT / "08_dash_menu.png"))
    s.locator(".mrowx", has_text="Banana bread").get_by_role("button", name="Edit").click(); s.fill("#ip", "150"); s.fill("#id", "Baked at dawn"); s.get_by_role("button", name="Save").click(); s.wait_for_timeout(700)
    s.locator(".mrowx", has_text="Masala chai").get_by_label("Available").uncheck(); s.wait_for_timeout(500)
    s.get_by_role("button", name="Add item").click(); s.fill("#in", "Walnut brownie"); s.fill("#ip", "130"); s.select_option("#ic", label="Bakes"); s.fill("#id", "Dense and a bit gooey")
    if PHOTO: s.set_input_files("#if", PHOTO)
    s.get_by_role("button", name="Add option group (size, sugar…)").click(); s.get_by_placeholder("Group name, e.g. Size").fill("Extras"); s.get_by_placeholder("Choice, e.g. Large").fill("Ice cream"); s.get_by_placeholder("Price change, e.g. 20").fill("30")
    s.screenshot(path=str(OUT / "09_dash_item_dialog.png")); s.get_by_role("button", name="Save").click(); s.wait_for_selector("text=Walnut brownie")
    s.get_by_role("button", name="Add category").click(); s.fill("#cn", "Cold drinks"); s.get_by_role("button", name="Save").click(); s.wait_for_selector("h2:has-text('Cold drinks')")
    pub.reload(); pub.wait_for_selector("#menu-live .mrow"); pub.wait_for_timeout(400)
    ptxt = pub.inner_text("#menu-live")
    check("site shows edited price and description", "Rs 150" in ptxt and "Baked at dawn" in ptxt)
    check("site shows the new item", "Walnut brownie" in ptxt and "Dense and a bit gooey" in ptxt)
    check("site marks the sold-out item", pub.locator(".mrow.sold", has_text="Masala chai").count() == 1)
    if PHOTO: check("new item photo is served", pub.locator("img[src*='/storage/v1/object/public/menu/']").count() >= 1)
    check("empty category not shown to customers", "Cold drinks" not in ptxt)
    c.reload(); c.wait_for_selector(".o-add"); c.get_by_role("button", name="Add Walnut brownie").click()
    check("new item option is orderable", c.get_by_label("Ice cream").count() == 1); c.screenshot(path=str(OUT / "10_new_item_sheet.png")); c.get_by_role("button", name="Cancel").click()

    # 6. analytics from the real test orders
    s.get_by_role("link", name="Analytics").click(); s.wait_for_selector(".kpis"); s.wait_for_timeout(300)
    k = s.inner_text(".kpis")
    check("analytics: revenue Rs 480 (cancelled order excluded)", "Rs 480" in k, k)
    check("analytics: 2 orders, average Rs 240, paid Rs 360", re.search(r"Orders\s*2\b", k) and "Rs 240" in k and "Rs 360" in k, k)
    a = s.inner_text("#view")
    check("analytics: top sellers and busiest hours present", "top sellers" in a.lower() and "Filter coffee" in a and "busiest hours" in a.lower())
    s.get_by_role("button", name="Weekly").click(); s.wait_for_timeout(600); s.get_by_role("button", name="Monthly").click(); s.wait_for_timeout(600)
    check("monthly view shows same revenue", "Rs 480" in s.inner_text(".kpis"))
    s.get_by_role("button", name="Daily").click(); s.wait_for_timeout(500); s.screenshot(path=str(OUT / "11_dash_analytics.png"), full_page=True)

    # 7. tables and settings
    s.get_by_role("link", name="Tables").click(); s.wait_for_selector(".qr svg"); check("table QR codes drawn", s.locator(".qr svg").count() == 3)
    s.screenshot(path=str(OUT / "12_dash_tables.png"))
    s.get_by_role("link", name="Settings").click(); s.wait_for_selector("#s-cafe_name"); s.screenshot(path=str(OUT / "13_dash_settings.png"))

    # 8. a non-staff login sees no data
    oc = br.new_context(); o = oc.new_page(); o.goto(B + "/order/staff.html"); o.fill("#em", "other@test.cafe"); o.fill("#pw", "test-pass"); o.get_by_role("button", name="Sign in").click(); o.wait_for_timeout(1500)
    check("non-staff user sees no orders", "Table T1" not in o.inner_text("body"))
    unexpected = [x for x in badhttp if not (x[0] == 400 and ("place_order" in x[1] or "grant_type=password" in x[1]))]
    check("no browser errors or unexpected HTTP failures on any page", not errs and not unexpected, str(errs[:3]) + str(unexpected[:3]))
    br.close()
print("FAILED: %d" % bad if bad else "ALL PASSED"); sys.exit(1 if bad else 0)
