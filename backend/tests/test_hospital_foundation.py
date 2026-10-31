"""Phase 2: roles and permissions, hospital profile and settings, branches, price list, UHID, duplicate check, consents, ABHA, insurance, merge, break-glass."""
import re

import pytest

from app.database.connection import SessionLocal, init_db
from app.database.models import Patient, Permission, Role
from tests.conftest import PASSWORD, login

UHID_RE = re.compile(r"^[A-Z0-9]{2,8}-\d{2}-\d{6}$")


def new_patient(client, world, email, name, dob="1990-01-01", phone="9811111111", **extra):
    res = client.post("/api/patients", headers=world.employee, json={"email": email, "full_name": name, "password": PASSWORD, "gender": "male", "date_of_birth": dob, "phone": phone, **extra})
    return res


def make(client, world, path, email, name, **extra):
    res = client.post(f"/api/admin/{path}", headers=world.admin, json={"email": email, "full_name": name, "password": PASSWORD, **extra})
    assert res.status_code == 201, res.text
    return login(client, email), res.json()["user"]["id"]


# ------------------------------------------------------------------ roles and permissions
def test_every_login_role_maps_to_a_hospital_role_with_permissions(client, world):
    mine = {who: client.get("/api/access/me", headers=h).json() for who, h in (("admin", world.admin), ("doctor", world.doctor), ("employee", world.employee), ("patient", world.patient), ("pharmacy", world.pharmacy))}
    assert "SUPER_ADMIN" in mine["admin"]["roles"] and "HOSPITAL_ADMIN" in mine["admin"]["roles"] and "role.manage" in mine["admin"]["permissions"]
    assert mine["doctor"]["roles"] == ["DOCTOR"] and "breakglass.use" in mine["doctor"]["permissions"] and "patient.merge" not in mine["doctor"]["permissions"]
    assert mine["employee"]["roles"] == ["RECEPTIONIST"] and "patient.register" in mine["employee"]["permissions"] and "patient.merge" not in mine["employee"]["permissions"]
    assert mine["patient"]["permissions"] == [] and mine["pharmacy"]["roles"] == ["PHARMACIST"]


def test_the_25_hospital_roles_and_their_permissions_exist_and_seeding_repeats_safely(client, world):
    roles = client.get("/api/access/roles", headers=world.admin).json()
    assert len(roles) == 25 and {r["code"] for r in roles} >= {"NURSE", "PATHOLOGIST", "RADIOLOGIST", "BILLING_EXECUTIVE", "AUDITOR", "SUPER_ADMIN", "PATIENT"}
    init_db(); init_db()
    with SessionLocal() as db:
        assert db.query(Role).count() == 25 and db.query(Permission).count() == len(client.get("/api/access/permissions", headers=world.admin).json())


def test_only_the_admin_manages_roles(client, world):
    for who in (world.doctor, world.employee, world.pharmacy, world.patient):
        assert client.get("/api/access/roles", headers=who).status_code == 403
        assert client.get("/api/access/permissions", headers=who).status_code == 403
        assert client.put("/api/access/roles/1/permissions", headers=who, json={"permissions": []}).status_code == 403
        assert client.put("/api/access/users/1/roles", headers=who, json={"roles": ["NURSE"]}).status_code == 403
    assert client.get("/api/access/roles").status_code == 401


def test_an_extra_role_adds_permissions_and_removing_it_takes_them_away(client, world):
    doc_user = client.get("/api/admin/people?role=DOCTOR", headers=world.admin).json()[0]["id"]
    assert "patient.merge" not in client.get("/api/access/me", headers=world.doctor).json()["permissions"]
    assert client.put(f"/api/access/users/{doc_user}/roles", headers=world.admin, json={"roles": ["BRANCH_ADMIN"]}).status_code == 200
    assert "audit.view" in client.get("/api/access/me", headers=world.doctor).json()["permissions"]
    client.put(f"/api/access/users/{doc_user}/roles", headers=world.admin, json={"roles": []})
    assert "audit.view" not in client.get("/api/access/me", headers=world.doctor).json()["permissions"]


@pytest.mark.parametrize("roles", [["NOPE"], ["SUPER_ADMIN"], "x", [1], [""]])
def test_bad_role_assignments_are_422(client, world, roles):
    assert client.put("/api/access/users/2/roles", headers=world.admin, json={"roles": roles}).status_code == 422


def test_a_patient_cannot_be_given_a_staff_role(client, world):
    patient_user = client.get("/api/admin/people?role=PATIENT", headers=world.admin).json()[0]["id"]
    assert client.put(f"/api/access/users/{patient_user}/roles", headers=world.admin, json={"roles": ["NURSE"]}).status_code == 422


def test_role_permissions_can_be_edited_but_the_admin_keeps_role_management(client, world):
    roles = {r["code"]: r for r in client.get("/api/access/roles", headers=world.admin).json()}
    nurse = roles["NURSE"]
    done = client.put(f"/api/access/roles/{nurse['id']}/permissions", headers=world.admin, json={"permissions": ["hospital.view"]}).json()
    assert done["permissions"] == ["hospital.view"]
    assert client.put(f"/api/access/roles/{nurse['id']}/permissions", headers=world.admin, json={"permissions": ["no.such"]}).status_code == 422
    assert client.put(f"/api/access/roles/{roles['HOSPITAL_ADMIN']['id']}/permissions", headers=world.admin, json={"permissions": ["hospital.view"]}).status_code == 422
    assert client.put("/api/access/roles/999999/permissions", headers=world.admin, json={"permissions": []}).status_code == 404
    init_db()                                                                              # a restart does not undo the edit
    assert client.get("/api/access/roles", headers=world.admin).json()[[r["code"] for r in client.get("/api/access/roles", headers=world.admin).json()].index("NURSE")]["permissions"] == ["hospital.view"]


# ------------------------------------------------------------------ hospital profile, branches, settings, price list
def test_hospital_profile_is_saved_and_used_on_the_prescription_letterhead(client, world):
    assert client.put("/api/hospital/profile", headers=world.admin, json={"name": "City Hospital", "address": "12 MG Road, Pune", "phone": "020 1234 5678", "gst_number": "27ABCDE1234F1Z5"}).status_code == 200
    assert client.get("/api/hospital/profile", headers=world.doctor).json()["name"] == "City Hospital"
    rx = client.post("/api/prescriptions", headers=world.doctor, json={"patient_id": world.patient_id, "clinical_indication": "Fever", "items": [
        {"medicine_name": "Tab. Test", "dosage": "5 mg", "frequency": "Daily", "duration": "5 days", "quantity": 5}]}).json()
    assert rx["hospital"]["name"] == "City Hospital" and rx["hospital"]["address"] == "12 MG Road, Pune"


def test_only_permitted_staff_change_the_hospital(client, world):
    for who in (world.doctor, world.employee, world.pharmacy, world.patient):
        assert client.put("/api/hospital/profile", headers=who, json={"name": "X"}).status_code == 403
        assert client.post("/api/hospital/branches", headers=who, json={"code": "ZZ", "name": "Zed"}).status_code == 403
        assert client.put("/api/hospital/settings", headers=who, json={"key": "currency", "value": "USD"}).status_code == 403
        assert client.post("/api/hospital/services", headers=who, json={"code": "X1", "name": "Test", "category": "OTHER"}).status_code == 403
    assert client.get("/api/hospital/profile").status_code == 401
    assert client.get("/api/hospital/profile", headers=world.patient).status_code == 403          # patients have no use for it


def test_branches_have_unique_codes_and_one_always_stays_active(client, world):
    branches = client.get("/api/hospital/branches", headers=world.admin).json()
    assert len(branches) == 1 and branches[0]["is_active"]
    added = client.post("/api/hospital/branches", headers=world.admin, json={"code": " pun ", "name": "Pune Branch", "phone": "020 2222 2222"})
    assert added.status_code == 201 and added.json()["code"] == "PUN"
    assert client.post("/api/hospital/branches", headers=world.admin, json={"code": "PUN", "name": "Again"}).status_code == 409
    for bad in ("P", "TOOLONGCODE", "P-N", "<b>"):
        assert client.post("/api/hospital/branches", headers=world.admin, json={"code": bad, "name": "Bad"}).status_code in (409, 422), bad
    assert client.put(f"/api/hospital/branches/{branches[0]['id']}", headers=world.admin, json={"is_active": False}).status_code == 200
    assert client.put(f"/api/hospital/branches/{added.json()['id']}", headers=world.admin, json={"is_active": False}).status_code == 409
    assert client.put("/api/hospital/branches/999999", headers=world.admin, json={"name": "Nope"}).status_code == 404


def test_settings_are_checked_and_can_be_set_per_branch(client, world):
    listed = {s["key"]: s for s in client.get("/api/hospital/settings", headers=world.admin).json()}
    assert listed["break_glass_minutes"]["value"] == "60"
    assert client.put("/api/hospital/settings", headers=world.admin, json={"key": "break_glass_minutes", "value": "30"}).status_code == 200
    assert {s["key"]: s for s in client.get("/api/hospital/settings", headers=world.admin).json()}["break_glass_minutes"]["value"] == "30"
    for key, value in (("break_glass_minutes", "2"), ("break_glass_minutes", "abc"), ("working_hours_start", "25:00"), ("working_hours_start", "9:00"), ("duplicate_check", "maybe"), ("nonsense", "1"), ("currency", "")):
        assert client.put("/api/hospital/settings", headers=world.admin, json={"key": key, "value": value}).status_code == 422, (key, value)
    assert client.put("/api/hospital/settings", headers=world.admin, json={"key": "currency", "value": "INR", "branch_id": 999999}).status_code == 422


def test_price_list_add_change_deactivate_and_validation(client, world):
    dep = world.department_id
    added = client.post("/api/hospital/services", headers=world.admin, json={"code": "opd 01", "name": "OPD consultation", "category": "consultation", "department_id": dep, "price": 500, "gst_percent": 0})
    assert added.status_code == 201 and added.json()["code"] == "OPD01" and added.json()["category"] == "CONSULTATION"
    sid = added.json()["id"]
    assert client.post("/api/hospital/services", headers=world.admin, json={"code": "OPD01", "name": "Again", "category": "OTHER"}).status_code == 409
    for body in ({"code": "A", "name": "X", "category": "OTHER"}, {"code": "BAD1", "name": "Bad", "category": "MAGIC"}, {"code": "BAD2", "name": "Bad", "category": "LAB", "price": -5},
                 {"code": "BAD3", "name": "Bad", "category": "LAB", "gst_percent": 150}, {"code": "BAD4", "name": "Bad", "category": "LAB", "department_id": 999999}, {"code": "BAD5", "name": "Bad", "category": "LAB", "price": "NaN"}):
        assert client.post("/api/hospital/services", headers=world.admin, json=body).status_code == 422, body
    assert client.put(f"/api/hospital/services/{sid}", headers=world.admin, json={"price": 650.5}).json()["price"] == 650.5
    assert [s["code"] for s in client.get("/api/hospital/services", headers=world.doctor).json()] == ["OPD01"]               # a doctor can read the prices
    client.put(f"/api/hospital/services/{sid}", headers=world.admin, json={"is_active": False})
    assert client.get("/api/hospital/services", headers=world.doctor).json() == []
    assert len(client.get("/api/hospital/services?include_inactive=true", headers=world.admin).json()) == 1
    assert client.get("/api/hospital/services?include_inactive=true", headers=world.doctor).json() == []                     # inactive ones are for managers only
    assert client.get("/api/hospital/services?category=MAGIC", headers=world.admin).status_code == 422
    assert client.put("/api/hospital/services/999999", headers=world.admin, json={"price": 1}).status_code == 404


# ------------------------------------------------------------------ UHID
def test_every_new_patient_gets_a_unique_uhid_in_the_branch_format(client, world):
    first = new_patient(client, world, "u1@example.com", "Uhid One", phone="9811111101").json()["patient"]
    second = new_patient(client, world, "u2@example.com", "Uhid Two", phone="9811111102").json()["patient"]
    assert UHID_RE.match(first["uhid"]) and UHID_RE.match(second["uhid"]) and first["uhid"] != second["uhid"]
    assert int(second["uhid"][-6:]) == int(first["uhid"][-6:]) + 1 and first["patient_code"].startswith("P-")
    year = first["uhid"].split("-")[1]
    assert len(year) == 2


def test_each_branch_has_its_own_numbering_and_a_failed_registration_wastes_no_number(client, world):
    branch = client.post("/api/hospital/branches", headers=world.admin, json={"code": "PUN", "name": "Pune"}).json()["id"]
    a = new_patient(client, world, "b1@example.com", "Branch One", phone="9811111103", branch_id=branch).json()["patient"]
    assert a["uhid"].startswith("PUN-") and a["uhid"].endswith("-000001")
    assert new_patient(client, world, "b1@example.com", "Branch Dup", phone="9811111104", branch_id=branch).status_code == 409           # e-mail taken
    b = new_patient(client, world, "b2@example.com", "Branch Two", phone="9811111105", branch_id=branch).json()["patient"]
    assert b["uhid"].endswith("-000002")
    assert new_patient(client, world, "b3@example.com", "Branch Three", phone="9811111106", branch_id=999999).status_code == 422


def test_the_startup_gives_a_uhid_to_patients_that_have_none_and_is_idempotent(client, world):
    with SessionLocal() as db:
        p = db.get(Patient, world.patient_id)
        old = p.uhid
        assert old
        p.uhid = None
        db.commit()
    init_db()
    init_db()
    with SessionLocal() as db:
        assert UHID_RE.match(db.get(Patient, world.patient_id).uhid)


def test_patients_are_found_by_uhid(client, world):
    uhid = client.get(f"/api/patients/{world.patient_id}", headers=world.employee).json()["uhid"]
    assert [p["id"] for p in client.get(f"/api/patients?q={uhid}", headers=world.employee).json()] == [world.patient_id]


# ------------------------------------------------------------------ duplicates
def test_the_same_name_and_birth_date_asks_before_a_second_record_is_made(client, world):
    first = new_patient(client, world, "d1@example.com", "Sunita Kale", "1985-04-04", "9811111111")
    assert first.status_code == 201
    dup = new_patient(client, world, "d2@example.com", "  sunita   KALE ", "1985-04-04", "9822222222")
    assert dup.status_code == 409 and dup.json()["duplicates"][0]["uhid"] == first.json()["patient"]["uhid"] and "same name and date of birth" in dup.json()["duplicates"][0]["reasons"]
    assert "already registered" in dup.json()["detail"]
    assert new_patient(client, world, "d2@example.com", "Sunita Kale", "1985-04-04", "9822222222", allow_duplicate=True).status_code == 201


def test_the_same_phone_alone_is_a_warning_not_a_block(client, world):
    new_patient(client, world, "p1@example.com", "Mother Kale", "1960-01-01", "9833333333")
    assert new_patient(client, world, "p2@example.com", "Child Kale", "2015-01-01", "9833333333").status_code == 201
    found = client.get("/api/patient-registry/duplicates?phone=9833333333", headers=world.employee).json()
    assert len(found) == 2 and all(not f["strong"] for f in found)


def test_the_duplicate_check_can_be_switched_off(client, world):
    new_patient(client, world, "s1@example.com", "Same Person", "1970-07-07", "9844444444")
    client.put("/api/hospital/settings", headers=world.admin, json={"key": "duplicate_check", "value": "off"})
    assert new_patient(client, world, "s2@example.com", "Same Person", "1970-07-07", "9855555555").status_code == 201


def test_the_duplicate_endpoint_needs_staff_and_checks_input(client, world):
    for who in (world.doctor, world.pharmacy, world.patient):
        assert client.get("/api/patient-registry/duplicates?phone=9811111111", headers=who).status_code == 403
    assert client.get("/api/patient-registry/duplicates?date_of_birth=2999-01-01", headers=world.employee).status_code == 422
    assert client.get("/api/patient-registry/duplicates?phone=abc", headers=world.employee).status_code == 422
    assert client.get("/api/patient-registry/duplicates", headers=world.employee).json() == []


# ------------------------------------------------------------------ consent, ABHA, insurance
def test_consent_is_recorded_once_withdrawn_and_audited(client, world):
    pid = world.patient_id
    assert client.post(f"/api/patient-registry/{pid}/consents", headers=world.employee, json={"kind": "treatment"}).status_code == 201
    assert client.post(f"/api/patient-registry/{pid}/consents", headers=world.employee, json={"kind": "TREATMENT"}).status_code == 409
    assert client.post(f"/api/patient-registry/{pid}/consents", headers=world.employee, json={"kind": "WHATEVER"}).status_code == 422
    reg = client.get(f"/api/patient-registry/{pid}", headers=world.employee).json()
    cid = reg["consents"][0]["id"]
    assert client.post(f"/api/patient-registry/{pid}/consents/{cid}/withdraw", headers=world.employee).json()["active"] is False
    assert client.post(f"/api/patient-registry/{pid}/consents", headers=world.employee, json={"kind": "TREATMENT", "given_by": "Father"}).status_code == 201     # given again after withdrawing
    assert client.post(f"/api/patient-registry/{pid}/consents/999999/withdraw", headers=world.employee).status_code == 404
    actions = {a["action"] for a in client.get("/api/admin/audit-logs?limit=200", headers=world.admin).json()}
    assert {"CONSENT_RECORDED", "CONSENT_WITHDRAWN"} <= actions


def test_abha_needs_the_patients_consent_and_goes_away_with_it(client, world):
    pid = world.patient_id
    url = f"/api/patient-registry/{pid}/abha"
    assert client.put(url, headers=world.employee, json={"abha_id": "12-3456-7890-1234"}).status_code == 422                       # no consent yet
    cid = client.post(f"/api/patient-registry/{pid}/consents", headers=world.employee, json={"kind": "ABHA"}).json()["id"]
    for bad in ("123", "12-3456-7890-12AB", "1" * 20):
        assert client.put(url, headers=world.employee, json={"abha_id": bad}).status_code == 422
    assert client.put(url, headers=world.employee, json={"abha_id": "12345678901234"}).json()["abha_id"] == "12-3456-7890-1234"
    client.post(f"/api/patient-registry/{pid}/consents/{cid}/withdraw", headers=world.employee)
    assert client.get(f"/api/patient-registry/{pid}", headers=world.employee).json()["abha_id"] is None


def test_insurance_is_added_validated_and_deactivated(client, world):
    pid = world.patient_id
    ok = client.post(f"/api/patient-registry/{pid}/insurance", headers=world.employee, json={"insurer_name": "Star Health", "policy_number": "SH-12345", "valid_from": "2026-01-01", "valid_to": "2026-12-31"})
    assert ok.status_code == 201
    assert client.post(f"/api/patient-registry/{pid}/insurance", headers=world.employee, json={"insurer_name": "Star Health", "policy_number": "X", "valid_from": "2026-05-01", "valid_to": "2026-01-01"}).status_code == 422
    assert client.post(f"/api/patient-registry/{pid}/insurance", headers=world.employee, json={"insurer_name": "<b>", "policy_number": "SH-1"}).status_code == 422
    assert client.post(f"/api/patient-registry/{pid}/insurance/{ok.json()['id']}/deactivate", headers=world.employee).json()["is_active"] is False
    assert client.get(f"/api/patient-registry/{pid}", headers=world.employee).json()["insurance"][0]["insurer_name"] == "Star Health"


def test_registry_details_are_for_staff_and_the_patient_themselves(client, world):
    pid = world.patient_id
    assert client.get(f"/api/patient-registry/{pid}", headers=world.patient).status_code == 200
    other = new_patient(client, world, "o@example.com", "Other Person", phone="9866666666").json()["patient"]["id"]
    assert client.get(f"/api/patient-registry/{other}", headers=world.patient).status_code == 403               # not somebody else's
    assert client.get(f"/api/patient-registry/{pid}", headers=world.pharmacy).status_code == 403
    assert client.get("/api/patient-registry/999999", headers=world.employee).status_code == 404
    for who in (world.doctor, world.patient, world.pharmacy):
        assert client.post(f"/api/patient-registry/{pid}/consents", headers=who, json={"kind": "TREATMENT"}).status_code == 403
        assert client.put(f"/api/patient-registry/{pid}/abha", headers=who, json={"abha_id": None}).status_code == 403
        assert client.post(f"/api/patient-registry/{pid}/insurance", headers=who, json={"insurer_name": "Star", "policy_number": "A1"}).status_code == 403


# ------------------------------------------------------------------ merge
def test_merge_moves_the_records_archives_the_old_one_and_is_audited(client, world):
    dup = new_patient(client, world, "m1@example.com", "Rahul Patil", "1998-05-14", "9877777777", allow_duplicate=True).json()["patient"]
    client.post("/api/appointments", headers=world.employee, json={"patient_id": dup["id"], "doctor_id": world.doctor_id, "scheduled_at": __import__("tests.conftest", fromlist=["future"]).future(30)})
    res = client.post("/api/patient-registry/merge", headers=world.admin, json={"keep_id": world.patient_id, "merge_id": dup["id"], "reason": "Same person registered twice at the desk"})
    assert res.status_code == 201 and res.json()["details"]["moved"]["appointments"] == 1
    assert client.get("/api/appointments", headers=world.patient).json()[0]["patient_id"] == world.patient_id
    assert dup["id"] not in [p["id"] for p in client.get("/api/patients", headers=world.employee).json()]
    assert client.get(f"/api/patient-registry/{dup['id']}", headers=world.admin).json()["merged_into_id"] == world.patient_id
    assert client.post("/api/patient-registry/merge", headers=world.admin, json={"keep_id": world.patient_id, "merge_id": dup["id"], "reason": "Trying to merge it again"}).status_code == 409
    assert client.get("/api/patient-registry/merges", headers=world.admin).json()[0]["reason"].startswith("Same person")
    assert "PATIENT_MERGED" in {a["action"] for a in client.get("/api/admin/audit-logs?limit=200", headers=world.admin).json()}
    assert client.post("/api/auth/login", json={"email": "m1@example.com", "password": PASSWORD}).status_code in (401, 403)          # the archived login is off


def test_merge_is_only_for_the_authorised_and_checks_input(client, world):
    other = new_patient(client, world, "m2@example.com", "Merge Other", phone="9888888888").json()["patient"]["id"]
    body = {"keep_id": world.patient_id, "merge_id": other, "reason": "A proper written reason"}
    for who in (world.doctor, world.employee, world.pharmacy, world.patient):
        assert client.post("/api/patient-registry/merge", headers=who, json=body).status_code == 403
        assert client.get("/api/patient-registry/merges", headers=who).status_code == 403
    for bad in ({**body, "merge_id": world.patient_id}, {**body, "reason": "short"}, {**body, "merge_id": 999999}, {**body, "keep_id": "x"}, {}):
        assert client.post("/api/patient-registry/merge", headers=world.admin, json=bad).status_code in (404, 422)


def test_merge_keeps_one_standing_history_per_patient(client, world):
    dup = new_patient(client, world, "m3@example.com", "History Twin", "1991-01-01", "9899999999").json()["patient"]["id"]
    for pid in (world.patient_id, dup):
        client.put(f"/api/health-history/patient/{pid}", headers=world.doctor, json={"history": {}}) if pid == world.patient_id else None
    res = client.post("/api/patient-registry/merge", headers=world.admin, json={"keep_id": world.patient_id, "merge_id": dup, "reason": "Duplicate registration confirmed"})
    assert res.status_code == 201


# ------------------------------------------------------------------ break-glass
def test_break_glass_opens_one_patient_for_a_limited_time_and_is_reviewed(client, world):
    other = new_patient(client, world, "bg@example.com", "Glass Patient", phone="9800000001").json()["patient"]
    other_id, uhid = other["id"], other["uhid"]
    assert client.get(f"/api/doctor/patients/{other_id}/history", headers=world.doctor).status_code == 403              # not authorised
    found = client.get(f"/api/access/break-glass/lookup?uhid={uhid}", headers=world.doctor).json()
    assert found["id"] == other_id and set(found) == {"id", "uhid", "full_name", "age", "gender"}
    assert client.post("/api/access/break-glass", headers=world.doctor, json={"patient_id": other_id, "reason": "short"}).status_code == 422
    grant = client.post("/api/access/break-glass", headers=world.doctor, json={"patient_id": other_id, "reason": "Unconscious patient brought to casualty"})
    assert grant.status_code == 201 and grant.json()["active"]
    assert client.get(f"/api/doctor/patients/{other_id}/history", headers=world.doctor).status_code == 200                # now open
    assert client.get(f"/api/doctor/patients/{other_id}/history", headers=world.other_doctor).status_code == 403          # only for the doctor who asked
    unreviewed = client.get("/api/access/break-glass?only_unreviewed=true", headers=world.admin).json()
    assert unreviewed[0]["patient_name"] == "Glass Patient" and "Unconscious" in unreviewed[0]["reason"]
    assert client.post(f"/api/access/break-glass/{unreviewed[0]['id']}/review", headers=world.admin, json={"note": "Justified"}).json()["reviewed_at"]
    assert client.get("/api/access/break-glass?only_unreviewed=true", headers=world.admin).json() == []
    assert "BREAK_GLASS" in {a["action"] for a in client.get("/api/admin/audit-logs?limit=200", headers=world.admin).json()}


def test_break_glass_ends_by_itself(client, world):
    from datetime import timedelta
    from app.database.models import BreakGlassGrant
    other_id = new_patient(client, world, "bg2@example.com", "Glass Two", phone="9800000002").json()["patient"]["id"]
    client.post("/api/access/break-glass", headers=world.doctor, json={"patient_id": other_id, "reason": "Collapsed in the waiting hall"})
    with SessionLocal() as db:
        g = db.query(BreakGlassGrant).one()
        g.expires_at = g.granted_at - timedelta(minutes=1)
        db.commit()
    assert client.get(f"/api/doctor/patients/{other_id}/history", headers=world.doctor).status_code == 403


def test_break_glass_is_only_for_clinicians_and_cannot_be_used_to_browse(client, world):
    for who in (world.employee, world.pharmacy, world.patient):
        assert client.post("/api/access/break-glass", headers=who, json={"patient_id": world.patient_id, "reason": "I would like to look"}).status_code == 403
        assert client.get("/api/access/break-glass/lookup?uhid=ABCD", headers=who).status_code == 403
        assert client.get("/api/access/break-glass", headers=who).status_code == 403
    assert client.get("/api/access/break-glass/lookup?uhid=NOPE-00", headers=world.doctor).status_code == 404
    assert client.get("/api/access/break-glass/lookup?uhid=a", headers=world.doctor).status_code == 422
    assert client.get("/api/access/break-glass/lookup?uhid=%25", headers=world.doctor).status_code in (404, 422)          # no wildcard search
    assert client.post("/api/access/break-glass", headers=world.doctor, json={"patient_id": 999999, "reason": "Emergency, patient unknown"}).status_code == 404
    assert client.get("/api/access/break-glass", headers=world.doctor).status_code == 403                              # a doctor cannot read the review list
