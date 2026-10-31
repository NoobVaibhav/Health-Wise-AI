"""Phase 3: encounters, OPD queue, consultation, nursing, emergency, IPD with beds, discharge, referral requests, and the trainee referral into the OPD queue."""
from datetime import date, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.database.connection import SessionLocal
from app.database.models import Bed, BedAssignment, MarEntry
from tests.conftest import PASSWORD, future, login


def dept(client, auth, name):
    return next(d["id"] for d in client.get("/api/catalog/departments", headers=auth).json() if d["name"] == name)


def staff(client, world, path, email, name, **extra):
    res = client.post(f"/api/admin/{path}", headers=world.admin, json={"email": email, "full_name": name, "password": PASSWORD, **extra})
    assert res.status_code == 201, res.text
    return login(client, email), res.json()["user"]["id"]


def patient(client, world, email, name, phone, **extra):
    res = client.post("/api/patients", headers=world.employee, json={"email": email, "full_name": name, "password": PASSWORD, "gender": "male", "date_of_birth": "1980-02-02", "phone": phone, **extra})
    assert res.status_code == 201, res.text
    return res.json()["patient"]["id"]


@pytest.fixture()
def cw(client, world):
    """The hospital of the other tests plus a nurse, a ward with beds, a price for the consultation and a cardiologist."""
    world.nurse, world.nurse_user = staff(client, world, "nurses", "nurse@hospital.example.com", "Nurse Meera", designation="Staff nurse")
    ward = client.post("/api/ipd/wards", headers=world.admin, json={"name": "General Ward A", "ward_type": "GENERAL"}).json()
    icu = client.post("/api/ipd/wards", headers=world.admin, json={"name": "ICU", "ward_type": "ICU"}).json()
    world.ward_id = ward["id"]
    world.beds = [client.post(f"/api/ipd/wards/{ward['id']}/beds", headers=world.admin, json={"code": f"A{i}"}).json()["id"] for i in (1, 2, 3)]
    world.icu_bed = client.post(f"/api/ipd/wards/{icu['id']}/beds", headers=world.admin, json={"code": "I1"}).json()["id"]
    client.post("/api/hospital/services", headers=world.admin, json={"code": "OPD-GM", "name": "OPD consultation, General Medicine", "category": "CONSULTATION", "department_id": world.department_id, "price": 500, "gst_percent": 0})
    world.cardio = dept(client, world.admin, "Cardiology")
    world.cardiologist, cardio_user = staff(client, world, "doctors", "heart@hospital.example.com", "Dr. Heart Doctor", department_id=world.cardio)
    world.cardiologist_id = next(d["id"] for d in client.get("/api/doctors", headers=world.employee).json() if d["full_name"] == "Dr. Heart Doctor")
    world.cardiologist_user = cardio_user
    return world


_slot = [0]


def booked(client, w, patient_id=None, doctor_id=None):
    """Every booking gets its own time, so two bookings in the same second never clash."""
    _slot[0] += 1
    res = client.post("/api/appointments", headers=w.employee, json={"patient_id": patient_id or w.patient_id, "doctor_id": doctor_id or w.doctor_id, "scheduled_at": future(30 + _slot[0]), "reason": "Check"})
    assert res.status_code == 201, res.text
    return res.json()["id"]


def visit(client, w, patient_id=None, doctor_id=None, urgent=False):
    """Walk-in check-in: returns the token."""
    res = client.post("/api/opd/walk-in", headers=w.employee, json={"patient_id": patient_id or w.patient_id, "doctor_id": doctor_id or w.doctor_id, "urgent": urgent})
    assert res.status_code == 201, res.text
    return res.json()


def admit(client, w, patient_id=None, bed=None, **extra):
    res = client.post("/api/ipd/admissions", headers=w.doctor, json={"patient_id": patient_id or w.patient_id, "diagnosis": "Pneumonia", **({"bed_id": bed} if bed else {}), **extra})
    assert res.status_code == 201, res.text
    return res.json()


# ------------------------------------------------------------------ OPD
def test_check_in_gives_tokens_in_order_and_a_visit_is_opened(client, cw):
    appt = booked(client, cw)
    first = client.post("/api/opd/check-in", headers=cw.employee, json={"appointment_id": appt}).json()
    other = patient(client, cw, "t2@example.com", "Second Patient", "9811100002")
    second = visit(client, cw, other)
    assert (first["number"], second["number"]) == (1, 2) and first["status"] == "WAITING" and first["patient"]["uhid"]
    assert client.post("/api/opd/check-in", headers=cw.employee, json={"appointment_id": appt}).status_code == 409           # already checked in
    assert client.get("/api/appointments", headers=cw.employee).json()[0]["status"] == "CONFIRMED"
    queue = client.get("/api/opd/queue", headers=cw.employee).json()
    assert [t["number"] for t in queue] == [1, 2] and all(t["waiting_minutes"] is not None for t in queue)


def test_only_reception_checks_in_and_bad_input_is_refused(client, cw):
    appt = booked(client, cw)
    for who in (cw.doctor, cw.pharmacy, cw.patient, cw.nurse):
        assert client.post("/api/opd/check-in", headers=who, json={"appointment_id": appt}).status_code == 403
        assert client.post("/api/opd/walk-in", headers=who, json={"patient_id": cw.patient_id, "doctor_id": cw.doctor_id}).status_code == 403
    assert client.post("/api/opd/check-in", headers=cw.employee, json={"appointment_id": 999999}).status_code == 404
    assert client.post("/api/opd/check-in", headers=cw.employee, json={"appointment_id": "x"}).status_code == 422
    assert client.post("/api/opd/walk-in", headers=cw.employee, json={"patient_id": 999999, "doctor_id": cw.doctor_id}).status_code == 404
    assert client.post("/api/opd/walk-in", headers=cw.employee, json={"patient_id": cw.patient_id, "doctor_id": 999999}).status_code == 404
    assert client.post("/api/opd/walk-in", headers=cw.employee, json={"patient_id": cw.patient_id, "doctor_id": cw.doctor_id, "department_id": 999999}).status_code == 422
    cancelled = booked(client, cw)
    client.put(f"/api/appointments/{cancelled}", headers=cw.employee, json={"status": "CANCELLED"})
    assert client.post("/api/opd/check-in", headers=cw.employee, json={"appointment_id": cancelled}).status_code == 409


def test_the_same_patient_cannot_stand_twice_in_one_doctors_queue(client, cw):
    visit(client, cw)
    assert client.post("/api/opd/walk-in", headers=cw.employee, json={"patient_id": cw.patient_id, "doctor_id": cw.doctor_id}).status_code == 409


def test_token_numbers_never_repeat_for_a_doctor_on_a_day(client, cw):
    numbers = [visit(client, cw, patient(client, cw, f"q{i}@example.com", f"Queue Patient{chr(65 + i)}", f"98111003{i:02d}"))["number"] for i in range(5)]
    assert numbers == [1, 2, 3, 4, 5]
    assert visit(client, cw, patient(client, cw, "q9@example.com", "Queue Other", "9811100399"), doctor_id=cw.other_doctor_id)["number"] == 1       # each doctor has their own numbers


def test_doctor_sees_only_their_queue_and_calls_the_urgent_patient_first(client, cw):
    normal = visit(client, cw)
    urgent = visit(client, cw, patient(client, cw, "u@example.com", "Urgent Person", "9811100301"), urgent=True)
    visit(client, cw, patient(client, cw, "o@example.com", "Other Queue", "9811100302"), doctor_id=cw.other_doctor_id)
    mine = client.get("/api/opd/queue", headers=cw.doctor).json()
    assert {t["doctor_id"] for t in mine} == {cw.doctor_id} and len(mine) == 2
    nxt = client.post("/api/opd/queue/next", headers=cw.doctor).json()
    assert nxt["id"] == urgent["id"] and nxt["status"] == "IN_CONSULTATION"
    assert client.post(f"/api/opd/queue/{normal['id']}/call", headers=cw.other_doctor).status_code == 403
    assert client.post("/api/opd/queue/next", headers=cw.other_doctor).json()["doctor_id"] == cw.other_doctor_id
    assert client.post("/api/opd/queue/next", headers=cw.other_doctor).status_code == 404           # nobody left


def test_reception_marks_no_show_but_not_after_the_consultation_started(client, cw):
    token = visit(client, cw)
    assert client.post(f"/api/opd/queue/{token['id']}/no-show", headers=cw.employee).json()["status"] == "NO_SHOW"
    other = visit(client, cw, patient(client, cw, "ns@example.com", "Called Person", "9811100303"))
    client.post(f"/api/opd/queue/{other['id']}/call", headers=cw.doctor)
    assert client.post(f"/api/opd/queue/{other['id']}/cancel", headers=cw.employee).status_code == 409
    assert client.post(f"/api/opd/queue/{other['id']}/whatever", headers=cw.employee).status_code == 404
    assert client.post("/api/opd/queue/999999/cancel", headers=cw.employee).status_code == 404


# ------------------------------------------------------------------ consultation
FULL = {"complaint": "Fever for 3 days", "hpi": "Started with chills", "examination": "Throat red", "assessment": "Viral fever", "plan": "Rest and fluids", "advice": "Review if worse"}


def test_consultation_draft_sign_charge_and_lock(client, cw):
    token = visit(client, cw)
    eid = token["encounter_id"]
    ws = client.get(f"/api/opd/encounters/{eid}", headers=cw.doctor).json()
    assert ws["patient"]["uhid"] and ws["template"]["name"] and ws["consultation"] is None
    saved = client.put(f"/api/opd/encounters/{eid}/consultation", headers=cw.doctor, json={**FULL, "follow_up_date": (date.today() + timedelta(days=7)).isoformat(), "data": {"general_exam": "Alert"}})
    assert saved.status_code == 200 and saved.json()["status"] == "DRAFT" and saved.json()["data"]["general_exam"] == "Alert"
    client.put(f"/api/opd/encounters/{eid}/consultation", headers=cw.doctor, json={"complaint": "", "assessment": ""})
    res = client.post(f"/api/opd/encounters/{eid}/sign", headers=cw.doctor)
    assert res.status_code == 422 and "complaint" in res.json()["detail"] and "diagnosis" in res.json()["detail"]
    client.put(f"/api/opd/encounters/{eid}/consultation", headers=cw.doctor, json={**FULL, "follow_up_date": (date.today() + timedelta(days=7)).isoformat()})
    assert client.post(f"/api/opd/encounters/{eid}/diagnoses", headers=cw.doctor, json={"text": "Viral fever", "code": "B34.9"}).status_code == 201
    signed = client.post(f"/api/opd/encounters/{eid}/sign", headers=cw.doctor).json()
    assert signed["charge"] == {"description": "OPD consultation, General Medicine", "amount": 500.0} and signed["consultation"]["status"] == "SIGNED"
    after = client.get(f"/api/opd/encounters/{eid}", headers=cw.doctor).json()
    assert after["encounter"]["status"] == "CLOSED" and after["charges"][0]["status"] == "PENDING"
    assert client.get("/api/opd/queue", headers=cw.employee).json()[0]["status"] == "DONE"
    assert client.put(f"/api/opd/encounters/{eid}/consultation", headers=cw.doctor, json=FULL).status_code == 409           # visit closed
    assert client.post(f"/api/opd/encounters/{eid}/sign", headers=cw.doctor).status_code == 409
    cid = after["consultation"]["id"]
    add = client.post(f"/api/opd/consultations/{cid}/addenda", headers=cw.doctor, json={"text": "Culture result normal"})
    assert add.status_code == 201
    assert client.get(f"/api/opd/encounters/{eid}", headers=cw.doctor).json()["addenda"][0]["text"] == "Culture result normal"
    assert client.get("/api/doctor/dashboard", headers=cw.doctor).json()["pending_follow_ups"] is not None


def test_nobody_but_the_visits_doctor_writes_the_consultation(client, cw):
    eid = visit(client, cw)["encounter_id"]
    assert client.get(f"/api/opd/encounters/{eid}", headers=cw.other_doctor).status_code == 403
    assert client.put(f"/api/opd/encounters/{eid}/consultation", headers=cw.other_doctor, json=FULL).status_code == 403
    for who in (cw.employee, cw.pharmacy, cw.patient):
        assert client.get(f"/api/opd/encounters/{eid}", headers=who).status_code == 403
        assert client.put(f"/api/opd/encounters/{eid}/consultation", headers=who, json=FULL).status_code == 403
        assert client.post(f"/api/opd/encounters/{eid}/sign", headers=who).status_code == 403
    assert client.put(f"/api/opd/encounters/{eid}/consultation", headers=cw.nurse, json=FULL).status_code == 403          # a nurse does not write the consultation
    assert client.get("/api/opd/encounters/999999", headers=cw.doctor).status_code == 404
    assert client.post(f"/api/opd/encounters/{eid}/sign", headers=cw.doctor).status_code == 409                          # nothing saved yet


def test_consultation_input_is_checked(client, cw):
    eid = visit(client, cw)["encounter_id"]
    url = f"/api/opd/encounters/{eid}/consultation"
    assert client.put(url, headers=cw.doctor, json={"follow_up_date": "2020-01-01"}).status_code == 422
    assert client.put(url, headers=cw.doctor, json={"template_id": 999999}).status_code == 422
    assert client.put(url, headers=cw.doctor, json={"complaint": "x" * 3000}).status_code == 422
    assert client.put(url, headers=cw.doctor, json={"data": {"k": "y" * 4000}}).status_code == 422
    assert client.put(url, headers=cw.doctor, json={"follow_up_date": "not a date"}).status_code == 422
    assert client.put(url, headers=cw.doctor, json={"complaint": "<script>alert(1)</script>Fever"}).json()["complaint"] == "alert(1)Fever"


def test_diagnoses_are_withdrawn_never_deleted_and_orders_follow_their_status(client, cw):
    eid = visit(client, cw)["encounter_id"]
    d = client.post(f"/api/opd/encounters/{eid}/diagnoses", headers=cw.doctor, json={"text": "Anaemia", "kind": "PROVISIONAL"}).json()
    assert client.post(f"/api/opd/encounters/{eid}/diagnoses", headers=cw.doctor, json={"text": "A"}).status_code == 422
    client.post(f"/api/opd/diagnoses/{d['id']}/withdraw", headers=cw.doctor)
    assert client.get(f"/api/opd/encounters/{eid}", headers=cw.doctor).json()["diagnoses"] == []
    order = client.post(f"/api/opd/encounters/{eid}/orders", headers=cw.doctor, json={"kind": "LAB", "text": "CBC", "priority": "URGENT"}).json()
    assert client.post(f"/api/opd/encounters/{eid}/orders", headers=cw.doctor, json={"kind": "MAGIC", "text": "x"}).status_code == 422
    assert client.post(f"/api/opd/encounters/{eid}/orders", headers=cw.nurse, json={"kind": "LAB", "text": "CBC"}).status_code == 403
    assert client.post(f"/api/opd/orders/{order['id']}/status", headers=cw.doctor, json={"status": "DONE"}).json()["status"] == "DONE"
    assert client.post(f"/api/opd/orders/{order['id']}/status", headers=cw.doctor, json={"status": "CANCELLED"}).status_code == 409
    assert client.post("/api/opd/diagnoses/999999/withdraw", headers=cw.doctor).status_code == 404


def test_vitals_with_a_critical_value_raise_an_alert_from_plain_rules(client, cw):
    eid = visit(client, cw)["encounter_id"]
    res = client.post(f"/api/opd/encounters/{eid}/vitals", headers=cw.nurse, json={"pulse": 88, "spo2": 85, "bp_systolic": 120, "bp_diastolic": 80}).json()
    assert [a["level"] for a in res["alerts"]] == ["CRITICAL"] and "Oxygen" in res["alerts"][0]["message"]
    warning = client.post(f"/api/opd/encounters/{eid}/vitals", headers=cw.doctor, json={"spo2": 92}).json()
    assert [a["level"] for a in warning["alerts"]] == ["WARNING"]
    assert client.post(f"/api/opd/encounters/{eid}/vitals", headers=cw.doctor, json={"spo2": 98, "pulse": 70}).json()["alerts"] == []
    for bad in ({}, {"pulse": 5}, {"spo2": 130}, {"bp_systolic": 120}, {"bp_systolic": 80, "bp_diastolic": 90}, {"temperature_f": 500}, {"gcs": 2}, {"pain_score": 11}):
        assert client.post(f"/api/opd/encounters/{eid}/vitals", headers=cw.nurse, json=bad).status_code == 422, bad
    assert client.post(f"/api/opd/encounters/{eid}/vitals", headers=cw.employee, json={"pulse": 80}).status_code == 403
    assert client.get(f"/api/opd/encounters/{eid}", headers=cw.doctor).json()["vitals"][0]["recorded_by"]


def test_a_prescription_can_be_tied_to_the_visit_of_the_same_patient_only(client, cw):
    eid = visit(client, cw)["encounter_id"]
    rx = {"patient_id": cw.patient_id, "clinical_indication": "Fever", "encounter_id": eid, "items": [{"medicine_name": "Tab. Paracetamol", "dosage": "500 mg", "frequency": "Twice a day", "duration": "3 days", "quantity": 6}]}
    assert client.post("/api/prescriptions", headers=cw.doctor, json=rx).status_code == 201
    assert client.get(f"/api/opd/encounters/{eid}", headers=cw.doctor).json()["prescriptions"][0]["status"] == "ACTIVE"
    other = patient(client, cw, "rx2@example.com", "Rx Other", "9811100304", assigned_doctor_id=cw.doctor_id)
    assert client.post("/api/prescriptions", headers=cw.doctor, json={**rx, "patient_id": other}).status_code == 422
    assert client.post("/api/prescriptions", headers=cw.doctor, json={**rx, "encounter_id": 999999}).status_code == 422
    assert client.post("/api/prescriptions", headers=cw.other_doctor, json={**rx}).status_code in (403, 404)


def test_templates_are_configurable_by_the_admin_only(client, cw):
    default = client.get("/api/opd/templates", headers=cw.admin).json()
    assert any(t["department_id"] is None for t in default) and any(t["name"].startswith("Cardiology") for t in default)
    body = {"name": "Medicine round", "department_id": cw.department_id, "fields": [{"key": "bmi", "label": "BMI", "kind": "number"}, {"key": "diet", "label": "Diet", "kind": "choice", "options": ["Veg", "Non-veg"]}]}
    made = client.post("/api/opd/templates", headers=cw.admin, json=body)
    assert made.status_code == 201
    eid = visit(client, cw)["encounter_id"]
    assert client.get(f"/api/opd/encounters/{eid}", headers=cw.doctor).json()["template"]["name"] == "Medicine round"
    for bad in ({**body, "fields": [{"key": "a", "label": "A"}, {"key": "a", "label": "B"}]}, {**body, "fields": [{"key": "c", "label": "C", "kind": "choice", "options": ["one"]}]},
                {**body, "fields": [{"key": "bad key!", "label": "X"}]}, {**body, "department_id": 999999}, {**body, "name": "x"}):
        assert client.post("/api/opd/templates", headers=cw.admin, json=bad).status_code == 422
    for who in (cw.doctor, cw.employee, cw.nurse, cw.patient):
        assert client.post("/api/opd/templates", headers=who, json=body).status_code == 403
    assert client.put(f"/api/opd/templates/{made.json()['id']}", headers=cw.admin, json={**body, "is_active": False}).status_code == 200


# ------------------------------------------------------------------ wards and beds
def test_wards_and_beds_are_managed_by_the_admin_and_counted(client, cw):
    for who in (cw.doctor, cw.employee, cw.nurse, cw.patient):
        assert client.post("/api/ipd/wards", headers=who, json={"name": "X Ward", "ward_type": "GENERAL"}).status_code == 403
        assert client.post(f"/api/ipd/wards/{cw.ward_id}/beds", headers=who, json={"code": "Z9"}).status_code == 403
    assert client.post("/api/ipd/wards", headers=cw.admin, json={"name": "general ward a", "ward_type": "GENERAL"}).status_code == 409
    assert client.post("/api/ipd/wards", headers=cw.admin, json={"name": "Bad", "ward_type": "SPACESHIP"}).status_code == 422
    assert client.post(f"/api/ipd/wards/{cw.ward_id}/beds", headers=cw.admin, json={"code": "a1"}).status_code == 409
    counts = client.get("/api/ipd/bed-counts", headers=cw.employee).json()
    assert counts["counts"]["AVAILABLE"] == 4 and counts["beds"] == 4
    client.post(f"/api/ipd/beds/{cw.beds[2]}/status", headers=cw.nurse, json={"status": "MAINTENANCE"})
    board = client.get("/api/ipd/wards", headers=cw.nurse).json()
    ward = next(w for w in board if w["id"] == cw.ward_id)
    assert ward["counts"]["MAINTENANCE"] == 1 and ward["counts"]["AVAILABLE"] == 2
    assert client.get("/api/ipd/wards", headers=cw.patient).status_code == 403
    assert client.post(f"/api/ipd/beds/{cw.beds[0]}/status", headers=cw.nurse, json={"status": "RESERVED"}).status_code == 422          # needs a patient


def test_a_bed_never_holds_two_patients_in_the_api_or_in_the_database(client, cw):
    a = admit(client, cw, bed=cw.beds[0])
    other = patient(client, cw, "b2@example.com", "Second Inpatient", "9811100305", assigned_doctor_id=cw.doctor_id)
    second = admit(client, cw, other)
    assert client.post(f"/api/ipd/admissions/{second['id']}/bed", headers=cw.nurse, json={"bed_id": cw.beds[0]}).status_code == 409
    assert client.post(f"/api/ipd/admissions/{a['id']}/bed", headers=cw.nurse, json={"bed_id": cw.beds[0]}).status_code == 409        # already there
    with SessionLocal() as db:                                                                                                          # even a direct write is refused by the database
        db.add(BedAssignment(admission_id=second["id"], bed_id=cw.beds[0]))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        db.add(BedAssignment(admission_id=a["id"], bed_id=cw.beds[1]))                                                                   # and a patient cannot lie in two beds
        with pytest.raises(IntegrityError):
            db.commit()


def test_transfer_releases_the_old_bed_to_cleaning_and_a_dirty_bed_cannot_be_used(client, cw):
    a = admit(client, cw, bed=cw.beds[0])
    moved = client.post(f"/api/ipd/admissions/{a['id']}/bed", headers=cw.nurse, json={"bed_id": cw.beds[1], "reason": "Closer to the nurses"}).json()
    assert moved["bed"]["code"] == "A2"
    board = {b["id"]: b["status"] for w in client.get("/api/ipd/wards", headers=cw.nurse).json() for b in w["beds"]}
    assert board[cw.beds[0]] == "CLEANING" and board[cw.beds[1]] == "OCCUPIED"
    assert client.post(f"/api/ipd/admissions/{a['id']}/bed", headers=cw.nurse, json={"bed_id": cw.beds[0]}).status_code == 409        # still being cleaned
    assert client.post(f"/api/ipd/beds/{cw.beds[1]}/status", headers=cw.nurse, json={"status": "AVAILABLE"}).status_code == 409        # a patient is in it
    assert client.post(f"/api/ipd/beds/{cw.beds[0]}/status", headers=cw.nurse, json={"status": "AVAILABLE"}).status_code == 200
    assert client.post(f"/api/ipd/admissions/{a['id']}/bed", headers=cw.nurse, json={"bed_id": 999999}).status_code == 404


def test_a_reserved_bed_is_only_for_its_patient(client, cw):
    other = patient(client, cw, "r1@example.com", "Reserved For", "9811100306", assigned_doctor_id=cw.doctor_id)
    assert client.post(f"/api/ipd/beds/{cw.beds[0]}/status", headers=cw.nurse, json={"status": "RESERVED", "reserved_for_patient_id": other}).status_code == 200
    first = admit(client, cw)
    assert client.post(f"/api/ipd/admissions/{first['id']}/bed", headers=cw.nurse, json={"bed_id": cw.beds[0]}).status_code == 409
    second = admit(client, cw, other)
    assert client.post(f"/api/ipd/admissions/{second['id']}/bed", headers=cw.nurse, json={"bed_id": cw.beds[0]}).status_code == 200


# ------------------------------------------------------------------ admission
def test_admission_number_bed_and_the_patient_cannot_be_admitted_twice(client, cw):
    a = admit(client, cw, bed=cw.beds[0], expected_discharge=(date.today() + timedelta(days=4)).isoformat())
    assert a["admission_no"].startswith("ADM-") and a["status"] == "ADMITTED" and a["bed"]["ward"] == "General Ward A" and a["attending_doctor"] == "Dr. Anjali Sharma"
    assert client.post("/api/ipd/admissions", headers=cw.doctor, json={"patient_id": cw.patient_id}).status_code == 409
    other = patient(client, cw, "a2@example.com", "Next Inpatient", "9811100307", assigned_doctor_id=cw.doctor_id)
    assert int(admit(client, cw, other)["admission_no"].split("-")[-1]) == int(a["admission_no"].split("-")[-1]) + 1
    assert client.post("/api/ipd/admissions", headers=cw.doctor, json={"patient_id": 999999}).status_code == 404
    assert client.post("/api/ipd/admissions", headers=cw.doctor, json={"patient_id": other, "bed_id": 999999}).status_code in (409, 422)
    for who in (cw.nurse, cw.employee, cw.pharmacy, cw.patient):
        assert client.post("/api/ipd/admissions", headers=who, json={"patient_id": cw.patient_id}).status_code == 403


def test_a_doctor_cannot_admit_a_patient_who_is_not_theirs(client, cw):
    stranger = patient(client, cw, "st@example.com", "Stranger Patient", "9811100308", assigned_doctor_id=cw.other_doctor_id)
    assert client.post("/api/ipd/admissions", headers=cw.doctor, json={"patient_id": stranger}).status_code == 403


def test_admission_with_a_taken_bed_changes_nothing(client, cw):
    admit(client, cw, bed=cw.beds[0])
    other = patient(client, cw, "a3@example.com", "Half Admitted", "9811100309", assigned_doctor_id=cw.doctor_id)
    res = client.post("/api/ipd/admissions", headers=cw.doctor, json={"patient_id": other, "bed_id": cw.beds[0]})
    assert res.status_code == 409
    assert [a["patient"]["id"] for a in client.get("/api/ipd/admissions", headers=cw.doctor).json()].count(other) == 0


def test_consulting_doctor_and_nurse_assignment_give_the_right_access(client, cw):
    a = admit(client, cw)
    assert client.get(f"/api/doctor/patients/{cw.patient_id}/history", headers=cw.cardiologist).status_code == 403
    assert client.post(f"/api/ipd/admissions/{a['id']}/staff", headers=cw.doctor, json={"user_id": cw.cardiologist_user, "kind": "NURSE"}).status_code == 422
    assert client.post(f"/api/ipd/admissions/{a['id']}/staff", headers=cw.doctor, json={"user_id": cw.nurse_user, "kind": "CONSULTING_DOCTOR"}).status_code == 422
    done = client.post(f"/api/ipd/admissions/{a['id']}/staff", headers=cw.doctor, json={"user_id": cw.cardiologist_user, "kind": "CONSULTING_DOCTOR"})
    assert done.status_code == 201 and done.json()["staff"][0]["kind"] == "CONSULTING_DOCTOR"
    assert client.post(f"/api/ipd/admissions/{a['id']}/staff", headers=cw.doctor, json={"user_id": cw.cardiologist_user, "kind": "CONSULTING_DOCTOR"}).status_code == 409
    assert client.get(f"/api/doctor/patients/{cw.patient_id}/history", headers=cw.cardiologist).status_code == 200
    assert client.post(f"/api/ipd/admissions/{a['id']}/notes", headers=cw.cardiologist, json={"note": "Cardiac review done"}).status_code == 201
    assert client.post(f"/api/ipd/admissions/{a['id']}/staff", headers=cw.other_doctor, json={"user_id": cw.nurse_user, "kind": "NURSE"}).status_code == 403
    assert client.post(f"/api/ipd/admissions/{a['id']}/staff", headers=cw.doctor, json={"user_id": cw.nurse_user, "kind": "NURSE"}).status_code == 201


def test_progress_notes_are_never_edited_and_only_the_treating_team_writes_them(client, cw):
    a = admit(client, cw)
    note = client.post(f"/api/ipd/admissions/{a['id']}/notes", headers=cw.doctor, json={"note": "Day 1: fever settling"}).json()
    fix = client.post(f"/api/ipd/admissions/{a['id']}/notes", headers=cw.doctor, json={"note": "Correction: fever settling, SpO2 96", "corrects_id": note["id"]}).json()
    detail = client.get(f"/api/ipd/admissions/{a['id']}", headers=cw.doctor).json()
    assert [n["id"] for n in detail["progress_notes"]] == [fix["id"], note["id"]] and detail["progress_notes"][0]["corrects_id"] == note["id"]
    assert client.post(f"/api/ipd/admissions/{a['id']}/notes", headers=cw.other_doctor, json={"note": "Not my patient"}).status_code == 403
    assert client.post(f"/api/ipd/admissions/{a['id']}/notes", headers=cw.nurse, json={"note": "Nurse writing a doctor note"}).status_code == 403
    assert client.post(f"/api/ipd/admissions/{a['id']}/notes", headers=cw.doctor, json={"note": "x"}).status_code == 422
    assert client.post(f"/api/ipd/admissions/{a['id']}/notes", headers=cw.doctor, json={"note": "Fine note", "corrects_id": 999999}).status_code == 422
    assert client.get(f"/api/ipd/admissions/{a['id']}", headers=cw.other_doctor).status_code == 403
    assert client.get("/api/ipd/admissions/999999", headers=cw.doctor).status_code == 404


def test_reception_sees_the_admission_summary_but_not_the_clinical_content(client, cw):
    a = admit(client, cw, bed=cw.beds[0])
    client.post(f"/api/ipd/admissions/{a['id']}/notes", headers=cw.doctor, json={"note": "Confidential clinical note"})
    seen = client.get(f"/api/ipd/admissions/{a['id']}", headers=cw.employee).json()
    assert seen["clinical"] is False and "progress_notes" not in seen and seen["admission"]["bed"]["code"] == "A1"


# ------------------------------------------------------------------ nursing: medicines, vitals, alerts, intake and output
def due_time() -> str:
    return (datetime.now() - timedelta(minutes=5)).strftime("%H:%M")


def test_medication_order_makes_doses_the_nurse_gives_them_once_and_a_refusal_needs_a_reason(client, cw):
    a = admit(client, cw, bed=cw.beds[0])
    order = client.post(f"/api/ipd/admissions/{a['id']}/medication-orders", headers=cw.doctor, json={"medicine_name": "Inj. Ceftriaxone", "dose": "1 g", "route": "IV", "times": [due_time()]})
    assert order.status_code == 201
    chart = client.get(f"/api/nursing/admissions/{a['id']}/chart", headers=cw.nurse).json()
    dose = next(m for m in chart["mar"] if m["medicine_name"] == "Inj. Ceftriaxone")
    assert dose["status"] == "PENDING" and chart["pending_doses"] >= 1
    assert client.post(f"/api/nursing/mar/{dose['id']}/act", headers=cw.nurse, json={"status": "REFUSED"}).status_code == 422
    given = client.post(f"/api/nursing/mar/{dose['id']}/act", headers=cw.nurse, json={"status": "GIVEN"}).json()
    assert given["status"] == "GIVEN" and given["acted_at"]
    assert client.post(f"/api/nursing/mar/{dose['id']}/act", headers=cw.nurse, json={"status": "GIVEN"}).status_code == 409
    for who in (cw.doctor, cw.employee, cw.pharmacy, cw.patient):
        assert client.post(f"/api/nursing/mar/{dose['id']}/act", headers=who, json={"status": "GIVEN"}).status_code == 403
    assert client.post("/api/nursing/mar/999999/act", headers=cw.nurse, json={"status": "GIVEN"}).status_code == 404


def test_a_dose_that_is_not_due_yet_and_a_stopped_medicine_cannot_be_given(client, cw):
    a = admit(client, cw)
    order = client.post(f"/api/ipd/admissions/{a['id']}/medication-orders", headers=cw.doctor, json={"medicine_name": "Tab. Test", "dose": "5 mg", "times": [due_time()]}).json()
    dose = client.get(f"/api/nursing/admissions/{a['id']}/chart", headers=cw.nurse).json()["mar"][0]
    with SessionLocal() as db:
        entry = db.get(MarEntry, dose["id"])
        entry.scheduled_at = datetime.now() + timedelta(hours=5)
        db.commit()
    assert client.post(f"/api/nursing/mar/{dose['id']}/act", headers=cw.nurse, json={"status": "GIVEN"}).status_code == 409
    client.post(f"/api/ipd/medication-orders/{order['id']}/stop", headers=cw.doctor)
    with SessionLocal() as db:
        db.get(MarEntry, dose["id"]).scheduled_at = datetime.now() - timedelta(minutes=5)
        db.commit()
    assert client.post(f"/api/nursing/mar/{dose['id']}/act", headers=cw.nurse, json={"status": "GIVEN"}).status_code == 409
    assert client.post(f"/api/ipd/medication-orders/{order['id']}/stop", headers=cw.other_doctor).status_code == 403


@pytest.mark.parametrize("change", [{"times": []}, {"times": ["8:00"]}, {"times": ["25:00"]}, {"times": ["08:00", "08:00"]}, {"medicine_name": "x"}, {"dose": ""}, {"start_date": "2020-01-01"},
                                    {"end_date": "2020-01-01"}, {"times": "08:00"}])
def test_bad_medication_orders_are_422(client, cw, change):
    a = admit(client, cw)
    body = {"medicine_name": "Tab. Test", "dose": "5 mg", "times": ["08:00"], **change}
    assert client.post(f"/api/ipd/admissions/{a['id']}/medication-orders", headers=cw.doctor, json=body).status_code == 422


def test_inpatient_vitals_raise_alerts_the_nurse_and_doctor_can_acknowledge(client, cw):
    a = admit(client, cw, bed=cw.beds[0])
    res = client.post(f"/api/nursing/admissions/{a['id']}/vitals", headers=cw.nurse, json={"spo2": 85, "pulse": 140}).json()
    assert sorted(x["level"] for x in res["alerts"]) == ["CRITICAL", "CRITICAL"]
    dash = client.get("/api/nursing/dashboard", headers=cw.nurse).json()
    assert dash["open_alerts"] == 2 and dash["patients"][0]["open_alerts"] == 2 and dash["patients"][0]["bed"] == "General Ward A A1"
    alerts = client.get("/api/nursing/alerts", headers=cw.nurse).json()
    assert client.post(f"/api/nursing/alerts/{alerts[0]['id']}/ack", headers=cw.nurse, json={"note": "Doctor informed"}).json()["status"] == "ACKNOWLEDGED"
    assert client.post(f"/api/nursing/alerts/{alerts[1]['id']}/ack", headers=cw.doctor, json={}).json()["status"] == "ACKNOWLEDGED"
    assert client.get("/api/nursing/alerts", headers=cw.nurse).json() == []
    for who in (cw.employee, cw.pharmacy, cw.patient):
        assert client.post(f"/api/nursing/alerts/{alerts[0]['id']}/ack", headers=who, json={}).status_code == 403
        assert client.get("/api/nursing/alerts", headers=who).status_code == 403
    assert client.post(f"/api/nursing/alerts/{alerts[0]['id']}/ack", headers=cw.other_doctor, json={}).status_code == 403
    assert client.post("/api/nursing/alerts/999999/ack", headers=cw.nurse, json={}).status_code == 404


def test_the_hospital_changes_the_alert_thresholds_without_code(client, cw):
    a = admit(client, cw)
    assert client.post(f"/api/nursing/admissions/{a['id']}/vitals", headers=cw.nurse, json={"pulse": 120}).json()["alerts"][0]["level"] == "WARNING"
    rules = client.get("/api/nursing/escalation-rules", headers=cw.admin).json()
    rule = next(r for r in rules if r["parameter"] == "pulse" and r["level"] == "WARNING")
    assert client.put(f"/api/nursing/escalation-rules/{rule['id']}", headers=cw.admin, json={**rule, "threshold": 125}).json()["reviewed_at"]
    assert client.post(f"/api/nursing/admissions/{a['id']}/vitals", headers=cw.nurse, json={"pulse": 120}).json()["alerts"] == []
    assert client.post("/api/nursing/escalation-rules", headers=cw.admin, json={"parameter": "pulse", "comparison": "LT", "threshold": 50, "level": "WARNING", "message": "Slow pulse"}).status_code == 201
    for bad in ({"parameter": "mood"}, {"comparison": "EQ"}, {"threshold": -1}, {"level": "PANIC"}, {"message": "x"}):
        assert client.post("/api/nursing/escalation-rules", headers=cw.admin, json={"parameter": "pulse", "comparison": "LT", "threshold": 50, "level": "WARNING", "message": "Slow pulse", **bad}).status_code == 422
    for who in (cw.doctor, cw.nurse, cw.employee):
        assert client.put(f"/api/nursing/escalation-rules/{rule['id']}", headers=who, json=rule).status_code == 403
        assert client.post("/api/nursing/escalation-rules", headers=who, json=rule).status_code == 403


def test_notes_care_plan_handover_and_intake_output_on_the_chart(client, cw):
    a = admit(client, cw)
    base = f"/api/nursing/admissions/{a['id']}"
    client.post(f"{base}/notes", headers=cw.nurse, json={"text": "Patient comfortable"})
    client.post(f"{base}/notes", headers=cw.nurse, json={"kind": "CARE_PLAN", "text": "Turn every 2 hours"})
    assert client.post(f"{base}/notes", headers=cw.nurse, json={"kind": "HANDOVER", "text": "Stable overnight"}).status_code == 422          # needs a shift
    client.post(f"{base}/notes", headers=cw.nurse, json={"kind": "HANDOVER", "shift": "NIGHT", "text": "Stable overnight"})
    client.post(f"{base}/intake-output", headers=cw.nurse, json={"kind": "INTAKE", "item": "IV saline", "amount_ml": 500})
    totals = client.post(f"{base}/intake-output", headers=cw.nurse, json={"kind": "OUTPUT", "item": "Urine", "amount_ml": 300}).json()["totals"]
    assert totals == {"intake": 500, "output": 300, "balance": 200}
    chart = client.get(f"{base}/chart", headers=cw.doctor).json()
    assert chart["care_plan"]["text"] == "Turn every 2 hours" and chart["handover"]["shift"] == "NIGHT" and {n["by"] for n in chart["notes"]} == {"Nurse Meera"}
    for bad in ({"kind": "INTAKE", "item": "x", "amount_ml": 5}, {"kind": "INTAKE", "item": "Water", "amount_ml": 0}, {"kind": "INTAKE", "item": "Water", "amount_ml": 99999}, {"kind": "DRINK", "item": "Water", "amount_ml": 10}):
        assert client.post(f"{base}/intake-output", headers=cw.nurse, json=bad).status_code == 422
    for who in (cw.employee, cw.pharmacy, cw.patient):
        assert client.get(f"{base}/chart", headers=who).status_code == 403
    assert client.get(f"{base}/chart", headers=cw.other_doctor).status_code == 403
    assert client.get("/api/nursing/admissions/999999/chart", headers=cw.nurse).status_code == 404


def test_a_nurse_only_reaches_patients_who_are_in_the_hospital_now(client, cw):
    outsider = patient(client, cw, "no@example.com", "Not Here", "9811100310")
    assert client.post("/api/nursing/alerts/1/ack", headers=cw.nurse, json={}).status_code == 404
    from app.database.models import ClinicalAlert
    with SessionLocal() as db:
        db.add(ClinicalAlert(patient_id=outsider, level="WARNING", message="Old alert"))
        db.commit()
        alert_id = db.query(ClinicalAlert).one().id
    assert client.post(f"/api/nursing/alerts/{alert_id}/ack", headers=cw.nurse, json={}).status_code == 403          # not admitted and no open visit
    visit(client, cw, outsider)
    assert client.post(f"/api/nursing/alerts/{alert_id}/ack", headers=cw.nurse, json={}).status_code == 200            # now an open visit


# ------------------------------------------------------------------ discharge
SUMMARY = {"final_diagnosis": "Community acquired pneumonia", "hospital_course": "Treated with IV antibiotics, afebrile on day 3", "follow_up": "Review in 1 week", "discharge_medicines": "Tab. Amoxicillin 500 mg TDS 5 days"}


def test_discharge_needs_the_treating_doctors_approved_summary_and_frees_the_bed(client, cw):
    a = admit(client, cw, bed=cw.beds[0])
    base = f"/api/ipd/admissions/{a['id']}"
    client.post(f"{base}/medication-orders", headers=cw.doctor, json={"medicine_name": "Inj. Test", "dose": "1 g", "times": [due_time()]})
    client.post(f"{base}/orders", headers=cw.doctor, json={"kind": "LAB", "text": "CBC"})
    assert client.post(f"{base}/discharge", headers=cw.doctor, json={}).status_code == 409                                                  # no summary
    assert client.post(f"{base}/discharge-summary/approve", headers=cw.doctor).status_code == 409
    client.put(f"{base}/discharge-summary", headers=cw.doctor, json={"final_diagnosis": "Pneumonia"})
    incomplete = client.post(f"{base}/discharge-summary/approve", headers=cw.doctor)
    assert incomplete.status_code == 422 and "hospital course" in incomplete.json()["detail"]
    client.put(f"{base}/discharge-summary", headers=cw.doctor, json=SUMMARY)
    client.post(f"{base}/staff", headers=cw.doctor, json={"user_id": cw.cardiologist_user, "kind": "CONSULTING_DOCTOR"})
    assert client.post(f"{base}/discharge-summary/approve", headers=cw.cardiologist).status_code == 403                                      # a consultant is not the treating doctor
    assert client.post(f"{base}/discharge", headers=cw.doctor, json={}).status_code == 409                                                  # still a draft
    assert client.post(f"{base}/discharge-summary/approve", headers=cw.doctor).json()["status"] == "APPROVED"
    assert client.put(f"{base}/discharge-summary", headers=cw.doctor, json=SUMMARY).status_code == 409                                      # locked after approval
    assert client.post(f"{base}/discharge", headers=cw.cardiologist, json={}).status_code == 403
    done = client.post(f"{base}/discharge", headers=cw.doctor, json={"discharge_type": "NORMAL"}).json()
    assert done["admission"]["status"] == "DISCHARGED" and done["admission"]["bed"] is None and done["pending_charges"] == 0
    assert {b["id"]: b["status"] for w in client.get("/api/ipd/wards", headers=cw.nurse).json() for b in w["beds"]}[cw.beds[0]] == "CLEANING"
    assert client.post(f"{base}/discharge", headers=cw.doctor, json={}).status_code == 409
    assert client.post(f"{base}/notes", headers=cw.doctor, json={"note": "Late note after discharge"}).status_code == 409
    assert client.post(f"{base}/bed", headers=cw.nurse, json={"bed_id": cw.beds[1]}).status_code == 409
    detail = client.get(base, headers=cw.doctor).json()
    assert [m["status"] for m in detail["medication_orders"]] == ["STOPPED"] and [o["status"] for o in detail["orders"]] == ["CANCELLED"]
    assert client.get("/api/ipd/admissions", headers=cw.doctor).json() == []
    assert len(client.get("/api/ipd/admissions?state=DISCHARGED", headers=cw.doctor).json()) == 1
    assert client.post("/api/ipd/admissions", headers=cw.doctor, json={"patient_id": cw.patient_id}).status_code == 201                    # can be admitted again later


def test_discharge_input_and_roles(client, cw):
    a = admit(client, cw)
    base = f"/api/ipd/admissions/{a['id']}"
    client.put(f"{base}/discharge-summary", headers=cw.doctor, json=SUMMARY)
    client.post(f"{base}/discharge-summary/approve", headers=cw.doctor)
    assert client.post(f"{base}/discharge", headers=cw.doctor, json={"discharge_type": "ESCAPE"}).status_code == 422
    for who in (cw.nurse, cw.employee, cw.pharmacy, cw.patient):
        assert client.post(f"{base}/discharge", headers=who, json={}).status_code == 403
        assert client.put(f"{base}/discharge-summary", headers=who, json=SUMMARY).status_code == 403
    assert client.put(f"{base}/discharge-summary", headers=cw.other_doctor, json=SUMMARY).status_code == 403
    assert client.put(f"{base}/discharge-summary", headers=cw.doctor, json={"hospital_course": "x" * 6000}).status_code in (409, 422)
    assert client.get("/api/ipd/admissions?state=NOPE", headers=cw.doctor).status_code == 422


# ------------------------------------------------------------------ emergency
def test_emergency_registration_triage_treatment_and_admission(client, cw):
    reg = client.post("/api/emergency/visits", headers=cw.employee, json={"patient_id": cw.patient_id, "chief_complaint": "Chest pain", "arrival_mode": "AMBULANCE"})
    assert reg.status_code == 201 and reg.json()["status"] == "WAITING"
    vid = reg.json()["id"]
    assert client.post("/api/emergency/visits", headers=cw.employee, json={"patient_id": cw.patient_id, "chief_complaint": "Again"}).status_code == 409
    assert client.post(f"/api/emergency/visits/{vid}/triage", headers=cw.employee, json={"category": 1}).status_code == 403
    tri = client.post(f"/api/emergency/visits/{vid}/triage", headers=cw.nurse, json={"category": 1, "note": "Unresponsive", "vitals": {"pulse": 150, "spo2": 82}}).json()
    assert tri["triage_category"] == 1 and tri["status"] == "TRIAGED" and tri["triage_label"] == "Resuscitation"
    levels = {a["level"] for a in tri["alerts"]}
    assert levels == {"CRITICAL"} and len(tri["alerts"]) >= 2                                   # category 1 and the vitals, from plain rules
    other = patient(client, cw, "ed2@example.com", "Mild Case", "9811100311")
    client.post("/api/emergency/visits", headers=cw.employee, json={"patient_id": other, "chief_complaint": "Sprain"})
    board = client.get("/api/emergency/board", headers=cw.nurse).json()
    assert [b["triage_category"] for b in board] == [1, None] and board[0]["waiting_minutes"] is not None
    assert client.post(f"/api/emergency/visits/{vid}/assign", headers=cw.doctor, json={"doctor_id": cw.doctor_id}).json()["status"] == "IN_TREATMENT"
    assert client.get(f"/api/emergency/visits/{vid}", headers=cw.other_doctor).status_code == 403
    client.post(f"/api/emergency/visits/{vid}/timeline", headers=cw.doctor, json={"kind": "ASSESSMENT", "text": "ECG shows ST elevation"})
    client.post(f"/api/emergency/visits/{vid}/orders", headers=cw.doctor, json={"kind": "LAB", "text": "Troponin", "priority": "STAT"})
    done = client.post(f"/api/emergency/visits/{vid}/disposition", headers=cw.doctor, json={"disposition": "ICU", "bed_id": cw.icu_bed, "diagnosis": "STEMI"}).json()
    assert done["status"] == "DISPOSED" and done["admission_id"]
    kinds = [t["kind"] for t in done["timeline"]]
    assert kinds[0] == "ARRIVAL" and "TRIAGE" in kinds and "ORDER" in kinds and kinds[-1] == "DISPOSITION"
    adm = client.get(f"/api/ipd/admissions/{done['admission_id']}", headers=cw.doctor).json()["admission"]
    assert adm["bed"]["ward_type"] == "ICU" and adm["admitting_diagnosis"] == "STEMI"
    assert client.post(f"/api/emergency/visits/{vid}/disposition", headers=cw.doctor, json={"disposition": "DISCHARGE"}).status_code == 409
    assert client.post(f"/api/emergency/visits/{vid}/timeline", headers=cw.doctor, json={"kind": "NOTE", "text": "after the end"}).status_code == 409


def test_an_unidentified_patient_gets_a_record_and_a_uhid_at_once(client, cw):
    res = client.post("/api/emergency/visits", headers=cw.employee, json={"unidentified": {"gender": "male", "approx_age": 45, "description": "Found on the road"}, "chief_complaint": "Head injury", "arrival_mode": "POLICE"})
    assert res.status_code == 201 and res.json()["unidentified"] and res.json()["patient"]["uhid"]
    ghosts = [p for p in client.get("/api/admin/people?role=PATIENT", headers=cw.admin).json() if p["email"].endswith("@ed.invalid")]
    assert len(ghosts) == 1 and ghosts[0]["is_active"] is False                                                                      # no login for an unidentified patient
    for bad in ({"chief_complaint": "x"}, {"patient_id": cw.patient_id, "unidentified": {"gender": "male"}, "chief_complaint": "Both"}, {"unidentified": {"approx_age": 500}, "chief_complaint": "Old"},
                {"patient_id": 999999, "chief_complaint": "Ghost"}, {"unidentified": {"gender": "robot"}, "chief_complaint": "Alien"}, {"patient_id": cw.patient_id, "chief_complaint": "Fever", "triage_category": 9}):
        assert client.post("/api/emergency/visits", headers=cw.employee, json=bad).status_code in (404, 422), bad
    assert client.post("/api/emergency/visits", headers=cw.pharmacy, json={"unidentified": {}, "chief_complaint": "Fever"}).status_code == 403
    assert client.post("/api/emergency/visits", headers=cw.patient, json={"unidentified": {}, "chief_complaint": "Fever"}).status_code == 403


def test_emergency_outcomes_need_a_note_where_it_matters_and_only_doctors_decide(client, cw):
    vid = client.post("/api/emergency/visits", headers=cw.nurse, json={"patient_id": cw.patient_id, "chief_complaint": "Fever", "triage_category": 4}).json()["id"]
    for who in (cw.nurse, cw.employee, cw.pharmacy, cw.patient):
        assert client.post(f"/api/emergency/visits/{vid}/disposition", headers=who, json={"disposition": "DISCHARGE"}).status_code == 403
    assert client.post(f"/api/emergency/visits/{vid}/disposition", headers=cw.doctor, json={"disposition": "TRANSFER"}).status_code == 422
    assert client.post(f"/api/emergency/visits/{vid}/disposition", headers=cw.doctor, json={"disposition": "TELEPORT"}).status_code == 422
    assert client.post(f"/api/emergency/visits/{vid}/disposition", headers=cw.doctor, json={"disposition": "ADMIT", "bed_id": 999999}).status_code == 422
    assert client.get("/api/emergency/board", headers=cw.nurse).json()[0]["status"] != "DISPOSED"                                         # the failed attempts changed nothing
    out = client.post(f"/api/emergency/visits/{vid}/disposition", headers=cw.doctor, json={"disposition": "DISCHARGE", "note": "Advised paracetamol"}).json()
    assert out["status"] == "DISPOSED" and out["assigned_doctor"] == "Dr. Anjali Sharma"
    assert client.get("/api/emergency/board", headers=cw.nurse).json() == []
    assert client.get("/api/emergency/board", headers=cw.patient).status_code == 403
    assert client.get("/api/emergency/visits/999999", headers=cw.doctor).status_code == 404


# ------------------------------------------------------------------ referral to another department (workflow 7)
def test_a_department_referral_shares_the_records_with_the_specialist_and_brings_the_plan_back(client, cw):
    eid = visit(client, cw)["encounter_id"]
    client.put(f"/api/opd/encounters/{eid}/consultation", headers=cw.doctor, json={**FULL, "assessment": "Chest pain, needs cardiac opinion"})
    body = {"patient_id": cw.patient_id, "from_encounter_id": eid, "to_department_id": cw.cardio, "reason": "Exertional chest pain, please advise", "urgency": "URGENT"}
    req = client.post("/api/referral-requests", headers=cw.doctor, json=body)
    assert req.status_code == 201 and req.json()["status"] == "REQUESTED"
    rid = req.json()["id"]
    assert client.post("/api/referral-requests", headers=cw.doctor, json=body).status_code == 409
    assert client.get(f"/api/doctor/patients/{cw.patient_id}/history", headers=cw.cardiologist).status_code == 403              # the records stay closed until somebody accepts
    incoming = client.get("/api/referral-requests?box=incoming", headers=cw.cardiologist).json()
    assert [r["id"] for r in incoming] == [rid] and client.get("/api/referral-requests?box=incoming", headers=cw.other_doctor).json() == []
    seen = client.get(f"/api/referral-requests/{rid}", headers=cw.cardiologist).json()
    assert seen["origin_consultation"] is None                                                                                      # nothing clinical before accepting
    accepted = client.post(f"/api/referral-requests/{rid}/accept", headers=cw.cardiologist).json()
    assert accepted["status"] == "ACCEPTED" and accepted["to_doctor_id"] == cw.cardiologist_id and accepted["consult_encounter_id"]
    assert client.get(f"/api/doctor/patients/{cw.patient_id}/history", headers=cw.cardiologist).status_code == 200                # shared, authorised access
    assert client.get(f"/api/referral-requests/{rid}", headers=cw.cardiologist).json()["origin_consultation"]["complaint"] == "Fever for 3 days"
    assert any(t["urgent"] for t in client.get("/api/opd/queue", headers=cw.cardiologist).json())                                   # the specialist's queue
    assert client.post(f"/api/referral-requests/{rid}/complete", headers=cw.cardiologist, json={}).status_code == 409           # the consult is not signed yet
    ceid = accepted["consult_encounter_id"]
    client.put(f"/api/opd/encounters/{ceid}/consultation", headers=cw.cardiologist, json={"complaint": "Referred for chest pain", "assessment": "Stable angina", "plan": "Start aspirin, do a stress test"})
    assert client.post(f"/api/opd/encounters/{ceid}/sign", headers=cw.cardiologist).status_code == 200
    done = client.post(f"/api/referral-requests/{rid}/complete", headers=cw.cardiologist, json={"note": "See plan"}).json()
    assert done["status"] == "COMPLETED" and done["consult_note"]["plan"] == "Start aspirin, do a stress test" and done["consult_note"]["status"] == "SIGNED"
    back = client.get(f"/api/referral-requests/{rid}", headers=cw.doctor).json()
    assert back["consult_note"]["assessment"] == "Stable angina" and back["status"] == "COMPLETED"
    assert [r["id"] for r in client.get("/api/referral-requests?box=outgoing", headers=cw.doctor).json()] == [rid]


def test_referral_request_rules(client, cw):
    base = {"patient_id": cw.patient_id, "to_department_id": cw.cardio, "reason": "Please advise on this patient"}
    assert client.post("/api/referral-requests", headers=cw.doctor, json={**base, "to_doctor_id": cw.doctor_id}).status_code == 422
    assert client.post("/api/referral-requests", headers=cw.doctor, json={**base, "to_doctor_id": cw.other_doctor_id}).status_code == 422      # not in that department
    assert client.post("/api/referral-requests", headers=cw.doctor, json={**base, "to_department_id": 999999}).status_code == 422
    assert client.post("/api/referral-requests", headers=cw.doctor, json={**base, "reason": "no"}).status_code == 422
    assert client.post("/api/referral-requests", headers=cw.doctor, json={**base, "from_encounter_id": 999999}).status_code == 422
    assert client.post("/api/referral-requests", headers=cw.other_doctor, json=base).status_code == 403                               # not their patient
    for who in (cw.nurse, cw.employee, cw.pharmacy, cw.patient):
        assert client.post("/api/referral-requests", headers=who, json=base).status_code == 403
    rid = client.post("/api/referral-requests", headers=cw.doctor, json={**base, "to_doctor_id": cw.cardiologist_id}).json()["id"]
    assert client.get(f"/api/referral-requests/{rid}", headers=cw.cardiologist).status_code == 200
    assert client.get(f"/api/referral-requests/{rid}", headers=cw.other_doctor).status_code == 404
    assert client.post(f"/api/referral-requests/{rid}/accept", headers=cw.doctor).status_code == 404                                  # the asker cannot answer
    assert client.post(f"/api/referral-requests/{rid}/decline", headers=cw.cardiologist, json={}).status_code == 422
    assert client.post(f"/api/referral-requests/{rid}/decline", headers=cw.cardiologist, json={"note": "Please do an ECG first"}).json()["status"] == "DECLINED"
    assert client.post(f"/api/referral-requests/{rid}/accept", headers=cw.cardiologist).status_code == 409
    assert client.get("/api/referral-requests?box=sideways", headers=cw.doctor).status_code == 422


def test_a_trainee_referral_puts_the_patient_in_the_doctors_opd_queue(client, cw):
    intern = client.post("/api/admin/trainees", headers=cw.admin, json={"email": "intern@hospital.example.com", "full_name": "Neha Kulkarni", "password": PASSWORD, "department_id": cw.department_id, "trainee_type": "INTERN"})
    assert intern.status_code == 201
    auth = login(client, "intern@hospital.example.com")
    hid = client.post("/api/trainee/histories", headers=auth, json={"patient_id": cw.patient_id}).json()["id"]
    client.put(f"/api/trainee/histories/{hid}", headers=auth, json={"data": {"chief_complaint": "Fever", "duration": "2 days", "allergies": "NONE"}})
    client.post(f"/api/trainee/histories/{hid}/complete", headers=auth)
    ref = client.post("/api/trainee/referrals", headers=auth, json={"history_id": hid, "doctor_id": cw.doctor_id, "reason": "Fever, so General Medicine", "urgent": True}).json()
    queue = client.get("/api/opd/queue", headers=cw.doctor).json()
    assert len(queue) == 1 and queue[0]["urgent"] and queue[0]["source"] == "TRAINEE_REFERRAL"
    assert client.get(f"/api/opd/encounters/{queue[0]['encounter_id']}", headers=cw.doctor).status_code == 200


# ------------------------------------------------------------------ the new Nurse login
def test_the_nurse_account_and_her_limits(client, cw):
    me = client.get("/api/auth/me", headers=cw.nurse).json()
    assert me["role"] == "NURSE"
    access = client.get("/api/access/me", headers=cw.nurse).json()
    assert access["roles"] == ["NURSE"] and "nursing.chart" in access["permissions"] and "consult.write" not in access["permissions"]
    assert client.get("/api/dashboard", headers=cw.nurse).json()["role"] == "NURSE"
    assert client.get("/api/profile", headers=cw.nurse).status_code == 200
    for method, path in (("get", "/api/prescriptions"), ("get", "/api/lab/orders"), ("get", "/api/billing/sales"), ("get", "/api/reports"), ("get", "/api/patients"), ("get", "/api/admin/users"),
                         ("get", "/api/pharmacy/inventory"), ("get", "/api/referrals"), ("get", "/api/trainee/dashboard"), ("get", f"/api/health-history/patient/{cw.patient_id}")):
        assert getattr(client, method)(path, headers=cw.nurse).status_code in (403, 404), path
    assert client.post("/api/admin/nurses", headers=cw.doctor, json={"email": "x@hospital.example.com", "full_name": "Some Nurse"}).status_code == 403
    assert client.get("/api/admin/people?role=NURSE", headers=cw.admin).json()[0]["details"] == [["Job", "Staff nurse"]]


def test_audit_trail_of_the_clinical_steps(client, cw):
    token = visit(client, cw)
    client.put(f"/api/opd/encounters/{token['encounter_id']}/consultation", headers=cw.doctor, json=FULL)
    client.post(f"/api/opd/encounters/{token['encounter_id']}/diagnoses", headers=cw.doctor, json={"text": "Viral fever"})
    client.post(f"/api/opd/encounters/{token['encounter_id']}/sign", headers=cw.doctor)
    a = admit(client, cw, bed=cw.beds[0])
    client.post(f"/api/ipd/admissions/{a['id']}/notes", headers=cw.doctor, json={"note": "Day 1 review done"})
    actions = {x["action"] for x in client.get("/api/admin/audit-logs?limit=200", headers=cw.admin).json()}
    assert {"ENCOUNTER_OPENED", "CONSULTATION_SIGNED", "ADMISSION_CREATED", "PROGRESS_NOTE_ADDED"} <= actions
