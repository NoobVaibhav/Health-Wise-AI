"""Doctor grades: intern, PG resident, senior resident and consultant. What each may finish alone, the consultant's countersign, the pharmacy rule, and the
move of the old trainee accounts into grades."""
import pytest
from sqlalchemy import text

from app.database.connection import SessionLocal, engine
from app.database.models import ClinicalOrder, Doctor, LabTestOrder, Prescription, TraineeHistory, User
from app.services import grade_service, lab_service
from tests.conftest import PASSWORD, login

RX = {"clinical_indication": "Fever", "tests": ["CBC"], "items": [{"medicine_name": "Tab. Paracetamol", "dosage": "500 mg", "frequency": "Twice a day", "duration": "3 days", "quantity": 6}]}


def make_doctor(client, world, email, name, grade="CONSULTANT", **extra):
    body = {"email": email, "full_name": name, "password": PASSWORD, "department_id": world.department_id, "grade": grade, **extra}
    if grade != "CONSULTANT":
        body.setdefault("supervisor_id", world.doctor_id)
    res = client.post("/api/admin/doctors", headers=world.admin, json=body)
    assert res.status_code == 201, res.text
    did = next(d["id"] for d in client.get("/api/doctors", headers=world.employee).json() if d["full_name"] == name)
    return login(client, email), did, res.json()["user"]["id"]


@pytest.fixture()
def gw(client, world):
    """The usual hospital plus an intern, a PG resident and a senior resident under Dr. Anjali, and a second consultant."""
    world.intern, world.intern_id, world.intern_user = make_doctor(client, world, "intern@hospital.example.com", "Dr. Ira Intern", "INTERN")
    world.res, world.res_id, world.res_user = make_doctor(client, world, "res@hospital.example.com", "Dr. Ravi Resident", "PG_RESIDENT", pg_year=2, pg_branch="MD Medicine")
    world.sr, world.sr_id, _ = make_doctor(client, world, "sr@hospital.example.com", "Dr. Sana Senior", "SENIOR_RESIDENT", pg_branch="MD Medicine")
    return world


def walk_in(client, w, doctor_id, patient_id=None):
    """Reception puts the patient in this doctor's queue: that is what gives the doctor the visit (and so access to the patient)."""
    res = client.post("/api/opd/walk-in", headers=w.employee, json={"patient_id": patient_id or w.patient_id, "doctor_id": doctor_id})
    assert res.status_code == 201, res.text
    return res.json()["encounter_id"]


# ------------------------------------------------------------------ creating the grades
def test_admin_creates_every_grade_and_a_doctor_cannot(client, gw):
    people = {p["full_name"]: p for p in client.get("/api/admin/people?role=DOCTOR", headers=gw.admin).json()}
    assert [people[n]["grade"] for n in ("Dr. Ira Intern", "Dr. Ravi Resident", "Dr. Sana Senior", "Dr. Anjali Sharma")] == ["INTERN", "PG_RESIDENT", "SENIOR_RESIDENT", "CONSULTANT"]
    assert ["Grade", "PG Resident, year 2, MD Medicine"] in people["Dr. Ravi Resident"]["details"] and people["Dr. Ravi Resident"]["supervisor_id"] == gw.doctor_id
    assert client.get("/api/auth/me", headers=gw.res).json() == {**client.get("/api/auth/me", headers=gw.res).json(), "role": "DOCTOR", "grade": "PG_RESIDENT"}
    body = {"email": "x@hospital.example.com", "full_name": "Dr. Some Intern", "department_id": gw.department_id, "grade": "INTERN", "supervisor_id": gw.doctor_id}
    for who in (gw.doctor, gw.intern, gw.res, gw.employee, gw.patient, gw.pharmacy):
        assert client.post("/api/admin/doctors", headers=who, json=body).status_code == 403


def test_existing_doctors_are_consultants(client, world):
    assert {d["grade"] for d in client.get("/api/doctors", headers=world.employee).json()} == {"CONSULTANT"}
    assert client.get("/api/auth/me", headers=world.doctor).json()["grade"] == "CONSULTANT"


@pytest.mark.parametrize("change,word", [
    ({"supervisor_id": None}, "supervising consultant"), ({"supervisor_id": 999999}, "does not exist"), ({"grade": "GOD"}, ""), ({"department_id": None}, "department"),
    ({"grade": "PG_RESIDENT", "pg_branch": "MD Medicine"}, "PG year"), ({"grade": "PG_RESIDENT", "pg_year": 2}, "PG branch"), ({"grade": "PG_RESIDENT", "pg_year": 4, "pg_branch": "MD"}, ""),
    ({"grade": "PG_RESIDENT", "pg_year": 0, "pg_branch": "MD"}, ""), ({"pg_branch": "x" * 200, "grade": "SENIOR_RESIDENT"}, "")])
def test_junior_doctor_details_are_checked_with_a_clear_422(client, world, change, word):
    body = {"email": "t@hospital.example.com", "full_name": "Dr. Test Junior", "department_id": world.department_id, "grade": "INTERN", "supervisor_id": world.doctor_id, **change}
    res = client.post("/api/admin/doctors", headers=world.admin, json=body)
    assert res.status_code == 422 and word.lower() in res.json()["detail"].lower()


def test_the_supervisor_must_be_a_consultant_of_the_same_department(client, gw):
    body = {"email": "s@hospital.example.com", "full_name": "Dr. Sup Test", "department_id": gw.department_id, "grade": "INTERN"}
    assert client.post("/api/admin/doctors", headers=gw.admin, json={**body, "supervisor_id": gw.res_id}).status_code == 422             # a resident cannot supervise
    cardio = next(d["id"] for d in client.get("/api/catalog/departments", headers=gw.admin).json() if d["name"] == "Cardiology")
    heart = make_doctor(client, gw, "heart@hospital.example.com", "Dr. Heart Doctor", department_id=cardio)[1]
    other_dept = client.post("/api/admin/doctors", headers=gw.admin, json={**body, "supervisor_id": heart})
    assert other_dept.status_code == 422 and "same department" in other_dept.json()["detail"]
    assert cardio and client.post("/api/admin/doctors", headers=gw.admin, json={**body, "supervisor_id": gw.doctor_id}).status_code == 201


def test_a_consultant_keeps_the_form_as_it_was_and_ignores_junior_fields(client, world):
    res = client.post("/api/admin/doctors", headers=world.admin, json={"email": "c@hospital.example.com", "full_name": "Dr. Plain Consultant", "department_id": world.department_id,
                                                                         "supervisor_id": world.doctor_id, "pg_year": 2, "can_prescribe_independently": True})
    assert res.status_code == 201
    with SessionLocal() as db:
        d = db.query(Doctor).join(User).filter(User.email == "c@hospital.example.com").one()
        assert (d.current_grade, d.supervisor_id, d.pg_year, d.can_prescribe_independently) == ("CONSULTANT", None, None, False)


# ------------------------------------------------------------------ the prescription
def test_an_intern_cannot_prescribe(client, gw):
    walk_in(client, gw, gw.intern_id)
    res = client.post("/api/prescriptions", headers=gw.intern, json={**RX, "patient_id": gw.patient_id})
    assert res.status_code == 403 and "intern cannot prescribe" in res.json()["detail"]
    assert client.get("/api/prescriptions", headers=gw.intern).json() == []


def test_a_residents_prescription_waits_for_the_consultant_and_the_pharmacy_cannot_touch_it(client, gw):
    walk_in(client, gw, gw.res_id)
    rx = client.post("/api/prescriptions", headers=gw.res, json={**RX, "patient_id": gw.patient_id})
    assert rx.status_code == 201 and rx.json()["status"] == "PENDING_COUNTERSIGN"
    rid, item = rx.json()["id"], rx.json()["items"][0]["id"]
    assert client.get("/api/pharmacy/prescriptions", headers=gw.pharmacy).json() == []                                        # not on the pharmacy's list
    assert client.get(f"/api/prescriptions/{rid}", headers=gw.pharmacy).status_code == 404
    assert client.post("/api/pharmacy/dispense", headers=gw.pharmacy, json={"prescription_item_id": item, "quantity": 1}).status_code in (404, 409)
    assert client.get("/api/prescriptions", headers=gw.patient).json() == []                                                  # the patient does not see it yet
    assert client.get(f"/api/prescriptions/{rid}", headers=gw.patient).status_code == 403
    with SessionLocal() as db:
        lab_service.sync_orders(db)
        assert db.query(LabTestOrder).count() == 0                                                                            # no lab order from a prescription that is not in force
    waiting = client.get("/api/countersign/awaiting", headers=gw.doctor).json()
    assert [w["kind"] for w in waiting] == ["PRESCRIPTION"] and "Paracetamol" in waiting[0]["summary"] and waiting[0]["requested_by"] == "Dr. Ravi Resident"
    mine = client.get("/api/countersign/mine", headers=gw.res).json()
    assert mine[0]["status"] == "PENDING"


def test_the_consultant_countersigns_and_then_the_pharmacy_can_dispense(client, gw):
    walk_in(client, gw, gw.res_id)
    rx = client.post("/api/prescriptions", headers=gw.res, json={**RX, "patient_id": gw.patient_id}).json()
    cid = client.get("/api/countersign/awaiting", headers=gw.doctor).json()[0]["id"]
    assert client.post(f"/api/countersign/{cid}/approve", headers=gw.res, json={}).status_code in (403, 404)                  # the resident cannot approve their own
    assert client.post(f"/api/countersign/{cid}/approve", headers=gw.other_doctor, json={}).status_code == 404               # not the supervisor of this resident
    done = client.post(f"/api/countersign/{cid}/approve", headers=gw.doctor, json={"comment": "Fine"}).json()
    assert done["status"] == "APPROVED" and done["comment"] == "Fine"
    assert client.post(f"/api/countersign/{cid}/approve", headers=gw.doctor, json={}).status_code == 409
    assert [r["id"] for r in client.get("/api/pharmacy/prescriptions", headers=gw.pharmacy).json()] == [rx["id"]]
    ok = client.post("/api/pharmacy/dispense", headers=gw.pharmacy, json={"prescription_item_id": rx["items"][0]["id"], "quantity": 2})
    assert ok.status_code == 200, ok.text
    assert [r["status"] for r in client.get("/api/prescriptions", headers=gw.patient).json()] == ["PARTIALLY_DISPENSED"]
    with SessionLocal() as db:
        lab_service.sync_orders(db)
        assert db.query(LabTestOrder).count() == 1                                                                            # the test is ordered once the prescription is in force
    assert client.get("/api/countersign/awaiting", headers=gw.doctor).json() == []
    assert client.get("/api/countersign/awaiting?state=DECIDED", headers=gw.doctor).json()[0]["status"] == "APPROVED"


def test_edit_and_approve_keeps_the_residents_original(client, gw):
    walk_in(client, gw, gw.res_id)
    rx = client.post("/api/prescriptions", headers=gw.res, json={**RX, "patient_id": gw.patient_id}).json()
    cid = client.get("/api/countersign/awaiting", headers=gw.doctor).json()[0]["id"]
    new_items = [{"medicine_name": "Tab. Ibuprofen", "dosage": "400 mg", "frequency": "Thrice a day", "duration": "2 days", "quantity": 6}]
    assert client.post(f"/api/countersign/{cid}/approve", headers=gw.doctor, json={"items": new_items}).json()["status"] == "EDITED"
    shown = client.get(f"/api/prescriptions/{rx['id']}", headers=gw.pharmacy).json()
    assert [i["medicine_name"] for i in shown["items"]] == ["Tab. Ibuprofen"]
    with SessionLocal() as db:
        from app.database.models import CountersignRequest
        original = db.get(CountersignRequest, cid).original_json
        assert "Paracetamol" in original                                                                                      # the resident's version is still there
    assert client.post(f"/api/countersign/{cid}/approve", headers=gw.doctor, json={"items": []}).status_code in (409, 422)


def test_return_with_a_comment_blocks_the_prescription_and_tells_the_resident(client, gw):
    walk_in(client, gw, gw.res_id)
    rx = client.post("/api/prescriptions", headers=gw.res, json={**RX, "patient_id": gw.patient_id}).json()
    cid = client.get("/api/countersign/awaiting", headers=gw.doctor).json()[0]["id"]
    assert client.post(f"/api/countersign/{cid}/return", headers=gw.doctor, json={"comment": "x"}).status_code == 422
    back = client.post(f"/api/countersign/{cid}/return", headers=gw.doctor, json={"comment": "Please check the dose for the age"}).json()
    assert back["status"] == "RETURNED"
    assert client.get("/api/countersign/mine", headers=gw.res).json()[0]["comment"] == "Please check the dose for the age"
    assert client.get("/api/prescriptions", headers=gw.res).json()[0]["status"] == "RETURNED"
    assert client.get("/api/pharmacy/prescriptions", headers=gw.pharmacy).json() == []
    assert client.post(f"/api/countersign/{cid}/approve", headers=gw.doctor, json={}).status_code == 409


def test_only_the_administrator_can_let_a_resident_prescribe_independently(client, gw):
    walk_in(client, gw, gw.res_id)
    uid = gw.res_user
    for who in (gw.doctor, gw.res, gw.intern, gw.employee):
        assert client.put(f"/api/admin/users/{uid}", headers=who, json={"can_prescribe_independently": True}).status_code == 403
    assert client.put(f"/api/admin/users/{uid}", headers=gw.admin, json={"can_prescribe_independently": True}).status_code == 200
    rx = client.post("/api/prescriptions", headers=gw.res, json={**RX, "patient_id": gw.patient_id}).json()
    assert rx["status"] == "ACTIVE"
    assert [r["id"] for r in client.get("/api/pharmacy/prescriptions", headers=gw.pharmacy).json()] == [rx["id"]]
    assert client.get("/api/countersign/awaiting", headers=gw.doctor).json() == []
    client.put(f"/api/admin/users/{uid}", headers=gw.admin, json={"can_prescribe_independently": False})
    assert client.post("/api/prescriptions", headers=gw.res, json={**RX, "patient_id": gw.patient_id}).json()["status"] == "PENDING_COUNTERSIGN"
    intern_user = gw.intern_user
    client.put(f"/api/admin/users/{intern_user}", headers=gw.admin, json={"can_prescribe_independently": True})
    walk_in(client, gw, gw.intern_id)
    assert client.post("/api/prescriptions", headers=gw.intern, json={**RX, "patient_id": gw.patient_id}).status_code == 403       # even with the flag an intern never prescribes


def test_the_administrator_changes_a_grade_with_the_same_checks_and_it_is_audited(client, gw):
    uid = gw.res_user
    assert client.put(f"/api/admin/users/{uid}", headers=gw.admin, json={"grade": "SENIOR_RESIDENT"}).status_code == 200
    assert client.get("/api/auth/me", headers=gw.res).json()["grade"] == "SENIOR_RESIDENT"
    assert client.put(f"/api/admin/users/{uid}", headers=gw.admin, json={"grade": "PG_RESIDENT", "pg_year": None}).status_code == 422             # a resident needs the year
    assert client.put(f"/api/admin/users/{uid}", headers=gw.admin, json={"supervisor_id": gw.res_id}).status_code == 422
    assert client.put(f"/api/admin/users/{uid}", headers=gw.admin, json={"grade": "CONSULTANT"}).status_code == 200
    assert client.get("/api/auth/me", headers=gw.res).json()["grade"] == "CONSULTANT"
    patient_user = client.get("/api/admin/people?role=PATIENT", headers=gw.admin).json()[0]["id"]
    assert client.put(f"/api/admin/users/{patient_user}", headers=gw.admin, json={"grade": "INTERN"}).status_code == 422
    actions = {a["action"] for a in client.get("/api/admin/audit-logs?limit=200", headers=gw.admin).json()}
    assert "GRADE_CHANGED" in actions


# ------------------------------------------------------------------ orders, diagnoses, consultation, discharge
def test_an_interns_order_is_a_draft_until_the_consultant_approves_a_residents_goes_ahead(client, gw):
    eid = walk_in(client, gw, gw.intern_id)
    order = client.post(f"/api/opd/encounters/{eid}/orders", headers=gw.intern, json={"kind": "LAB", "text": "CBC"}).json()
    assert order["status"] == "DRAFT"
    waiting = client.get("/api/countersign/awaiting", headers=gw.doctor).json()
    assert waiting[0]["kind"] == "ORDER" and "CBC" in waiting[0]["summary"]
    assert client.post(f"/api/countersign/{waiting[0]['id']}/approve", headers=gw.doctor, json={}).status_code == 200
    with SessionLocal() as db:
        assert db.get(ClinicalOrder, order["id"]).status == "ORDERED"
    returned = client.post(f"/api/opd/encounters/{eid}/orders", headers=gw.intern, json={"kind": "RADIOLOGY", "text": "Chest X-ray"}).json()
    cid = client.get("/api/countersign/awaiting", headers=gw.doctor).json()[0]["id"]
    client.post(f"/api/countersign/{cid}/return", headers=gw.doctor, json={"comment": "Not needed for this"})
    with SessionLocal() as db:
        assert db.get(ClinicalOrder, returned["id"]).status == "CANCELLED"
    reid = walk_in(client, gw, gw.res_id)
    assert client.post(f"/api/opd/encounters/{reid}/orders", headers=gw.res, json={"kind": "LAB", "text": "CBC"}).json()["status"] == "ORDERED"


def test_diagnosis_is_a_draft_for_an_intern_provisional_for_a_resident_final_only_for_a_consultant(client, gw):
    ie, re_ = walk_in(client, gw, gw.intern_id), walk_in(client, gw, gw.res_id)
    assert client.post(f"/api/opd/encounters/{ie}/diagnoses", headers=gw.intern, json={"text": "Viral fever", "kind": "FINAL"}).json()["kind"] == "DRAFT"
    assert client.post(f"/api/opd/encounters/{re_}/diagnoses", headers=gw.res, json={"text": "Viral fever", "kind": "PROVISIONAL"}).json()["kind"] == "PROVISIONAL"
    refused = client.post(f"/api/opd/encounters/{re_}/diagnoses", headers=gw.res, json={"text": "Viral fever", "kind": "FINAL"})
    assert refused.status_code == 403 and "consultant" in refused.json()["detail"]
    ce = walk_in(client, gw, gw.doctor_id)
    assert client.post(f"/api/opd/encounters/{ce}/diagnoses", headers=gw.doctor, json={"text": "Viral fever", "kind": "FINAL"}).json()["kind"] == "FINAL"


def test_an_intern_cannot_sign_a_consultation_but_a_resident_can(client, gw):
    body = {"complaint": "Fever", "assessment": "Viral fever"}
    ie, re_ = walk_in(client, gw, gw.intern_id), walk_in(client, gw, gw.res_id)
    assert client.put(f"/api/opd/encounters/{ie}/consultation", headers=gw.intern, json=body).status_code == 200            # the draft is saved
    refused = client.post(f"/api/opd/encounters/{ie}/sign", headers=gw.intern)
    assert refused.status_code == 403 and "intern" in refused.json()["detail"].lower()
    client.put(f"/api/opd/encounters/{re_}/consultation", headers=gw.res, json=body)
    assert client.post(f"/api/opd/encounters/{re_}/sign", headers=gw.res).status_code == 200


def test_a_resident_prepares_the_discharge_summary_and_only_the_consultant_approves_and_discharges(client, gw):
    adm = client.post("/api/ipd/admissions", headers=gw.res, json={"patient_id": gw.patient_id, "diagnosis": "Pneumonia"})
    assert adm.status_code in (201, 403)
    walk_in(client, gw, gw.res_id)
    adm = client.post("/api/ipd/admissions", headers=gw.res, json={"patient_id": gw.patient_id, "diagnosis": "Pneumonia"})
    assert adm.status_code == 201, adm.text
    aid = adm.json()["id"]
    base = f"/api/ipd/admissions/{aid}"
    summary = {"final_diagnosis": "Pneumonia", "hospital_course": "Treated with IV antibiotics", "follow_up": "Review in 1 week"}
    assert client.put(f"{base}/discharge-summary", headers=gw.res, json=summary).status_code == 200
    assert client.post(f"{base}/discharge-summary/approve", headers=gw.res).status_code == 403                                 # a resident cannot approve their own
    assert client.post(f"{base}/discharge", headers=gw.res, json={}).status_code in (403, 409)
    waiting = client.get("/api/countersign/awaiting", headers=gw.doctor).json()
    assert [w["kind"] for w in waiting] == ["DISCHARGE_SUMMARY"]
    assert client.get(base, headers=gw.doctor).status_code == 200                                                             # the supervisor sees their resident's inpatient
    assert client.post(f"/api/countersign/{waiting[0]['id']}/approve", headers=gw.doctor, json={}).status_code == 200
    done = client.post(f"{base}/discharge", headers=gw.doctor, json={})
    assert done.status_code == 200 and done.json()["admission"]["status"] == "DISCHARGED"


def test_an_intern_admits_only_under_a_consultant_and_cannot_order_medicines_or_write_the_summary(client, gw):
    walk_in(client, gw, gw.intern_id)
    assert client.post("/api/ipd/admissions", headers=gw.intern, json={"patient_id": gw.patient_id, "attending_doctor_id": gw.intern_id}).status_code == 422
    adm = client.post("/api/ipd/admissions", headers=gw.intern, json={"patient_id": gw.patient_id, "diagnosis": "Fever"})
    assert adm.status_code == 201 and adm.json()["attending_doctor_id"] == gw.doctor_id                                       # the supervisor becomes the attending doctor
    aid = adm.json()["id"]
    client.post(f"/api/ipd/admissions/{aid}/staff", headers=gw.doctor, json={"user_id": gw.intern_user, "kind": "CONSULTING_DOCTOR"})
    med = {"medicine_name": "Inj. Test", "dose": "1 g", "times": ["08:00"]}
    assert client.post(f"/api/ipd/admissions/{aid}/medication-orders", headers=gw.intern, json=med).status_code == 403
    assert client.put(f"/api/ipd/admissions/{aid}/discharge-summary", headers=gw.intern, json={"final_diagnosis": "x"}).status_code == 403
    assert client.post(f"/api/ipd/admissions/{aid}/notes", headers=gw.intern, json={"note": "Day 1 seen with the consultant"}).status_code == 201


def test_an_intern_does_not_decide_the_emergency_outcome(client, gw):
    vid = client.post("/api/emergency/visits", headers=gw.employee, json={"patient_id": gw.patient_id, "chief_complaint": "Fever"}).json()["id"]
    client.post(f"/api/emergency/visits/{vid}/assign", headers=gw.intern, json={"doctor_id": gw.intern_id})
    assert client.post(f"/api/emergency/visits/{vid}/disposition", headers=gw.intern, json={"disposition": "DISCHARGE"}).status_code == 403


# ------------------------------------------------------------------ scope
def test_a_junior_doctor_reaches_only_the_patients_they_work_on(client, gw):
    other = client.post("/api/patients", headers=gw.employee, json={"email": "o@example.com", "full_name": "Other Patient", "password": PASSWORD, "gender": "male", "date_of_birth": "1990-01-01",
                                                                    "phone": "9811100001", "assigned_doctor_id": gw.other_doctor_id}).json()["patient"]["id"]
    assert client.get(f"/api/doctor/patients/{gw.patient_id}/history", headers=gw.res).status_code == 403
    walk_in(client, gw, gw.res_id)
    assert client.get(f"/api/doctor/patients/{gw.patient_id}/history", headers=gw.res).status_code == 200
    assert client.get(f"/api/doctor/patients/{other}/history", headers=gw.res).status_code == 403
    assert client.get(f"/api/doctor/patients/{gw.patient_id}/history", headers=gw.intern).status_code == 403              # a different junior doctor


def test_the_juniors_history_and_referral_flow_goes_to_a_consultant(client, gw):
    hid = client.post("/api/trainee/histories", headers=gw.intern, json={"patient_id": gw.patient_id}).json()["id"]
    client.put(f"/api/trainee/histories/{hid}", headers=gw.intern, json={"data": {"chief_complaint": "Fever", "duration": "2 days", "allergies": "NONE"}})
    client.post(f"/api/trainee/histories/{hid}/complete", headers=gw.intern)
    suggestion = client.get(f"/api/trainee/histories/{hid}/suggestion", headers=gw.intern).json()
    assert {d["id"] for d in suggestion["doctors"]} == {gw.doctor_id, gw.other_doctor_id}                                    # consultants only, never the juniors
    ref = client.post("/api/trainee/referrals", headers=gw.intern, json={"history_id": hid, "doctor_id": gw.doctor_id, "reason": "Fever, so General Medicine"})
    assert ref.status_code == 201 and ref.json()["taken_by"] == "Dr. Ira Intern (Intern)"
    assert client.post(f"/api/referrals/histories/{hid}/verify", headers=gw.doctor).json()["status"] == "VERIFIED"
    assert client.put(f"/api/trainee/histories/{hid}", headers=gw.intern, json={"data": {"chief_complaint": "Changed"}}).status_code == 409


# ------------------------------------------------------------------ the move of the old trainee accounts
def test_old_trainee_accounts_become_doctor_grades_with_their_histories_and_it_repeats_safely(client, world):
    with engine.begin() as c:
        c.execute(text("CREATE TABLE IF NOT EXISTS trainees (id INTEGER PRIMARY KEY, user_id INTEGER, department_id INTEGER, trainee_type VARCHAR(15), year_branch VARCHAR(120), supervisor_id INTEGER, phone VARCHAR(30))"))
    with SessionLocal() as db:
        users = []
        for i, email in enumerate(("old.intern@hospital.example.com", "old.pg@hospital.example.com")):
            u = User(email=email, password_hash="x", full_name=f"Old Trainee {i}", role="TRAINEE", is_active=True)
            db.add(u)
            db.flush()
            users.append(u.id)
        db.commit()
    with engine.begin() as c:
        c.execute(text("INSERT INTO trainees (id, user_id, department_id, trainee_type, year_branch, supervisor_id) VALUES (1, :u1, :d, 'INTERN', NULL, :s), (2, :u2, :d, 'PG_STUDENT', 'MD Medicine, Year 2', :s)"),
                  {"u1": users[0], "u2": users[1], "d": world.department_id, "s": world.doctor_id})
    with SessionLocal() as db:                                                                         # a legacy doctor row without a grade
        db.query(Doctor).update({Doctor.grade: None})
        db.add_all([TraineeHistory(patient_id=world.patient_id, trainee_id=1, status="COMPLETE"), TraineeHistory(patient_id=world.patient_id, trainee_id=2, status="DRAFT")])
        db.commit()
    for _ in range(2):                                                                                 # twice: the second run changes nothing
        with SessionLocal() as db:
            grade_service.migrate(db)
    with SessionLocal() as db:
        intern = db.query(Doctor).join(User).filter(User.email == "old.intern@hospital.example.com").one()
        pg = db.query(Doctor).join(User).filter(User.email == "old.pg@hospital.example.com").one()
        assert (intern.current_grade, intern.supervisor_id, intern.user.role) == ("INTERN", world.doctor_id, "DOCTOR")
        assert (pg.current_grade, pg.pg_year, pg.pg_branch) == ("PG_RESIDENT", 2, "MD Medicine")
        histories = {h.status: h.trainee_id for h in db.query(TraineeHistory)}
        assert histories == {"COMPLETE": intern.id, "DRAFT": pg.id}                                    # the histories follow their authors
        assert {d.current_grade for d in db.query(Doctor).filter(Doctor.id.in_((world.doctor_id, world.other_doctor_id)))} == {"CONSULTANT"}
        assert db.query(Doctor).filter(Doctor.grade.is_(None)).count() == 0
