"""Activity diagram (swimlanes) and sequence diagram."""
from diagrams_common import *


def start(ax, x, y):
    ax.add_patch(Circle((x, y), 0.13, fc=DARK, ec=DARK, zorder=4))


def end(ax, x, y):
    ax.add_patch(Circle((x, y), 0.17, fc="white", ec=DARK, lw=1.6, zorder=4))
    ax.add_patch(Circle((x, y), 0.1, fc=DARK, ec=DARK, zorder=5))


def activity():
    """Upload report -> analysis -> doctor review -> patient result -> pharmacy, in swimlanes."""
    fig, ax = canvas(9.6, 12.4)
    lanes = [("Employee", 1.2), ("System", 3.7), ("Doctor", 6.2), ("Patient", 8.1), ("Pharmacy", 9.1)]
    lanes = [("Employee", 0.0, 2.0), ("System", 2.0, 5.5), ("Doctor", 5.5, 7.7), ("Patient", 7.7, 8.8), ("Pharmacy", 8.8, 9.6)]
    # horizontal lanes would need a wide figure, so use vertical swimlanes instead
    ax.clear()
    ax.set_xlim(0, 9.6)
    ax.set_ylim(0, 12.4)
    ax.axis("off")
    ax.set_aspect("equal")
    cols = [("Employee", 0.2, 2.15), ("System", 2.15, 5.1), ("Doctor", 5.1, 7.15), ("Patient", 7.15, 8.4), ("Pharmacy", 8.4, 9.5)]
    for name, x0, x1 in cols:
        ax.add_patch(Rectangle((x0, 0.2), x1 - x0, 11.9, fc="#fbfeff", ec=TEAL, lw=1.2, zorder=0))
        ax.add_patch(Rectangle((x0, 11.5), x1 - x0, 0.6, fc=TEAL, ec=TEAL, zorder=1))
        ax.text((x0 + x1) / 2, 11.8, name, ha="center", va="center", fontsize=9, fontweight="bold", color="white", zorder=2)
    cx = {n: (a + b) / 2 for n, a, b in cols}
    cw = {n: b - a - 0.25 for n, a, b in cols}

    def act(lane, y, text, h=0.62, fc=TEAL_LIGHT, fs=6.8):
        box(ax, cx[lane], y, cw[lane], h, text, fc=fc, fs=fs)
        return (cx[lane], y)

    A = lambda p, q, t=None, **k: arrow(ax, p, q, t, color=k.pop("color", DARK), **k)

    start(ax, cx["Employee"], 11.1)
    a1 = act("Employee", 10.45, "Log in and open\n'Upload report'")
    a2 = act("Employee", 9.4, "Choose the patient\n(and doctor if needed)")
    a3 = act("Employee", 8.35, "Add the report file\n(PDF / photo / text)")
    A((cx["Employee"], 11.0), (cx["Employee"], 10.76)); A((cx["Employee"], 10.14), (cx["Employee"], 9.71))
    A((cx["Employee"], 9.09), (cx["Employee"], 8.66))

    s1 = act("System", 8.35, "Check file type,\nsize and content")
    d1 = (cx["System"], 7.3)
    diamond(ax, d1[0], d1[1], 2.2, 0.85, "File valid?", fs=6.8)
    A((cx["Employee"] + cw["Employee"] / 2, 8.35), (cx["System"] - cw["System"] / 2, 8.35), "upload", loff=(0, 0.22))
    A((cx["System"], 8.04), (cx["System"], 7.73))
    s_err = act("Employee", 7.3, "Read the clear error\nmessage (nothing saved)", fc="#fdecec")
    A((d1[0] - 1.1, d1[1]), (cx["Employee"] + cw["Employee"] / 2, 7.3), "No", color="#c53030")
    s2 = act("System", 6.35, "PDF text, or OCR for\nscans and photos")
    A((d1[0], d1[1] - 0.43), (d1[0], 6.66), "Yes", loff=(0.2, 0.0))
    s3 = act("System", 5.45, "Clean text, find lab\nvalues and ranges")
    A((cx["System"], 6.04), (cx["System"], 5.76))
    d2 = (cx["System"], 4.45)
    diamond(ax, d2[0], d2[1], 2.4, 0.9, "Lab values\nor medical text?", fs=6.6)
    A((cx["System"], 5.14), (cx["System"], 4.9))
    s_rej = act("Employee", 4.45, "Told: not a medical\nreport (nothing saved)", fc="#fdecec")
    A((d2[0] - 1.2, d2[1]), (cx["Employee"] + cw["Employee"] / 2, 4.45), "Neither", color="#c53030")
    s4 = act("System", 3.4, "Classify with printed ranges\nor read the wording;\nwrite suggestions", h=0.8)
    A((d2[0], d2[1] - 0.45), (d2[0], 3.8), "Yes", loff=(0.2, 0.0))
    s5 = act("System", 2.3, "Save report:\n'Waiting for doctor'")
    A((cx["System"], 3.0), (cx["System"], 2.61))

    dr1 = act("Doctor", 2.3, "Open report: read\nsummary, suggestions,\nhistory and trends", h=0.85)
    A((cx["System"] + cw["System"] / 2, 2.3), (cx["Doctor"] - cw["Doctor"] / 2, 2.3), "on dashboard", loff=(0, 0.22))
    dr2 = act("Doctor", 3.4, "Approve / change /\nexplain the analysis")
    A((cx["Doctor"], 2.73), (cx["Doctor"], 3.09))
    dr3 = act("Doctor", 4.45, "Add notes, advice\nand prescription\n(optional)", h=0.8)
    A((cx["Doctor"], 3.71), (cx["Doctor"], 4.05))
    dr4 = act("Doctor", 5.55, "Mark report\n'Checked by doctor'")
    A((cx["Doctor"], 4.85), (cx["Doctor"], 5.24))

    pt = act("Patient", 5.55, "Sees summary,\ntips, doctor's\nadvice", h=0.85)
    A((cx["Doctor"] + cw["Doctor"] / 2, 5.55), (cx["Patient"] - cw["Patient"] / 2, 5.55), "released", loff=(0, 0.22))
    ph1 = act("Pharmacy", 4.45, "Open prescription\nand dispense")
    A((cx["Doctor"] + cw["Doctor"] / 2, 4.45), (cx["Pharmacy"] - cw["Pharmacy"] / 2, 4.45), "if prescribed")
    ph2 = act("Pharmacy", 3.4, "Record quantity,\nstock goes down")
    A((cx["Pharmacy"], 4.14), (cx["Pharmacy"], 3.71))
    pt2 = act("Patient", 3.4, "Sees medicine\nstatus", h=0.6)
    A((cx["Pharmacy"] - cw["Pharmacy"] / 2, 3.4), (cx["Patient"] + cw["Patient"] / 2, 3.4))
    end(ax, cx["Patient"], 2.35)
    A((cx["Patient"], 3.1), (cx["Patient"], 2.52))
    A((cx["Patient"], 5.12), (cx["Patient"], 3.7), None, ls="--", color=GRAY)
    ax.text(4.8, 0.05, "Every step above is also written to the audit log.", ha="center", fontsize=6.6, color=GRAY, style="italic")
    save(fig, "activity.png")


def sequence():
    """Report upload to dispensing as a sequence diagram."""
    fig, ax = canvas(9.8, 11.6)
    parts = [("Employee", 0.8), ("Web app\n(React)", 2.3), ("API server\n(FastAPI)", 3.95), ("Analysis\nengine", 5.6), ("Database", 7.1), ("Doctor", 8.45), ("Patient /\nPharmacy", 9.3)]
    parts = [("Employee", 0.75), ("Web app", 2.15), ("API server", 3.65), ("Analysis\nengine", 5.15), ("Database", 6.55), ("Doctor", 7.9), ("Patient /\nPharmacy", 9.1)]
    top, bottom = 11.0, 0.3
    X = {name.replace("\n", " "): x for name, x in parts}      # look up a participant by its name without line breaks
    for name, x in parts:
        box(ax, x, top + 0.2, 1.15, 0.6, name, fc=TEAL_LIGHT, fs=7.2, bold=True)
        ax.plot([x, x], [top - 0.1, bottom], color="#94a3b8", lw=1, ls=(0, (4, 3)), zorder=1)
    y = [top - 0.5]

    def msg(a, b, text, dashed=False, self_=False, note=None):
        y[0] -= 0.52 if not self_ else 0.5
        x1, x2 = X[a.replace("\n", " ")], X[b.replace("\n", " ")]
        if self_:
            ax.plot([x1, x1 + 0.45, x1 + 0.45], [y[0] + 0.12, y[0] + 0.12, y[0] - 0.12], color=DARK, lw=1.1, zorder=3)
            arrow(ax, (x1 + 0.45, y[0] - 0.12), (x1 + 0.02, y[0] - 0.12), None, color=DARK)
            ax.text(x1 + 0.52, y[0], text, ha="left", va="center", fontsize=6.5, color=DARK, linespacing=1.15)
        else:
            arrow(ax, (x1, y[0]), (x2, y[0]), None, color=DARK, ls="--" if dashed else "-", lw=1.1)
            ax.text((x1 + x2) / 2, y[0] + 0.13, text, ha="center", va="bottom", fontsize=6.5, color=DARK, linespacing=1.1)
        return y[0]

    n = [0]

    def num(text):
        n[0] += 1
        return f"{n[0]}. {text}"

    msg("Employee", "Web app", num("choose patient + file"))
    msg("Web app", "API server", num("POST /reports/upload (JWT)"))
    msg("API server", "API server", num("check role, file type,\nsize and content"), self_=True)
    msg("API server", "Analysis engine", num("process_report(file)"))
    msg("Analysis engine", "Analysis engine", num("PDF text / OCR, parse,\nclassify, insights"), self_=True)
    msg("Analysis engine", "API server", num("analysis (or clear error)"), dashed=True)
    msg("API server", "Database", num("save report, results,\ninsights + audit entry"))
    msg("API server", "Web app", num("201 report 'waiting for doctor'"), dashed=True)
    msg("Web app", "Employee", num("upload status"), dashed=True)
    y[0] -= 0.15
    msg("Doctor", "API server", num("open report (dashboard)"))
    msg("API server", "Database", num("load report, insights, history"))
    msg("API server", "Doctor", num("analysis + suggestions"), dashed=True)
    msg("Doctor", "API server", num("review + note + advice\n+ prescription"))
    msg("API server", "Database", num("save, status 'doctor reviewed',\naudit entry"))
    y[0] -= 0.15
    msg("Patient /\nPharmacy", "API server", num("patient: view report and tips"))
    msg("API server", "Patient /\nPharmacy", num("doctor-reviewed result only"), dashed=True)
    msg("Patient /\nPharmacy", "API server", num("pharmacy: open prescription,\ndispense"))
    msg("API server", "Database", num("check remaining qty, lower stock,\nsave dispensing + audit"))
    msg("API server", "Patient /\nPharmacy", num("updated prescription status"), dashed=True)
    ax.text(4.9, 0.12, "Solid arrows: requests. Dashed arrows: responses.", ha="center", fontsize=6.6, color=GRAY, style="italic")
    save(fig, "sequence.png")


if __name__ == "__main__":
    activity()
    sequence()
