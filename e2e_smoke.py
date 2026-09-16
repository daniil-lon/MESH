import sys

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8000"

LOGIN = "abdulkadirova0001"
PASS = "abur2wza9z"

results = []


def check(name, ok, extra=""):
    results.append(ok)
    print(("PASS" if ok else "FAIL"), name, extra)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        ctx = browser.new_context(viewport={"width": 420, "height": 800})
        ctx.add_init_script("localStorage.setItem('mesh_onboard', '1');")
        page = ctx.new_page()
        errors = []

        def on_error(msg):
            if "favicon" in msg:
                return
            errors.append(msg)

        page.on("pageerror", lambda e: on_error(str(e)))
        page.on("console", lambda m: m.type == "error" and on_error(m.text))

        tok = page.request.post(BASE + "/api/auth/login", data={"login": LOGIN, "password": PASS}).json()["access_token"]

        # Student: news
        page.goto(BASE + "/?token=" + tok)
        page.wait_for_selector("#bottom-nav", state="visible", timeout=15000)
        check("student login / main shown", True)

        page.evaluate("App.navigateTo('news')")
        page.wait_for_selector(".news-card", timeout=15000)
        check("news render", page.locator(".news-card").count() > 0)
        page.wait_for_selector(".news-voice", timeout=8000)
        check("news voice button", page.locator(".news-voice").count() > 0)

        # Student: today (debts card)
        page.evaluate("App.navigateTo('today')")
        page.wait_for_selector(".today-card--debts, .today-card--ok", timeout=15000)
        check("today card + debts block", page.locator(".today-card--debts, .today-card--ok").count() > 0)

        # Search Ctrl+K
        page.keyboard.press("Control+K")
        page.wait_for_selector("#search-overlay:not([style*='none'])", timeout=8000)
        page.fill("#search-input", "расписани")
        page.wait_for_selector(".search-hit", timeout=10000)
        check("search ctrl+k results", page.locator(".search-hit").count() > 0)
        page.keyboard.press("Escape")
        check("search closes on esc", page.is_visible("#search-overlay") is False or page.get_attribute("#search-overlay", "style") is not None)

        # Sova
        page.click("#sova-fab")
        page.wait_for_selector("#sova-panel[style*='flex']", timeout=5000)
        page.fill("#sova-input", "долги")
        page.keyboard.press("Enter")
        page.wait_for_function("document.getElementById('sova-messages').textContent.length > 0", timeout=8000)
        txt = page.text_content("#sova-messages") or ""
        check("sova replies", "долг" in txt.lower(), txt[:80])

        # Profile badges
        page.evaluate("App.navigateTo('profile')")
        page.wait_for_selector(".badge-chip", timeout=15000)
        check("profile badges render", page.locator(".badge-chip").count() >= 1)

        # Teacher flow: form login
        page.evaluate("localStorage.clear()")
        page.goto(BASE + "/")
        page.fill("#login-username", "teacher01")
        page.fill("#login-password", "teacher01")
        page.click("#btn-login-submit")
        page.wait_for_selector("#bottom-nav", state="visible", timeout=15000)
        page.evaluate("App.navigateTo('profile')")
        page.wait_for_function("getComputedStyle(document.getElementById('btn-teacher-panel')).display === 'flex'", timeout=15000)

        page.click("#btn-teacher-panel")
        page.wait_for_selector("#screen-teacher.active", timeout=15000)
        page.wait_for_selector("#tj-subject option", timeout=15000, state="attached")
        page.wait_for_selector(".tj-row", timeout=15000)
        check("teacher journal renders rows", page.locator(".tj-row").count() > 0)

        first_row = page.locator(".tj-row").first
        first_row.locator("select").select_option("4")
        first_row.locator(".tj-save").click()
        page.wait_for_function("(document.getElementById('tj-status').textContent || '').toLowerCase().includes('сохранен')", timeout=10000)
        check("teacher grade save", "сохранен" in (page.text_content("#tj-status") or "").lower(), (page.text_content("#tj-status") or "")[:60])

        # Share report (student)
        page.evaluate("localStorage.clear()")
        page.goto(BASE + "/?token=" + tok)
        page.wait_for_selector("#bottom-nav", state="visible", timeout=15000)
        page.evaluate("App.showReport()")
        page.wait_for_selector("#spravka-modal[style*='flex']", timeout=10000)
        share = page.text_content("#btn-share-report") or ""
        if "display: none" in page.get_attribute("#btn-share-report", "style") or not page.is_visible("#btn-share-report"):
            check("share report button visible", False, share[:60])
        else:
            check("share report button visible", True)
            page.click("#btn-share-report")
            page.wait_for_function("(document.getElementById('btn-share-report').textContent || '').includes('http') || (document.getElementById('btn-share-report').textContent || '').includes('Ссылка')", timeout=10000)
            txt = page.text_content("#btn-share-report") or ""
            share_url = [w for w in txt.replace(" ", " ").split() if w.startswith("http")]
            if share_url:
                shared = share_url[0]
                check("share link created", True, shared)
                page2 = ctx.new_page()
                page2.goto(shared)
                page2.wait_for_selector("#spravka-modal[style*='flex']", timeout=15000)
                body = page2.text_content("#spravka-body") or ""
                check("share report opens for parent", "по ссылке" in body and "Абдулкадирова" in body, body[:80])
                page2.close()
            else:
                check("share link created", False, txt[:80])

        # Admin
        adm = ctx.new_page()
        adm.goto(BASE + "/admin.html")
        adm.fill("#admin-pass", "1111")
        adm.click("button:has-text('Войти')")
        adm.wait_for_selector("#app-box:not(.hidden)", timeout=15000)
        adm.wait_for_selector(".stat-card", timeout=15000)
        check("admin stat cards", adm.locator(".stat-card").count() == 6)
        adm.click("button:has-text('Тема')")
        adm.wait_for_selector("html[data-theme='dark']", timeout=5000)
        check("admin dark theme", True)
        adm.close()

        if errors:
            print("CONSOLE/PAGE ERRORS:")
            for e in errors[:12]:
                print("  -", e)

        browser.close()

    ok = all(results)
    print(f"\nRESULT: {sum(results)}/{len(results)} passed")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()