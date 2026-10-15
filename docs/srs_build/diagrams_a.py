"""Use case diagram, context diagram, DFD level 0 and DFD level 1 (clean layouts, no crossing labels)."""
from diagrams_common import *

ENT = dict(fc=GREEN, ec="#2f855a")
EXT = dict(fc=VIOLET, ec="#6b46c1")


def process(ax, x, y, w, h, code, text, fs=7.2):
    """DFD process: rounded box with the process number in a header strip."""
    box(ax, x, y, w, h, "", fc=TEAL_LIGHT, ec=TEAL, lw=1.5)
    ax.plot([x - w / 2, x + w / 2], [y + h / 2 - 0.26, y + h / 2 - 0.26], color=TEAL, lw=1.0, zorder=4)
    ax.text(x, y + h / 2 - 0.13, code, ha="center", va="center", fontsize=7.5, fontweight="bold", color=TEAL, zorder=5)
    ax.text(x, y - 0.1, text, ha="center", va="center", fontsize=fs, color=DARK, zorder=5, linespacing=1.2)


def store(ax, x, y, w, text, fs=6.8):
    """DFD data store: two parallel lines with the name between them."""
    ax.add_patch(Rectangle((x - w / 2, y - 0.16), w, 0.32, fc="white", ec="none", zorder=2))
    ax.plot([x - w / 2, x + w / 2], [y + 0.16, y + 0.16], color=DARK, lw=1.4, zorder=3)
    ax.plot([x - w / 2, x + w / 2], [y - 0.16, y - 0.16], color=DARK, lw=1.4, zorder=3)
    ax.text(x, y, text, ha="center", va="center", fontsize=fs, color=DARK, zorder=4)


def use_case():
    """One column of use cases; every actor has its own coloured line that runs down a lane and branches into its use cases."""
    fig, ax = canvas(7.6, 10.7)
    colors = {"Admin": "#dd6b20", "Employee": "#2b6cb0", "Doctor": "#2f855a", "Patient": "#c53030", "Pharmacy staff": "#6b46c1"}
    lanes = {"Admin": 1.5, "Employee": 1.8, "Doctor": 2.1, "Patient": 2.4, "Pharmacy staff": 2.7}
    ex, ew, eh = 5.3, 3.5, 0.5
    ax.add_patch(Rectangle((3.2, 0.2), 4.2, 10.3, fc="#fbfeff", ec=TEAL, lw=1.6, zorder=0))
    ax.text(5.3, 10.25, "HealthWise AI", ha="center", va="center", fontsize=10.5, fontweight="bold", color=TEAL)

    # the three use cases shared by every actor
    ax.add_patch(Rectangle((3.35, 8.35), 3.9, 1.72, fc="#f1f5f9", ec="#94a3b8", lw=1, ls="--", zorder=1))
    ax.text(5.3, 9.93, "Used by all five actors", ha="center", fontsize=6.8, color=GRAY, style="italic")
    for y, t in ((9.55, "UC-01  Log in"), (9.1, "UC-02  Change password"), (8.65, "UC-17  View dashboard")):
        ellipse(ax, ex, y, 2.6, 0.36, t, fs=6.8, fc=TEAL_LIGHT)

    uses = [
        ("UC-03", "Manage staff accounts", ["Admin"]), ("UC-16", "View activity log", ["Admin"]),
        ("UC-04", "Register patient", ["Admin", "Employee"]), ("UC-06", "Upload report", ["Employee", "Doctor"]),
        ("UC-05", "Manage appointments", ["Admin", "Employee", "Doctor", "Patient"]),
        ("UC-08", "Review report", ["Doctor"]), ("UC-07", "View insights and suggestions", ["Doctor"]),
        ("UC-09", "Write notes and advice", ["Doctor"]), ("UC-10", "Create prescription", ["Doctor"]),
        ("UC-15", "Compare reports and trends", ["Doctor", "Patient"]), ("UC-14", "View health timeline", ["Doctor", "Patient"]),
        ("UC-13", "View reviewed report and tips", ["Patient"]), ("UC-11", "Dispense medicine", ["Pharmacy staff"]),
        ("UC-12", "Manage medicine stock", ["Pharmacy staff"]),
    ]
    ys = [8.0 - 0.57 * i for i in range(len(uses))]
    stubs = {a: [] for a in lanes}
    for (code, text, who), y in zip(uses, ys):
        ellipse(ax, ex, y, ew, eh, f"{code}  {text}", fs=7)
        for a in who:
            stubs[a].append(y)
    actor_y = {"Admin": 7.6, "Employee": 6.3, "Doctor": 4.4, "Patient": 2.6, "Pharmacy staff": 1.0}
    for a, lx in lanes.items():
        ay, c = actor_y[a], colors[a]
        actor(ax, 0.6, ay - 0.1, a.replace(" staff", "\nstaff"))
        ys_a = stubs[a] + [ay]
        ax.plot([0.85, lx], [ay, ay], color=c, lw=1.6, zorder=2)
        ax.plot([lx, lx], [min(ys_a), max(ys_a)], color=c, lw=1.6, zorder=2)
        for y in stubs[a]:
            ax.plot([lx, ex - ew / 2 + 0.02], [y, y], color=c, lw=1.2, zorder=1)
            ax.add_patch(Circle((lx, y), 0.045, fc=c, ec=c, zorder=3))
    save(fig, "use_case.png")


def context():
    """Level-0 view: one process in the middle, every external party with one arrow in and one arrow out."""
    fig, ax = canvas(9.6, 7.8)
    box(ax, 4.8, 3.9, 1.9, 7.2, "HealthWise AI\nSystem", fc=TEAL_LIGHT, ec=TEAL, fs=11, bold=True, lw=2.2, round_=0.2)
    left = [("Admin", 6.6, "staff details,\nuser status", "statistics,\nactivity log"),
            ("Employee\n(reception)", 3.9, "patient details, reports,\nappointments", "upload status,\nappointment list"),
            ("Pharmacy staff", 1.2, "dispensing entries,\nstock updates", "prescriptions,\nstock alerts")]
    right = [("Doctor", 6.9, "review, notes, advice,\nprescriptions", "reports, insights,\npatient history"),
             ("Patient", 5.1, "view and booking\nrequests", "reviewed reports, tips,\nmedicines, timeline"),
             ("OCR engine\n(Tesseract)", 3.3, "page images", "recognised text"),
             ("AI model\n(optional)", 1.5, "report text, personal\ndetails removed", "draft suggestions")]
    for name, y, out, inn in left:
        kw = ENT
        box(ax, 0.95, y, 1.6, 0.8, name, fs=8, bold=True, **kw)
        arrow(ax, (1.75, y + 0.2), (3.85, y + 0.2), out, color=TEAL, loff=(0, 0.27), lw=1.3)
        arrow(ax, (3.85, y - 0.2), (1.75, y - 0.2), inn, color="#2f855a", loff=(0, -0.27), lw=1.3)
    for name, y, out, inn in right:
        kw = EXT if "OCR" in name or "AI" in name else ENT
        box(ax, 8.65, y, 1.6, 0.8, name, fs=8, bold=True, **kw)
        # entity -> system on the upper arrow, system -> entity on the lower arrow
        if "OCR" in name or "AI" in name:   # for external services the system calls them first
            arrow(ax, (5.75, y + 0.2), (7.85, y + 0.2), out, color=TEAL, loff=(0, 0.27), lw=1.3)
            arrow(ax, (7.85, y - 0.2), (5.75, y - 0.2), inn, color="#2f855a", loff=(0, -0.27), lw=1.3)
        else:
            arrow(ax, (7.85, y + 0.2), (5.75, y + 0.2), out, color=TEAL, loff=(0, 0.27), lw=1.3)
            arrow(ax, (5.75, y - 0.2), (7.85, y - 0.2), inn, color="#2f855a", loff=(0, -0.27), lw=1.3)
    save(fig, "context.png")


def dfd0():
    """Process -> data store -> next process, top to bottom. Entities at the sides."""
    fig, ax = canvas(9.8, 11.0)
    px, pw, ph = 4.9, 3.2, 0.9
    P = {"1.0": (10.1, "Authenticate and\nmanage users"), "2.0": (8.4, "Register patients and\nbook appointments"),
         "3.0": (6.7, "Process and analyse\nreports"), "4.0": (5.0, "Doctor review, notes,\nadvice, prescriptions"),
         "5.0": (3.3, "Pharmacy dispensing\nand stock"), "6.0": (1.6, "History, comparison\nand dashboards")}
    S = {"D1": (9.25, "D1  Users"), "D2": (7.55, "D2  Patients, appointments"), "D3": (5.85, "D3  Reports, results, insights"),
         "D4": (4.15, "D4  Notes, advice, prescriptions"), "D5": (2.45, "D5  Medicine stock, dispensing")}
    for code, (y, t) in P.items():
        process(ax, px, y, pw, ph, code, t)
    for code, (y, t) in S.items():
        store(ax, px, y, 2.9, t)
    # entities
    box(ax, 1.0, 10.1, 1.5, 0.65, "Admin", fs=8, bold=True, **ENT)
    box(ax, 1.0, 7.55, 1.5, 0.65, "Employee", fs=8, bold=True, **ENT)
    box(ax, 1.0, 3.3, 1.5, 0.65, "Pharmacy\nstaff", fs=8, bold=True, **ENT)
    box(ax, 8.8, 5.9, 1.5, 0.65, "Doctor", fs=8, bold=True, **ENT)
    box(ax, 8.8, 1.6, 1.5, 0.65, "Patient", fs=8, bold=True, **ENT)
    A = lambda p, q, t=None, **k: arrow(ax, p, q, t, color=k.pop("color", GRAY), **k)
    # process <-> store (short vertical arrows)
    for (py, sy) in ((10.1, 9.25), (8.4, 7.55), (6.7, 5.85), (5.0, 4.15), (3.3, 2.45)):
        A((px - 0.35, py - ph / 2), (px - 0.35, sy + 0.17), None)
        A((px + 0.35, sy + 0.17), (px + 0.35, py - ph / 2), None)
    # flows through the stores to the next process
    A((px - 0.35, 7.55 - 0.17), (px - 0.35, 6.7 + ph / 2), None)
    A((px - 0.35, 5.85 - 0.17), (px - 0.35, 5.0 + ph / 2), "reports waiting\nfor review", loff=(-0.95, 0.0), ha="center")
    A((px - 0.35, 4.15 - 0.17), (px - 0.35, 3.3 + ph / 2), "prescriptions to fill", loff=(-1.1, 0.0))
    A((px - 0.35, 2.45 - 0.17), (px - 0.35, 1.6 + ph / 2), None)
    # entities <-> processes
    A((1.75, 10.15), (px - pw / 2, 10.15), "staff details, login", loff=(0, 0.2))
    A((px - pw / 2, 10.0), (1.75, 10.0), "statistics, activity log", loff=(0, -0.2))
    A((1.75, 7.7), (px - pw / 2, 8.3), "patients, appointments", loff=(-0.1, 0.22), rad=-0.05)
    A((1.75, 7.45), (px - pw / 2, 6.8), "report files", loff=(0.0, -0.22), rad=0.05)
    A((px + pw / 2, 6.8), (8.05, 6.1), "reports, insights", loff=(0.1, 0.25))
    A((8.05, 5.75), (px + pw / 2, 5.0), "review, notes,\nadvice, prescriptions", loff=(0.55, -0.22))
    A((1.75, 3.45), (px - pw / 2, 3.45), "dispensing entries", loff=(0, 0.2))
    A((px - pw / 2, 3.15), (1.75, 3.15), "prescriptions, stock alerts", loff=(0, -0.2))
    A((px + pw / 2, 1.6), (8.05, 1.6), "timeline, tips,\nmedicines", loff=(0, 0.28))
    A((8.05, 1.45), (px + pw / 2, 1.45), "view requests", loff=(0, -0.2))
    ax.text(4.9, 0.55, "Process 6.0 reads the data stores D2 to D5. Every process writes an audit entry (not drawn, to keep the diagram readable).", ha="center", fontsize=6.2, color=GRAY, style="italic")
    save(fig, "dfd0.png")


def dfd1():
    """Process 3.0 expanded into six sub-processes, drawn as a snake: top row left to right, bottom row right to left."""
    fig, ax = canvas(9.8, 7.4)
    w, h = 1.9, 1.05
    xs = [3.0, 5.4, 7.8]
    top, bot = 5.4, 2.9
    steps = {"3.1": (xs[0], top, "Validate file\n(type, size, content)"), "3.2": (xs[1], top, "Extract text\n(PDF text or OCR)"),
             "3.3": (xs[2], top, "Clean text and\nparse values"), "3.4": (xs[2], bot, "Classify values with\nprinted ranges"),
             "3.5": (xs[1], bot, "Build insights\n(rules, optional AI)"), "3.6": (xs[0], bot, "Save report for\ndoctor review")}
    for code, (x, y, t) in steps.items():
        process(ax, x, y, w, h, code, t, fs=6.8)
    box(ax, 0.8, top, 1.15, 0.7, "Employee /\nDoctor", fs=7.2, bold=True, **ENT)
    box(ax, 0.8, bot, 1.15, 0.7, "Doctor", fs=7.5, bold=True, **ENT)
    box(ax, xs[1], 7.0, 1.9, 0.6, "OCR engine", fs=7.5, bold=True, **EXT)
    box(ax, xs[1], 0.95, 1.9, 0.6, "AI model (optional)", fs=7.5, bold=True, **EXT)
    box(ax, xs[0], 7.0, 1.9, 0.6, "Error message to user", fs=7, fc="#fdecec", ec="#c53030")
    store(ax, xs[0], 0.95, 2.3, "D3  Reports, results, insights")
    A = lambda p, q, t=None, **k: arrow(ax, p, q, t, color=k.pop("color", GRAY), **k)
    A((1.5, top), (xs[0] - w / 2, top), "file", loff=(0, 0.2))
    A((xs[0] + w / 2, top), (xs[1] - w / 2, top), "valid file", loff=(0, 0.2))
    A((xs[1] + w / 2, top), (xs[2] - w / 2, top), "text", loff=(0, 0.2))
    A((xs[2], top - h / 2), (xs[2], bot + h / 2), "values,\nunits, ranges", loff=(0.62, 0.0))
    A((xs[2] - w / 2, bot), (xs[1] + w / 2, bot), "statuses", loff=(0, 0.2))
    A((xs[1] - w / 2, bot), (xs[0] + w / 2, bot), "insights", loff=(0, 0.2))
    A((xs[0] - w / 2, bot), (1.5, bot), "for review", loff=(0, 0.22))
    A((xs[0], top + h / 2), (xs[0], 6.7), "rejected", loff=(0.42, 0.0), color="#c53030", ls="--")
    A((xs[1] - 0.4, top + h / 2), (xs[1] - 0.4, 6.7), "page images", loff=(-0.75, 0.0), ls="--")
    A((xs[1] + 0.4, 6.7), (xs[1] + 0.4, top + h / 2), "recognised\ntext", loff=(0.7, 0.0), ls="--")
    A((xs[1] - 0.4, bot - h / 2), (xs[1] - 0.4, 1.25), "redacted text", loff=(-0.78, 0.0), ls="--")
    A((xs[1] + 0.4, 1.25), (xs[1] + 0.4, bot - h / 2), "draft\nsuggestions", loff=(0.68, 0.0), ls="--")
    A((xs[0], bot - h / 2), (xs[0], 1.12), "report, results,\ninsights", loff=(-0.95, 0.0))
    ax.text(4.9, 0.25, "Process 3.0 of the Level 0 diagram, expanded. Dashed lines: optional OCR / AI exchanges and the error path (any of steps 3.1 to 3.5 can reject a file, and then nothing is saved).", ha="center", fontsize=6.2, color=GRAY, style="italic")
    save(fig, "dfd1.png")


if __name__ == "__main__":
    use_case()
    context()
    dfd0()
    dfd1()
