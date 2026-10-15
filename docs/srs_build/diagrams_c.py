"""Class diagram and ER diagram (landscape)."""
import json
from diagrams_common import *

LINE_H = 0.25


def rect_edge(cx, cy, w, h, tx, ty):
    """Point where the line from the centre (cx, cy) towards (tx, ty) leaves the rectangle."""
    dx, dy = tx - cx, ty - cy
    if dx == 0 and dy == 0:
        return cx, cy
    sx = (w / 2) / abs(dx) if dx else 1e9
    sy = (h / 2) / abs(dy) if dy else 1e9
    s = min(sx, sy)
    return cx + dx * s, cy + dy * s


def table_box(ax, x, y, w, title, lines, head=TEAL, fs=8):
    """Box with a coloured title bar and one line per entry. (x, y) is the centre; returns (x, y, w, h)."""
    h = 0.3 + LINE_H * len(lines) + 0.1
    ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, fc="white", ec=head, lw=1.3, zorder=3))
    ax.add_patch(Rectangle((x - w / 2, y + h / 2 - 0.3), w, 0.3, fc=head, ec=head, zorder=4))
    ax.text(x, y + h / 2 - 0.15, title, ha="center", va="center", fontsize=9.2, fontweight="bold", color="white", zorder=5)
    for i, t in enumerate(lines):
        ax.text(x - w / 2 + 0.1, y + h / 2 - 0.3 - 0.05 - LINE_H * (i + 0.55), t, ha="left", va="center", fontsize=fs, color=DARK, zorder=5, family="DejaVu Sans Mono")
    return (x, y, w, h)


def link(ax, a, b, ca="1", cb="N", color=GRAY, rad=0.0):
    p = rect_edge(*a, b[0], b[1])
    q = rect_edge(*b, a[0], a[1])
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-", lw=1.0, color=color, connectionstyle=f"arc3,rad={rad}", zorder=2))
    for pt, other, txt in ((p, q, ca), (q, p, cb)):
        t = 0.16 / max(((other[0] - pt[0]) ** 2 + (other[1] - pt[1]) ** 2) ** 0.5, 1e-6)
        ax.text(pt[0] + (other[0] - pt[0]) * t * 1.6, pt[1] + (other[1] - pt[1]) * t * 1.6 + 0.08, txt, fontsize=7, fontweight="bold", color=TEAL, ha="center", va="center", zorder=6,
                bbox=dict(fc="white", ec="none", pad=0.4))


def er():
    schema = json.load(open("D:/helth_wise_AI/docs/srs_build/schema.json"))
    W, H = 17.4, 13.8
    fig, ax = canvas(W, H)
    pos = {
        "departments": (2.0, 12.5), "users": (8.0, 12.5), "audit_logs": (13.2, 12.5),
        "doctors": (2.0, 9.6), "patients": (5.5, 9.6), "employees": (9.0, 9.6), "pharmacy_staff": (12.5, 9.6),
        "appointments": (2.0, 6.6), "health_reports": (5.5, 6.6), "medical_history": (12.5, 6.6),
        "health_parameters": (1.7, 3.9), "doctor_notes": (5.2, 3.9), "doctor_recommendations": (8.7, 3.9), "report_comparisons": (12.2, 3.9), "prescriptions": (15.7, 3.9),
        "medicine_inventory": (5.2, 1.2), "medicine_dispensing": (12.2, 1.2), "prescription_items": (15.7, 1.2),
    }
    links = [("users", "audit_logs"), ("users", "doctors"), ("users", "patients"), ("users", "employees"), ("users", "pharmacy_staff"),
             ("departments", "doctors"), ("doctors", "patients"), ("patients", "appointments"), ("doctors", "appointments"),
             ("patients", "health_reports"), ("patients", "medical_history"),
             ("health_reports", "health_parameters"), ("health_reports", "doctor_notes"), ("health_reports", "doctor_recommendations"),
             ("health_reports", "report_comparisons"), ("health_reports", "prescriptions"),
             ("prescriptions", "prescription_items"), ("prescription_items", "medicine_dispensing")]
    boxes = {}
    for name, (x, y) in pos.items():
        if y > 5.0:
            x += 0.9
        cols = schema[name]
        keep = [c for c in cols if c["pk"] or c["fk"]]
        other = [c for c in cols if not c["pk"] and not c["fk"]]
        shown = keep[:4] + other[: max(0, 4 - len(keep[:4]))]
        lines = []
        for c in shown:
            tag = "PK" if c["pk"] else ("FK" if c["fk"] else "  ")
            lines.append(f"{tag} {c['name']}")
        if len(cols) > len(shown):
            lines.append(f"   ... +{len(cols) - len(shown)} more")
        head = TEAL if name not in ("audit_logs", "medicine_inventory", "departments") else GRAY
        boxes[name] = table_box(ax, x, y, 3.2, name, lines, head=head)
    for p, c in links:
        link(ax, boxes[p], boxes[c])
    ax.text(W / 2, 0.12, "PK = primary key, FK = foreign key.  1 = parent side, N = many side.  Main relationships only; every column is listed in the data dictionary.", ha="center", fontsize=7, color=GRAY, style="italic")
    save(fig, "er.png")


def class_box(ax, x, y, w, title, attrs, methods, head=TEAL, abstract=False):
    n = len(attrs) + len(methods)
    h = 0.38 + LINE_H * (len(attrs) + len(methods)) + 0.2
    ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, fc="white", ec=head, lw=1.3, zorder=3))
    ax.add_patch(Rectangle((x - w / 2, y + h / 2 - 0.38), w, 0.38, fc=head, ec=head, zorder=4))
    ax.text(x, y + h / 2 - 0.19, title, ha="center", va="center", fontsize=9, fontweight="bold", color="white", style="italic" if abstract else "normal", zorder=5)
    top = y + h / 2 - 0.38
    for i, t in enumerate(attrs):
        ax.text(x - w / 2 + 0.1, top - 0.05 - LINE_H * (i + 0.55), t, ha="left", va="center", fontsize=7.6, color=DARK, zorder=5)
    sep = top - 0.05 - LINE_H * len(attrs) - 0.02
    ax.plot([x - w / 2, x + w / 2], [sep, sep], color=head, lw=0.9, zorder=5)
    for i, t in enumerate(methods):
        ax.text(x - w / 2 + 0.1, sep - 0.03 - LINE_H * (i + 0.55), t, ha="left", va="center", fontsize=7.6, color="#334155", zorder=5)
    return (x, y, w, h)


def uml_link(ax, a, b, ma="", mb="", kind="assoc", label=None):
    p = rect_edge(*a, b[0], b[1])
    q = rect_edge(*b, a[0], a[1])
    if kind == "inherit":
        ax.add_patch(FancyArrowPatch(q, p, arrowstyle="-|>", mutation_scale=12, lw=1.1, color=DARK, fc="white", zorder=2))
    else:
        ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-", lw=1.0, color=GRAY, zorder=2))
    for pt, other, txt in ((p, q, ma), (q, p, mb)):
        if not txt:
            continue
        d = max(((other[0] - pt[0]) ** 2 + (other[1] - pt[1]) ** 2) ** 0.5, 1e-6)
        ax.text(pt[0] + (other[0] - pt[0]) / d * 0.28, pt[1] + (other[1] - pt[1]) / d * 0.28 + 0.1, txt, fontsize=6.8, color=TEAL, fontweight="bold", ha="center", zorder=6,
                bbox=dict(fc="white", ec="none", pad=0.3))
    if label:
        ax.text((p[0] + q[0]) / 2, (p[1] + q[1]) / 2 + 0.12, label, fontsize=6.2, color="#334155", ha="center", zorder=6, bbox=dict(fc="white", ec="none", pad=0.3))


def classes():
    W, H = 15.0, 12.6
    fig, ax = canvas(W, H)
    B = {}
    w = 2.9
    B["User"] = class_box(ax, 7.5, 11.2, w, "User", ["email, full_name", "password_hash, role, is_active"], ["verify_password()", "issue_token()"], abstract=True)
    B["Admin"] = class_box(ax, 1.6, 11.5, 2.6, "Admin (role)", ["role = ADMIN"], ["create_staff()", "manage_departments()", "view_audit_log()"], head=GRAY)
    B["Employee"] = class_box(ax, 12.9, 11.6, 2.6, "Employee", ["designation", "phone"], ["register_patient()", "upload_report()", "book_appointment()"])
    B["Doctor"] = class_box(ax, 4.45, 7.6, w, "Doctor", ["specialization, phone", "department_id"], ["review_report()", "add_note()", "recommend()", "prescribe()"])
    B["Patient"] = class_box(ax, 7.5, 8.3, w, "Patient", ["patient_code, date_of_birth", "gender, blood_group, phone", "assigned_doctor_id"], ["view_released_report()", "view_timeline()", "compare_reports()"])
    B["Pharmacy"] = class_box(ax, 12.2, 8.6, 2.9, "PharmacyStaff", ["pharmacy_name", "phone"], ["open_prescription()", "dispense()", "update_stock()"])
    B["Report"] = class_box(ax, 7.5, 5.0, 3.3, "HealthReport", ["filename, report_type, processing_status", "extracted_text, insights_json", "uploaded_by, reviewed_by"], ["process()", "refresh_insights()", "mark_reviewed()"])
    B["Param"] = class_box(ax, 2.8, 5.0, 2.9, "HealthParameter", ["test_name, value, unit", "reference_low, reference_high", "status (WITHIN/ABOVE/BELOW)"], ["classify()"])
    B["Appt"] = class_box(ax, 12.4, 5.7, 2.9, "Appointment", ["scheduled_at, reason", "status, patient_id, doctor_id"], ["confirm()", "cancel()", "complete()"])
    B["Note"] = class_box(ax, 1.9, 1.9, 2.6, "DoctorNote /\nRecommendation", ["note / recommendation, priority", "report_id, doctor_id"], ["add()", "edit()"])
    B["Rx"] = class_box(ax, 5.2, 1.7, 2.8, "Prescription", ["prescription_date, status", "patient_id, doctor_id"], ["add_item()", "refresh_status()"])
    B["Item"] = class_box(ax, 8.9, 1.7, 2.8, "PrescriptionItem", ["medicine_name, dosage", "frequency, quantity", "dispense_status"], ["remaining()"])
    B["Disp"] = class_box(ax, 12.5, 1.9, 2.8, "MedicineDispensing", ["quantity_dispensed, status", "pharmacy_staff_id, dispensed_at"], ["record()"])
    B["Stock"] = class_box(ax, 12.5, 3.7, 2.5, "MedicineInventory", ["medicine_name, quantity", "batch_number, expiry_date"], ["reduce()"], head=GRAY)
    B["Audit"] = class_box(ax, 1.6, 9.4, 2.4, "AuditLog", ["user_id, action", "entity_type, timestamp"], ["write()"], head=GRAY)
    for k in ("Doctor", "Patient", "Pharmacy", "Employee", "Admin"):
        uml_link(ax, B[k], B["User"], kind="inherit")
    uml_link(ax, B["Patient"], B["Report"], "1", "N", label="has")
    uml_link(ax, B["Report"], B["Param"], "1", "N", label="contains")
    uml_link(ax, B["Doctor"], B["Report"], "1", "N", label="reviews")
    uml_link(ax, B["Patient"], B["Appt"], "1", "N", label="books")
    uml_link(ax, B["Report"], B["Note"], "1", "N")
    uml_link(ax, B["Report"], B["Rx"], "1", "N")
    uml_link(ax, B["Rx"], B["Item"], "1", "N", label="lists")
    uml_link(ax, B["Item"], B["Disp"], "1", "N")
    uml_link(ax, B["Disp"], B["Stock"], "N", "1")
    uml_link(ax, B["Admin"], B["Audit"], "1", "N")
    ax.text(W / 2, 0.2, "Arrow with a hollow head = inheritance (role).  1 / N = one / many.", ha="center", fontsize=7, color=GRAY, style="italic")
    save(fig, "class.png")


if __name__ == "__main__":
    er()
    classes()
