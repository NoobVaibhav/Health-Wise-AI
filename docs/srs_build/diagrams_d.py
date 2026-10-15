"""Portrait-friendly class and ER diagrams: each is split in two so that the text stays readable on an A4 portrait page."""
import json
from diagrams_common import *
from diagrams_c import rect_edge

LH = 0.3  # line height


def tbox(ax, x, y, w, title, lines, head=TEAL, fs=9.5, tfs=10.5):
    h = 0.42 + LH * len(lines) + 0.12
    ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, fc="white", ec=head, lw=1.5, zorder=3))
    ax.add_patch(Rectangle((x - w / 2, y + h / 2 - 0.42), w, 0.42, fc=head, ec=head, zorder=4))
    ax.text(x, y + h / 2 - 0.21, title, ha="center", va="center", fontsize=tfs, fontweight="bold", color="white", zorder=5)
    for i, t in enumerate(lines):
        ax.text(x - w / 2 + 0.12, y + h / 2 - 0.42 - 0.06 - LH * (i + 0.55), t, ha="left", va="center", fontsize=fs, color=DARK, zorder=5, family="DejaVu Sans Mono")
    return (x, y, w, h)


def link(ax, a, b, ca="1", cb="N", label=None, hollow=False):
    p = rect_edge(*a, b[0], b[1])
    q = rect_edge(*b, a[0], a[1])
    if hollow:
        ax.add_patch(FancyArrowPatch(q, p, arrowstyle="-|>", mutation_scale=14, lw=1.4, color=DARK, zorder=2))
        return
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-", lw=1.3, color=GRAY, zorder=2))
    for pt, other, txt in ((p, q, ca), (q, p, cb)):
        d = max(((other[0] - pt[0]) ** 2 + (other[1] - pt[1]) ** 2) ** 0.5, 1e-6)
        ax.text(pt[0] + (other[0] - pt[0]) / d * 0.3 + (0.25 if abs(other[0] - pt[0]) < 0.3 else 0), pt[1] + (other[1] - pt[1]) / d * 0.3 + 0.1, txt, fontsize=10, fontweight="bold", color=TEAL, ha="center", va="center", zorder=6, bbox=dict(fc="white", ec="none", pad=0.4))
    if label:
        ax.text((p[0] + q[0]) / 2 + (0.5 if abs(q[0] - p[0]) < 0.3 else 0), (p[1] + q[1]) / 2 + 0.15, label, fontsize=8.5, color="#334155", ha="center", zorder=6, bbox=dict(fc="white", ec="none", pad=0.3))


COL = [1.9, 5.9, 9.9]   # three columns, 4.0 apart (box width 3.4)
BW = 3.4


def er_part(name, cells, links, rows, note):
    schema = json.load(open("D:/helth_wise_AI/docs/srs_build/schema.json"))
    W, H = 11.8, 1.0 + rows * 2.75
    fig, ax = canvas(W, H)
    boxes = {}
    for t, (c, r) in cells.items():
        cols = schema[t]
        keep = [k for k in cols if k["pk"] or k["fk"]]
        other = [k for k in cols if not k["pk"] and not k["fk"]]
        shown = keep[:4] + other[: max(0, 4 - len(keep[:4]))]
        lines = [("PK " if k["pk"] else "FK " if k["fk"] else "   ") + k["name"] for k in shown]
        if len(cols) > len(shown):
            lines.append(f"   ... +{len(cols) - len(shown)} more")
        head = GRAY if t in ("audit_logs", "medicine_inventory", "departments") else TEAL
        boxes[t] = tbox(ax, COL[c] + 0.0, H - 0.3 - 1.2 - r * 2.75, BW, t, lines, head=head)
    for a, b in links:
        link(ax, boxes[a], boxes[b])
    ax.text(W / 2, 0.2, note, ha="center", fontsize=8.5, color=GRAY, style="italic")
    save(fig, name)


def er():
    er_part("er_a.png",
            {"pharmacy_staff": (0, 0), "users": (1, 0), "audit_logs": (2, 0), "doctors": (0, 1), "patients": (1, 1), "employees": (2, 1),
             "departments": (0, 2), "appointments": (1, 2), "medical_history": (2, 2)},
            [("users", "pharmacy_staff"), ("users", "audit_logs"), ("users", "doctors"), ("users", "patients"), ("users", "employees"),
             ("doctors", "patients"), ("departments", "doctors"), ("patients", "appointments"), ("doctors", "appointments"), ("patients", "medical_history")],
            3, "Part 1: people, patients and appointments.  PK = primary key, FK = foreign key.  1 = parent side, N = many side.")
    er_part("er_b.png",
            {"health_parameters": (0, 0), "health_reports": (1, 0), "report_comparisons": (2, 0), "doctor_notes": (0, 1), "prescriptions": (1, 1),
             "doctor_recommendations": (2, 1), "medicine_inventory": (0, 2), "prescription_items": (1, 2), "medicine_dispensing": (2, 2)},
            [("health_reports", "health_parameters"), ("health_reports", "report_comparisons"), ("health_reports", "doctor_notes"), ("health_reports", "prescriptions"),
             ("health_reports", "doctor_recommendations"), ("prescriptions", "prescription_items"), ("prescription_items", "medicine_dispensing")],
            3, "Part 2: reports, doctor's notes, prescriptions and pharmacy.  health_reports, doctor_notes, doctor_recommendations and prescriptions also hold patient_id (see Part 1).")


def cbox(ax, c, r, rows_h, title, attrs, methods, head=TEAL, abstract=False):
    n = len(attrs) + len(methods)
    w = BW
    h = 0.44 + LH * n + 0.25
    x, y = COL[c], rows_h - 0.3 - 1.2 - r * 2.75
    ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, fc="white", ec=head, lw=1.5, zorder=3))
    ax.add_patch(Rectangle((x - w / 2, y + h / 2 - 0.44), w, 0.44, fc=head, ec=head, zorder=4))
    ax.text(x, y + h / 2 - 0.22, title, ha="center", va="center", fontsize=10.5, fontweight="bold", color="white", style="italic" if abstract else "normal", zorder=5)
    top = y + h / 2 - 0.44
    for i, t in enumerate(attrs):
        ax.text(x - w / 2 + 0.12, top - 0.06 - LH * (i + 0.55), t, ha="left", va="center", fontsize=9, color=DARK, zorder=5)
    sep = top - 0.06 - LH * len(attrs) - 0.03
    ax.plot([x - w / 2, x + w / 2], [sep, sep], color=head, lw=1.1, zorder=5)
    for i, t in enumerate(methods):
        ax.text(x - w / 2 + 0.12, sep - 0.04 - LH * (i + 0.55), t, ha="left", va="center", fontsize=9, color="#334155", zorder=5)
    return (x, y, w, h)


def class_part(name, spec, links, rows, note):
    W, H = 11.8, 1.0 + rows * 2.75
    fig, ax = canvas(W, H)
    B = {k: cbox(ax, c, r, H, *rest) for k, (c, r, *rest) in spec.items()}
    for a, b, *opt in links:
        o = opt[0] if opt else {}
        link(ax, B[a], B[b], o.get("ca", "1"), o.get("cb", "N"), o.get("label"), o.get("hollow", False))
    ax.text(W / 2, 0.2, note, ha="center", fontsize=8.5, color=GRAY, style="italic")
    save(fig, name)


def classes():
    h = {"hollow": True}
    class_part("class_a.png", {
        "Audit": (1, 0, "AuditLog", ["user_id, action", "entity_type, timestamp"], ["write()"], GRAY),
        "Admin": (0, 1, "Admin (role)", ["role = ADMIN"], ["create_staff()", "view_audit_log()"], GRAY),
        "User": (1, 1, "User", ["email, full_name", "password_hash, role, is_active"], ["verify_password()", "issue_token()"], TEAL, True),
        "Employee": (2, 1, "Employee", ["designation, phone"], ["register_patient()", "upload_report()"]),
        "Doctor": (0, 2, "Doctor", ["specialization, phone", "department_id"], ["review_report()", "add_note()", "prescribe()"]),
        "Patient": (1, 2, "Patient", ["patient_code, date_of_birth", "gender, blood_group", "assigned_doctor_id"], ["view_released_report()", "view_timeline()"]),
        "Pharmacy": (2, 2, "PharmacyStaff", ["pharmacy_name, phone"], ["dispense()", "update_stock()"]),
        "Appt": (1, 3, "Appointment", ["scheduled_at, reason", "status"], ["confirm()", "cancel()", "complete()"]),
    }, [("User", "Audit", {"label": "writes"}), ("User", "Admin", h), ("User", "Employee", h), ("User", "Doctor", h), ("User", "Patient", h), ("User", "Pharmacy", h),
        ("Patient", "Appt", {"label": "books"}), ("Doctor", "Appt")],
        4, "Part 1: people and roles.  Hollow arrow = inheritance (role).  1 / N = one / many.")
    class_part("class_b.png", {
        "Param": (0, 0, "HealthParameter", ["test_name, value, unit", "reference_low, reference_high", "status"], ["classify()"]),
        "Report": (1, 0, "HealthReport", ["filename, report_type", "processing_status", "extracted_text, insights_json", "uploaded_by, reviewed_by"], ["process()", "refresh_insights()", "mark_reviewed()"]),
        "Note": (2, 0, "DoctorNote / Advice", ["note, recommendation", "priority, follow_up_date"], ["add()", "edit()"]),
        "Rx": (1, 1, "Prescription", ["prescription_date, status", "patient_id, doctor_id"], ["add_item()", "refresh_status()"]),
        "Item": (1, 2, "PrescriptionItem", ["medicine_name, dosage", "frequency, quantity", "dispense_status"], ["remaining()"]),
        "Disp": (2, 2, "MedicineDispensing", ["quantity_dispensed, status", "pharmacy_staff_id", "dispensed_at"], ["record()"]),
        "Stock": (2, 1, "MedicineInventory", ["medicine_name, quantity", "batch_number, expiry_date"], ["reduce()"], GRAY),
    }, [("Report", "Param", {"label": "contains"}), ("Report", "Note"), ("Report", "Rx"), ("Rx", "Item", {"label": "lists"}), ("Item", "Disp"),
        ("Disp", "Stock", {"ca": "N", "cb": "1", "label": "lowers"})],
        3, "Part 2: reports, advice, prescriptions and pharmacy.  1 / N = one / many.")


if __name__ == "__main__":
    er()
    classes()
