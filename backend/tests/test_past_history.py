"""Detailed past medical history: chronic illnesses, regular medicines, hospital admissions, operations. Synthetic records only."""
import json
from datetime import datetime

import pytest

from app.database.connection import SessionLocal
from app.database.models import HistoryRevision, PatientHistory
from tests.conftest import PASSWORD, login

H = "/api/health-history/patient"


def diabetes(**over):
    return {"kind": "DIABETES", "diagnosis_type": "Type 2", "duration_text": "5 years", "diagnosis_year": 2021, "control_status": "FAIR", "on_treatment": True,
            "control": {"fasting": 140, "hba1c": 7.4, "noted_on": "Sep 2026"},
            "complications": {"retinopathy": "NO", "neuropathy": "YES", "nephropathy": "UNKNOWN"},
            "hospitalisation": {"happened": "YES", "reason": "Very high sugar", "date_text": "2023", "treatment": "IV fluids and insulin", "outcome": "Recovered"},
            "other_details": "Follows a diet plan.", **over}


def admission(**over):
    return {"hospital_name": "City General Hospital", "admitted_at": "2024-03-10T09:30:00", "discharged_at": "2024-03-13T14:45:00", "admission_type": "EMERGENCY",
            "main_complaint": "Fever and vomiting", "final_diagnosis": "Viral gastroenteritis",
            "vitals": {"bp_systolic": 100, "bp_diastolic": 60, "pulse": 112, "temperature_f": 101.8, "spo2": 97, "resp_rate": 20, "pain_score": 3},
            "medications": [{"name": "Inj. Ceftriaxone", "dose": "1 g", "frequency": "twice daily", "route": "IV", "duration": "3 days", "category": "ANTIBIOTIC"}],
            "discharge_medications": [{"name": "ORS", "frequency": "after each loose stool"}], **over}


def post(client, who, pid, path, body, expect=201):
    r = client.post(f"{H}/{pid}/{path}", headers=who, json=body)
    assert r.status_code == expect, r.text
    return r.json()


def test_diabetes_and_hypertension_records_keep_every_detail(client, world):
    past = post(client, world.doctor, world.patient_id, "conditions", diabetes())["past"]
    d = past["diabetes"]
    assert d["name"] == "Diabetes mellitus" and d["diagnosis_type"] == "Type 2" and d["diagnosis_year"] == 2021 and d["control"]["hba1c"] == 7.4
    assert d["complications"]["neuropathy"] == "YES" and d["complications"]["retinopathy"] == "NO" and d["complications"]["foot"] == "UNKNOWN"     # unanswered stays unknown
    assert d["complications_present"] == ["Diabetic neuropathy (nerves)"] and d["hospitalisation"]["reason"] == "Very high sugar"
    assert d["years_since_diagnosis"] == datetime.now().year - 2021
    assert d["source"] == "PATIENT_REPORTED" and d["verified"] is False and d["verified_by_name"] is None
    bp = post(client, world.doctor, world.patient_id, "conditions", {"kind": "HYPERTENSION", "diagnosis_type": "Hypertension", "control": {"bp_usual": "130/80"},
                                                                    "complications": {"stroke": "NO"}, "hospitalisation": {"happened": "NO"}})["past"]
    assert bp["hypertension"]["name"] == "Hypertension" and bp["hypertension"]["control"]["bp_usual"] == "130/80" and bp["hypertension"]["hospitalisation"]["happened"] == "NO"
    other = post(client, world.doctor, world.patient_id, "conditions", {"kind": "OTHER", "name": "Asthma", "duration_text": "10 years", "control_status": "GOOD"})["past"]
    assert [c["name"] for c in other["other_conditions"]] == ["Asthma"]


def test_one_diabetes_and_one_hypertension_record_and_bad_input_is_refused(client, world):
    post(client, world.doctor, world.patient_id, "conditions", diabetes())
    assert "already recorded" in post(client, world.doctor, world.patient_id, "conditions", diabetes(), expect=409)["detail"]
    for bad in (diabetes(diagnosis_year=datetime.now().year + 2), {"kind": "OTHER"}, {"kind": "OTHER", "name": "x"}, diabetes(complications={"nonsense": "YES"}),
                diabetes(control={"hba1c": 55}), {"kind": "HYPERTENSION", "complications": {"retinopathy": "YES"}}):
        assert client.post(f"{H}/{world.patient_id}/conditions", headers=world.doctor, json=bad).status_code == 422, bad


def test_medicines_link_to_their_illness_without_duplicating_it(client, world):
    past = post(client, world.doctor, world.patient_id, "conditions", diabetes())["past"]
    cid = past["diabetes"]["id"]
    post(client, world.doctor, world.patient_id, "medicines", {"name": "Tab. Metformin", "dose": "500 mg", "frequency": "twice daily", "route": "oral", "since": "2021",
                                                              "prescriber": "Dr. Test", "adherence": "SOMETIMES_MISSED", "condition_id": cid})
    past = post(client, world.doctor, world.patient_id, "medicines", {"name": "Tab. Vitamin D", "dose": "60000 IU", "frequency": "weekly", "route": "oral"})["past"]
    assert [m["name"] for m in past["diabetes"]["medications"]] == ["Tab. Metformin"]                       # shown under the illness
    assert [m["name"] for m in past["unlinked_medications"]] == ["Tab. Vitamin D"] and past["counts"]["medications"] == 2
    metformin = past["diabetes"]["medications"][0]
    assert metformin["route"] == "oral" and metformin["adherence"] == "SOMETIMES_MISSED" and metformin["prescriber"] == "Dr. Test"
    assert client.post(f"{H}/{world.patient_id}/medicines", headers=world.doctor, json={"name": "Tab. X", "condition_id": 9999}).status_code == 422     # unknown illness
    # a link to another patient's illness is refused
    other = client.post("/api/patients", headers=world.employee, json={"email": "meera@example.com", "full_name": "Meera K", "password": PASSWORD, "assigned_doctor_id": world.doctor_id}).json()["patient"]["id"]
    assert client.post(f"{H}/{other}/medicines", headers=world.doctor, json={"name": "Tab. Y", "condition_id": cid}).status_code == 422


def test_admission_length_of_stay_comes_only_from_real_timestamps(client, world):
    past = post(client, world.doctor, world.patient_id, "admissions", admission())["past"]
    a = past["admissions"][0]
    assert a["length_of_stay"]["days"] == 3 and a["length_of_stay"]["hours"] == 5 and a["length_of_stay"]["minutes"] == 15 and a["length_of_stay"]["text"] == "3 days 5 hours"
    assert a["vitals"]["pulse"] == 112 and a["vitals"]["temperature_f"] == 101.8 and a["medications"][0]["route"] == "IV" and a["discharge_medications"][0]["name"] == "ORS"
    short = post(client, world.doctor, world.patient_id, "admissions", admission(admitted_at="2024-05-01T10:00:00", discharged_at="2024-05-01T16:30:00", main_complaint="Observation"))["past"]
    assert next(x for x in short["admissions"] if x["main_complaint"] == "Observation")["length_of_stay"]["text"] == "6 hours 30 minutes"
    unknown = post(client, world.doctor, world.patient_id, "admissions", admission(discharged_at=None, main_complaint="Chest pain"))["past"]
    assert next(x for x in unknown["admissions"] if x["main_complaint"] == "Chest pain")["length_of_stay"] is None     # no discharge time: no invented stay
    vague = post(client, world.doctor, world.patient_id, "admissions", {"hospital_name": "Village clinic", "admitted_date_text": "around 2015", "reason": "Typhoid"})["past"]
    assert vague["admissions"][-1]["reason"] == "Typhoid" and vague["admissions"][-1]["admitted_at"] is None          # undated stays go last


def test_admission_input_checks(client, world):
    future = datetime.now().replace(year=datetime.now().year + 1).isoformat()
    for bad in (admission(discharged_at="2024-03-09T10:00:00"), admission(admitted_at=future, discharged_at=None), admission(vitals={"spo2": 140}), admission(vitals={"pulse": 0}),
                admission(medications=[{"name": "x"}]), {"admission_type": "MAYBE"}):
        assert client.post(f"{H}/{world.patient_id}/admissions", headers=world.doctor, json=bad).status_code == 422, bad
    assert client.post(f"{H}/{world.patient_id}/admissions", headers=world.doctor, json={}).status_code == 422          # an empty admission is not recorded


def test_todays_vitals_are_never_copied_into_an_old_admission(client, world):
    client.post(f"{H}/{world.patient_id}/assessments", headers=world.doctor, json={"chief_complaint": "x", "vitals": {"pulse": 88, "bp_systolic": 150, "bp_diastolic": 95}})
    past = post(client, world.doctor, world.patient_id, "admissions", admission(vitals={}))["past"]
    assert past["admissions"][0]["vitals"] == {}                                                                       # nothing recorded stays empty


def test_surgery_with_implant_details_and_no_assumptions(client, world):
    adm = post(client, world.doctor, world.patient_id, "admissions", admission(main_complaint="Right leg fracture", final_diagnosis="Closed fracture, right femur shaft"))["past"]["admissions"][0]
    past = post(client, world.doctor, world.patient_id, "surgeries", {"admission_id": adm["id"], "procedure_name": "Intramedullary nailing", "body_site": "Right femur shaft",
                                                                      "reason": "Displaced fracture", "operation_date": "2024-03-11", "anesthesia": "Spinal", "implant_used": True,
                                                                      "implant_type": "rod/nail", "implant_material": "Titanium", "implant_serial": "SN-12345", "postop_xray": "Good alignment",
                                                                      "recovery_progress": "Walking with support at 6 weeks"})["past"]
    s = past["admissions"][0]["surgeries"][0]
    assert s["implant_used"] is True and s["implant_type"] == "rod/nail" and s["implant_serial"] == "SN-12345" and s["body_site"] == "Right femur shaft"
    plain = post(client, world.doctor, world.patient_id, "surgeries", {"procedure_name": "Plaster cast only", "operation_year": 2015})["past"]
    assert plain["standalone_surgeries"][0]["implant_used"] is None                                                    # "not documented", never assumed
    assert client.post(f"{H}/{world.patient_id}/surgeries", headers=world.doctor, json={"procedure_name": "Cast", "implant_used": False, "implant_type": "plate"}).status_code == 422
    assert client.post(f"{H}/{world.patient_id}/surgeries", headers=world.doctor, json={"procedure_name": "Cast", "admission_id": 9999}).status_code == 422
    assert past["counts"]["surgeries"] == 1


def test_every_change_is_logged_and_nothing_is_destroyed(client, world):
    cid = post(client, world.doctor, world.patient_id, "conditions", diabetes())["past"]["diabetes"]["id"]
    r = client.put(f"{H}/{world.patient_id}/conditions/{cid}", headers=world.doctor, json=diabetes(control_status="GOOD", duration_text="6 years"))
    assert r.status_code == 200 and r.json()["past"]["diabetes"]["control_status"] == "GOOD"
    removed = client.delete(f"{H}/{world.patient_id}/conditions/{cid}", headers=world.doctor)
    assert removed.status_code == 200 and removed.json()["past"]["diabetes"] is None
    log = client.get(f"{H}/{world.patient_id}/revisions", headers=world.doctor).json()["revisions"]
    assert [x["action"] for x in log if x["entity_type"] == "condition"] == ["DELETE", "UPDATE", "CREATE"]
    update = next(x for x in log if x["action"] == "UPDATE")
    assert update["before"]["control_status"] == "FAIR" and update["before"]["duration_text"] == "5 years" and update["changed_by"] == "Dr. Anjali Sharma"      # the earlier version is kept
    with SessionLocal() as db:
        from app.database.models import ChronicCondition
        row = db.get(ChronicCondition, cid)
        assert row is not None and row.is_deleted is True                                                              # hidden, not deleted
    assert client.put(f"{H}/{world.patient_id}/conditions/{cid}", headers=world.doctor, json=diabetes()).status_code == 404      # a hidden record cannot be edited
    again = post(client, world.doctor, world.patient_id, "conditions", diabetes())                                       # and a fresh record can be made
    assert again["past"]["diabetes"]["id"] != cid


def test_a_doctor_can_verify_what_the_patient_said(client, world):
    cid = post(client, world.doctor, world.patient_id, "conditions", diabetes())["past"]["diabetes"]["id"]
    verified = client.post(f"{H}/{world.patient_id}/verify/condition/{cid}", headers=world.doctor).json()["past"]["diabetes"]
    assert verified["source"] == "DOCTOR_VERIFIED" and verified["verified"] and verified["verified_by_name"] == "Dr. Anjali Sharma" and verified["verified_at"]
    edited = client.put(f"{H}/{world.patient_id}/conditions/{cid}", headers=world.doctor, json=diabetes(source="PATIENT_REPORTED", duration_text="7 years")).json()["past"]["diabetes"]
    assert edited["verified"] is False and edited["source"] == "PATIENT_REPORTED"                                         # changed after the check: needs checking again
    assert client.post(f"{H}/{world.patient_id}/verify/nonsense/1", headers=world.doctor).status_code == 404
    assert post(client, world.doctor, world.patient_id, "conditions", {"kind": "OTHER", "name": "Asthma", "source": "HOSPITAL_RECORD"})["past"]["other_conditions"][0]["source_label"] == "From a hospital record"


def test_access_rules_for_the_detailed_history(client, world):
    cid = post(client, world.doctor, world.patient_id, "conditions", diabetes())["past"]["diabetes"]["id"]
    mine = client.get("/api/health-history/me", headers=world.patient).json()
    assert mine["past"]["diabetes"]["name"] == "Diabetes mellitus"                                                       # the patient can read it
    for method, path, body in (("post", "conditions", diabetes()), ("put", f"conditions/{cid}", diabetes()), ("delete", f"conditions/{cid}", None), ("post", "admissions", admission()),
                               ("post", "medicines", {"name": "Tab. A"}), ("post", f"verify/condition/{cid}", None)):
        for who in (world.patient, world.employee, world.admin, world.pharmacy, world.other_doctor):
            r = client.request(method, f"{H}/{world.patient_id}/{path}", headers=who, **({"json": body} if body else {}))
            assert r.status_code in (403, 404), (who, method, path, r.status_code)
    for who in (world.employee, world.admin, world.pharmacy, world.other_doctor):
        assert client.get(f"{H}/{world.patient_id}/past", headers=who).status_code == 403
        assert client.get(f"{H}/{world.patient_id}/revisions", headers=who).status_code == 403
    assert client.get(f"{H}/{world.patient_id}/past").status_code == 401
    # a record id belonging to patient 1 does not work under another patient's address
    other = client.post("/api/patients", headers=world.employee, json={"email": "meera@example.com", "full_name": "Meera K", "password": PASSWORD, "assigned_doctor_id": world.doctor_id}).json()["patient"]["id"]
    assert client.put(f"{H}/{other}/conditions/{cid}", headers=world.doctor, json=diabetes()).status_code == 404
    assert client.delete(f"{H}/{other}/conditions/{cid}", headers=world.doctor).status_code == 404


def test_records_written_before_these_screens_are_migrated_once_and_kept(client, world):
    legacy = {"conditions": [{"name": "Diabetes", "since": "2015", "on_treatment": True}, {"name": "High blood pressure", "since": "5 years", "on_treatment": True, "notes": "on tablets"}, {"name": "Asthma"}],
              "surgeries": [{"what": "Appendectomy", "year": "2010", "hospital": "Old clinic"}], "allergies": [], "family": []}
    with SessionLocal() as db:
        db.add(PatientHistory(patient_id=world.patient_id, data_json=json.dumps(legacy)))
        db.commit()
    first = client.get(f"{H}/{world.patient_id}/past", headers=world.doctor).json()["past"]
    assert first["diabetes"]["diagnosis_year"] == 2015 and first["diabetes"]["source"] == "EARLIER_ENTRY" and first["diabetes"]["on_treatment"] is True
    assert first["hypertension"]["duration_text"] == "5 years" and first["hypertension"]["notes"] == "on tablets"
    assert [c["name"] for c in first["other_conditions"]] == ["Asthma"] and first["standalone_surgeries"][0]["procedure_name"] == "Appendectomy" and first["standalone_surgeries"][0]["operation_year"] == 2010
    second = client.get(f"{H}/{world.patient_id}/past", headers=world.doctor).json()["past"]
    assert second["counts"] == first["counts"]                                                                           # not copied twice
    with SessionLocal() as db:
        stored = json.loads(db.query(PatientHistory).filter_by(patient_id=world.patient_id).one().data_json)
        assert len(stored["conditions"]) == 3 and stored["surgeries"][0]["what"] == "Appendectomy"                        # the earlier lists are untouched
        assert db.query(HistoryRevision).filter_by(patient_id=world.patient_id, action="MIGRATE", entity_type="patient").count() == 1


def test_the_earlier_one_form_screen_still_works_and_never_deletes(client, world):
    form = {"conditions": [{"name": "Diabetes", "since": "2018", "on_treatment": True}, {"name": "Asthma", "on_treatment": False}], "surgeries": [{"what": "Hernia repair", "year": "2012"}],
            "medications": [{"name": "Tab. Metformin 500 mg", "dose": "500 mg", "frequency": "twice daily", "is_current": True}], "allergies": [{"name": "Iodine contrast", "kind": "DRUG"}]}
    saved = client.put(f"{H}/{world.patient_id}", headers=world.doctor, json=form).json()["history"]
    assert [c["name"] for c in saved["conditions"]] == ["Diabetes mellitus", "Asthma"] and saved["surgeries"][0]["what"] == "Hernia repair" and saved["medications"][0]["name"] == "Tab. Metformin 500 mg"
    # a detailed medicine record (with route and adherence) survives the one-form save that lists the same medicine
    past = client.get(f"{H}/{world.patient_id}/past", headers=world.doctor).json()["past"]
    mid = past["medications"][0]["id"]
    client.put(f"{H}/{world.patient_id}/medicines/{mid}", headers=world.doctor, json={"name": "Tab. Metformin 500 mg", "dose": "500 mg", "frequency": "twice daily", "route": "oral", "adherence": "REGULAR"})
    client.put(f"{H}/{world.patient_id}", headers=world.doctor, json={**form, "medications": [{"name": "Tab. Metformin 500 mg", "dose": "500 mg", "frequency": "twice daily", "is_current": True}]})
    kept = client.get(f"{H}/{world.patient_id}/past", headers=world.doctor).json()["past"]["medications"][0]
    assert kept["id"] == mid and kept["route"] == "oral" and kept["adherence"] == "REGULAR"
    # an empty list means "not touched"; removing from a non-empty list hides the record but keeps it (and logs it)
    client.put(f"{H}/{world.patient_id}", headers=world.doctor, json={"conditions": [], "medications": [], "surgeries": []})
    assert client.get(f"{H}/{world.patient_id}/past", headers=world.doctor).json()["past"]["counts"]["conditions"] == 2
    client.put(f"{H}/{world.patient_id}", headers=world.doctor, json={**form, "conditions": [{"name": "Diabetes", "since": "2018", "on_treatment": True}]})
    log = client.get(f"{H}/{world.patient_id}/revisions", headers=world.doctor).json()["revisions"]
    assert any(x["action"] == "DELETE" and x["entity_type"] == "condition" and x["before"]["name"] == "Asthma" for x in log)


def test_medicine_reconciliation_and_follow_up_block(client, world):
    client.post("/api/prescriptions", headers=world.doctor, json={"patient_id": world.patient_id, "clinical_indication": "Check", "tests": ["ECG"], "items": [
        {"medicine_name": "Tab. Metformin 500 mg", "dosage": "500 mg", "frequency": "Twice daily", "duration": "30 days", "quantity": 60},
        {"medicine_name": "Tab. Amlodipine 5 mg", "dosage": "5 mg", "frequency": "Once daily", "duration": "30 days", "quantity": 30}]})
    for med in ({"name": "Metformin", "dose": "1000 mg", "frequency": "twice daily"}, {"name": "Tab. Aspirin 75 mg", "dose": "75 mg", "frequency": "once daily"}):
        post(client, world.doctor, world.patient_id, "medicines", med)
    client.post("/api/doctor/recommendations", headers=world.doctor, json={"patient_id": world.patient_id, "title": "Review", "recommendation": "Repeat HbA1c.", "follow_up_date": "2027-01-10"})
    view = client.get(f"{H}/{world.patient_id}", headers=world.doctor).json()
    verdicts = {r["name"]: r["verdict"] for r in view["reconciliation"]["rows"]}
    assert verdicts["Metformin"] == "DOSE_DIFFERS" and verdicts["Tab. Aspirin 75 mg"] == "IN_HISTORY_ONLY" and verdicts["Tab. Amlodipine 5 mg"] == "PRESCRIBED_ONLY"
    assert view["reconciliation"]["needs_attention"] == 3
    fu = view["follow_up"]
    assert fu["recommendations"][0]["follow_up_date"] == "2027-01-10" and fu["prescriptions"][0]["tests"] == ["ECG"] and len(fu["prescriptions"][0]["items"]) == 2
    assert "past" in view and view["past"]["counts"]["medications"] == 2
