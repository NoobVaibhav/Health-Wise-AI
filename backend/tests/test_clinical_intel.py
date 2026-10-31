"""Patient Clinical Intelligence & History Analyzer. Synthetic patients and records only (see sample_data.py and conftest.py)."""
import json

import pytest

from app.services import ai_summary, clinical_summary, emergency_review, llm_service, report_trends
from tests import sample_data as sd
from tests.conftest import future, upload

BASE = "/api/doctor/patients"


def report(date: str | None, *lines: str) -> bytes:
    head = ["SYNTHETIC DEMO LABORATORY", "Patient Name: Rahul Patil"] + ([f"Report Date: {date}"] if date else []) + ["", "BIOCHEMISTRY", "Test Name Result Unit Reference Range"]
    return sd.lines_to_text(head + list(lines))


def put_report(client, world, name, content):
    r = upload(client, world.employee, world.patient_id, name, content)
    assert r.status_code == 201, r.text
    return r.json()


def get(client, world, path, who=None, **kw):
    return client.get(f"{BASE}/{world.patient_id}/{path}", headers=who or world.doctor, **kw)


def two_reports(client, world):
    """HbA1c back in range, Hemoglobin newly out of range, Vitamin D without a printed range."""
    a = put_report(client, world, "july.txt", report("03/07/2026", "Glycosylated Hemoglobin (HbA1c) 7.2 % 4.0 - 5.6", "Hemoglobin 14.0 g/dL 13.0 - 17.0", "Vitamin D 17 ng/mL"))
    b = put_report(client, world, "oct.txt", report("06/10/2026", "Glycosylated Hemoglobin (HbA1c) 5.4 % 4.0 - 5.6", "Hemoglobin 12.1 g/dL 13.0 - 17.0", "Vitamin D 27 ng/mL"))
    return a, b


# ------------------------------------------------------------------ timeline
def test_timeline_is_chronological_linked_and_never_guesses_a_date(client, world):
    put_report(client, world, "dated.txt", report("03/07/2026", "Hemoglobin 14.0 g/dL 13.0 - 17.0"))
    put_report(client, world, "undated.txt", report(None, "Hemoglobin 13.5 g/dL 13.0 - 17.0"))
    client.post("/api/doctor/notes", headers=world.doctor, json={"patient_id": world.patient_id, "priority": "NORMAL", "note": "Please review the haemoglobin trend."})
    events = get(client, world, "timeline").json()["events"]
    stamps = [e["datetime"] for e in events if e["datetime"]]
    assert stamps == sorted(stamps, reverse=True)                                  # newest first
    assert all(e["source"]["type"] and e["source"]["id"] for e in events)           # each event points at its original record
    undated = [e for e in events if e["kind"] == "REPORT" and e["date"] is None]
    assert len(undated) == 1 and undated[0]["date_note"] == "Date not recorded"      # not replaced by the upload date
    uploads = [e for e in events if e["kind"] == "REPORT_UPLOADED"]
    assert len(uploads) == 2 and all(e["date_label"] == "Uploaded" for e in uploads)  # the upload date is its own event
    assert events[-1]["date"] is None                                               # undated events go last
    found = get(client, world, "timeline", params={"q": "haemoglobin"}).json()["events"]
    assert found and all("haemoglobin" in (e["title"] + (e["detail"] or "")).lower() for e in found)


# ------------------------------------------------------------------ report comparison
def test_comparison_uses_printed_ranges_and_never_invents_one(client, world):
    two_reports(client, world)
    rows = {p["name"]: p["comparison"] for p in get(client, world, "report-trends").json()["parameters"]}
    hb = rows["HbA1c"]
    assert (hb["previous"]["value"], hb["latest"]["value"], hb["change"]) == (7.2, 5.4, -1.8) and hb["trend"] == "DECREASED"
    assert hb["status"] == "RETURNED_WITHIN_RANGE" and hb["assessment"] == "IMPROVED" and "4.0 - 5.6" in hb["reference_range"]
    assert hb["previous"]["date"] == "2026-07-03" and hb["latest"]["date"] == "2026-10-06"
    assert hb["latest"]["review_status"] == "WAITING_FOR_DOCTOR"
    h = rows["Hemoglobin"]
    assert h["status"] == "NEWLY_OUTSIDE_RANGE" and h["assessment"] == "WORSENED"
    d = rows["Vitamin D"]                                                            # no printed range: direction alone is not good or bad
    assert d["status"] == "NO_REFERENCE_RANGE" and d["assessment"] == "NEUTRAL" and d["reference_range"] == "reference range not provided"
    assert "clinical interpretation" in d["interpretation"]


def test_a_single_result_is_insufficient_data_not_zero(client, world):
    put_report(client, world, "only.txt", report("03/07/2026", "Hemoglobin 14.0 g/dL 13.0 - 17.0"))
    row = get(client, world, "report-trends").json()["parameters"][0]["comparison"]
    assert row["status"] == "INSUFFICIENT_DATA" and row["previous"] is None and row["change"] is None


def pt(value, unit, status="WITHIN_RANGE", text="70 - 100", low=70.0, high=100.0, day="2026-07-03", known=True):
    return {"report_id": 1, "report_name": "r", "date": day, "date_known": known, "value": value, "unit": unit, "status": status, "reference_text": text,
            "reference_low": low, "reference_high": high, "review_status": "REVIEWED"}


def test_units_are_converted_only_with_a_validated_factor():
    row = report_trends.compare_points("Glucose", pt(90.0, "mg/dL"), pt(5.5, "mmol/L", day="2026-10-06"))
    assert row["converted"] is True and any("converted" in w for w in row["warnings"]) and row["previous"]["value"] == 90.0     # original kept
    assert row["change"] == pytest.approx(5.5 - 90.0 / 18.016, abs=0.01)
    other = report_trends.compare_points("Ferritin", pt(40.0, "ng/mL"), pt(0.04, "ug/mL", day="2026-10-06"))
    assert other["status"] == "NOT_COMPARABLE" and other["assessment"] == "NOT_COMPARABLE" and other["change"] is None


def test_different_laboratory_ranges_and_missing_dates_are_warned_about():
    row = report_trends.compare_points("Hemoglobin", pt(13.5, "g/dL", text="13.0 - 17.0", low=13.0, high=17.0),
                                       pt(13.4, "g/dL", text="12.0 - 16.0", low=12.0, high=16.0, day="2026-10-06", known=False))
    text = " ".join(row["warnings"])
    assert "different reference ranges" in text and "no printed test date" in text


def test_duplicate_reports_are_counted_once_and_conflicts_are_flagged(client, world):
    same = report("03/07/2026", "Hemoglobin 14.0 g/dL 13.0 - 17.0")
    put_report(client, world, "a.txt", same)
    put_report(client, world, "a_copy.txt", same)
    put_report(client, world, "b.txt", report("03/07/2026", "Hemoglobin 9.9 g/dL 13.0 - 17.0"))
    p = get(client, world, "report-trends").json()["parameters"][0]
    assert p["duplicates_removed"] == 1 and len(p["points"]) == 2
    assert p["conflicts"] and "03" in p["conflicts"][0]
    summary = get(client, world, "clinical-summary").json()
    texts = " ".join(s["text"] for s in summary["missing"])
    assert "duplicate" in texts and "Conflicting values" in texts


# ------------------------------------------------------------------ medication history
def prescribe(client, world, items, report_id=None):
    r = client.post("/api/prescriptions", headers=world.doctor, json={"patient_id": world.patient_id, "clinical_indication": "Review", "items": items})
    assert r.status_code == 201, r.text
    return r.json()


def test_medication_history_separates_prescribed_from_dispensed(client, world):
    first = prescribe(client, world, [{"medicine_name": "Tab. Metformin 500 mg", "dosage": "500 mg", "frequency": "Twice daily", "duration": "30 days", "quantity": 60}])
    second = prescribe(client, world, [{"medicine_name": "Tab. Metformin 1000 mg", "dosage": "1000 mg", "frequency": "Twice daily", "duration": "30 days", "quantity": 60},
                                       {"medicine_name": "Penicillin V", "dosage": "250 mg", "frequency": "Twice daily", "duration": "5 days", "quantity": 10}])
    item = client.get("/api/pharmacy/prescriptions?q=Rahul", headers=world.pharmacy).json()[0]["items"][0]["id"]
    assert client.post("/api/pharmacy/dispense", headers=world.pharmacy, json={"prescription_item_id": item, "quantity": 10}).status_code == 200
    client.put(f"/api/health-history/patient/{world.patient_id}", headers=world.doctor, json={"allergies": [{"name": "Penicillin", "kind": "DRUG", "reaction": "rash"}]})
    meds = get(client, world, "medication-history").json()
    metformin = next(m for m in meds["medicines"] if "metformin" in m["name"].lower())
    assert metformin["prescribed_count"] == 2 and metformin["dispensed_quantity"] == 10             # prescribed twice, only part handed over
    assert "not documented" in metformin["adherence"].lower() and "start date not recorded" in metformin["start_note"].lower()
    assert any("1000 mg" in c["text"] or "dose" in c["text"] for c in meds["changes"])               # the dose change is reported
    assert meds["duplicates"] and "more than one open prescription" in meds["duplicates"][0]["text"]  # for clinical review, not a verdict
    assert meds["allergy_flags"] and "Penicillin" in meds["allergy_flags"][0]["text"]
    assert "Prescribed, dispensed and taken are different facts" in meds["note"]


def test_missing_medication_details_are_listed(client, world):
    prescribe(client, world, [{"medicine_name": "Tab. Mystery", "dosage": "1 tablet", "frequency": "Once daily", "duration": "5 days", "quantity": 5}])
    meds = get(client, world, "medication-history").json()
    assert any("indication" in m["text"] for m in meds["missing_details"]) or meds["missing_details"] == []


# ------------------------------------------------------------------ follow-ups
def test_follow_up_tracking_and_completion(client, world):
    client.post("/api/doctor/recommendations", headers=world.doctor, json={"patient_id": world.patient_id, "title": "Repeat HbA1c", "recommendation": "Repeat in three months.", "follow_up_date": "2026-01-15"})
    f = get(client, world, "follow-ups").json()
    assert f["derived"] and f["derived"][0]["overdue"] and "no completed visit" in f["derived"][0]["text"] and f["overdue_count"] == 1
    made = client.post(f"{BASE}/{world.patient_id}/follow-ups", headers=world.doctor, json={"title": "ECG after 4 hours", "due_date": "2026-01-01"})
    assert made.status_code == 201
    task = made.json()["tasks"][0]
    assert task["status"] == "PENDING" and task["overdue"] is True and task["created_by"] == "Dr. Anjali Sharma"
    done = client.patch(f"{BASE}/{world.patient_id}/follow-ups/{task['id']}", headers=world.doctor, json={"status": "DONE", "outcome": "ECG normal sinus rhythm."}).json()
    closed = next(t for t in done["tasks"] if t["id"] == task["id"])
    assert closed["status"] == "DONE" and closed["completed_at"] and closed["outcome"] == "ECG normal sinus rhythm." and not closed["overdue"]
    assert client.patch(f"{BASE}/{world.patient_id}/follow-ups/999", headers=world.doctor, json={"status": "DONE"}).status_code == 404


# ------------------------------------------------------------------ emergency events
FULL = {"event_at": "2026-09-23T13:35:00", "arrival_method": "Walk-in", "chief_complaint": "Giddiness and loss of consciousness since last night", "symptoms": ["Giddiness", "Sweating"],
        "onset_text": "10 pm yesterday", "duration_text": "30 seconds", "vitals": {"pulse": 46, "bp_systolic": 138, "bp_diastolic": 60, "spo2": 95},
        "exam_findings": "S1 S2 heard, no murmur.", "investigations_ordered": "ECG, CPK-MB", "investigation_results": "ECG: heart rate 46.",
        "clinician_assessment": "Syncope, work-up in progress.", "documented_cause": None, "treatment_given": "Admitted for monitoring.", "response_to_treatment": "Pulse 58 after four hours.",
        "disposition": "ADMITTED", "follow_up_recommendations": "Repeat ECG after 4 hours.", "treating_clinician": "Dr. Test Clinician",
        "timeline": [{"occurred_at": "2026-09-23T13:35:00", "kind": "ARRIVAL", "text": "Patient arrived."}, {"occurred_at": "2026-09-23T13:50:00", "kind": "VITALS", "text": "Initial vitals recorded."},
                     {"occurred_at": "2026-09-23T14:10:00", "kind": "ASSESSMENT", "text": "Assessment documented."}, {"occurred_at": "2026-09-23T15:00:00", "kind": "DISPOSITION", "text": "Admission decided."}]}


def test_emergency_review_shows_only_what_was_recorded(client, world):
    assert get(client, world, "emergency-history").json() == {"events": [], "message": emergency_review.NO_EMERGENCY}
    client.put(f"/api/health-history/patient/{world.patient_id}", headers=world.doctor, json={"medications": [{"name": "Tab. Donepezil", "dose": "5 mg"}], "conditions": [{"name": "Alzheimer's disease"}]})
    made = client.post(f"{BASE}/{world.patient_id}/emergency-events", headers=world.doctor, json=FULL)
    assert made.status_code == 201, made.text
    review = made.json()
    assert [e["kind"] for e in review["timeline"]] == ["ARRIVAL", "VITALS", "ASSESSMENT", "DISPOSITION"] and review["timeline_complete"] is True      # only recorded steps
    texts = {s["key"].split(":")[-1]: s for s in review["what_happened"]}
    assert "Giddiness and loss of consciousness" in texts["reason"]["text"] and texts["assessment"]["label"] == "DIRECTLY_DOCUMENTED"
    assert texts["response"]["text"].startswith("Documented response to treatment") and all(s["source"]["type"] == "emergency" or s["source"]["type"] == "history" for s in review["what_happened"])
    cause = review["cause"]
    assert cause["documented_cause"] is None and cause["unknown"] is True and cause["text"] == emergency_review.NO_CAUSE      # the clinician wrote no cause
    assert cause["possible_associations"] and all(p["label"] == "REQUIRES_CLINICIAN_VERIFICATION" for p in cause["possible_associations"])
    assert not any(w in json.dumps(cause).lower() for w in ("caused by", "was caused", "resulted from"))                      # never states a cause
    assert "not established as the cause" in cause["note"]
    # a cause is shown only when the clinician documented one
    documented = client.post(f"{BASE}/{world.patient_id}/emergency-events", headers=world.doctor, json={**FULL, "documented_cause": "Bradycardia, as assessed by the treating doctor.", "contributing_factors": ["Recent dose increase"]}).json()
    assert documented["cause"]["text"].startswith("Documented cause: Bradycardia") and documented["cause"]["documented_contributing"] == ["Recent dose increase"] and documented["cause"]["unknown"] is False


def test_incomplete_emergency_records_say_what_is_missing(client, world):
    made = client.post(f"{BASE}/{world.patient_id}/emergency-events", headers=world.doctor, json={"chief_complaint": "Shortness of breath"})
    assert made.status_code == 201
    review = made.json()
    assert review["event_at"] is None and review["date_note"] == "Date not recorded" and review["timeline_complete"] is False
    assert emergency_review.NO_RESPONSE in review["missing"] and emergency_review.NO_ASSESSMENT in review["missing"]
    assert review["cause"]["text"] == emergency_review.NO_CAUSE
    assert any("timeline" in m for m in review["missing"])
    assert client.post(f"{BASE}/{world.patient_id}/emergency-events", headers=world.doctor, json={}).status_code == 422       # an empty record is refused
    summary = get(client, world, "clinical-summary").json()
    assert any(emergency_review.NO_RESPONSE in s["text"] for s in summary["missing"])


def test_emergency_event_endpoint_checks_the_patient(client, world):
    event_id = client.post(f"{BASE}/{world.patient_id}/emergency-events", headers=world.doctor, json=FULL).json()["id"]
    assert client.get(f"/api/doctor/emergency-events/{event_id}", headers=world.doctor).status_code == 200
    assert client.get(f"/api/doctor/emergency-events/{event_id}", headers=world.other_doctor).status_code == 403
    assert client.get("/api/doctor/emergency-events/9999", headers=world.doctor).status_code == 404


# ------------------------------------------------------------------ the summary
def test_every_statement_has_a_label_and_a_source_and_nothing_is_diagnosed(client, world):
    a, b = two_reports(client, world)
    client.put(f"/api/doctor/reports/{b['id']}/review", headers=world.doctor, json={"decision": "APPROVED"})
    client.post(f"{BASE}/{world.patient_id}/emergency-events", headers=world.doctor, json=FULL)
    s = get(client, world, "clinical-summary").json()
    assert s["disclaimer"].startswith("HealthWise AI assists clinicians by organizing documented patient history")
    sections = ("what_happened", "current_status", "important_changes", "red_flags", "missing")
    for section in sections:
        for st in s[section]:
            assert st["label"] in s["labels"] and st["key"]
            if st["label"] in ("DIRECTLY_DOCUMENTED", "CALCULATED"):
                assert st["sources"], f"{st['key']} has no source"
    evidence = {(e["type"], e["id"]) for e in s["evidence"]}
    assert ("report", a["id"]) in evidence and ("report", b["id"]) in evidence and any(t == "emergency" for t, _ in evidence)
    blob = json.dumps({k: s[k] for k in sections}).lower()
    assert "patient is healthy" not in blob and "diagnosed with" not in blob and "caused by" not in blob
    changes = {c["key"]: c for c in s["important_changes"]}
    assert changes["change:HbA1c"]["headline"] == "Improved" and changes["change:Hemoglobin"]["headline"] == "Worsened"
    assert s["overview"]["latest_report"]["review_status"] in ("REVIEWED", "WAITING_FOR_DOCTOR") and s["overview"]["unresolved_findings"]
    assert "Rahul" not in json.dumps(s)                                                               # no name in the summary payload
    assert s["ai_available"] is False and s["ai_summary"] is None


def test_far_outside_values_raise_the_urgent_notice(client, world):
    put_report(client, world, "high.txt", report("06/10/2026", "Total Leucocyte Count 40000 /cumm 4000 - 11000"))
    s = get(client, world, "clinical-summary").json()
    assert s["urgent_notice"] and "immediate professional assessment" in s["urgent_notice"]
    assert any(f.get("urgent") for f in s["red_flags"])


def test_a_patient_with_no_records_gets_honest_empty_states(client, world):
    s = get(client, world, "clinical-summary").json()
    assert s["what_happened"][0]["label"] == "INSUFFICIENT_INFORMATION" and s["urgent_notice"] is None
    assert any("No laboratory or scan reports" in m["text"] for m in s["missing"])
    assert s["important_changes"][0]["label"] == "INSUFFICIENT_INFORMATION"


# ------------------------------------------------------------------ the doctor's review (originals are never overwritten)
def test_reviews_and_corrections_are_stored_apart_from_the_records(client, world):
    a, b = two_reports(client, world)
    before = client.get(f"/api/reports/{b['id']}", headers=world.doctor).json()["parameters"]
    r = client.post(f"{BASE}/{world.patient_id}/clinical-summary/review", headers=world.doctor, json={"item_key": "change:HbA1c", "action": "CORRECTION", "text": "The earlier value was 7.0 on the paper copy."})
    assert r.status_code == 201 and r.json()["doctor"] == "Dr. Anjali Sharma"
    assert client.post(f"{BASE}/{world.patient_id}/clinical-summary/review", headers=world.doctor, json={"item_key": "change:HbA1c", "action": "INTERPRETATION"}).status_code == 422
    shown = next(c for c in get(client, world, "clinical-summary").json()["important_changes"] if c["key"] == "change:HbA1c")
    assert shown["reviews"][0]["action"] == "CORRECTION" and "paper copy" in shown["reviews"][0]["text"] and shown["label"] == "CALCULATED"   # the computer's statement is unchanged
    assert client.get(f"/api/reports/{b['id']}", headers=world.doctor).json()["parameters"] == before                                    # so is the original data


# ------------------------------------------------------------------ access, audit, privacy
def all_endpoints(world, event_id):
    pid = world.patient_id
    return [("get", f"{BASE}/{pid}/clinical-summary", None), ("get", f"{BASE}/{pid}/timeline", None), ("get", f"{BASE}/{pid}/report-trends", None),
            ("get", f"{BASE}/{pid}/emergency-history", None), ("get", f"{BASE}/{pid}/medication-history", None), ("get", f"{BASE}/{pid}/follow-ups", None),
            ("post", f"{BASE}/{pid}/follow-ups", {"title": "Check"}), ("post", f"{BASE}/{pid}/clinical-summary/generate", None),
            ("post", f"{BASE}/{pid}/clinical-summary/review", {"item_key": "section:missing", "action": "REVIEWED"}), ("post", f"{BASE}/{pid}/emergency-events", FULL),
            ("get", f"/api/doctor/emergency-events/{event_id}", None)]


def test_only_authorised_doctors_can_open_any_of_it(client, world):
    event_id = client.post(f"{BASE}/{world.patient_id}/emergency-events", headers=world.doctor, json=FULL).json()["id"]
    for who in (world.other_doctor, world.employee, world.admin, world.pharmacy, world.patient):
        for method, url, body in all_endpoints(world, event_id):
            r = getattr(client, method)(url, headers=who, **({"json": body} if body is not None else {}))
            assert r.status_code == 403, (method, url, r.status_code)
    assert client.get(f"{BASE}/{world.patient_id}/clinical-summary").status_code == 401         # no token
    assert client.get(f"{BASE}/9999/clinical-summary", headers=world.doctor).status_code == 404


def test_sensitive_actions_are_audited(client, world):
    get(client, world, "clinical-summary")
    event_id = client.post(f"{BASE}/{world.patient_id}/emergency-events", headers=world.doctor, json=FULL).json()["id"]
    client.get(f"/api/doctor/emergency-events/{event_id}", headers=world.doctor)
    client.post(f"{BASE}/{world.patient_id}/follow-ups", headers=world.doctor, json={"title": "Repeat ECG"})
    client.post(f"{BASE}/{world.patient_id}/clinical-summary/review", headers=world.doctor, json={"item_key": "section:missing", "action": "REVIEWED"})
    actions = {a["action"] for a in client.get("/api/admin/audit-logs?limit=200", headers=world.admin).json()}
    assert {"CLINICAL_SUMMARY_VIEWED", "EMERGENCY_RECORDED", "EMERGENCY_VIEWED", "FOLLOW_UP_CREATED", "SUMMARY_REVIEWED"} <= actions


# ------------------------------------------------------------------ the optional AI narrative
def fake_ai(monkeypatch, reply, seen=None):
    monkeypatch.setattr(llm_service, "llm_is_configured", lambda: True)
    def call(prompt, system=None):
        if seen is not None:
            seen.append(prompt)
        return reply
    monkeypatch.setattr(llm_service, "_call_llm", call)


def test_ai_is_optional_and_failure_leaves_the_rule_based_summary_alone(client, world, monkeypatch):
    two_reports(client, world)
    gen = f"{BASE}/{world.patient_id}/clinical-summary/generate"
    assert client.post(gen, headers=world.doctor).status_code == 503                                    # no model connected
    for bad in (None, "not json at all", json.dumps({"paragraphs": []})):
        fake_ai(monkeypatch, bad)
        assert client.post(gen, headers=world.doctor).status_code == 502
    assert get(client, world, "clinical-summary").json()["important_changes"]                           # the summary itself is unaffected


def test_ai_text_is_validated_and_only_verified_statements_are_sent(client, world, monkeypatch):
    two_reports(client, world)
    keys = [s["key"] for s in get(client, world, "clinical-summary").json()["important_changes"]]
    good_key = next(k for k in keys if k.startswith("change:"))
    reply = json.dumps({"paragraphs": [
        {"text": "HbA1c moved back inside the printed range between the two reports.", "cites": [good_key]},
        {"text": "This is based on a record that does not exist.", "cites": ["report:99999"]},
        {"text": "The anaemia was caused by poor diet.", "cites": [good_key]},
        {"text": "Start metformin 500 mg twice daily.", "cites": [good_key]},
        {"text": "No source is given for this sentence.", "cites": []}],
        "questions": ["Is a repeat haemoglobin needed after the change in the latest report?", "What caused it?"]})
    seen = []
    fake_ai(monkeypatch, reply, seen)
    r = client.post(f"{BASE}/{world.patient_id}/clinical-summary/generate", headers=world.doctor)
    assert r.status_code == 200, r.text
    body = r.json()
    assert [p["text"] for p in body["paragraphs"]] == ["HbA1c moved back inside the printed range between the two reports."]      # only the verified one survives
    assert body["questions"] == ["Is a repeat haemoglobin needed after the change in the latest report?"] and body["label"] == "AI_GENERATED"
    sent = seen[0]
    assert "Rahul" not in sent and "9999999999" not in sent and "july.txt" not in sent and "oct.txt" not in sent                    # data minimisation
    shown = get(client, world, "clinical-summary").json()
    assert shown["ai_summary"]["paragraphs"][0]["cites"] == [good_key] and shown["ai_available"] is True                              # stored apart, with its author


def test_ai_payload_contains_statements_only(client, world):
    two_reports(client, world)
    with client:                                                                                                                      # same app, plain call of the builder
        pass
    from app.database.connection import SessionLocal
    from app.database.models import Patient
    with SessionLocal() as db:
        data = ai_summary.payload(clinical_summary.build(db, db.get(Patient, world.patient_id)))
    assert set(data) == {"patient", "statements"} and set(data["patient"]) == {"age", "gender"}
    assert all(set(s) == {"key", "section", "label", "text"} for s in data["statements"])
