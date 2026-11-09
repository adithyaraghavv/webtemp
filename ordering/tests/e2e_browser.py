"""Browser test of the whole flow against the local test server (dev/mock_server.py) on port 8780 with the seed data.
Needs Playwright. Run: QR_PSQL=... python3 dev/mock_server.py 8780 &  then  python3 tests/e2e_browser.py"""
import re, sys
from playwright.sync_api import sync_playwright
B = "http://localhost:8780"
log = []
def check(name, cond, extra=""):
    log.append((name, bool(cond))); print(("PASS " if cond else "FAIL ") + name, extra)

with sync_playwright() as p:
    br = p.chromium.launch()
    ctx_c = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
    cust = ctx_c.new_page()
    errs = []
    cust.on("pageerror", lambda e: errs.append(str(e)))
    cust.on("console", lambda m: errs.append(m.text) if m.type == "error" and "ERR_TUNNEL" not in m.text and "fonts" not in m.text else None)
    # bad / missing secret
    bad = ctx_c.new_page(); bad.goto(B + "/order.html?t=T1&k=wrong"); bad.wait_for_timeout(800)
    bad.get_by_role("button", name=re.compile("Add one Filter")).click(); bad.get_by_role("button", name="Review order").click()
    bad.get_by_role("button", name=re.compile("Send order")).click(); bad.wait_for_timeout(800)
    check("wrong secret is refused", "not valid" in bad.inner_text("#app"))
    none = ctx_c.new_page(); none.goto(B + "/order.html"); none.wait_for_timeout(400)
    check("no QR params shows scan hint", "Scan the QR" in none.inner_text("#app"))

    cust.goto(B + "/order.html?t=T1&k=demo-secret-t1"); cust.wait_for_selector(".item")
    check("menu shows 4 items", cust.locator(".item").count() == 4)
    for _ in range(2): cust.get_by_role("button", name="Add one Filter coffee").click()
    cust.get_by_role("button", name="Add one Cold brew").click()
    check("cart bar totals Rs 320", "Rs 320" in cust.inner_text(".bar"))
    cust.screenshot(path="01_menu.png")
    cust.get_by_role("button", name="Review order").click(); cust.fill("#note", "less sugar")
    cust.screenshot(path="02_cart.png")
    cust.get_by_role("button", name=re.compile("Send order")).click(); cust.wait_for_selector("text=Your table")
    txt = cust.inner_text("#app")
    check("bill shows lines and total", "2 × Filter coffee" in txt and "Rs 320" in txt)
    cust.screenshot(path="03_bill.png")

    # staff
    sctx = br.new_context(viewport={"width": 1280, "height": 800})
    staff = sctx.new_page(); staff.on("dialog", lambda d: d.accept())
    staff.goto(B + "/staff.html"); check("staff sees login first", "staff sign in" in staff.inner_text("#app").lower())
    staff.fill("#em", "staff@test.cafe"); staff.fill("#pw", "wrong"); staff.get_by_role("button", name="Sign in").click(); staff.wait_for_timeout(600)
    check("bad password refused", "Sign in failed" in staff.inner_text("#app"))
    staff.fill("#em", "staff@test.cafe"); staff.fill("#pw", "test-pass"); staff.get_by_role("button", name="Sign in").click()
    staff.wait_for_selector(".ord"); st = staff.inner_text("#app")
    check("staff sees the order with items and note", "Table T1" in st and "2 × Filter coffee" in st and "less sugar" in st)
    staff.screenshot(path="04_staff_new.png")
    staff.get_by_role("button", name="Start preparing").click(); staff.wait_for_selector(".ord.preparing")
    staff.get_by_role("button", name="Served").click(); staff.wait_for_timeout(900)
    check("served order leaves the kitchen list", "No open orders" in staff.inner_text("#app"))

    # customer asks for bill, skips rating
    cust.get_by_role("button", name="Ask for the bill").click(); cust.wait_for_selector("text=How was your visit")
    cust.screenshot(path="05_rate.png")
    cust.get_by_role("button", name="Skip").click(); cust.wait_for_selector("text=Amount to pay")
    check("pay screen shows Rs 320", "Rs 320" in cust.inner_text("#app"))
    href = cust.locator("a:has-text('Open UPI app')").get_attribute("href")
    check("UPI link carries exact amount and test id", "pa=test.cafe@upi" in href and "am=320.00" in href and "cu=INR" in href, href)
    cust.locator(".qr").screenshot(path="qr_pay.png"); cust.screenshot(path="06_pay.png")

    staff.wait_for_timeout(4500)
    check("staff sees bill waiting", "bills waiting for payment" in staff.inner_text("#app").lower() and "Rs 320" in staff.inner_text("#app"))
    staff.screenshot(path="07_staff_bill.png")
    # tables page
    staff.goto(B + "/tables.html"); staff.wait_for_selector(".qr"); check("tables page shows 3 QR codes", staff.locator(".qr").count() == 3)
    staff.locator(".qr").first.screenshot(path="qr_table.png")
    staff.goto(B + "/staff.html"); staff.wait_for_selector("text=Payment received")
    staff.get_by_role("button", name="Payment received").click(); staff.wait_for_timeout(900)
    check("bill leaves the staff list after payment", "None." in staff.inner_text("#app"))
    cust.wait_for_selector("text=Thank you", timeout=9000); check("customer sees thank you after staff confirm", True)
    cust.screenshot(path="08_thanks.png")

    # non-staff signed in cannot see orders
    octx = br.new_context(); o = octx.new_page(); o.goto(B + "/staff.html")
    o.fill("#em", "other@test.cafe"); o.fill("#pw", "test-pass"); o.get_by_role("button", name="Sign in").click(); o.wait_for_timeout(1200)
    check("signed-in non-staff sees no orders", "no open orders" in o.inner_text("#app").lower() and o.locator(".ord").count() == 0 )
    check("no console/page errors", not errs, str(errs[:3]))
    br.close()
print("TOTAL", sum(1 for _, ok in log if ok), "/", len(log))
