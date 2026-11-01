"""Phase 5C: blood bank. Donor eligibility, screening by a second person, ABO/Rh compatibility, cross-match, issue with a verifier, return rules, and the bedside transfusion."""
from datetime import date, timedelta

import pytest

from app.database.connection import SessionLocal
from app.database.models import BloodUnit, Patient
from app.services.bloodbank_service import compatible
from tests.conftest import PASSWORD, login

DOB = str(date.today() - timedelta(days=30 * 365))


@pytest.fixture()
def bw(client, world):
    def person(path, email, name, roles=None, **extra):
        res = client.post(f"/api/admin/{path}", headers=world.admin, json={"email": email, "full_name": name, "password": PASSWORD, **extra})
        assert res.status_code == 201, res.text
        if roles:
            assert client.put(f"/api/access/users/{res.json()['user']['id']}/roles", headers=world.admin, json={"roles": roles}).status_code == 200
        return login(client, email)

    world.bb1 = person("employees", "bb1@hospital.example.com", "Bela Blood", ["BLOOD_BANK_STAFF"], designation="Technician")
    world.bb2 = person("employees", "bb2@hospital.example.com", "Bimal Blood", ["BLOOD_BANK_STAFF"], designation="Technician")
    world.n1 = person("nurses", "n1@hospital.example.com", "Nina Nurse", designation="Staff nurse")
    world.n2 = person("nurses", "n2@hospital.example.com", "Neeta Nurse", designation="Staff nurse")
    world.intern = person("doctors", "intern@hospital.example.com", "Dr. Ira Intern", department_id=world.department_id, grade="INTERN", supervisor_id=world.doctor_id)
    return world


def donor(client, w, group="O-", gender="male", dob=DOB, who=None):
    r = client.post("/api/bloodbank/donors", headers=who or w.bb1, json={"full_name": "Dev Donor", "gender": gender, "date_of_birth": dob, "blood_group": group, "phone": "9000000000"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def donate(client, w, donor_id, components=("PRBC",), **over):
    body = {"volume_ml": 450, "haemoglobin": 14.0, "weight_kg": 70, "components": list(components), **over}
    return client.post(f"/api/bloodbank/donors/{donor_id}/donations", headers=w.bb1, json=body)


def clear(client, w, donation_id):
    return client.post(f"/api/bloodbank/donations/{donation_id}/screening", headers=w.bb2, json={"result": "CLEARED"})


def available_unit(client, w, group="O-", component="PRBC"):
    d = donate(client, w, donor(client, w, group), (component,)).json()
    assert clear(client, w, d["id"]).status_code == 200
    return d["units"][0]["id"]


def set_patient_group(group):
    with SessionLocal() as db:
        p = db.query(Patient).first()
        p.blood_group = group
        db.commit()


def request(client, w, who=None, **over):
    body = {"patient_id": w.patient_id, "component": "PRBC", "units_requested": 1, "urgency": "ROUTINE", "indication": "Anaemia, Hb 6.5", **over}
    return client.post("/api/bloodbank/requests", headers=who or w.doctor, json=body)


# ------------------------------------------------------------------ the compatibility rule
@pytest.mark.parametrize("unit,component,patient,ok", [
    ("O-", "PRBC", "A+", True), ("A+", "PRBC", "O+", False), ("A-", "PRBC", "A+", True), ("A+", "PRBC", "A-", False), ("AB+", "PRBC", "AB+", True), ("AB-", "PRBC", "O-", False),
    ("O+", "WHOLE_BLOOD", "O-", False), ("B-", "WHOLE_BLOOD", "AB+", True),
    ("AB+", "FFP", "O+", True), ("A+", "FFP", "B+", False), ("O+", "FFP", "O-", True), ("O+", "FFP", "A+", False),
    ("O+", "PLATELETS", "A-", False), ("A-", "PLATELETS", "O+", True),
    ("O-", "PRBC", None, True), ("O+", "PRBC", None, False), ("AB+", "FFP", None, True), ("A+", "FFP", None, False)])
def test_abo_rh_rule(unit, component, patient, ok):
    assert compatible(unit, component, patient) is ok


# ------------------------------------------------------------------ donors
def test_donor_eligibility_is_checked_before_blood_is_taken(client, bw):
    d = donor(client, bw)
    assert donate(client, bw, d, haemoglobin=11.0).status_code == 409
    assert donate(client, bw, d, weight_kg=40).status_code == 409
    young = donor(client, bw, dob=str(date.today() - timedelta(days=17 * 365)))
    assert donate(client, bw, young).status_code == 409
    old = donor(client, bw, dob=str(date.today() - timedelta(days=70 * 365)))
    assert donate(client, bw, old).status_code == 409
    assert donate(client, bw, d, volume_ml=100).status_code == 422                                                # too little blood for a unit
    assert donate(client, bw, d, components=("WHOLE_BLOOD", "FFP")).status_code == 422
    assert donate(client, bw, d, components=("PRBC", "PRBC")).status_code == 422
    first = donate(client, bw, d, components=("PRBC", "FFP", "PLATELETS"))
    assert first.status_code == 201 and {u["status"] for u in first.json()["units"]} == {"QUARANTINE"}
    again = donate(client, bw, d)
    assert again.status_code == 409 and "90 days" in again.text                                                  # too soon, a man
    woman = donor(client, bw, gender="female")
    donate(client, bw, woman)
    assert "120 days" in donate(client, bw, woman).text
    for who in (bw.patient, bw.doctor, bw.employee, bw.n1):
        assert client.post("/api/bloodbank/donors", headers=who, json={"full_name": "X Y", "gender": "male", "date_of_birth": DOB, "blood_group": "O+"}).status_code == 403
    assert client.post("/api/bloodbank/donors", headers=bw.bb1, json={"full_name": "X Y", "gender": "male", "date_of_birth": DOB, "blood_group": "Z+"}).status_code == 422


def test_screening_needs_a_second_person_and_clears_or_discards(client, bw):
    d = donate(client, bw, donor(client, bw), ("PRBC", "FFP")).json()
    assert client.post(f"/api/bloodbank/donations/{d['id']}/screening", headers=bw.bb1, json={"result": "CLEARED"}).status_code == 409        # the collector cannot screen
    assert client.post(f"/api/bloodbank/donations/{d['id']}/screening", headers=bw.bb2, json={"result": "MAYBE"}).status_code == 422
    ok = clear(client, bw, d["id"]).json()
    assert {u["status"] for u in ok["units"]} == {"AVAILABLE"}
    assert clear(client, bw, d["id"]).status_code == 409
    bad = donate(client, bw, donor(client, bw, "A+"), ("PRBC",)).json()
    assert client.post(f"/api/bloodbank/donations/{bad['id']}/screening", headers=bw.bb2, json={"result": "REACTIVE"}).status_code == 422
    r = client.post(f"/api/bloodbank/donations/{bad['id']}/screening", headers=bw.bb2, json={"result": "REACTIVE", "note": "HBsAg reactive"}).json()
    assert r["units"][0]["status"] == "DISCARDED"
    donors = client.get("/api/bloodbank/donors", headers=bw.bb1).json()
    assert any(x["ineligible_reasons"] and "Deferred" in x["ineligible_reasons"][0] for x in donors)


def test_expired_units_never_stay_available(client, bw):
    uid = available_unit(client, bw)
    with SessionLocal() as db:
        u = db.get(BloodUnit, uid)
        u.expires_at = u.expires_at - timedelta(days=100)
        db.commit()
    assert client.get("/api/bloodbank/units?status_filter=EXPIRED", headers=bw.bb1).json()[0]["id"] == uid
    assert [r for r in client.get("/api/bloodbank/stock", headers=bw.bb1).json() if r["available"]] == []
    set_patient_group("A+")
    req = request(client, bw).json()
    assert client.post(f"/api/bloodbank/requests/{req['id']}/crossmatch", headers=bw.bb1, json={"unit_id": uid, "result": "COMPATIBLE"}).status_code == 409


# ------------------------------------------------------------------ requests, cross-match, issue
def test_requests_have_rules_about_who_asks_and_the_group(client, bw):
    set_patient_group("A+")
    for who in (bw.patient, bw.employee, bw.n1, bw.pharmacy):
        assert request(client, bw, who=who).status_code == 403
    assert request(client, bw, who=bw.intern).status_code == 403                    # an intern cannot ask for blood
    assert request(client, bw, who=bw.other_doctor).status_code == 403                    # not this doctor's patient
    assert request(client, bw, blood_group="B+").status_code == 422                       # does not match the record
    assert request(client, bw, component="BEER").status_code == 422
    assert request(client, bw, units_requested=11).status_code == 422
    assert request(client, bw, units_requested=0).status_code == 422
    set_patient_group(None)
    assert request(client, bw).status_code == 422                                          # no group, not an emergency
    assert request(client, bw, urgency="EMERGENCY").status_code == 201
    assert request(client, bw, blood_group="O+").status_code == 201                        # group supplied when the record has none
    mine = client.get("/api/bloodbank/requests", headers=bw.doctor).json()
    assert len(mine) == 2 and client.get("/api/bloodbank/requests", headers=bw.other_doctor).json() == []
    assert client.get("/api/bloodbank/requests", headers=bw.patient).status_code == 403
    assert len(client.get("/api/bloodbank/requests", headers=bw.bb1).json()) == 2


def test_only_compatible_available_units_of_the_right_component_are_matched(client, bw):
    set_patient_group("A+")
    ok_unit = available_unit(client, bw, "O-")
    wrong_group = available_unit(client, bw, "B+")
    plasma = available_unit(client, bw, "A+", "FFP")
    req = request(client, bw).json()
    cands = client.get(f"/api/bloodbank/requests/{req['id']}/candidates", headers=bw.bb1).json()
    assert [c["id"] for c in cands] == [ok_unit]
    assert client.get(f"/api/bloodbank/requests/{req['id']}/candidates", headers=bw.doctor).status_code == 403
    assert client.post(f"/api/bloodbank/requests/{req['id']}/crossmatch", headers=bw.bb1, json={"unit_id": wrong_group, "result": "COMPATIBLE"}).status_code == 409
    assert client.post(f"/api/bloodbank/requests/{req['id']}/crossmatch", headers=bw.bb1, json={"unit_id": plasma, "result": "COMPATIBLE"}).status_code == 409
    inc = client.post(f"/api/bloodbank/requests/{req['id']}/crossmatch", headers=bw.bb1, json={"unit_id": ok_unit, "result": "INCOMPATIBLE"})
    assert inc.status_code == 201 and inc.json()["status"] == "PENDING" and inc.json()["units_matched"] == 0
    assert client.post(f"/api/bloodbank/requests/{req['id']}/issue", headers=bw.bb1, json={"unit_id": ok_unit}).status_code == 409        # not matched compatible
    done = client.post(f"/api/bloodbank/requests/{req['id']}/crossmatch", headers=bw.bb1, json={"unit_id": ok_unit, "result": "COMPATIBLE"}).json()
    assert done["status"] == "CROSSMATCHED" and done["units_matched"] == 1
    assert client.post(f"/api/bloodbank/requests/{req['id']}/crossmatch", headers=bw.bb1, json={"unit_id": ok_unit, "result": "COMPATIBLE"}).status_code == 409   # now reserved
    other = request(client, bw).json()
    assert client.get(f"/api/bloodbank/requests/{other['id']}/candidates", headers=bw.bb1).json() == []                                  # reserved units are not offered again


def issued(client, w, group="O-", patient_group="A+"):
    set_patient_group(patient_group)
    uid = available_unit(client, w, group)
    req = request(client, w).json()
    client.post(f"/api/bloodbank/requests/{req['id']}/crossmatch", headers=w.bb1, json={"unit_id": uid, "result": "COMPATIBLE"})
    return req["id"], client.post(f"/api/bloodbank/requests/{req['id']}/issue", headers=w.bb1, json={"unit_id": uid}).json()["issue_id"], uid


def admit(client, w):
    ward = client.post("/api/ipd/wards", headers=w.admin, json={"name": "Ward B", "ward_type": "GENERAL"}).json()
    bed = client.post(f"/api/ipd/wards/{ward['id']}/beds", headers=w.admin, json={"code": "B1"}).json()
    assert client.post("/api/ipd/admissions", headers=w.doctor, json={"patient_id": w.patient_id, "diagnosis": "Anaemia", "bed_id": bed["id"]}).status_code == 201


def test_issue_needs_a_second_person_and_the_nurse_cannot_start_before_it(client, bw):
    admit(client, bw)
    rid, iid, uid = issued(client, bw)
    assert client.post(f"/api/bloodbank/issues/{iid}/verify", headers=bw.bb1).status_code == 409                    # the issuer cannot verify
    assert client.post(f"/api/bloodbank/issues/{iid}/verify", headers=bw.n1).status_code == 403
    start = {"patient_checked": True, "unit_checked": True}
    assert client.post(f"/api/bloodbank/issues/{iid}/transfusion", headers=bw.n1, json=start).status_code == 409    # not verified yet
    assert client.post(f"/api/bloodbank/issues/{iid}/verify", headers=bw.bb2).json()["verified"] is True
    assert client.post(f"/api/bloodbank/issues/{iid}/verify", headers=bw.bb2).status_code == 409
    assert client.get("/api/bloodbank/ready", headers=bw.bb1).status_code == 403
    assert [r["issue_id"] for r in client.get("/api/bloodbank/ready", headers=bw.n1).json()] == [iid]
    assert client.post(f"/api/bloodbank/issues/{iid}/transfusion", headers=bw.n1, json={"patient_checked": True, "unit_checked": False}).status_code == 422
    for who in (bw.patient, bw.pharmacy, bw.employee, bw.bb1):
        assert client.post(f"/api/bloodbank/issues/{iid}/transfusion", headers=who, json=start).status_code == 403
    t = client.post(f"/api/bloodbank/issues/{iid}/transfusion", headers=bw.n1, json=start)
    assert t.status_code == 201 and t.json()["status"] == "AWAITING_CHECK"
    assert client.post(f"/api/bloodbank/issues/{iid}/transfusion", headers=bw.n2, json=start).status_code == 409           # already started
    tid = t.json()["id"]
    assert client.post(f"/api/bloodbank/transfusions/{tid}/end", headers=bw.n1, json={"volume_given_ml": 300}).status_code == 409          # no bedside check yet
    assert client.post(f"/api/bloodbank/transfusions/{tid}/verify", headers=bw.n1).status_code == 409                    # the starter cannot check
    waiting = client.get("/api/bloodbank/transfusions", headers=bw.n2).json()                                          # the second person finds it
    assert [w["id"] for w in waiting] == [tid] and waiting[0]["started_by_me"] is False
    assert client.get("/api/bloodbank/transfusions", headers=bw.n1).json()[0]["started_by_me"] is True
    assert client.get("/api/bloodbank/transfusions", headers=bw.patient).status_code == 403
    assert client.post(f"/api/bloodbank/transfusions/{tid}/verify", headers=bw.n2).json()["status"] == "IN_PROGRESS"
    assert client.post(f"/api/bloodbank/transfusions/{tid}/end", headers=bw.n1, json={"volume_given_ml": 300, "reaction": True}).status_code == 422   # a reaction needs a description
    ended = client.post(f"/api/bloodbank/transfusions/{tid}/end", headers=bw.n1, json={"volume_given_ml": 280}).json()
    assert ended["status"] == "COMPLETED" and ended["volume_given_ml"] == 280
    assert client.post(f"/api/bloodbank/transfusions/{tid}/end", headers=bw.n1, json={"volume_given_ml": 1}).status_code == 409
    assert next(r for r in client.get("/api/bloodbank/requests", headers=bw.bb1).json() if r["id"] == rid)["status"] == "COMPLETED"
    with SessionLocal() as db:
        assert db.get(BloodUnit, uid).status == "TRANSFUSED"
    history = client.get(f"/api/bloodbank/patient/{bw.patient_id}/transfusions", headers=bw.doctor).json()
    assert len(history) == 1 and client.get(f"/api/bloodbank/patient/{bw.patient_id}/transfusions", headers=bw.other_doctor).status_code == 403


def test_a_reaction_stops_the_transfusion_and_a_patient_not_in_hospital_cannot_be_transfused(client, bw):
    rid, iid, uid = issued(client, bw)
    client.post(f"/api/bloodbank/issues/{iid}/verify", headers=bw.bb2)
    start = {"patient_checked": True, "unit_checked": True}
    assert client.post(f"/api/bloodbank/issues/{iid}/transfusion", headers=bw.n1, json=start).status_code == 403          # not admitted, no open visit
    admit(client, bw)
    tid = client.post(f"/api/bloodbank/issues/{iid}/transfusion", headers=bw.n1, json=start).json()["id"]
    client.post(f"/api/bloodbank/transfusions/{tid}/verify", headers=bw.n2)
    r = client.post(f"/api/bloodbank/transfusions/{tid}/end", headers=bw.n1, json={"volume_given_ml": 50, "reaction": True, "reaction_note": "Fever and rigors at 10 minutes"}).json()
    assert r["status"] == "STOPPED" and r["reaction"] is True


def test_return_goes_back_only_within_the_window_with_the_cold_chain_kept(client, bw):
    rid, iid, uid = issued(client, bw)
    client.post(f"/api/bloodbank/issues/{iid}/verify", headers=bw.bb2)
    assert client.post(f"/api/bloodbank/issues/{iid}/return", headers=bw.n1, json={"reason": "Not needed"}).status_code == 403
    back = client.post(f"/api/bloodbank/issues/{iid}/return", headers=bw.bb1, json={"reason": "Patient discharged", "cold_chain_ok": True}).json()
    assert back["unit_status"] == "AVAILABLE"
    assert client.post(f"/api/bloodbank/issues/{iid}/return", headers=bw.bb1, json={"reason": "again please"}).status_code == 409
    rid2, iid2, uid2 = issued(client, bw)
    lost = client.post(f"/api/bloodbank/issues/{iid2}/return", headers=bw.bb1, json={"reason": "Left on the ward", "cold_chain_ok": False}).json()
    assert lost["unit_status"] == "DISCARDED"


def test_requests_can_be_cancelled_or_rejected_and_reserved_units_are_released(client, bw):
    set_patient_group("A+")
    uid = available_unit(client, bw, "O-")
    req = request(client, bw).json()
    client.post(f"/api/bloodbank/requests/{req['id']}/crossmatch", headers=bw.bb1, json={"unit_id": uid, "result": "COMPATIBLE"})
    assert client.post(f"/api/bloodbank/requests/{req['id']}/cancel", headers=bw.other_doctor).status_code == 404
    assert client.post(f"/api/bloodbank/requests/{req['id']}/cancel", headers=bw.doctor).json()["status"] == "CANCELLED"
    with SessionLocal() as db:
        assert db.get(BloodUnit, uid).status == "AVAILABLE"
    assert client.post(f"/api/bloodbank/requests/{req['id']}/cancel", headers=bw.doctor).status_code == 409
    second = request(client, bw).json()
    assert client.post(f"/api/bloodbank/requests/{second['id']}/reject", headers=bw.bb1, json={"reason": "x"}).status_code == 422
    assert client.post(f"/api/bloodbank/requests/{second['id']}/reject", headers=bw.bb1, json={"reason": "Request incomplete"}).json()["status"] == "REJECTED"
    assert client.post(f"/api/bloodbank/units/{uid}/discard", headers=bw.bb1, json={"reason": "Bag damaged"}).json()["status"] == "DISCARDED"
    assert client.post(f"/api/bloodbank/units/{uid}/discard", headers=bw.bb1, json={"reason": "again please"}).status_code == 409
    assert client.get("/api/bloodbank/rules", headers=bw.doctor).status_code == 403
    assert "medical officer" in client.get("/api/bloodbank/rules", headers=bw.bb1).json()["note"]
