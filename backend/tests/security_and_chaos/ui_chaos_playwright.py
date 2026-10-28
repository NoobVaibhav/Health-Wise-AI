"""Manual browser sweep (not part of pytest): every page of every role, with the server answering badly, at phone width and with the keyboard.
Run against an ISOLATED copy of the stack, never the live one:
    DATABASE_URL=sqlite:///C:/copy.db uvicorn app.main:app --port 8001      (in backend)
    API_TARGET=http://127.0.0.1:8001 npx vite --port 5199 --strictPort      (in frontend)
    python tests/security_and_chaos/ui_chaos_playwright.py
Prints one line per finding."""
import json
import sys

from playwright.sync_api import sync_playwright

BASE = "http://localhost:5199"
PW = "Demo@12345"
ROLES = {
    "ADMIN": ("admin@healthwise.demo.com", ["/admin", "/admin/users", "/admin/doctors", "/admin/reports", "/admin/audit"]),
    "DOCTOR": ("anjali.sharma@healthwise.demo.com", ["/doctor", "/doctor/patients", "/doctor/reports/3", "/doctor/appointments", "/doctor/notes"]),
    "EMPLOYEE": ("priya.joshi@healthwise.demo.com", ["/employee", "/employee/patients", "/employee/reports", "/employee/register", "/employee/upload"]),
    "PHARMACY": ("pharmacy@healthwise.demo.com", ["/pharmacy", "/pharmacy/billing", "/pharmacy/bills", "/pharmacy/prescriptions", "/pharmacy/inventory"]),
    "LAB": ("lab@healthwise.demo.com", ["/lab"]),
    "PATIENT": ("rahul.patil@healthwise.demo.com", ["/patient", "/patient/reports", "/patient/history", "/patient/health-history", "/patient/prescriptions", "/patient/appointments", "/patient/assistant", "/patient/profile"]),
}
MODES = {
    "server error 500": lambda route: route.fulfill(status=500, content_type="application/json", body='{"detail":"boom"}'),
    "forbidden 403": lambda route: route.fulfill(status=403, content_type="application/json", body='{"detail":"no"}'),
    "empty object": lambda route: route.fulfill(status=200, content_type="application/json", body="{}"),
    "null body": lambda route: route.fulfill(status=200, content_type="application/json", body="null"),
    "empty list": lambda route: route.fulfill(status=200, content_type="application/json", body="[]"),
    "network down": lambda route: route.abort("failed"),
}


def make_route(handler):
    def route_it(route, request):
        if "/auth/me" in request.url:
            route.continue_()
        else:
            handler(route)
    return route_it


def blank(page) -> bool:
    return len(page.inner_text("body").strip()) < 30


def run():
    problems = []
    handled_count = [0]
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge", headless=True)
        for role, (email, pages) in ROLES.items():
            ctx = browser.new_context(viewport={"width": 1366, "height": 900})
            page = ctx.new_page()
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)[:100]))
            page.on("console", lambda m: errors.append("console: " + m.text[:100]) if m.type == "error" and "Failed to load resource" not in m.text else None)
            page.goto(BASE + "/login")
            page.wait_for_load_state("networkidle")
            page.fill("input[type=email]", email)
            page.fill("input[type=password]", PW)
            page.press("input[type=password]", "Enter")
            page.wait_for_url(lambda u: "/login" not in u, timeout=15000)
            token = page.evaluate("localStorage.getItem('healthwise_token')")
            for path in pages:
                errors.clear()
                page.goto(BASE + path)
                page.wait_for_load_state("networkidle")
                page.wait_for_timeout(300)
                if errors:
                    problems.append((role, path, "normal load", "console/page errors: " + "; ".join(sorted(set(errors))[:2])))
                over = page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 2")
                for mode, handler in MODES.items():
                    errors.clear()
                    page.route("**/api/**", make_route(handler))
                    page.goto(BASE + path)
                    page.wait_for_load_state("domcontentloaded")
                    page.wait_for_timeout(700)
                    handled = page.locator("text=Something went wrong on this page").count() > 0      # the error boundary caught it and shows a way out
                    if handled:
                        handled_count[0] += 1
                    elif blank(page) or any("is not a function" in e or "Cannot read" in e or "undefined" in e for e in errors):
                        problems.append((role, path, mode, "WHITE SCREEN" if blank(page) else "script error: " + "; ".join(sorted(set(errors))[:1])))
                    page.unroute("**/api/**")
                page.set_viewport_size({"width": 375, "height": 800})
                page.goto(BASE + path)
                page.wait_for_load_state("networkidle")
                if page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 2"):
                    problems.append((role, path, "375px wide", "horizontal scroll: the page is wider than the phone screen"))
                unnamed = page.evaluate("""() => [...document.querySelectorAll('button, a[href], input, select, textarea')].filter(el => {
                    const r = el.getBoundingClientRect(); if (!r.width || !r.height || el.closest('details:not([open])')) return false;
                    const name = (el.getAttribute('aria-label') || el.innerText || el.getAttribute('title') || el.getAttribute('placeholder') || (el.labels && el.labels[0] && el.labels[0].innerText) || el.getAttribute('alt') || '').trim();
                    return !name && el.type !== 'hidden'; }).length""")
                if unnamed:
                    problems.append((role, path, "accessibility", f"{unnamed} control(s) without a name for a screen reader"))
                page.set_viewport_size({"width": 1366, "height": 900})
            ctx.close()
        browser.close()
    for item in problems:
        print(" | ".join(item))
    print("shown by the error boundary instead of a white screen:", handled_count[0])
    print("problems:", len(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(run())
