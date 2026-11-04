"""Captures the user-manual screenshots of Chapter 11 from a locally running HealthWise AI (synthetic demo data only).
Usage (backend on :8000 with a throw-away database seeded by app.seed_demo, frontend dev server on FRONT):
    backend/.venv/Scripts/python.exe report/figures/capture_screenshots.py http://localhost:5174
"""
import json, sys, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
from PIL import Image

FRONT = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5174"
OUT = Path(__file__).parent / "screens"
PASSWORD = "Demo@12345"
ROLES = {"patient": "rahul.patil@healthwise.demo.com", "doctor": "anjali.sharma@healthwise.demo.com", "employee": "priya.joshi@healthwise.demo.com",
         "pharmacy": "pharmacy@healthwise.demo.com", "lab": "lab@healthwise.demo.com", "admin": "admin@healthwise.demo.com",
         "nurse": "nurse@healthwise.demo.com", "radiology": "radiologist@healthwise.demo.com"}


def token(email):
    req = urllib.request.Request("http://127.0.0.1:8000/api/auth/login", data=json.dumps({"email": email, "password": PASSWORD}).encode(), headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req))["access_token"]


# (file name, role or None, path, optional action(page), full_page)
def ask(page):
    page.get_by_placeholder("Ask").first.fill("What was my latest vitamin D value?") if page.get_by_placeholder("Ask").count() else page.locator("textarea, input[type=text]").last.fill("What was my latest vitamin D value?")
    page.keyboard.press("Enter")
    page.wait_for_timeout(2500)


SHOTS = [
    ("login", None, "/login", None, False),
    ("patient_dashboard", "patient", "/patient", None, False),
    ("patient_reports", "patient", "/patient/reports", None, False),
    ("patient_report_detail", "patient", "/patient/reports/13", None, False),
    ("patient_prescriptions", "patient", "/patient/prescriptions", None, False),
    ("patient_assistant", "patient", "/patient/assistant", ask, False),
    ("patient_history", "patient", "/patient/history", None, False),
    ("doctor_dashboard", "doctor", "/doctor", None, False),
    ("doctor_report_review", "doctor", "/doctor/reports/15", None, False),
    ("doctor_patient", "doctor", "/doctor/patients/1", None, False),
    ("doctor_prescriptions", "doctor", "/doctor/prescriptions", None, False),
    ("employee_dashboard", "employee", "/employee", None, False),
    ("employee_register", "employee", "/employee/register", None, False),
    ("employee_upload", "employee", "/employee/upload", None, False),
    ("employee_opd", "employee", "/employee/opd", None, False),
    ("pharmacy_dashboard", "pharmacy", "/pharmacy", None, False),
    ("pharmacy_prescriptions", "pharmacy", "/pharmacy/prescriptions", None, False),
    ("pharmacy_dispensing", "pharmacy", "/pharmacy/dispensing/8", None, False),
    ("pharmacy_inventory", "pharmacy", "/pharmacy/inventory", None, False),
    ("lab_dashboard", "lab", "/lab", None, False),
    ("admin_dashboard", "admin", "/admin", None, False),
    ("admin_users", "admin", "/admin/users", None, False),
    ("admin_audit", "admin", "/admin/audit-logs", None, False),
    ("admin_hospital", "admin", "/admin/hospital", None, False),
]

only = set(sys.argv[2:])
with sync_playwright() as p:
    browser = p.chromium.launch(channel="msedge")
    tokens = {}
    for name, role, path, action, full in SHOTS:
        if only and name not in only:
            continue
        ctx = browser.new_context(viewport={"width": 1366, "height": 800}, device_scale_factor=2)
        if role:
            tokens.setdefault(role, token(ROLES[role]))
            ctx.add_init_script(f"localStorage.setItem('healthwise_token', '{tokens[role]}')")
        page = ctx.new_page()
        page.goto(FRONT + path)
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1200)
        if action:
            action(page)
        raw = OUT / f"{name}.png"
        page.screenshot(path=str(raw), full_page=full)
        img = Image.open(raw).convert("RGB")
        img.thumbnail((1700, 4000))
        img.save(raw, optimize=True)
        print(name, img.size)
        ctx.close()
    browser.close()
