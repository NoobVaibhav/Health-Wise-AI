"""Phase 5B: operation theatre. Clash prevention, the safety gates, who writes which record, consumables and the charge at completion."""
from datetime import datetime, timedelta

import pytest

from tests.conftest import PASSWORD, login

T0 = (datetime.now() + timedelta(days=2)).replace(hour=9, minute=0, second=0, microsecond=0)


def at(h, m=0):
    return (T0 + timedelta(hours=h, minutes=m)).isoformat()


@pytest.fixture()
def ow(client, world):
    def person(path, email, name, roles=None, **extra):
        res = client.post(f"/api/admin/{path}", headers=world.admin, json={"email": email, "full_name": name, "password": PASSWORD, **extra})
        assert res.status_code == 201, res.text
        if roles:
            assert client.put(f"/api/access/users/{res.json()['user']['id']}/roles", headers=world.admin, json={"roles": roles}).status_code == 200
        return login(client, email)

    world.ot = person("employees", "ot@hospital.example.com", "Omkar OT", ["OT_STAFF"], designation="OT technician")
    world.inv = person("employees", "inv@hospital.example.com", "Ila Inventory", ["INVENTORY_MANAGER"], designation="Store manager")
    world.nurse = person("nurses", "nurse@hospital.example.com", "Nina Nurse", designation="Staff nurse")
    world.intern = person("doctors", "intern@hospital.example.com", "Dr. Ira Intern", department_id=world.department_id, grade="INTERN", supervisor_id=world.doctor_id)
    world.ot1 = client.post("/api/ot/theatres", headers=world.admin, json={"name": "OT 1"}).json()["id"]
    world.ot2 = client.post("/api/ot/theatres", headers=world.admin, json={"name": "OT 2"}).json()["id"]
    return world


def booking(w, **over):
    return {"patient_id": w.patient_id, "theatre_id": w.ot1, "procedure": "Laparoscopic cholecystectomy", "surgeon_id": w.doctor_id, "anaesthetist_id": w.other_doctor_id,
            "scheduled_start": at(0), "scheduled_end": at(2), **over}


def book(client, w, who=None, **over):
    return client.post("/api/ot/surgeries", headers=who or w.doctor, json=booking(w, **over))


def full_flow(client, w):
    """Everything up to the start of the surgery."""
    sid = book(client, w).json()["id"]
    assert client.post(f"/api/ot/surgeries/{sid}/preop", headers=w.other_doctor, json={"fit": True, "notes": "ASA II"}).status_code == 200
    assert client.post(f"/api/ot/surgeries/{sid}/consent", headers=w.doctor, json={"given": True, "by_name": "Rahul Patil"}).status_code == 200
    items = ["Patient identity and procedure confirmed", "Surgical site marked", "Consent checked", "Anaesthesia machine and medicines checked", "Allergies reviewed"]
    assert client.post(f"/api/ot/surgeries/{sid}/checklist", headers=w.ot, json={"phase": "SIGN_IN", "items": items}).status_code == 200
    return sid


# ------------------------------------------------------------------ booking and clashes
def test_booking_rules_and_who_may_book(client, ow):
    assert book(client, ow).status_code == 201
    for who in (ow.patient, ow.pharmacy, ow.employee, ow.nurse):
        assert client.post("/api/ot/surgeries", headers=who, json=booking(ow, scheduled_start=at(5), scheduled_end=at(6))).status_code == 403
    assert book(client, ow, who=ow.other_doctor, scheduled_start=at(5), scheduled_end=at(6)).status_code == 403            # not this doctor's patient
    assert book(client, ow, who=ow.ot, scheduled_start=at(5), scheduled_end=at(6)).status_code == 201                       # OT staff book for the patient
    for change in ({"scheduled_end": at(0)}, {"scheduled_end": at(40)}, {"theatre_id": 9999}, {"surgeon_id": ow.doctor_id, "anaesthetist_id": ow.doctor_id},
                   {"procedure": "x"}, {"priority": "WHENEVER"}):
        assert book(client, ow, **{"scheduled_start": at(10), "scheduled_end": at(11), **change}).status_code == 422, change
    intern = next(d["id"] for d in client.get("/api/doctors", headers=ow.employee).json() if d["full_name"] == "Dr. Ira Intern")
    assert book(client, ow, scheduled_start=at(10), scheduled_end=at(11), surgeon_id=intern).status_code == 422
    assert book(client, ow, scheduled_start=at(10), scheduled_end=at(11), anaesthetist_id=intern).status_code == 422


def test_no_overlap_in_a_theatre_for_a_surgeon_or_an_anaesthetist(client, ow):
    assert book(client, ow).status_code == 201                                                                         # OT 1, 09:00-11:00
    assert book(client, ow, who=ow.ot, scheduled_start=at(1), scheduled_end=at(3), surgeon_id=ow.other_doctor_id, anaesthetist_id=None).status_code == 409   # same theatre
    assert book(client, ow, who=ow.ot, theatre_id=ow.ot2, scheduled_start=at(1), scheduled_end=at(3), anaesthetist_id=None).status_code == 409                 # same surgeon, other theatre
    assert book(client, ow, who=ow.ot, theatre_id=ow.ot2, scheduled_start=at(1), scheduled_end=at(3), surgeon_id=ow.other_doctor_id, anaesthetist_id=ow.doctor_id).status_code == 409   # swapped roles
    assert book(client, ow, who=ow.ot, scheduled_start=at(2), scheduled_end=at(4), surgeon_id=ow.other_doctor_id, anaesthetist_id=None).status_code == 201     # back to back is fine


def test_rescheduling_rechecks_clashes_and_a_cancelled_slot_is_free(client, ow):
    first = book(client, ow).json()["id"]
    second = book(client, ow, who=ow.ot, scheduled_start=at(3), scheduled_end=at(4), surgeon_id=ow.other_doctor_id, anaesthetist_id=None).json()["id"]
    assert client.put(f"/api/ot/surgeries/{second}", headers=ow.ot, json={"scheduled_start": at(1), "scheduled_end": at(2)}).status_code == 409
    assert client.post(f"/api/ot/surgeries/{first}/cancel", headers=ow.ot, json={"reason": "x"}).status_code == 422
    assert client.post(f"/api/ot/surgeries/{first}/cancel", headers=ow.ot, json={"reason": "Patient postponed"}).json()["status"] == "CANCELLED"
    assert client.put(f"/api/ot/surgeries/{second}", headers=ow.ot, json={"scheduled_start": at(1), "scheduled_end": at(2)}).status_code == 200
    assert client.post(f"/api/ot/surgeries/{first}/cancel", headers=ow.ot, json={"reason": "again please"}).status_code == 409


# ------------------------------------------------------------------ gates
def test_a_surgery_cannot_start_without_preop_consent_and_sign_in(client, ow):
    sid = book(client, ow).json()["id"]
    r = client.post(f"/api/ot/surgeries/{sid}/start", headers=ow.ot)
    assert r.status_code == 409 and all(w in r.text for w in ("pre-operative", "consent", "sign-in"))
    assert client.post(f"/api/ot/surgeries/{sid}/preop", headers=ow.doctor, json={"fit": True}).status_code == 403            # the surgeon is not the anaesthetist
    assert client.post(f"/api/ot/surgeries/{sid}/preop", headers=ow.other_doctor, json={"fit": False}).status_code == 422       # not fit needs a reason
    client.post(f"/api/ot/surgeries/{sid}/preop", headers=ow.other_doctor, json={"fit": False, "notes": "Uncontrolled BP"})
    assert client.post(f"/api/ot/surgeries/{sid}/start", headers=ow.ot).status_code == 409
    client.post(f"/api/ot/surgeries/{sid}/preop", headers=ow.other_doctor, json={"fit": True, "notes": "BP controlled"})
    assert client.post(f"/api/ot/surgeries/{sid}/start", headers=ow.ot).status_code == 409                                   # still no consent
    assert client.post(f"/api/ot/surgeries/{sid}/consent", headers=ow.nurse, json={"given": True, "by_name": "X Y"}).status_code == 403
    client.post(f"/api/ot/surgeries/{sid}/consent", headers=ow.ot, json={"given": False, "by_name": "Rahul Patil", "note": "Refused"})
    assert client.post(f"/api/ot/surgeries/{sid}/start", headers=ow.ot).status_code == 409                                   # consent refused is not consent
    client.post(f"/api/ot/surgeries/{sid}/consent", headers=ow.ot, json={"given": True, "by_name": "Rahul Patil"})
    assert client.post(f"/api/ot/surgeries/{sid}/checklist", headers=ow.ot, json={"phase": "SIGN_IN", "items": ["Surgical site marked"]}).status_code == 200
    assert client.post(f"/api/ot/surgeries/{sid}/start", headers=ow.ot).status_code == 409                                   # sign-in incomplete
    assert client.post(f"/api/ot/surgeries/{sid}/checklist", headers=ow.ot, json={"phase": "SIGN_IN", "items": ["Something invented"]}).status_code == 422
    assert client.post(f"/api/ot/surgeries/{sid}/checklist", headers=ow.ot, json={"phase": "TIME_OUT", "items": ["Team members introduced"]}).status_code == 409   # not started yet


def test_the_whole_operation_with_its_records_and_the_charge(client, ow):
    service = client.post("/api/hospital/services", headers=ow.admin, json={"code": "SURG-LAP", "name": "Laparoscopic surgery", "category": "PROCEDURE", "price": 45000, "gst_percent": 0})
    assert service.status_code in (200, 201), service.text
    glove = client.post("/api/procurement/items", headers=ow.inv, json={"code": "GLV-OT", "name": "Sterile gloves", "category": "CONSUMABLE", "min_level": 5}).json()["id"]
    count = client.post("/api/procurement/counts", headers=ow.inv, json={"inventory_item_id": glove, "counted_quantity": 20, "reason": "opening stock"}).json()
    client.post(f"/api/procurement/counts/{count['id']}/decide", headers=ow.admin, json={"approve": True})
    ward = client.post("/api/ipd/wards", headers=ow.admin, json={"name": "Surgical Ward", "ward_type": "GENERAL"}).json()
    bed = client.post(f"/api/ipd/wards/{ward['id']}/beds", headers=ow.admin, json={"code": "S1"}).json()
    adm = client.post("/api/ipd/admissions", headers=ow.doctor, json={"patient_id": ow.patient_id, "diagnosis": "Gallstones", "bed_id": bed["id"]}).json()["id"]
    sid = book(client, ow, admission_id=adm, service_id=service.json()["id"]).json()["id"]
    client.post(f"/api/ot/surgeries/{sid}/preop", headers=ow.other_doctor, json={"fit": True})
    client.post(f"/api/ot/surgeries/{sid}/consent", headers=ow.doctor, json={"given": True, "by_name": "Rahul Patil"})
    from app.services.ot_service import CHECKLIST
    client.post(f"/api/ot/surgeries/{sid}/checklist", headers=ow.ot, json={"phase": "SIGN_IN", "items": CHECKLIST["SIGN_IN"]})
    assert client.post(f"/api/ot/surgeries/{sid}/anaesthesia", headers=ow.other_doctor, json={"type": "GENERAL"}).status_code == 409        # not started
    assert client.post(f"/api/ot/surgeries/{sid}/start", headers=ow.ot).json()["status"] == "IN_PROGRESS"
    assert client.post(f"/api/ot/surgeries/{sid}/events", headers=ow.patient, json={"text": "Incision made"}).status_code == 403
    assert client.post(f"/api/ot/surgeries/{sid}/events", headers=ow.ot, json={"text": "Incision made"}).status_code == 200
    assert client.post(f"/api/ot/surgeries/{sid}/consumables", headers=ow.ot, json={"inventory_item_id": glove, "quantity": 25}).status_code == 409           # not enough in store
    assert client.post(f"/api/ot/surgeries/{sid}/consumables", headers=ow.ot, json={"inventory_item_id": glove, "quantity": 6}).status_code == 200
    assert next(i for i in client.get("/api/procurement/items", headers=ow.inv).json() if i["id"] == glove)["quantity"] == 14
    assert client.post(f"/api/ot/surgeries/{sid}/recovery", headers=ow.ot, json={}).status_code == 409                                   # no time-out, no note
    client.post(f"/api/ot/surgeries/{sid}/checklist", headers=ow.ot, json={"phase": "TIME_OUT", "items": CHECKLIST["TIME_OUT"]})
    note = {"findings": "Inflamed gallbladder", "procedure_done": "Cholecystectomy", "blood_loss_ml": 50}
    assert client.post(f"/api/ot/surgeries/{sid}/op-note", headers=ow.other_doctor, json=note).status_code == 403                          # only the surgeon
    assert client.post(f"/api/ot/surgeries/{sid}/op-note", headers=ow.doctor, json=note).status_code == 200
    assert client.post(f"/api/ot/surgeries/{sid}/anaesthesia", headers=ow.doctor, json={"type": "GENERAL"}).status_code == 403            # only the anaesthetist
    assert client.post(f"/api/ot/surgeries/{sid}/anaesthesia", headers=ow.other_doctor, json={"type": "MAGIC"}).status_code == 422
    assert client.post(f"/api/ot/surgeries/{sid}/anaesthesia", headers=ow.other_doctor, json={"type": "GENERAL", "notes": "Uneventful"}).status_code == 200
    assert client.post(f"/api/ot/surgeries/{sid}/recovery", headers=ow.ot, json={"notes": "Stable"}).json()["status"] == "RECOVERY"
    assert client.post(f"/api/ot/surgeries/{sid}/complete", headers=ow.ot).status_code == 409                                              # no sign-out, note not final
    client.post(f"/api/ot/surgeries/{sid}/checklist", headers=ow.ot, json={"phase": "SIGN_OUT", "items": CHECKLIST["SIGN_OUT"]})
    assert client.post(f"/api/ot/surgeries/{sid}/complete", headers=ow.ot).status_code == 409
    assert client.post(f"/api/ot/surgeries/{sid}/op-note", headers=ow.doctor, json={**note, "final": True}).status_code == 200
    assert client.post(f"/api/ot/surgeries/{sid}/op-note", headers=ow.doctor, json={**note, "findings": "Changed"}).status_code == 409   # final
    done = client.post(f"/api/ot/surgeries/{sid}/complete", headers=ow.ot)
    assert done.status_code == 200 and done.json()["status"] == "COMPLETED"
    detail = client.get(f"/api/ot/surgeries/{sid}", headers=ow.doctor).json()
    assert detail["op_note"]["final"] and detail["consumables"][0]["quantity"] == 6 and detail["events"][0]["text"] == "Incision made"
    assert all(i["done"] for phase in detail["checklist"].values() for i in phase)
    from app.database.connection import SessionLocal
    from app.database.models import EncounterCharge
    with SessionLocal() as db:
        charges = db.query(EncounterCharge).filter(EncounterCharge.description.like("Laparoscopic surgery%")).all()
        assert len(charges) == 1 and charges[0].amount == 45000 and charges[0].status == "PENDING"
    assert client.post(f"/api/ot/surgeries/{sid}/events", headers=ow.ot, json={"text": "Late entry"}).status_code == 409                    # closed record
    assert client.post(f"/api/ot/surgeries/{sid}/complete", headers=ow.ot).status_code == 409


# ------------------------------------------------------------------ privacy
def test_who_can_see_which_surgeries(client, ow):
    sid = book(client, ow).json()["id"]
    assert client.get(f"/api/ot/surgeries/{sid}", headers=ow.doctor).status_code == 200
    assert client.get(f"/api/ot/surgeries/{sid}", headers=ow.other_doctor).status_code == 200            # the anaesthetist
    assert [s["id"] for s in client.get("/api/ot/surgeries", headers=ow.ot).json()] == [sid]
    assert [s["id"] for s in client.get("/api/ot/surgeries", headers=ow.doctor).json()] == [sid]
    for who in (ow.patient, ow.pharmacy, ow.employee):
        assert client.get("/api/ot/surgeries", headers=who).status_code == 403
        assert client.get(f"/api/ot/surgeries/{sid}", headers=who).status_code == 403
    assert client.get(f"/api/ot/surgeries/{sid}", headers=ow.intern).status_code == 403
    assert client.get("/api/ot/surgeries?day=not-a-date", headers=ow.ot).status_code == 422
    assert client.post("/api/ot/theatres", headers=ow.doctor, json={"name": "OT 9"}).status_code == 403
    assert client.post("/api/ot/theatres", headers=ow.admin, json={"name": "OT 1"}).status_code == 409
