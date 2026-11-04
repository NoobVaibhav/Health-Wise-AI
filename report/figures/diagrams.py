"""Draws the diagrams of the HealthWise AI final report (matplotlib only, black and white safe, 300 dpi).
Run:  python report/figures/diagrams.py        -> writes fig_*.png next to this file.
Every diagram is drawn from facts in the repository (docs, schema, routers); the Gantt chart is read from `git log`."""
import subprocess
import textwrap
from collections import OrderedDict
from datetime import date, datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse, FancyArrowPatch, FancyBboxPatch, Rectangle

OUT = Path(__file__).parent

_text = matplotlib.axes.Axes.text


def _scaled_text(self, x, y, s, fontdict=None, **kw):
    kw["fontsize"] = kw.get("fontsize", 10) * FS
    return _text(self, x, y, s, fontdict, **kw)


matplotlib.axes.Axes.text = _scaled_text
plt.rcParams["font.family"] = ["Arial", "DejaVu Sans"]
W = 5.8          # figure width in inches = the text width of the report, so figures are inserted at 100 per cent
FS = 1.32        # all text is enlarged by this factor so that the smallest label prints at about 6 pt
INK, GREY, LIGHT = "#111111", "#d9d9d9", "#f2f2f2"


def canvas(w, h, height_in=None):
    fig = plt.figure(figsize=(W, height_in or W * h / w), dpi=300)
    ax = fig.add_axes([0.005, 0.005, 0.99, 0.99])
    ax.set_xlim(0, w); ax.set_ylim(0, h); ax.axis("off"); ax.set_aspect("auto")
    return fig, ax


def save(fig, name):
    fig.savefig(OUT / name, dpi=300, facecolor="white")
    plt.close(fig)
    print("wrote", name)


def box(ax, x, y, w, h, text="", fill="white", fs=6.5, bold=False, round_=True, lw=0.8, ha="center", ls="-", va="center"):
    p = (FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.2", fc=fill, ec=INK, lw=lw, ls=ls) if round_
         else Rectangle((x, y), w, h, fc=fill, ec=INK, lw=lw, ls=ls))
    ax.add_patch(p)
    if text:
        tx = x + w / 2 if ha == "center" else x + 1.2
        ax.text(tx, y + h / 2, text, ha=ha, va=va, fontsize=fs, fontweight="bold" if bold else "normal", color=INK, linespacing=1.25)


def arrow(ax, p, q, label=None, fs=5.6, style="-|>", ls="-", lw=0.8, rad=0.0, lpos=0.5, loff=(0, 1.0), both=False, ha="center", bg=True):
    a = FancyArrowPatch(p, q, arrowstyle="<|-|>" if both else style, mutation_scale=7, lw=lw, ls=ls, color=INK, connectionstyle=f"arc3,rad={rad}", shrinkA=0, shrinkB=0)
    ax.add_patch(a)
    if label:
        x = p[0] + (q[0] - p[0]) * lpos + loff[0]
        y = p[1] + (q[1] - p[1]) * lpos + loff[1]
        ax.text(x, y, label, fontsize=fs, ha=ha, va="center", color=INK, linespacing=1.15,
                bbox=dict(fc="white", ec="none", pad=0.6) if bg else None)


def line(ax, p, q, lw=0.8, ls="-"):
    ax.plot([p[0], q[0]], [p[1], q[1]], color=INK, lw=lw, ls=ls, solid_capstyle="butt")


def actor(ax, x, y, name, s=1.0, fs=6.3):
    ax.add_patch(Ellipse((x, y + 7.2 * s), 2.6 * s, 2.6 * s, fc="white", ec=INK, lw=0.8))
    line(ax, (x, y + 5.9 * s), (x, y + 2.6 * s)); line(ax, (x - 2.2 * s, y + 4.7 * s), (x + 2.2 * s, y + 4.7 * s))
    line(ax, (x, y + 2.6 * s), (x - 1.8 * s, y)); line(ax, (x, y + 2.6 * s), (x + 1.8 * s, y))
    ax.text(x, y - 1.6 * s, name, ha="center", va="top", fontsize=fs, fontweight="bold", linespacing=1.15)


def datastore(ax, x, y, w, h, text, fs=6.0):
    ax.add_patch(Rectangle((x, y), w, h, fc="white", ec="none"))
    line(ax, (x, y + h), (x + w, y + h)); line(ax, (x, y), (x + w, y)); line(ax, (x, y), (x, y + h), lw=0.8)
    ax.text(x + w / 2 + 0.6, y + h / 2, text, ha="center", va="center", fontsize=fs, linespacing=1.2)


def circle_proc(ax, x, y, r, text, fs=5.8, fill="white"):
    ax.add_patch(Ellipse((x, y), 2 * r, 2 * r * 0.82, fc=fill, ec=INK, lw=0.9))
    ax.text(x, y, text, ha="center", va="center", fontsize=fs, linespacing=1.2)


# --------------------------------------------------------------------------------------------- 6.1 architecture
def architecture():
    fig, ax = canvas(100, 112)
    # client
    box(ax, 4, 92, 92, 18, round_=False, fill=LIGHT)
    ax.text(6, 107.8, "Client tier: React 18 single-page application (Vite, Tailwind CSS 4, React Router 6, Axios, Recharts)", fontsize=6.4, fontweight="bold", va="center")
    for i, t in enumerate(["Role pages\n(patient, doctor, reception,\npharmacy, lab, admin ...)", "Shared components\n(report view, timeline,\nprescription sheet)", "Assistant and voice\n(browser speech APIs,\nEnglish / Hindi / Marathi)", "Route guards,\nerror boundary,\nvalidators"]):
        box(ax, 6 + i * 22.4, 94, 21, 11.5, t, fs=5.6)
    arrow(ax, (50, 92), (50, 85), "HTTPS, JSON, JWT bearer token  (/api/*)", fs=6, both=True)
    # server
    box(ax, 4, 38, 92, 47, round_=False, fill="white", lw=1.1)
    ax.text(6, 82.5, "Application tier: FastAPI (Python)", fontsize=6.4, fontweight="bold", va="center")
    box(ax, 6, 70, 88, 9, "Middleware: security headers, no-store cache control, request-size limit, global handlers (422 / 409 / report errors), CORS", fs=5.6, fill=LIGHT)
    box(ax, 6, 58, 40, 9.5, "Routers (38 modules, 385 operations)\nHTTP only: input schema, status codes,\nrole check  require_roles / require_permission", fs=5.5)
    box(ax, 54, 58, 40, 9.5, "Core: JWT + bcrypt, RBAC and patient-level\naccess (can_access_patient, break-glass),\nsettings, audit trail", fs=5.5)
    box(ax, 6, 40.5, 40, 14, "Services (58 modules): pdf, ocr, parser,\nanalysis engine, insights, comparison,\nhistory, dispensing, stock, billing,\npatient assistant, safety filter", fs=5.5)
    box(ax, 54, 40.5, 19, 14, "Schemas\n(Pydantic v2\nvalidators)", fs=5.5)
    box(ax, 75, 40.5, 19, 14, "ORM models\n(SQLAlchemy 2,\n125 tables)", fs=5.5)
    for x in (26, 74):
        arrow(ax, (x, 58), (x, 54.5), lw=0.7)
    arrow(ax, (50, 38), (50, 31))
    # data
    box(ax, 4, 6, 44, 25, round_=False, fill=LIGHT)
    ax.text(6, 28.5, "Data tier", fontsize=6.4, fontweight="bold", va="center")
    box(ax, 7, 9, 18, 14, "SQLite\n(development)\nPostgreSQL\n(production)", fs=5.5)
    box(ax, 27, 9, 19, 14, "Private upload\nfolder (random\nfile names, served\nonly via the API)", fs=5.3)
    # external
    box(ax, 52, 6, 44, 25, round_=False, fill="white", ls="--")
    ax.text(54, 28.5, "Optional external services", fontsize=6.4, fontweight="bold", va="center")
    box(ax, 55, 9, 13, 14, "Tesseract\nOCR\n(scans,\nphotos)", fs=5.3)
    box(ax, 70, 9, 13, 14, "LLM API\n(wording only,\nredacted,\nconsent)", fs=5.3)
    box(ax, 85, 9, 9, 14, "SMTP\ne-mail", fs=5.3)
    arrow(ax, (75, 38), (75, 31), ls="--")
    ax.text(50, 2.2, "Solid arrows: always present.  Dashed: optional or deployment dependent.", ha="center", fontsize=5.6, style="italic")
    save(fig, "fig_6_01_architecture.png")


# --------------------------------------------------------------------------------------------- DFD level 0
def dfd0():
    fig, ax = canvas(100, 100)
    circle_proc(ax, 50, 50, 15.5, "0\nHealthWise AI\nHospital management\nand report analysis", fs=6.6)
    left = [("Patient", 75), ("Doctor", 50), ("Reception\n(Employee)", 25)]
    right = [("Pharmacy\nstaff", 75), ("Lab and radiology\nstaff", 50), ("Administrator", 25)]
    for n, y in left:
        box(ax, 1, y - 5, 20, 10, n, fs=6.2, round_=False, lw=1.0)
    for n, y in right:
        box(ax, 79, y - 5, 20, 10, n, fs=6.2, round_=False, lw=1.0)
    arrow(ax, (21, 75), (38.5, 58), "reports, history, bills,\nassistant questions and answers", fs=5.2, both=True, loff=(-1, 7.5))
    arrow(ax, (21, 50), (34.5, 50), "reviews, notes,\nprescriptions", fs=5.2, both=True, loff=(0, 5))
    arrow(ax, (21, 25), (38.5, 42), "patients, appointments,\nreport files, bed board", fs=5.2, both=True, loff=(-1, -7.5))
    arrow(ax, (79, 75), (61.5, 58), "dispensing, stock,\nbills", fs=5.2, both=True, loff=(1, 6))
    arrow(ax, (79, 50), (65.5, 50), "test orders, results,\nscan reports", fs=5.2, both=True, loff=(0, 5))
    arrow(ax, (79, 25), (61.5, 42), "accounts, settings,\naudit queries", fs=5.2, both=True, loff=(1, -6.5))
    box(ax, 38, 88, 24, 8, "LLM service (optional)", fs=5.6, round_=False, ls="--")
    arrow(ax, (50, 88), (50, 65.5), "redacted text out,\nwording back", fs=5.2, ls="--", both=True, loff=(10, 0))
    box(ax, 38, 4, 24, 8, "E-mail server (optional)", fs=5.6, round_=False, ls="--")
    arrow(ax, (50, 12), (50, 34.5), "notifications", fs=5.2, ls="--", loff=(8, 0))
    save(fig, "fig_6_02_dfd_level0.png")


# --------------------------------------------------------------------------------------------- DFD level 1
def dfd1():
    fig, ax = canvas(100, 124)
    ROWS = [114, 92, 62, 38, 14]
    EL, PL, ST, PR, ER = 7.5, 28, 48, 69, 90

    def ent(x, y, t):
        box(ax, x - 6.5, y - 4, 13, 8, t, fs=5.5, round_=False)

    def sto(x, y, t, w=12.5):
        datastore(ax, x - w / 2, y - 3.5, w, 7, t, fs=5.0)

    R = 8.6
    ent(EL, ROWS[0], "All users")
    circle_proc(ax, PL, ROWS[0], R, "1.0\nAuthenticate\nand authorise", fs=5.4)
    sto(ST, ROWS[0], "D1 Users\nand roles")
    arrow(ax, (EL + 6.5, ROWS[0]), (PL - R, ROWS[0]), "credentials", fs=4.8, both=True, loff=(0, 2.4))
    arrow(ax, (PL + R, ROWS[0]), (ST - 6.25, ROWS[0]), "", both=True)
    ax.text(PR + 6, ROWS[0], "token and role gate\nevery flow below", fontsize=5.0, ha="center", va="center", style="italic")
    ent(EL, ROWS[1], "Reception")
    circle_proc(ax, PL, ROWS[1], R, "2.0\nRegister patient\nand book visit", fs=5.4)
    sto(ST, ROWS[1], "D2 Patients,\nappointments")
    circle_proc(ax, PR, ROWS[1], R, "3.0\nValidate, read\nand analyse report", fs=5.2)
    ent(ER, ROWS[1], "Reception /\nDoctor")
    arrow(ax, (EL + 6.5, ROWS[1]), (PL - R, ROWS[1]), "patient data", fs=4.8, loff=(0, 2.4))
    arrow(ax, (PL + R, ROWS[1]), (ST - 6.25, ROWS[1]))
    arrow(ax, (ST + 6.25, ROWS[1]), (PR - R, ROWS[1]), "patient id", fs=4.8, loff=(0, 2.4))
    arrow(ax, (ER - 6.5, ROWS[1]), (PR + R, ROWS[1]), "report file", fs=4.8, loff=(0, 2.4))
    sto(PR, 72.5, "D3 Reports,\nparameters", w=16)
    arrow(ax, (PR, ROWS[1] - 7.1), (PR, 82), "analysis", fs=4.8, loff=(6, 0))
    ent(EL, ROWS[2], "Doctor")
    circle_proc(ax, PL, ROWS[2], R, "4.0\nDoctor review,\nnotes, prescribing", fs=5.2)
    sto(ST, ROWS[2], "D4 Prescriptions,\ndispensing", w=15)
    circle_proc(ax, PR, ROWS[2], R, "5.0\nDispense and\ncontrol stock", fs=5.4)
    ent(ER, ROWS[2], "Pharmacy\nstaff")
    arrow(ax, (EL + 6.5, ROWS[2]), (PL - R, ROWS[2]), "review, rx", fs=4.8, both=True, loff=(0, 2.4))
    arrow(ax, (PL + R, ROWS[2]), (ST - 7.5, ROWS[2]))
    arrow(ax, (ST + 7.5, ROWS[2]), (PR - R, ROWS[2]), "open rx", fs=4.8, loff=(0, 2.4))
    arrow(ax, (ER - 6.5, ROWS[2]), (PR + R, ROWS[2]), "dispense", fs=4.8, both=True, loff=(0, 2.4))
    sto(PR, 50.5, "D5 Medicine\ninventory", w=16)
    arrow(ax, (PR, ROWS[2] - 7.1), (PR, 54), "stock", fs=4.8, both=True, loff=(5, 0))
    ent(EL, ROWS[3], "Patient")
    circle_proc(ax, PL, ROWS[3], R, "6.0\nPatient portal\nand assistant", fs=5.4)
    sto(ST, ROWS[3], "D3 + D4\n(read only)")
    arrow(ax, (EL + 6.5, ROWS[3]), (PL - R, ROWS[3]), "question,\nbooking", fs=4.6, both=True, loff=(0, 3.2))
    arrow(ax, (ST - 6.25, ROWS[3]), (PL + R, ROWS[3]), "reviewed results,\nstatus", fs=4.6, loff=(0, 3.4))
    ent(EL, ROWS[4], "Administrator")
    circle_proc(ax, PL, ROWS[4], R, "7.0\nAudit and\nadministration", fs=5.4)
    sto(ST, ROWS[4], "D6 Audit log")
    arrow(ax, (EL + 6.5, ROWS[4]), (PL - R, ROWS[4]), "accounts,\nsettings", fs=4.6, both=True, loff=(0, 3.2))
    arrow(ax, (PL + R, ROWS[4]), (ST - 6.25, ROWS[4]), "audit lines", fs=4.8, loff=(0, 2.4))
    ax.text(50, 3, "Every process 2.0 to 6.0 also writes audit lines to D6; employees and administrators never receive clinical values from D3.", fontsize=5.0, ha="center", style="italic")
    save(fig, "fig_6_03_dfd_level1.png")


# --------------------------------------------------------------------------------------------- use cases
def usecase(name, title, actor_name, uses):
    n = len(uses)
    H = 16 + n * 9.2
    fig, ax = canvas(100, H)
    ax.add_patch(Rectangle((26, 2), 72, H - 4, fc="white", ec=INK, lw=1.0))
    ax.text(62, H - 5, f"HealthWise AI: {title}", ha="center", va="center", fontsize=6.5, fontweight="bold")
    actor(ax, 11, H / 2 - 6, actor_name, s=1.25)
    for i, u in enumerate(uses):
        y = H - 15 - i * 9.2
        ax.add_patch(Ellipse((62, y), 50, 7.6, fc="white", ec=INK, lw=0.8))
        ax.text(62, y, u.replace(chr(10), " "), ha="center", va="center", fontsize=5.8)
        line(ax, (14.5, H / 2 + 1), (37, y), lw=0.5)
    save(fig, name)


def usecases():
    usecase("fig_6_04_usecase_patient.png", "Patient", "Patient",
            ["Log in (password or\nmobile code)", "View reviewed reports\nand trends", "View prescriptions and\ndispensing status", "Ask HealthWise\n(chat or voice)",
             "View timeline and\nhealth history", "Book or cancel\nappointment", "View bills", "Print emergency card\nand history"])
    usecase("fig_6_05_usecase_doctor.png", "Doctor", "Doctor\n(intern to consultant)",
            ["Review report and\ninsights", "Write note and\nrecommendation", "Create prescription and\nadvise tests", "Take history and\nrecord consultation",
             "Manage OPD queue and\nemergency visits", "Admit, round and\ndischarge inpatient", "Refer to department\nor doctor", "Countersign junior\ndoctor orders"])
    usecase("fig_6_06_usecase_reception.png", "Reception (Employee)", "Reception\n(Employee)",
            ["Register patient with\nduplicate check", "Upload report\n(PDF, photo, text)", "Book and manage\nappointments", "Check in OPD token\nand walk-in",
             "Register emergency\nvisit", "View bed board", "Record consent and\ninsurance"])
    usecase("fig_6_07_usecase_pharmacy.png", "Pharmacy", "Pharmacy\nstaff",
            ["Search prescription", "Dispense fully or\npartly", "Mark medicine\nunavailable", "Sell and bill with\nbarcode",
             "Manage stock batches\nand expiry", "View dispensing\nhistory", "Receive stock against\npurchase order"])
    usecase("fig_6_08_usecase_lab.png", "Laboratory and radiology", "Lab and\nradiology staff",
            ["View test worklist", "Collect sample and\nenter result", "Pathologist approves\nresult", "Raise critical-value\nalert",
             "View scan orders", "Radiologist writes and\napproves report"])
    usecase("fig_6_09_usecase_admin.png", "Administrator", "Administrator",
            ["Create staff accounts", "Activate, deactivate or\ndelete user", "View audit log", "Manage departments and\nspecializations",
             "Edit roles and\npermissions", "Configure hospital\nprofile and price list", "Review break-glass\naccess", "View integrations\nstatus"])


# --------------------------------------------------------------------------------------------- shared grid helpers for class and ER diagrams
COLS = (2, 36.5, 71)


def entity_box(ax, x, y, w, title, fields, fs=5.0, head=4.0, step=2.2, bold_pk=False):
    h = head + step * len(fields) + 0.8
    ax.add_patch(Rectangle((x, y), w, h, fc="white", ec=INK, lw=0.9))
    ax.add_patch(Rectangle((x, y + h - head), w, head, fc=GREY, ec=INK, lw=0.9))
    ax.text(x + w / 2, y + h - head / 2, title, ha="center", va="center", fontsize=5.8, fontweight="bold")
    for i, f in enumerate(fields):
        ax.text(x + 1, y + h - head - 1.4 - i * step, f, ha="left", va="center", fontsize=fs, fontweight="bold" if (bold_pk and f.startswith("PK")) else "normal")
    return (x, y, w, h)


def connect(ax, a, b, ca="", cb="", label=None, dashed=False):
    """Straight connector between two boxes (x, y, w, h): horizontal, vertical or diagonal from the nearer sides."""
    xa, ya, wa, ha = a; xb, yb, wb, hb = b
    cxa, cya, cxb, cyb = xa + wa / 2, ya + ha / 2, xb + wb / 2, yb + hb / 2
    if abs(cya - cyb) < 6:                                  # same row
        left, right = (a, b) if cxa < cxb else (b, a)
        p, q = (left[0] + left[2], left[1] + left[3] / 2), (right[0], right[1] + right[3] / 2)
        if a is not left:
            p, q = q, p
    elif abs(cxa - cxb) < 6:                                # same column
        upper, lower = (a, b) if cya > cyb else (b, a)
        p, q = (upper[0] + upper[2] / 2, upper[1]), (lower[0] + lower[2] / 2, lower[1] + lower[3])
        if a is not upper:
            p, q = q, p
    else:                                                   # diagonal, from the upper box downwards
        upper, lower = (a, b) if cya > cyb else (b, a)
        p, q = (upper[0] + upper[2] / 2, upper[1]), (lower[0] + lower[2] / 2, lower[1] + lower[3])
        if a is not upper:
            p, q = q, p
    line(ax, p, q, lw=0.7, ls="--" if dashed else "-")
    for pt, other, c in ((p, q, ca), (q, p, cb)):
        if c:
            ax.text(pt[0] + (other[0] - pt[0]) * 0.12, pt[1] + (other[1] - pt[1]) * 0.12 + (1.3 if abs(pt[1] - other[1]) < 1 else 0), c, fontsize=5.0, ha="center", va="center",
                    bbox=dict(fc="white", ec="none", pad=0.2))
    if label:
        ax.text((p[0] + q[0]) / 2, (p[1] + q[1]) / 2 + (1.4 if abs(p[1] - q[1]) < 1 else 0), label, fontsize=4.9, ha="center", va="center", bbox=dict(fc="white", ec="none", pad=0.3))


def class_diagram():
    rows = [133, 114, 94, 70, 46, 22]
    fig, ax = canvas(100, 154)
    W3 = 27
    u = entity_box(ax, COLS[1], rows[0], W3, "User", ["id, email (unique)", "password_hash", "full_name, role", "is_active", "must_change_password"])
    pt = entity_box(ax, COLS[0], rows[1] - 3, W3, "Patient", ["patient_code, uhid", "date_of_birth, gender", "blood_group, allergies", "assigned_doctor_id"])
    st = entity_box(ax, COLS[1], rows[1] - 3, W3, "Staff profiles", ["Employee", "PharmacyStaff", "LabStaff (lab, radiology)", "Nurse"])
    dr = entity_box(ax, COLS[2], rows[1] - 3, W3, "Doctor", ["department_id", "grade (INTERN to", "   CONSULTANT)", "supervisor_id"])
    ap = entity_box(ax, COLS[1], rows[2] - 6, W3, "Appointment", ["scheduled_at, reason", "status", "patient_id, doctor_id"])
    hr = entity_box(ax, COLS[0], rows[3] - 5, W3, "HealthReport", ["filename, file_path", "report_date", "processing_status", "doctor_review_status", "insights_json"])
    hp = entity_box(ax, COLS[1], rows[3] - 5, W3, "HealthParameter", ["normalized_name", "value, unit", "reference_low / high", "status: WITHIN, ABOVE,", "   BELOW, UNKNOWN"])
    rx = entity_box(ax, COLS[0], rows[4] - 3, W3, "Prescription", ["prescription_date", "status: ACTIVE,", "  PARTIALLY_DISPENSED,", "  DISPENSED, CANCELLED"])
    it = entity_box(ax, COLS[1], rows[4] - 3, W3, "PrescriptionItem", ["medicine_name, dosage", "frequency, duration", "quantity", "dispense_status"])
    dp = entity_box(ax, COLS[2], rows[4] - 3, W3, "MedicineDispensing", ["quantity_prescribed", "quantity_dispensed", "status, dispensed_at"])
    inv = entity_box(ax, COLS[2], rows[5] - 8, W3, "MedicineInventory", ["medicine_name, batch", "quantity, expiry_date", "unit_price, reorder_level"])
    au = entity_box(ax, COLS[0], rows[5] - 8, W3, "AuditLog", ["user_id, action", "entity_type, entity_id", "timestamp, ip_address"])
    asst = entity_box(ax, COLS[1], rows[5] - 8, W3, "AssistantConversation", ["patient_id, language", "messages (role, text)", "evidence (pointers)"])
    connect(ax, u, pt, "1", "0..1")
    connect(ax, u, st, "1", "0..1")
    connect(ax, u, dr, "1", "0..1")
    connect(ax, pt, ap, "1", "*", "books")
    connect(ax, dr, ap, "1", "*", "attends")
    connect(ax, pt, hr, "1", "*", "has")
    connect(ax, hr, hp, "1", "*", "contains")
    connect(ax, hr, rx, "0..1", "*", "may lead to")
    connect(ax, rx, it, "1", "*", "lists")
    connect(ax, it, dp, "1", "*", "dispensed as")
    connect(ax, dp, inv, "*", "1", "deducts from")
    ax.text(50, 151.5, "Each profile table holds the extra fields of one User role (one to one with users.id).", ha="center", fontsize=5.4, style="italic")
    ax.text(50, 3.5, "AuditLog and AssistantConversation refer to User and Patient by id (relations not drawn).", ha="center", fontsize=5.2, style="italic")
    save(fig, "fig_6_10_class_diagram.png")


def er_diagram():
    rows = [136, 112, 88, 64, 40, 16]
    fig, ax = canvas(100, 150)
    W3 = 27
    E = {}
    def ent(key, col, row, title, fields):
        E[key] = entity_box(ax, COLS[col], rows[row] - 4, W3, title, fields, fs=4.9, bold_pk=True)
    ent("users", 1, 0, "users", ["PK id", "email (unique), full_name", "role, password_hash", "is_active"])
    ent("depts", 2, 0, "departments", ["PK id", "name, is_active"])
    ent("patients", 0, 1, "patients", ["PK id", "FK user_id, FK assigned_doctor_id", "uhid, patient_code", "date_of_birth"])
    ent("enc", 1, 1, "encounters", ["PK id", "FK patient_id", "FK attending_doctor_id", "type, status, started_at"])
    ent("doctors", 2, 1, "doctors", ["PK id", "FK user_id, FK department_id", "FK supervisor_id", "grade, registration_number"])
    ent("appts", 0, 2, "appointments", ["PK id", "FK patient_id, FK doctor_id", "scheduled_at, status"])
    ent("rep", 1, 2, "health_reports", ["PK id", "FK patient_id, FK uploaded_by", "FK assigned_doctor_id", "processing_status", "doctor_review_status"])
    ent("notes", 2, 2, "doctor_notes", ["PK id", "FK patient_id, FK doctor_id", "FK report_id, note, priority"])
    ent("rx", 0, 3, "prescriptions", ["PK id", "FK patient_id, FK doctor_id", "FK report_id, FK encounter_id", "status, prescription_date"])
    ent("par", 1, 3, "health_parameters", ["PK id", "FK report_id", "normalized_name, value, unit", "reference_low / high, status"])
    ent("item", 0, 4, "prescription_items", ["PK id", "FK prescription_id", "medicine_name, quantity", "dispense_status"])
    ent("disp", 1, 4, "medicine_dispensing", ["PK id", "FK prescription_item_id", "FK pharmacy_staff_id", "quantity_dispensed"])
    ent("move", 2, 4, "stock_movements", ["PK id", "FK medicine_id", "kind, quantity", "reference_type, reference_id"])
    ent("adm", 0, 5, "admissions", ["PK id", "FK patient_id", "FK attending_doctor_id", "status: one ADMITTED per patient"])
    ent("bed", 1, 5, "bed_assignments", ["PK id", "FK admission_id, FK bed_id", "released_at: one open per bed"])
    ent("inv", 2, 5, "medicine_inventory", ["PK id", "medicine_name, batch_number", "quantity, expiry_date", "unit_price"])
    connect(ax, E["users"], E["patients"], "1", "0..1")
    connect(ax, E["users"], E["doctors"], "1", "0..1")
    connect(ax, E["depts"], E["doctors"], "1", "N")
    connect(ax, E["patients"], E["enc"], "1", "N")
    connect(ax, E["doctors"], E["enc"], "1", "N")
    connect(ax, E["patients"], E["appts"], "1", "N")
    connect(ax, E["patients"], E["rep"], "1", "N")
    connect(ax, E["doctors"], E["notes"], "1", "N")
    connect(ax, E["rep"], E["par"], "1", "N")
    connect(ax, E["rep"], E["rx"], "0..1", "N")
    connect(ax, E["rx"], E["item"], "1", "N")
    connect(ax, E["item"], E["disp"], "1", "N")
    connect(ax, E["inv"], E["move"], "1", "N")
    connect(ax, E["patients"], E["adm"], "1", "N") if False else None
    connect(ax, E["adm"], E["bed"], "1", "N")
    ax.text(50, 1.5, "16 of the 125 tables are drawn, the ones behind the report, prescription and bed flows; PK primary key, FK foreign key.", ha="center", fontsize=5.0, style="italic")
    save(fig, "fig_6_11_er_diagram.png")


# --------------------------------------------------------------------------------------------- sequence diagrams
def seq(name, parts, msgs, title=None, width=100, row=5.2, notes=()):
    n = len(parts)
    H = 12 + row * (len(msgs) + 1) + 4
    fig, ax = canvas(100, H)
    xs = [width / n * (i + 0.5) for i in range(n)]
    for x, p in zip(xs, parts):
        box(ax, x - 8.2, H - 8, 16.4, 6, p, fs=5.5, bold=True, fill=GREY, round_=False)
        line(ax, (x, H - 8), (x, 3), lw=0.6, ls=(0, (4, 3)))
    y = H - 8 - row
    for m in msgs:
        if m[0] == "note":
            ax.text(50, y, textwrap.fill(m[2], 80), fontsize=5.1, ha="center", va="center", bbox=dict(fc=LIGHT, ec=INK, lw=0.5, pad=1.4), linespacing=1.15)
        else:
            a, b, text = m[0], m[1], m[2]
            dashed = len(m) > 3 and m[3]
            if a == b:
                ax.add_patch(FancyArrowPatch((xs[a], y + 0.4), (xs[a], y - 2.2), arrowstyle="-|>", mutation_scale=6, lw=0.7, color=INK, connectionstyle="arc3,rad=-1.2"))
                ax.text(xs[a] + (2 if a < n / 2 else -2), y - 0.5, text, fontsize=5.1, ha="left" if a < n / 2 else "right", va="center")
            else:
                ax.add_patch(FancyArrowPatch((xs[a], y), (xs[b], y), arrowstyle="-|>", mutation_scale=6, lw=0.7, ls="--" if dashed else "-", color=INK, shrinkA=0, shrinkB=0))
                ax.text((xs[a] + xs[b]) / 2, y + 1.15, text, fontsize=5.1, ha="center", va="center", bbox=dict(fc="white", ec="none", pad=0.3))
        y -= row
    save(fig, name)


def sequences():
    seq("fig_6_12_seq_login.png", ["Browser", "FastAPI router\n/api/auth", "Security\n(bcrypt, JWT)", "Database", "Audit log"], [
        (0, 1, "POST /login {email, password}"),
        (1, 3, "find user by e-mail"), (3, 1, "user row", True),
        (1, 3, "failed attempts in last 15 min?"), (3, 1, "count (5 per e-mail and address)", True),
        (1, 2, "verify SHA-256 + bcrypt hash"), (2, 1, "ok / wrong", True),
        ("note", 1, "wrong: generic 401, LOGIN_FAILED written; at the limit: 429 with minutes to wait"),
        (1, 2, "create JWT (user id, password fingerprint, expiry)"), (2, 1, "token", True),
        (1, 4, "LOGIN"), (1, 0, "200 {token, user, must_change_password}", True),
        (0, 1, "GET /api/auth/me  (Bearer token)"),
        ("note", 1, "every request: decode, load user, check is_active and fingerprint; temporary password -> only /me and change-password"),
        (1, 0, "profile and role", True),
    ])
    seq("fig_6_13_seq_report.png", ["Reception /\nDoctor", "Router\n/api/reports", "Processor\n(pdf, OCR, parser)", "Analysis\nengine", "Database", "Patient"], [
        (0, 1, "POST /upload (patient_id, file)"),
        (1, 1, "role check, patient access, type, size, signature"),
        (1, 2, "extract text (text layer, else OCR)"),
        (2, 2, "clean, find tests, values, units, ranges"),
        ("note", 2, "no health content or no parameters: rejected, nothing saved (422)"),
        (2, 3, "parameters"),
        (3, 3, "classify: WITHIN / ABOVE / BELOW / UNKNOWN"),
        (3, 3, "insights, optional LLM wording + safety filter"),
        (3, 1, "analysis", True),
        (1, 4, "save report WAITING_FOR_DOCTOR + audit"),
        (1, 0, "201 (employee: status only, no values)", True),
        (0, 1, "PUT /doctor/reports/{id}/review"),
        (1, 4, "DOCTOR_REVIEWED + audit"),
        (5, 1, "GET /api/reports/{id}"),
        (1, 5, "reviewed analysis, doctor's note", True),
    ])
    seq("fig_6_14_seq_prescription.png", ["Doctor", "Router\n/api/prescriptions", "Database", "Pharmacy\nstaff", "Dispensing\nservice", "Patient"], [
        (0, 1, "POST /prescriptions (items)"),
        (1, 1, "role DOCTOR, patient access, field validation"),
        (1, 2, "save ACTIVE, valid 30 days + audit"),
        (1, 0, "201 prescription RX-nnnnn", True),
        (3, 1, "GET /pharmacy/prescriptions?q="),
        (1, 3, "open prescriptions only", True),
        (3, 4, "POST /pharmacy/dispense (item, quantity)"),
        (4, 2, "lock item, read remaining"),
        (4, 4, "checks: open, remaining >= qty, not expired"),
        (4, 2, "deduct stock (earliest expiry), movement, record"),
        (4, 4, "item and prescription status refreshed"),
        (4, 3, "200 PARTIALLY_DISPENSED / DISPENSED", True),
        (5, 1, "GET /patient/prescriptions"),
        (1, 5, "status and quantities", True),
    ])
    seq("fig_6_15_seq_assistant.png", ["Patient\n(browser)", "Assistant\nrouter", "Safety\nrules", "Intent and\nretrieval", "Database", "Answer\nwriter"], [
        (0, 1, "POST /patient-assistant/chat {message, language}"),
        (1, 1, "patient taken from the token, never from the request"),
        (1, 2, "emergency, medicine change, diagnosis?"),
        ("note", 2, "emergency: fixed guidance and 112, no lookup, no AI"),
        (2, 3, "none: detect intent and test name (EN / HI / MR)"),
        (3, 4, "read only this patient's reviewed records"),
        (4, 3, "values, dates, units, ranges, sources", True),
        (3, 5, "write the answer from the records"),
        (5, 5, "optional AI reword: rejected if any number or safety rule changes"),
        (5, 1, "text + sources + disclaimer", True),
        (1, 4, "store message and evidence pointers; audit (no text)"),
        (1, 0, "200 reply", True),
    ])


# --------------------------------------------------------------------------------------------- activity flow of report pipeline (Fig 7.1)
def pipeline():
    fig, ax = canvas(100, 70)
    steps = [("Upload\n(PDF, image, TXT)", 2), ("Validate: type,\nsize, signature", 22), ("Text layer\nor OCR", 42), ("Clean and\nparse values", 62), ("Classify with the\nprinted range", 82)]
    for t, x in steps:
        box(ax, x, 50, 16, 14, t, fs=5.8)
    for i in range(4):
        arrow(ax, (steps[i][1] + 16, 57), (steps[i + 1][1], 57))
    box(ax, 2, 28, 16, 14, "Reject:\nnothing saved", fs=5.8, ls="--")
    arrow(ax, (10, 50), (10, 42), "invalid or\nno values", fs=5, loff=(7.5, 0))
    box(ax, 82, 28, 16, 14, "Insights:\nstatements, flags,\nsuggestions", fs=5.6)
    arrow(ax, (90, 50), (90, 42))
    box(ax, 62, 28, 16, 14, "Safety filter\n(+ optional LLM\nwording)", fs=5.6)
    arrow(ax, (82, 35), (78, 35))
    box(ax, 42, 28, 16, 14, "Save:\nWAITING_FOR_\nDOCTOR", fs=5.6)
    arrow(ax, (62, 35), (58, 35))
    box(ax, 22, 28, 16, 14, "Doctor review\n(approve / modify /\nclarify)", fs=5.6)
    arrow(ax, (42, 35), (38, 35))
    box(ax, 22, 6, 16, 14, "Patient sees\nreviewed result", fs=5.6)
    arrow(ax, (30, 28), (30, 20))
    box(ax, 54, 6, 44, 14, "Every step writes an audit line; employees and\nadministrators never receive extracted values", fs=5.0, ls="--")
    save(fig, "fig_7_01_report_pipeline.png")


# --------------------------------------------------------------------------------------------- Gantt from git
PHASES = [
    ("Foundation: roles, patients, reports, review,\nprescriptions, pharmacy, dashboards", "2026-10-08", "2026-10-15"),
    ("Pharmacy ERP plan, billing, profiles,\nlab role, SRS document", "2026-10-15", "2026-10-15"),
    ("Health history, emergency card,\nclinical intelligence, assistant", "2026-10-22", "2026-10-22"),
    ("Lab module, past history, hardening,\nvoice assistant, ranked analysis", "2026-10-23", "2026-10-28"),
    ("Red-team bust and its first fixes", "2026-10-28", "2026-10-28"),
    ("Validation rules, department lists,\ntrainee workflow, Rx sheet", "2026-10-31", "2026-10-31"),
    ("HMS phases 1 to 3: audit, foundation,\nclinical workflows", "2026-10-31", "2026-10-31"),
    ("Login redesign, doctor grades, phase 4\n(diagnostics), phase 5 (stock)", "2026-11-01", "2026-11-01"),
    ("HMS phases 5 to 9: blood bank, OT, finance,\nclaims, integrations, OTP, hospital assistant", "2026-11-01", "2026-11-01"),
    ("Phase 10 integration, premium login,\nassistant mobile UX", "2026-11-02", "2026-11-03"),
]


def gantt():
    out = subprocess.run(["git", "log", "--format=%ad", "--date=short"], capture_output=True, text=True, cwd=OUT.parent.parent).stdout.split()
    per_day = {}
    for d in out:
        per_day[d] = per_day.get(d, 0) + 1
    start = date(2026, 10, 7)
    end = date(2026, 11, 5)
    days = (end - start).days
    fig = plt.figure(figsize=(W, 4.6), dpi=300)
    ax = fig.add_axes([0.40, 0.17, 0.585, 0.78])
    n = len(PHASES)
    for i, (name, a, b) in enumerate(PHASES):
        da = (date.fromisoformat(a) - start).days
        db = (date.fromisoformat(b) - start).days + 1
        ax.barh(n - 1 - i, db - da, left=da, height=0.55, color="#555555", edgecolor=INK, lw=0.6)
    ax.set_yticks(range(n)); ax.set_yticklabels([p[0] for p in PHASES][::-1], fontsize=6.0)
    ticks = list(range(0, days + 1, 3))
    ax.set_xticks(ticks); ax.set_xticklabels([(start.fromordinal(start.toordinal() + t)).strftime("%d %b") for t in ticks], fontsize=5.8, rotation=90)
    ax.set_xlim(0, days); ax.grid(axis="x", color="#bbbbbb", lw=0.4); ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax2 = fig.add_axes([0.40, 0.04, 0.585, 0.07])
    ax2.set_xlim(0, days)
    for d, c in per_day.items():
        x = (date.fromisoformat(d) - start).days + 0.5
        ax2.bar(x, c, width=0.8, color="#777777", edgecolor=INK, lw=0.4)
        ax2.text(x, c + 0.3, str(c), ha="center", va="bottom", fontsize=4.8)
    ax2.set_ylim(0, 11); ax2.axis("off")
    fig.text(0.395, 0.065, "Commits\nper day", fontsize=5.2, ha="right", va="center")
    save(fig, "fig_6_16_gantt.png")


if __name__ == "__main__":
    architecture(); dfd0(); dfd1(); usecases(); class_diagram(); er_diagram(); sequences(); pipeline(); gantt()
