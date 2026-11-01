"""Phase 7: the history timeline, the trend engine and the patient assistant now use the hospital's own finished records (signed consultations, approved results and scan reports,
discharge summaries, operations, bills). Drafts and unapproved results are never shown as facts, a scan report reaches the patient only after the doctor has seen it, and
the assistant never answers from another patient's record."""
from datetime import date, timedelta

import pytest

from app.database.connection import SessionLocal
from app.database.models import (
    Admission, Consultation, Diagnosis, DiagnosticAnalyte, DiagnosticTest, DischargeSummary, LabResult, LabTestOrder, RadiologyOrder, RadiologyReport, Surgery, utcnow,
)
from tests.conftest import PASSWORD, login

TL = "/api/doctor/patients/{}/timeline"


@pytest.fixture()
def aw(client, world):
    res = client.post("/api/opd/walk-in", headers=world.employee, json={"patient_id": world.patient_id, "doctor_id": world.doctor_id})
    assert res.status_code == 201, res.text
    world.enc = res.json()["encounter_id"]
    return world


def chat(client, w, message, who=None):
    r = client.post("/api/patient-assistant/chat", headers=who or w.patient, json={"message": message, "language": "en"})
    assert r.status_code == 200, r.text
    return r.json()["reply"]


def add_lab(w, name="Serum Electrolytes", analyte="Potassium", value=6.4, flag="CRITICAL_HIGH", approved=True, seen=False, day_offset=0):
    with SessionLocal() as db:
        o = LabTestOrder(encounter_id=w.enc, patient_id=w.patient_id, doctor_id=w.doctor_id, test_name=name, status="COMPLETED" if approved else "IN_PROGRESS",
                         result_status="APPROVED" if approved else "PENDING_APPROVAL", approved_at=utcnow() - timedelta(days=day_offset) if approved else None, doctor_seen_at=utcnow() if seen else None, has_critical=flag.startswith("CRITICAL"))
        db.add(o)
        db.flush()
        db.add(LabResult(order_id=o.id, analyte_name=analyte, value_text=str(value), value_num=value, unit="mmol/L", ref_low=3.5, ref_high=5.0, flag=flag))
        db.commit()
        return o.id


def add_scan(w, status="APPROVED", seen=False, impression="Normal chest. No focal lesion."):
    with SessionLocal() as db:
        o = RadiologyOrder(encounter_id=w.enc, patient_id=w.patient_id, doctor_id=w.doctor_id, study="Chest X-ray", modality="XRAY", status=status,
                           approved_at=utcnow() if status == "APPROVED" else None, doctor_seen_at=utcnow() if seen else None)
        db.add(o)
        db.flush()
        db.add(RadiologyReport(order_id=o.id, findings="Lungs are clear.", impression=impression, reported_by=1))
        db.commit()
        return o.id


# ------------------------------------------------------------------ the doctor's timeline
def test_the_timeline_shows_only_finished_hospital_records(client, aw):
    with SessionLocal() as db:
        db.add(Consultation(encounter_id=aw.enc, patient_id=aw.patient_id, doctor_id=aw.doctor_id, complaint="Fever", assessment="Viral fever", status="SIGNED", signed_at=utcnow()))
        db.add(Diagnosis(encounter_id=aw.enc, patient_id=aw.patient_id, text="Viral fever", kind="FINAL", added_by=1, is_active=True))
        db.add(Diagnosis(encounter_id=aw.enc, patient_id=aw.patient_id, text="Maybe malaria", kind="DRAFT", added_by=1, is_active=True))
        db.commit()
    add_lab(aw)
    add_lab(aw, name="Unapproved panel", approved=False)
    add_scan(aw)
    add_scan(aw, status="REPORTED")
    events = client.get(TL.format(aw.patient_id), headers=aw.doctor).json()["events"]
    titles = [e["title"] for e in events]
    assert any(t.startswith("Consultation signed by Dr. Anjali Sharma") for t in titles)
    assert "Final diagnosis: Viral fever" in titles and "Draft diagnosis (not confirmed): Maybe malaria" in titles
    assert "Laboratory result approved: Serum Electrolytes" in titles and not any("Unapproved panel" in t for t in titles)
    assert titles.count("Scan report approved: Chest X-ray") == 1
    lab = next(e for e in events if e["kind"] == "LAB_TEST")
    assert "1 critical" in lab["detail"] and lab["source"]["type"] == "lab_test"
    assert client.get(TL.format(aw.patient_id), headers=aw.other_doctor).status_code == 403


def test_admission_discharge_and_operation_appear_only_when_approved_or_completed(client, aw):
    with SessionLocal() as db:
        adm = Admission(admission_no="ADM-T-1", patient_id=aw.patient_id, encounter_id=aw.enc, attending_doctor_id=aw.doctor_id, admitting_diagnosis="Pneumonia", status="DISCHARGED",
                        discharged_at=utcnow(), discharge_type="DISCHARGE")
        db.add(adm)
        db.flush()
        db.add(DischargeSummary(admission_id=adm.id, final_diagnosis="Pneumonia, recovered", follow_up="Review in 1 week", status="DRAFT"))
        from app.database.models import OperationTheatre
        theatre = OperationTheatre(name="OT-T")
        db.add(theatre)
        db.flush()
        for status in ("COMPLETED", "SCHEDULED"):
            db.add(Surgery(patient_id=aw.patient_id, theatre_id=theatre.id, procedure=f"Appendectomy {status}", surgeon_id=aw.doctor_id, scheduled_start=utcnow(), scheduled_end=utcnow() + timedelta(hours=1),
                           status=status, completed_at=utcnow() if status == "COMPLETED" else None, created_by=1))
        db.commit()
    titles = [e["title"] for e in client.get(TL.format(aw.patient_id), headers=aw.doctor).json()["events"]]
    assert any(t.startswith("Admitted for Pneumonia") for t in titles)
    assert not any(t.startswith("Discharge summary approved") for t in titles)                       # still a draft
    assert "Operation done: Appendectomy COMPLETED" in titles and not any("SCHEDULED" in t for t in titles)
    with SessionLocal() as db:
        db.query(DischargeSummary).update({"status": "APPROVED", "approved_at": utcnow()})
        db.commit()
    events = client.get(TL.format(aw.patient_id), headers=aw.doctor).json()["events"]
    assert any(e["kind"] == "DISCHARGE" and "Pneumonia, recovered" in e["detail"] for e in events)


# ------------------------------------------------------------------ approved lab values in the trend engine
def test_approved_hospital_lab_values_join_the_comparison_and_reach_the_patient_only_after_the_doctor_saw_them(client, aw):
    add_lab(aw, value=4.1, flag="NORMAL", seen=True, day_offset=5)
    add_lab(aw, value=6.4, flag="CRITICAL_HIGH", seen=False)
    doctor_view = client.get(f"/api/doctor/patients/{aw.patient_id}/report-trends", headers=aw.doctor)
    assert doctor_view.status_code == 200, doctor_view.text
    potassium = next(p for p in doctor_view.json()["parameters"] if "otassium" in p["name"])
    assert [round(x["value"], 1) for x in potassium["points"]] == [4.1, 6.4]
    reply = chat(client, aw, "what was my potassium result")
    assert "4.1" in reply["text"] and "6.4" not in reply["text"]                                          # the newer one is not released yet
    assert all(s["type"] != "report" for s in reply["sources"])
    with SessionLocal() as db:
        db.query(LabTestOrder).update({"doctor_seen_at": utcnow()})
        db.commit()
    assert "6.4" in chat(client, aw, "what was my potassium result")["text"]


# ------------------------------------------------------------------ the patient assistant
def test_bills_are_answered_from_the_patients_own_final_invoices(client, aw):
    assert "No bill has been made" in chat(client, aw, "how much do I owe")["text"]
    with SessionLocal() as db:
        from app.database.models import EncounterCharge
        c = EncounterCharge(encounter_id=aw.enc, patient_id=aw.patient_id, description="Consultation", amount=1000, gst_percent=0, status="PENDING")
        db.add(c)
        db.commit()
        cid = c.id
    inv = client.post("/api/finance/invoices", headers=aw.employee, json={"patient_id": aw.patient_id, "charge_ids": [cid]}).json()
    assert "No bill has been made" in chat(client, aw, "show my bill")["text"]                             # a draft is not a bill yet
    client.post(f"/api/finance/invoices/{inv['id']}/finalise", headers=aw.employee)
    client.post(f"/api/finance/invoices/{inv['id']}/pay", headers=aw.employee, json={"amount": 400, "method": "CASH"})
    reply = chat(client, aw, "how much is my bill")
    assert "1,000.00" in reply["text"] and "400.00" in reply["text"] and "600.00 is still to pay" in reply["text"]
    assert reply["intent"] == "BILLS" and reply["sources"][0]["type"] == "invoice"
    other = client.post("/api/patients", headers=aw.employee, json={"email": "o@example.com", "full_name": "Other Person", "password": PASSWORD, "gender": "male", "date_of_birth": "1990-01-01", "phone": "8888888888"})
    assert other.status_code == 201
    stranger = login(client, "o@example.com")
    assert "No bill has been made" in chat(client, aw, "how much is my bill", who=stranger)["text"]         # never someone else's bill


def test_a_scan_report_is_quoted_only_after_the_doctor_has_seen_it_and_is_never_explained(client, aw):
    assert "no scan report" in chat(client, aw, "what did my scan show")["text"]
    add_scan(aw, status="REPORTED")
    assert "not reported yet" in chat(client, aw, "what did my scan show")["text"]
    sid = add_scan(aw, seen=False)
    waiting = chat(client, aw, "what did my x-ray show")["text"]
    assert "Normal chest" not in waiting and "go through it with you first" in waiting
    with SessionLocal() as db:
        db.get(RadiologyOrder, sid).doctor_seen_at = utcnow()
        db.commit()
    reply = chat(client, aw, "what did my x-ray show")
    assert 'the radiologist wrote: "Normal chest. No focal lesion."' in reply["text"] and "I cannot explain what a scan means" in reply["text"]
    assert reply["sources"][0]["type"] == "radiology"


def test_hospital_stay_and_discharge_summary_for_the_patient(client, aw):
    assert "no hospital stay" in chat(client, aw, "tell me about my discharge")["text"]
    with SessionLocal() as db:
        adm = Admission(admission_no="ADM-T-2", patient_id=aw.patient_id, encounter_id=aw.enc, attending_doctor_id=aw.doctor_id, status="DISCHARGED", discharged_at=utcnow(), discharge_type="DISCHARGE")
        db.add(adm)
        db.flush()
        db.add(DischargeSummary(admission_id=adm.id, final_diagnosis="Pneumonia", follow_up="Review in 1 week", warning_signs="Fever above 101F", status="DRAFT"))
        db.commit()
    assert "not ready yet" in chat(client, aw, "my discharge summary")["text"]
    with SessionLocal() as db:
        db.query(DischargeSummary).update({"status": "APPROVED", "approved_at": utcnow()})
        db.commit()
    text = chat(client, aw, "my discharge summary")["text"]
    assert "final diagnosis Pneumonia" in text and "Review in 1 week" in text and "Fever above 101F" in text


def test_existing_intents_still_win_for_their_own_words(client, aw):
    assert chat(client, aw, "what are my allergies")["intent"] == "ALLERGY"
    assert chat(client, aw, "my current medicines")["intent"] == "MEDICINES"
    assert chat(client, aw, "hello")["intent"] != "BILLS"
