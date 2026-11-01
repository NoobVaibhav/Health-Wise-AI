"""Junior doctors (interns and PG residents): history drafts, the doctor suggestion, referrals, what the consultant sees, and what a junior doctor must NOT reach."""
import pytest

from app.services import referral_rules
from tests.conftest import PASSWORD, future, login

GOOD = {"chief_complaint": "Chest pain on climbing stairs", "duration": "2 weeks", "allergies": "NONE", "present_illness": "Pain spreads to the left arm.",
        "smoking": "NONE", "alcohol": "NONE", "vitals": {"pulse": 88, "bp_systolic": 130, "bp_diastolic": 85}}


def department(client, auth, name):
    return next(d["id"] for d in client.get("/api/catalog/departments", headers=auth).json() if d["name"] == name)


def make_trainee(client, world, email="intern@hospital.example.com", name="Neha Kulkarni", kind="INTERN", **extra):
    body = {"email": email, "full_name": name, "password": PASSWORD, "department_id": world.department_id, "grade": kind, "supervisor_id": world.doctor_id, **extra}
    res = client.post("/api/admin/doctors", headers=world.admin, json=body)
    assert res.status_code == 201, res.text
    return login(client, email)


@pytest.fixture()
def tw(client, world):
    """The usual hospital plus an intern and a PG resident, both supervised by the consultant Dr. Anjali."""
    world.intern = make_trainee(client, world)
    world.pg = make_trainee(client, world, "pg@hospital.example.com", "Arjun Deshmukh", "PG_RESIDENT", pg_year=2, pg_branch="MD Medicine")
    return world


def start(client, auth, patient_id):
    res = client.post("/api/trainee/histories", headers=auth, json={"patient_id": patient_id})
    assert res.status_code == 201, res.text
    return res.json()["id"]


def complete(client, auth, patient_id, data=None):
    hid = start(client, auth, patient_id)
    assert client.put(f"/api/trainee/histories/{hid}", headers=auth, json={"data": data or GOOD}).status_code == 200
    done = client.post(f"/api/trainee/histories/{hid}/complete", headers=auth)
    assert done.status_code == 200, done.text
    return hid


def refer(client, auth, hid, doctor_id, **extra):
    return client.post("/api/trainee/referrals", headers=auth, json={"history_id": hid, "doctor_id": doctor_id, "reason": "Chest pain, so Cardiology", **extra})


def refer_with(client, auth, hid, default_doctor, **change):
    """Like refer(), but a change may replace the doctor or the reason."""
    body = {"history_id": hid, "doctor_id": default_doctor, "reason": "Chest pain, so Cardiology", **change}
    return client.post("/api/trainee/referrals", headers=auth, json=body)


# ------------------------------------------------------------------ accounts (the grade rules are in test_doctor_grades.py)
def test_the_junior_doctors_are_doctors_with_a_grade(client, tw):
    people = {p["full_name"]: p for p in client.get("/api/admin/people?role=DOCTOR", headers=tw.admin).json()}
    assert people["Neha Kulkarni"]["grade"] == "INTERN" and people["Arjun Deshmukh"]["grade"] == "PG_RESIDENT"
    assert ["Grade", "PG Resident, year 2, MD Medicine"] in people["Arjun Deshmukh"]["details"]
    assert ["Supervisor", "Dr. Anjali Sharma"] in people["Arjun Deshmukh"]["details"]
    me = client.get("/api/auth/me", headers=tw.pg).json()
    assert me["role"] == "DOCTOR" and me["grade"] == "PG_RESIDENT"


def test_existing_staff_creation_is_unchanged(client, world):
    assert client.post("/api/admin/doctors", headers=world.admin, json={"email": "d@hospital.example.com", "full_name": "Dr Plain Doctor", "department_id": world.department_id}).status_code == 201
    assert client.post("/api/admin/employees", headers=world.admin, json={"email": "e@hospital.example.com", "full_name": "Plain Employee"}).status_code == 201


# ------------------------------------------------------------------ history drafts
def test_a_draft_can_be_half_empty_and_continues_on_the_second_tap(client, tw):
    first = start(client, tw.intern, tw.patient_id)
    assert client.put(f"/api/trainee/histories/{first}", headers=tw.intern, json={"data": {"chief_complaint": "Fever"}}).status_code == 200
    again = client.post("/api/trainee/histories", headers=tw.intern, json={"patient_id": tw.patient_id}).json()
    assert again["id"] == first and again["data"]["chief_complaint"] == "Fever"


def test_complete_needs_complaint_duration_and_an_allergy_answer(client, tw):
    hid = start(client, tw.intern, tw.patient_id)
    res = client.post(f"/api/trainee/histories/{hid}/complete", headers=tw.intern)
    assert res.status_code == 422 and "main complaint" in res.json()["detail"] and "allergy" in res.json()["detail"]
    client.put(f"/api/trainee/histories/{hid}", headers=tw.intern, json={"data": {**GOOD, "allergies": "YES"}})
    assert "allergic to" in client.post(f"/api/trainee/histories/{hid}/complete", headers=tw.intern).json()["detail"]
    client.put(f"/api/trainee/histories/{hid}", headers=tw.intern, json={"data": {**GOOD, "allergies": "YES", "allergy_details": "Penicillin rash"}})
    assert client.post(f"/api/trainee/histories/{hid}/complete", headers=tw.intern).json()["status"] == "COMPLETE"


def test_none_is_an_explicit_allergy_answer_and_clears_old_details(client, tw):
    hid = start(client, tw.intern, tw.patient_id)
    saved = client.put(f"/api/trainee/histories/{hid}", headers=tw.intern, json={"data": {**GOOD, "allergies": "NONE", "allergy_details": "stale"}}).json()
    assert saved["data"]["allergies"] == "NONE" and saved["data"]["allergy_details"] is None


@pytest.mark.parametrize("vitals", [{"pulse": 5}, {"pulse": 900}, {"bp_systolic": -1}, {"temperature_f": 500}, {"spo2": 130}, {"weight_kg": "abc"}, {"height_cm": 1e9}])
def test_vitals_out_of_range_are_422(client, tw, vitals):
    hid = start(client, tw.intern, tw.patient_id)
    assert client.put(f"/api/trainee/histories/{hid}", headers=tw.intern, json={"data": {"vitals": vitals}}).status_code == 422


@pytest.mark.parametrize("field,value", [("allergies", "MAYBE"), ("smoking", "A LOT"), ("chief_complaint", "x" * 400), ("symptoms", ["a"] * 40), ("present_illness", "y" * 5000), ("duration", 12)])
def test_bad_history_values_are_422_never_500(client, tw, field, value):
    hid = start(client, tw.intern, tw.patient_id)
    assert client.put(f"/api/trainee/histories/{hid}", headers=tw.intern, json={"data": {field: value}}).status_code == 422


def test_html_is_removed_from_the_text(client, tw):
    hid = start(client, tw.intern, tw.patient_id)
    data = client.put(f"/api/trainee/histories/{hid}", headers=tw.intern, json={"data": {"chief_complaint": "<script>alert(1)</script>Cough"}}).json()["data"]
    assert data["chief_complaint"] == "alert(1)Cough"


def test_editing_a_completed_history_keeps_the_original(client, tw):
    hid = complete(client, tw.intern, tw.patient_id)
    client.put(f"/api/trainee/histories/{hid}", headers=tw.intern, json={"data": {**GOOD, "duration": "3 weeks"}})
    refer(client, tw.intern, hid, tw.doctor_id)
    ref = client.get("/api/referrals", headers=tw.doctor).json()[0]
    detail = client.get(f"/api/referrals/{ref['id']}", headers=tw.doctor).json()
    assert detail["history"]["data"]["duration"] == "3 weeks" and detail["revisions"][0]["data"]["duration"] == "2 weeks"


# ------------------------------------------------------------------ scope and IDOR
def test_a_trainee_cannot_work_on_a_patient_of_another_department(client, tw):
    cardio = department(client, tw.admin, "Cardiology")
    doc = client.post("/api/admin/doctors", headers=tw.admin, json={"email": "heart@hospital.example.com", "full_name": "Dr Heart Doctor", "password": PASSWORD, "department_id": cardio}).json()["user"]["id"]
    heart_doctor = next(d["id"] for d in client.get("/api/doctors", headers=tw.employee).json() if d["full_name"] == "Dr Heart Doctor")
    other = client.post("/api/patients", headers=tw.employee, json={"email": "other.patient@example.com", "full_name": "Other Patient", "password": PASSWORD, "gender": "male",
                                                                 "date_of_birth": "1990-01-01", "phone": "9888888888", "assigned_doctor_id": heart_doctor}).json()["patient"]["id"]
    assert doc
    assert client.post("/api/trainee/histories", headers=tw.intern, json={"patient_id": other}).status_code == 403
    assert other not in [p["id"] for p in client.get("/api/trainee/patients", headers=tw.intern).json()]
    assert client.post("/api/trainee/histories", headers=tw.intern, json={"patient_id": 999999}).status_code == 404


def test_a_just_registered_patient_without_a_doctor_is_available(client, tw):
    new = client.post("/api/patients", headers=tw.employee, json={"email": "fresh@example.com", "full_name": "Fresh Patient", "password": PASSWORD, "gender": "female",
                                                               "date_of_birth": "1995-02-02", "phone": "9777777777"}).json()["patient"]["id"]
    assert new in [p["id"] for p in client.get("/api/trainee/patients", headers=tw.intern).json()]
    assert client.post("/api/trainee/histories", headers=tw.intern, json={"patient_id": new}).status_code == 201


def test_a_trainee_only_sees_basic_patient_details(client, tw):
    row = next(p for p in client.get("/api/trainee/patients", headers=tw.intern).json() if p["id"] == tw.patient_id)
    assert set(row) == {"id", "patient_code", "full_name", "age", "gender", "phone"}


def test_one_trainee_cannot_read_or_change_the_history_of_another(client, tw):
    hid = start(client, tw.intern, tw.patient_id)
    assert client.get(f"/api/trainee/histories/{hid}", headers=tw.pg).status_code == 404
    assert client.put(f"/api/trainee/histories/{hid}", headers=tw.pg, json={"data": GOOD}).status_code == 404
    assert client.post(f"/api/trainee/histories/{hid}/complete", headers=tw.pg).status_code == 404
    assert client.get(f"/api/trainee/histories/{hid}/suggestion", headers=tw.pg).status_code == 404
    assert client.get(f"/api/trainee/histories/{hid}", headers=tw.intern).status_code == 200
    assert client.get("/api/trainee/histories", headers=tw.pg).json() == []


def test_ids_that_make_no_sense_are_422_or_404(client, tw):
    for path in ("0", "-1", "abc", "99999999999", "999999"):
        assert client.get(f"/api/trainee/histories/{path}", headers=tw.intern).status_code in (404, 422)
    assert client.post("/api/trainee/histories", headers=tw.intern, json={"patient_id": "x"}).status_code == 422
    assert client.post("/api/trainee/referrals", headers=tw.intern, json={"history_id": 999, "doctor_id": tw.doctor_id, "reason": "ok ok"}).status_code == 404


# ------------------------------------------------------------------ suggestion
@pytest.mark.parametrize("complaint,department_name", [
    ("Chest pain on exertion", "Cardiology"), ("severe headache and giddiness", "Neurology"), ("skin rash with itching", "Dermatology"),
    ("knee pain after a fall", "Orthopedics"), ("fever and cough for 3 days", "General Medicine"), ("burning while urinating", "Urology"),
    ("toothache", "Dentistry"), ("sore throat", "ENT"), ("shortness of breath", "Pulmonology"), ("something unusual", "General Medicine"), ("", "General Medicine")])
def test_complaints_map_to_the_right_department(complaint, department_name):
    assert referral_rules.suggest_department(complaint)["department"] == department_name


def test_children_go_to_pediatrics_and_men_do_not_get_a_womens_department():
    assert referral_rules.suggest_department("fever and cough", age=5)["department"] == "Pediatrics"
    assert referral_rules.suggest_department("chest pain", age=5)["department"] == "Cardiology"
    assert referral_rules.suggest_department("missed period", gender="male")["department"] == "General Medicine"
    assert referral_rules.suggest_department("missed period", gender="female")["department"] == "Gynecology & Obstetrics"


def test_the_words_must_match_whole_beginnings_not_the_middle_of_other_words():
    assert referral_rules.suggest_department("scold")["department"] == "General Medicine"      # "cold" inside another word


def test_suggestion_endpoint_gives_the_reason_the_department_and_its_doctors(client, tw):
    hid = start(client, tw.intern, tw.patient_id)
    client.put(f"/api/trainee/histories/{hid}", headers=tw.intern, json={"data": {"chief_complaint": "Fever and cough"}})
    s = client.get(f"/api/trainee/histories/{hid}/suggestion", headers=tw.intern).json()
    assert s["department_name"] == "General Medicine" and s["reason"] and s["matched"]
    assert tw.doctor_id in [d["id"] for d in s["doctors"]]
    card = next(d for d in s["doctors"] if d["id"] == tw.doctor_id)
    assert {"today_appointments", "waiting_referrals", "availability", "specialization_name"} <= set(card)
    manual = client.get(f"/api/trainee/departments/{department(client, tw.admin, 'General Medicine')}/doctors", headers=tw.intern)
    assert manual.status_code == 200 and manual.json()
    assert client.get("/api/trainee/departments/999999/doctors", headers=tw.intern).status_code == 404


# ------------------------------------------------------------------ referral and the doctor's view
def test_a_referral_reaches_the_doctor_with_the_history(client, tw):
    hid = complete(client, tw.pg, tw.patient_id)
    other_doctor = refer(client, tw.pg, hid, tw.other_doctor_id)
    assert other_doctor.status_code == 201, other_doctor.text
    referral = other_doctor.json()
    assert referral["status"] == "SENT" and referral["taken_by"] == "Arjun Deshmukh (PG Resident)"
    listed = client.get("/api/referrals", headers=tw.other_doctor).json()
    assert [r["id"] for r in listed] == [referral["id"]]
    detail = client.get(f"/api/referrals/{referral['id']}", headers=tw.other_doctor).json()
    assert detail["history"]["status"] == "COMPLETE" and detail["history"]["pending_review"] is True
    assert detail["history"]["data"]["chief_complaint"] == GOOD["chief_complaint"]
    dash = client.get("/api/dashboard", headers=tw.other_doctor).json()
    assert [r["id"] for r in dash["trainee_referrals"]] == [referral["id"]]
    assert client.get(f"/api/referrals/patient/{tw.patient_id}", headers=tw.other_doctor).status_code == 200      # access through the referral


def test_a_patient_with_an_assigned_doctor_keeps_that_doctor(client, tw):
    hid = complete(client, tw.intern, tw.patient_id)
    refer(client, tw.intern, hid, tw.other_doctor_id)
    patient = client.get(f"/api/patients/{tw.patient_id}", headers=tw.employee).json()
    assert patient["assigned_doctor_id"] == tw.doctor_id


def test_a_doctor_who_was_not_referred_cannot_see_it(client, tw):
    hid = complete(client, tw.intern, tw.patient_id)
    ref = refer(client, tw.intern, hid, tw.doctor_id).json()
    assert client.get(f"/api/referrals/{ref['id']}", headers=tw.other_doctor).status_code == 404
    assert client.post(f"/api/referrals/{ref['id']}/seen", headers=tw.other_doctor).status_code == 404
    assert client.post(f"/api/referrals/histories/{hid}/verify", headers=tw.other_doctor).status_code == 404
    assert client.put(f"/api/referrals/histories/{hid}", headers=tw.other_doctor, json={"note": "x"}).status_code == 404
    assert client.get("/api/referrals", headers=tw.other_doctor).json() == []


def test_urgent_referrals_come_first_and_a_history_is_sent_once(client, tw):
    first = complete(client, tw.intern, tw.patient_id)
    ref1 = refer(client, tw.intern, first, tw.doctor_id).json()
    assert refer(client, tw.intern, first, tw.doctor_id).status_code == 409
    second_patient = client.post("/api/patients", headers=tw.employee, json={"email": "urgent@example.com", "full_name": "Urgent Patient", "password": PASSWORD, "gender": "male",
                                                                          "date_of_birth": "1980-03-03", "phone": "9666666666", "assigned_doctor_id": tw.doctor_id}).json()["patient"]["id"]
    ref2 = refer(client, tw.intern, complete(client, tw.intern, second_patient), tw.doctor_id, urgent=True).json()
    assert [r["id"] for r in client.get("/api/referrals", headers=tw.doctor).json()] == [ref2["id"], ref1["id"]]


def test_a_draft_cannot_be_sent(client, tw):
    hid = start(client, tw.intern, tw.patient_id)
    assert refer(client, tw.intern, hid, tw.doctor_id).status_code == 409


def test_doctor_marks_seen_then_completed_and_the_trainee_sees_the_status(client, tw):
    ref = refer(client, tw.intern, complete(client, tw.intern, tw.patient_id), tw.doctor_id).json()
    assert [r["status_label"] for r in client.get("/api/trainee/referrals", headers=tw.intern).json()] == ["Sent"]
    assert client.post(f"/api/referrals/{ref['id']}/seen", headers=tw.doctor).json()["status"] == "SEEN"
    assert client.get("/api/trainee/referrals", headers=tw.intern).json()[0]["status_label"] == "Seen by doctor"
    assert client.post(f"/api/referrals/{ref['id']}/complete", headers=tw.doctor).json()["status"] == "COMPLETED"
    assert client.get("/api/trainee/referrals", headers=tw.pg).json() == []


def test_referral_can_book_an_appointment_and_rejects_a_taken_slot(client, tw):
    slot = future(30)
    hid = complete(client, tw.intern, tw.patient_id)
    assert refer(client, tw.intern, hid, tw.doctor_id, book_at=slot).json()["appointment_id"]
    other_patient = client.post("/api/patients", headers=tw.employee, json={"email": "slot@example.com", "full_name": "Slot Patient", "password": PASSWORD, "gender": "male",
                                                                         "date_of_birth": "1985-05-05", "phone": "9555555555"}).json()["patient"]["id"]
    assert refer(client, tw.intern, complete(client, tw.intern, other_patient), tw.doctor_id, book_at=slot).status_code == 409
    assert refer(client, tw.intern, complete(client, tw.intern, other_patient), tw.doctor_id, book_at="2020-01-01T10:00:00").status_code == 422


@pytest.mark.parametrize("change", [{"doctor_id": 999999}, {"reason": ""}, {"reason": "x"}, {"urgent": "maybe"}, {"suggested_department_id": 999999}, {"book_at": "not a time"}])
def test_bad_referral_input_is_422(client, tw, change):
    hid = complete(client, tw.intern, tw.patient_id)
    assert refer_with(client, tw.intern, hid, tw.doctor_id, **change).status_code == 422


# ------------------------------------------------------------------ verification and edits
def test_after_the_doctor_verifies_the_trainee_cannot_change_the_history(client, tw):
    hid = complete(client, tw.intern, tw.patient_id)
    refer(client, tw.intern, hid, tw.doctor_id)
    verified = client.post(f"/api/referrals/histories/{hid}/verify", headers=tw.doctor).json()
    assert verified["status"] == "VERIFIED" and verified["verified_by"] == "Dr. Anjali Sharma"
    assert client.put(f"/api/trainee/histories/{hid}", headers=tw.intern, json={"data": GOOD}).status_code == 409
    assert client.post(f"/api/trainee/histories/{hid}/complete", headers=tw.intern).status_code == 409


def test_doctor_edit_keeps_the_trainees_original_and_adds_a_note(client, tw):
    hid = complete(client, tw.intern, tw.patient_id)
    ref = refer(client, tw.intern, hid, tw.doctor_id).json()
    res = client.put(f"/api/referrals/histories/{hid}", headers=tw.doctor, json={"data": {**GOOD, "duration": "5 days"}, "note": "Please ask about family history."})
    assert res.status_code == 200 and res.json()["data"]["duration"] == "5 days" and res.json()["doctor_notes"].startswith("Please ask")
    detail = client.get(f"/api/referrals/{ref['id']}", headers=tw.doctor).json()
    assert detail["revisions"][0]["data"]["duration"] == "2 weeks"                          # the original, not overwritten silently


def test_the_supervisor_sees_and_corrects_a_pg_students_referral(client, tw):
    ref = refer(client, tw.pg, complete(client, tw.pg, tw.patient_id), tw.other_doctor_id).json()
    mine = next(r for r in client.get("/api/referrals", headers=tw.doctor).json() if r["id"] == ref["id"])
    assert mine["as_supervisor"] and not mine["mine"]
    assert client.post(f"/api/referrals/{ref['id']}/seen", headers=tw.doctor).status_code == 403                       # only the referred doctor marks it seen
    done = client.post(f"/api/referrals/{ref['id']}/review", headers=tw.doctor, json={"approved": False, "note": "Better with me", "doctor_id": tw.doctor_id}).json()
    assert done["doctor_id"] == tw.doctor_id and done["supervisor_note"] == "Better with me" and done["supervisor_reviewed_at"]
    assert client.post(f"/api/referrals/{ref['id']}/review", headers=tw.other_doctor, json={"note": "no"}).status_code in (403, 404)
    assert client.post(f"/api/referrals/{ref['id']}/review", headers=tw.doctor, json={"doctor_id": 999999}).status_code == 422


def test_only_the_supervisor_reviews_a_junior_doctors_referral(client, tw):
    ref = refer(client, tw.intern, complete(client, tw.intern, tw.patient_id), tw.other_doctor_id).json()
    assert client.post(f"/api/referrals/{ref['id']}/review", headers=tw.other_doctor, json={"note": "ok"}).status_code == 403       # the referred doctor is not the supervisor
    assert client.post(f"/api/referrals/{ref['id']}/review", headers=tw.doctor, json={"note": "ok"}).status_code == 200


# ------------------------------------------------------------------ what a junior doctor must not reach
def test_a_junior_doctor_cannot_reach_other_roles_pages_or_other_patients(client, tw):
    for method, path in [("get", "/api/lab/orders"), ("get", "/api/billing/sales"), ("get", "/api/admin/users"), ("get", "/api/admin/audit-logs"), ("post", "/api/admin/doctors"),
                         ("get", "/api/pharmacy/inventory"), ("get", "/api/trainee/admin/overview"), ("get", "/api/access/roles"), ("get", "/api/countersign/awaiting")]:
        res = getattr(client, method)(path, headers=tw.intern, **({"json": {}} if method == "post" else {}))
        assert res.status_code in (403, 404, 405), (method, path, res.status_code)
    assert client.get("/api/patients", headers=tw.intern).json() == []                                       # no patient of theirs yet
    assert client.get(f"/api/patients/{tw.patient_id}", headers=tw.intern).status_code == 403
    assert client.get(f"/api/health-history/patient/{tw.patient_id}", headers=tw.intern).status_code == 403


def test_the_admin_can_only_look_at_the_trainee_area(client, tw):
    ref = refer(client, tw.intern, complete(client, tw.intern, tw.patient_id), tw.doctor_id).json()
    overview = client.get("/api/trainee/admin/overview", headers=tw.admin).json()
    assert len(overview["trainees"]) == 2 and {t["grade"] for t in overview["trainees"]} == {"INTERN", "PG_RESIDENT"} and overview["referrals"][0]["id"] == ref["id"]
    assert "history" not in overview["referrals"][0]
    assert client.get("/api/trainee/dashboard", headers=tw.admin).status_code == 403
    assert client.post("/api/trainee/histories", headers=tw.admin, json={"patient_id": tw.patient_id}).status_code == 403
    assert client.get("/api/trainee/admin/overview", headers=tw.doctor).status_code == 403


def test_a_consultant_or_other_staff_cannot_use_the_junior_endpoints(client, tw):
    for who in (tw.doctor, tw.employee, tw.pharmacy, tw.patient):
        assert client.get("/api/trainee/dashboard", headers=who).status_code == 403
        assert client.post("/api/trainee/histories", headers=who, json={"patient_id": tw.patient_id}).status_code == 403
        assert client.post("/api/trainee/referrals", headers=who, json={"history_id": 1, "doctor_id": tw.doctor_id, "reason": "A reason"}).status_code in (403, 404)
    assert client.get("/api/trainee/dashboard").status_code == 401
    assert client.get("/api/referrals", headers=tw.patient).status_code == 403
    assert client.get("/api/trainee/dashboard", headers=tw.admin).status_code == 403


def test_the_patient_cannot_see_the_trainee_history(client, tw):
    hid = complete(client, tw.intern, tw.patient_id)
    assert client.get(f"/api/referrals/patient/{tw.patient_id}", headers=tw.patient).status_code == 403
    assert client.get(f"/api/trainee/histories/{hid}", headers=tw.patient).status_code == 403


# ------------------------------------------------------------------ dashboard, audit, profile
def test_trainee_dashboard_counts(client, tw):
    before = client.get("/api/trainee/dashboard", headers=tw.intern).json()
    assert before["waiting_count"] >= 1 and before["histories_today"] == 0 and before["trainee"]["type"] == "INTERN"
    start(client, tw.intern, tw.patient_id)
    assert client.get("/api/trainee/dashboard", headers=tw.intern).json()["drafts"][0]["patient_id"] == tw.patient_id
    refer(client, tw.intern, complete(client, tw.intern, tw.patient_id), tw.doctor_id)
    after = client.get("/api/trainee/dashboard", headers=tw.intern).json()
    assert after["histories_today"] == 1 and after["referrals_today"] == 1


def test_history_and_referral_steps_are_in_the_audit_log(client, tw):
    hid = complete(client, tw.intern, tw.patient_id)
    ref = refer(client, tw.intern, hid, tw.doctor_id).json()
    client.post(f"/api/referrals/histories/{hid}/verify", headers=tw.doctor)
    client.post(f"/api/referrals/{ref['id']}/seen", headers=tw.doctor)
    actions = {a["action"] for a in client.get("/api/admin/audit-logs?limit=200", headers=tw.admin).json()}
    assert {"TRAINEE_HISTORY_STARTED", "TRAINEE_HISTORY_COMPLETED", "REFERRAL_CREATED", "TRAINEE_HISTORY_VERIFIED", "REFERRAL_UPDATED", "USER_CREATED"} <= actions


def test_the_profile_shows_the_grade_and_the_supervisor_read_only(client, tw):
    fields = {f["key"]: f for f in client.get("/api/profile", headers=tw.pg).json()["fields"]}
    assert fields["grade"]["value"] == "PG Resident" and fields["grade"]["editable"] is False
    assert fields["supervisor"]["value"] == "Dr. Anjali Sharma" and fields["supervisor"]["editable"] is False


def test_a_trainee_with_records_cannot_be_deleted_but_can_be_deactivated(client, tw):
    complete(client, tw.intern, tw.patient_id)
    uid = next(p["id"] for p in client.get("/api/admin/people?role=DOCTOR", headers=tw.admin).json() if p["full_name"] == "Neha Kulkarni")
    check = client.get(f"/api/admin/users/{uid}/delete-check", headers=tw.admin).json()
    assert check["can_delete"] is False and any("histories" in r for r in check["reasons"])
    assert client.put(f"/api/admin/users/{uid}", headers=tw.admin, json={"is_active": False}).status_code == 200
    assert client.get("/api/trainee/dashboard", headers=tw.intern).status_code == 401
