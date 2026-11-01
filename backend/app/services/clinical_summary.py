"""The evidence-linked clinical summary a doctor reads first.

Built by ordinary code from the hospital's records. Every statement has
- a KEY (so a doctor can review or correct that statement),
- a LABEL saying how it is known (directly documented / calculated from recorded values / requires clinician verification /
  insufficient information; AI text is kept in a separate block), and
- SOURCES: the original records it came from.
It does not diagnose, does not say that a patient is healthy because of laboratory values, and does not name a cause."""
import json
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import ClinicalAssessment, EmergencyEvent, HealthReport, Patient, SummaryReview, utcnow
from app.services import clinical_timeline, emergency_review, follow_ups, health_history_service, medication_history, report_trends
from app.services.clinical_timeline import source
from app.services.history_insights import vitals_points

DISCLAIMER = ("HealthWise AI assists clinicians by organizing documented patient history and generating evidence-linked summaries. "
              "It does not independently diagnose diseases, establish emergency causation, or replace clinical judgment.")
URGENT_NOTICE = ("If the patient is unwell now, arrange immediate professional assessment according to your clinical protocol. "
                 "Do not wait for this summary. The urgent-finding rules here are simple checks that qualified clinicians must validate before clinical use.")
LABELS = {"DIRECTLY_DOCUMENTED": "Directly documented", "CALCULATED": "Calculated from recorded values", "AI_GENERATED": "AI-generated summary of documented findings",
          "REQUIRES_CLINICIAN_VERIFICATION": "Requires clinician verification", "INSUFFICIENT_INFORMATION": "Insufficient information"}
D, C, V, M = "DIRECTLY_DOCUMENTED", "CALCULATED", "REQUIRES_CLINICIAN_VERIFICATION", "INSUFFICIENT_INFORMATION"
FAR = 3.0     # a value this many times beyond the printed limit is shown as a red flag (and may be a unit or typing mistake)


def fmt(day: str | None) -> str:
    return date.fromisoformat(day[:10]).strftime("%d %b %Y").lstrip("0") if day else "a date that was not recorded"


def stmt(key: str, label: str, text: str, *sources: dict, extra: dict | None = None) -> dict:
    return {"key": key, "label": label, "text": text, "sources": [s for s in sources if s], "reviews": [], **(extra or {})}


def _latest_value_line(p: dict) -> str:
    unit = f" {p['unit']}" if p.get("unit") else ""
    when = fmt(p["date"]) + ("" if p["date_known"] else " (upload date; test date not printed)")
    rng = p["reference_text"] or "reference range not provided"
    direction = {"ABOVE_RANGE": "above", "BELOW_RANGE": "below", "WITHIN_RANGE": "within", "UNKNOWN": "not judged: no range printed"}[p["status"]]
    tail = f"{direction} the printed range" if p["status"] in ("ABOVE_RANGE", "BELOW_RANGE", "WITHIN_RANGE") else direction
    return f"{p['value']:g}{unit} on {when} (printed range: {rng}): {tail}."


def build(db: Session, patient: Patient) -> dict:
    history = health_history_service.load_history(db, patient)
    trends = report_trends.analyse(db, patient)
    meds = medication_history.build(db, patient)
    follow = follow_ups.build(db, patient)
    emergencies = emergency_review.list_events(db, patient)
    timeline = clinical_timeline.build(db, patient)
    assessments = db.scalars(select(ClinicalAssessment).where(ClinicalAssessment.patient_id == patient.id).order_by(ClinicalAssessment.created_at.desc())).all()
    reports = db.scalars(select(HealthReport).where(HealthReport.patient_id == patient.id)).all()
    age = health_history_service.age_of(patient)
    today = date.today()

    # ------------------------------------------------------------ 1. overview
    def eff(r):
        return (r.report_date or r.uploaded_at.date(), r.id)
    latest_report = max(reports, key=eff) if reports else None
    latest_points = [pt["points"][-1] for pt in trends["parameters"] if pt["points"]]
    unresolved = [{"parameter": pt["name"], **pt["points"][-1], "text": _latest_value_line(pt["points"][-1]),
                   "source": source("report", pt["points"][-1]["report_id"], f"Report: {pt['points'][-1]['report_name']}", pt["points"][-1]["date"])}
                  for pt in trends["parameters"] if pt["points"] and pt["points"][-1]["status"] in ("ABOVE_RANGE", "BELOW_RANGE")]
    open_meds = [m for m in meds["medicines"] if m["status"] == "OPEN"]
    last_assessment = assessments[0] if assessments else None
    overview = {
        "patient_code": patient.patient_code, "age": age, "gender": patient.gender,
        "allergies": history.get("allergies", []), "allergies_status": ("documented" if history.get("allergies") else "none known" if history.get("no_known_allergies") else "not recorded"),
        "conditions": history.get("conditions", []),
        "current_medicines": {"prescribed_open": [{"name": m["name"], "source": m["entries"][-1]["source"]} for m in open_meds],
                              "reported_in_history": [m["name"] for m in meds["reported_only"]],
                              "note": "Open prescriptions and medicines entered in the history. This does not show what the patient actually takes."},
        "latest_report": {"id": latest_report.id, "name": latest_report.filename, "date": (latest_report.report_date or latest_report.uploaded_at.date()).isoformat(), "date_known": bool(latest_report.report_date),
                          "review_status": "REVIEWED" if latest_report.doctor_review_status == "REVIEWED" else "WAITING_FOR_DOCTOR",
                          "source": source("report", latest_report.id, f"Report: {latest_report.filename}", latest_report.report_date.isoformat() if latest_report.report_date else None)} if latest_report else None,
        "latest_encounter": ({"type": "ASSESSMENT", "date": last_assessment.created_at.date().isoformat(), "text": last_assessment.chief_complaint or "No complaint was written.", "doctor": last_assessment.doctor.user.full_name,
                              "source": source("assessment", last_assessment.id, "Doctor's assessment", last_assessment.created_at.date().isoformat())} if last_assessment else None),
        "pending_follow_ups": {"count": follow["pending_count"], "overdue": follow["overdue_count"], "items": [t for t in follow["tasks"] if t["status"] == "PENDING"][:5] + follow["derived"][:5]},
        "unresolved_findings": unresolved,
    }

    # ------------------------------------------------------------ 2. what has happened (documented events, oldest first)
    verbs = {"REPORT": "a laboratory report was recorded", "ASSESSMENT": "a doctor's assessment was recorded", "EMERGENCY": "an emergency visit was recorded", "NOTE": "a doctor's note was added",
             "RECOMMENDATION": "a recommendation was added", "PRESCRIPTION": "a prescription was issued", "APPOINTMENT": "an appointment was held or booked", "HISTORY": "a history entry was added",
             "CONSULTATION": "a consultation was signed", "DIAGNOSIS": "a diagnosis was recorded", "ADMISSION": "an admission was recorded", "DISCHARGE": "a discharge summary was approved",
             "LAB_TEST": "a hospital laboratory result was approved", "SCAN": "a scan report was approved", "SURGERY": "an operation was done", "TRANSFUSION": "a transfusion was recorded"}
    chosen = [e for e in timeline if e["kind"] in verbs]
    dated = sorted([e for e in chosen if e["datetime"]], key=lambda e: e["datetime"])[-12:]
    undated = [e for e in chosen if not e["datetime"]]
    what = []
    for e in dated + undated:
        what_it_is = e["title"][0].lower() + e["title"][1:] if e["kind"] == "APPOINTMENT" else verbs[e["kind"]]
        text = f"On {fmt(e['date'])}, {what_it_is}" + (f": {e['detail']}" if e["detail"] else ".")
        what.append(stmt(e["key"], D, text if text.endswith(".") else text + ".", e["source"], extra={"date": e["date"], "date_note": e["date_note"]}))
    if not what:
        what = [stmt("what:none", M, "No documented events were found in the records available to this system.")]

    # ------------------------------------------------------------ 3. current clinical status
    status_items = []
    for u in unresolved:
        status_items.append(stmt(f"status:{u['parameter']}", D, f"{u['parameter']}: {u['text']}", u["source"]))
    if latest_points and not unresolved:
        status_items.append(stmt("status:labs-in-range", D, "Every latest result that has a printed range is inside it. This does not show that the patient is well: it only describes the tests that were done.",
                                 *[source("report", p["report_id"], f"Report: {p['report_name']}", p["date"]) for p in latest_points[:1]]))
    if trends["compared_count"]:
        g = trends["groups"]
        status_items.append(stmt("status:changes", C, f"Since the previous report: {len(g['IMPROVED'])} improved, {len(g['WORSENED'])} worsened, {len(g['STABLE'])} stable, {len(g['NEUTRAL'])} changed without a way to judge the direction, "
                                 f"{len(g['NOT_COMPARABLE'])} not comparable ({trends['compared_count']} parameters compared).", source("report", latest_report.id, f"Report: {latest_report.filename}") if latest_report else None))
    for c in overview["conditions"]:
        status_items.append(stmt(f"condition:{c['name']}", D, f"Documented condition: {c['name']}" + (f", since {c['since']}" if c.get("since") else "") + (", on treatment" if c.get("on_treatment") else "") + ".",
                                 source("history", patient.id, "Medical history")))
    if open_meds:
        status_items.append(stmt("status:treatment", D, "Open prescriptions: " + ", ".join(m["name"] for m in open_meds) + ". Whether the patient takes them is not documented.", *[m["entries"][-1]["source"] for m in open_meds[:3]]))
    elif not meds["reported_only"]:
        status_items.append(stmt("status:treatment", M, "No current treatment was found in the prescriptions or the medicine list.", source("history", patient.id, "Medical history")))
    if follow["pending_count"]:
        status_items.append(stmt("status:followups", D, f"{follow['pending_count']} follow-up item(s) are pending" + (f", {follow['overdue_count']} overdue." if follow["overdue_count"] else "."), source("follow_up", patient.id, "Follow-up tracker")))
    if not status_items:
        status_items.append(stmt("status:none", M, "There are no recent findings to summarise.", ))

    # ------------------------------------------------------------ 4. important changes
    changes = []
    for pt in trends["parameters"]:
        c = pt["comparison"]
        if not c or c["assessment"] in ("INSUFFICIENT_DATA", "NOT_COMPARABLE"):
            continue
        prev, latest = c["previous"], c["latest"]
        if c["assessment"] in ("IMPROVED", "WORSENED") or c["status"] in ("NEWLY_OUTSIDE_RANGE", "STILL_OUTSIDE_RANGE", "RETURNED_WITHIN_RANGE") or c["assessment"] == "NEUTRAL":
            head = {"IMPROVED": "Improved", "WORSENED": "Worsened", "NEUTRAL": "Changed", "STABLE": "Stable"}.get(c["assessment"], "Changed")
            when = f"({fmt(prev['date'])} to {fmt(latest['date'])})"
            text = f"{c['parameter']} {when}: {c['interpretation']}"
            changes.append(stmt(f"change:{c['parameter']}", C, text, source("report", prev["report_id"], f"Report: {prev['report_name']}", prev["date"]), source("report", latest["report_id"], f"Report: {latest['report_name']}", latest["date"]),
                                extra={"assessment": c["assessment"], "headline": head, "warnings": c["warnings"]}))
    for ch in meds["changes"]:
        changes.append(stmt(f"medchange:{ch['medicine']}", C, f"Prescription changed. {ch['text']}", ch["source"]))
    for d in follow["derived"]:
        if d["kind"] == "RECOMMENDATION" and d["overdue"]:
            changes.append(stmt(f"followup:{d['source']['id']}", V, f"{d['title']}: {d['text']}", d["source"]))
    emergency_rows = db.scalars(select(EmergencyEvent).where(EmergencyEvent.patient_id == patient.id)).all()
    for a in assessments:
        later = [x for x in assessments if x.created_at > a.created_at] + [e for e in emergency_rows if e.event_at and e.event_at > a.created_at]
        if a.chief_complaint and not later and (utcnow() - a.created_at).days >= 7:
            changes.append(stmt(f"complaint:{a.id}", V, f"A complaint documented on {fmt(a.created_at.date().isoformat())} (\"{a.chief_complaint}\") has no later documented review.", source("assessment", a.id, "Doctor's assessment", a.created_at.date().isoformat())))
    if not changes:
        changes = [stmt("changes:none", M, "No comparable changes were found. At least two reports with the same parameter are needed to compare results.")]

    # ------------------------------------------------------------ red flags (for clinician verification)
    flags = []
    urgent = False
    for pt in trends["parameters"]:
        p = pt["points"][-1]
        if p["status"] == "ABOVE_RANGE" and p["reference_high"] and p["value"] >= FAR * p["reference_high"]:
            urgent = True
            flags.append(stmt(f"flag:far:{pt['name']}", C, f"{pt['name']} {p['value']:g} {p['unit'] or ''} is at least {FAR:g} times above the printed upper limit ({p['reference_text']}). Check the value for a measurement or unit mistake, or whether it needs prompt attention.", source("report", p["report_id"], f"Report: {p['report_name']}", p["date"]), extra={"urgent": True}))
        elif p["status"] == "BELOW_RANGE" and p["reference_low"] and p["value"] <= p["reference_low"] / FAR:
            urgent = True
            flags.append(stmt(f"flag:far:{pt['name']}", C, f"{pt['name']} {p['value']:g} {p['unit'] or ''} is less than a third of the printed lower limit ({p['reference_text']}). Check the value for a measurement or unit mistake, or whether it needs prompt attention.", source("report", p["report_id"], f"Report: {p['report_name']}", p["date"]), extra={"urgent": True}))
    for c in changes:
        if c.get("assessment") == "WORSENED":
            flags.append(stmt("flag:" + c["key"], C, c["text"], *c["sources"]))
    for m in meds["allergy_flags"]:
        flags.append(stmt(f"flag:allergy:{m['medicine']}", V, f"{m['medicine']}: {m['text']}", source("history", patient.id, "Medical history")))
    for dup in meds["duplicates"]:
        flags.append(stmt(f"flag:dup:{dup['medicine']}", V, dup["text"], dup["source"]))
    if last_assessment and last_assessment.vitals_json:
        for pnt in vitals_points(json.loads(last_assessment.vitals_json), age):
            flags.append(stmt(f"flag:vitals:{pnt['title']}", C, f"{pnt['title']}. {pnt['detail']}", source("assessment", last_assessment.id, "Doctor's assessment", last_assessment.created_at.date().isoformat())))
    for ev in emergencies["events"]:
        if not ev["has_assessment"]:
            flags.append(stmt(f"flag:emergency:{ev['id']}", V, f"The emergency visit of {fmt(ev['event_at'])} has no documented clinician assessment.", ev["source"]))
    for t in follow["tasks"]:
        if t["overdue"]:
            flags.append(stmt(f"flag:task:{t['id']}", D, f"Overdue follow-up (due {fmt(t['due_date'])}): {t['title']}.", t["source"]))
    if latest_report and latest_report.insights_json:
        for text in (json.loads(latest_report.insights_json).get("red_flags") or [])[:3]:
            flags.append(stmt(f"flag:wording:{latest_report.id}:{abs(hash(text)) % 10000}", V, "Wording in the latest report was marked for prompt attention by the reading software: " + text, source("report", latest_report.id, f"Report: {latest_report.filename}")))

    # ------------------------------------------------------------ missing information
    missing = []
    if not reports:
        missing.append(stmt("missing:reports", M, "No laboratory or scan reports are available for this patient."))
    elif trends["compared_count"] == 0:
        missing.append(stmt("missing:previous", M, "No previous report with the same parameters is available, so no comparison could be made."))
    no_date = [r for r in reports if not r.report_date]
    if no_date:
        missing.append(stmt("missing:dates", M, f"{len(no_date)} report(s) have no printed test date. Their upload date is used only for ordering and is not the date of the test.", *[source("report", r.id, f"Report: {r.filename}") for r in no_date[:3]]))
    unranged = [pt["name"] for pt in trends["parameters"] if pt["points"] and pt["points"][-1]["status"] == "UNKNOWN"]
    if unranged:
        missing.append(stmt("missing:ranges", M, "The report prints no reference range for: " + ", ".join(unranged[:8]) + ("..." if len(unranged) > 8 else "") + ". These results were not judged."))
    if overview["allergies_status"] == "not recorded":
        missing.append(stmt("missing:allergies", M, "Allergy status is not recorded.", source("history", patient.id, "Medical history")))
    if not open_meds and not meds["reported_only"] and not history.get("no_regular_medicines"):
        missing.append(stmt("missing:medicines", M, "No medicines are documented (no prescriptions and nothing entered in the history).", source("history", patient.id, "Medical history")))
    if not any((history.get("baseline") or {}).get(k) is not None for k in health_history_service.BASELINE_KEYS):
        missing.append(stmt("missing:usual", M, "The patient's usual pulse, blood pressure and sugar are not recorded.", source("history", patient.id, "Medical history")))
    for m in meds["missing_details"][:6]:
        missing.append(stmt(f"missing:med:{m['medicine']}", M, m["text"], m["source"]))
    for pt in trends["parameters"]:
        for conflict in pt["conflicts"]:
            missing.append(stmt(f"missing:conflict:{pt['name']}", V, f"Conflicting values for {pt['name']}. {conflict}"))
        if pt["duplicates_removed"]:
            missing.append(stmt(f"missing:dup:{pt['name']}", C, f"{pt['duplicates_removed']} duplicate result(s) of {pt['name']} (same day, value and unit) were counted once."))
    for ev in emergencies["events"]:
        if not ev["has_response"]:
            missing.append(stmt(f"missing:response:{ev['id']}", M, emergency_review.NO_RESPONSE + f" (visit of {fmt(ev['event_at'])})", ev["source"]))
    if not missing:
        missing = [stmt("missing:none", C, "No missing items were found by the checks in this summary. This does not mean the records are complete.")]

    reviews = {}
    for r in db.scalars(select(SummaryReview).where(SummaryReview.patient_id == patient.id).order_by(SummaryReview.created_at)):
        reviews.setdefault(r.item_key, []).append({"id": r.id, "action": r.action, "text": r.text, "doctor": r.doctor.user.full_name, "at": r.created_at.isoformat()})
    sections = {"what_happened": what, "current_status": status_items, "important_changes": changes, "red_flags": flags, "missing": missing}
    evidence: dict[tuple, dict] = {}
    for items in sections.values():
        for st in items:
            st["reviews"] = reviews.get(st["key"], [])
            for s in st["sources"]:
                evidence[(s["type"], s["id"])] = s
    return {"generated_at": utcnow().isoformat(), "overview": overview, **sections, "urgent_notice": URGENT_NOTICE if urgent else None,
            "evidence": sorted(evidence.values(), key=lambda s: (s["type"], s["id"])), "labels": LABELS, "disclaimer": DISCLAIMER,
            "counts": {"reports": len(reports), "events": len(timeline), "emergencies": len(emergencies["events"]), "compared_parameters": trends["compared_count"]}}
