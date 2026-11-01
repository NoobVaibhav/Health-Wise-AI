"""Phase 9: security and critical transactions across the new modules.
1. every route that changes data writes an audit line (or is on a short, explained list of routes that keep their own durable trail)
2. one patient can never reach another patient's bills, receipts, results, scans, transfusions, surgeries or exports
3. money and blood: two people acting at the same moment can never overpay a bill, refund twice, or give one unit to two patients."""
import ast
import glob
import os
import threading
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.database.connection import SessionLocal
from app.database.models import (
    BloodDonation, BloodDonor, BloodUnit, EncounterCharge, LabResult, LabTestOrder, Patient, RadiologyAttachment, RadiologyOrder, RadiologyReport, utcnow,
)
from app.main import app
from tests.conftest import PASSWORD, login

ROUTERS = os.path.join(os.path.dirname(__file__), "..", "app", "routers")

# Routes that change data but write no audit line, with the reason. A NEW route must call audit_service.log_action (or the helper _create) or be added here with a reason.
OWN_TRAIL = {
    "auth.py::otp_request": "writes only a hashed one-time code; the sign-in itself is audited when the code is used",
    "doctors.py::add_history_entry": "a history entry keeps who wrote it and when",
    "health_history.py::patient_cannot_change_history": "refuses and changes nothing",
    "health_history.py::preview_points": "a preview, nothing is saved",
    "nursing.py::add_vitals": "every vital set keeps who recorded it and when, and alerts keep their own trail",
    "nursing.py::add_intake_output": "every entry keeps who recorded it and when",
    "opd.py::add_vitals": "every vital set keeps who recorded it and when, and alerts keep their own trail",
    "opd.py::call_next": "moves the queue only; the visit keeps its own history",
    "opd.py::call": "moves the queue only; the visit keeps its own history",
    "opd.py::save_consultation": "a draft; signing and every addendum are audited and a signed note is never changed",
}
for _name in ("add_condition", "change_condition", "remove_condition", "add_medicine", "change_medicine", "remove_medicine", "add_admission", "change_admission", "remove_admission",
              "add_surgery", "change_surgery", "remove_surgery", "verify_record"):
    OWN_TRAIL[f"health_history.py::{_name}"] = "every change is kept in the history revisions with who, when and what changed"


def test_every_route_that_changes_data_writes_an_audit_line():
    missing, seen = [], 0
    for path in sorted(glob.glob(os.path.join(ROUTERS, "*.py"))):
        tree = ast.parse(open(path, encoding="utf-8").read())
        for fn in ast.walk(tree):
            if not isinstance(fn, ast.FunctionDef):
                continue
            changes = any(isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr in ("post", "put", "delete", "patch") for d in fn.decorator_list)
            if not changes:
                continue
            seen += 1
            source = ast.unparse(fn)
            key = f"{os.path.basename(path)}::{fn.name}"
            if not ("log_action" in source or "audit_service" in source or "_create(" in source) and key not in OWN_TRAIL:
                missing.append(key)
    assert seen > 200
    assert missing == [], "These routes change data but write no audit line: " + ", ".join(missing)


def test_the_explained_list_has_no_stale_entries():
    names = set()
    for path in glob.glob(os.path.join(ROUTERS, "*.py")):
        for fn in ast.walk(ast.parse(open(path, encoding="utf-8").read())):
            if isinstance(fn, ast.FunctionDef):
                names.add(f"{os.path.basename(path)}::{fn.name}")
    assert [k for k in OWN_TRAIL if k not in names] == []


# ------------------------------------------------------------------ isolation between patients
@pytest.fixture()
def sw(client, world):
    def person(path, email, name, roles=None, **extra):
        res = client.post(f"/api/admin/{path}", headers=world.admin, json={"email": email, "full_name": name, "password": PASSWORD, **extra})
        assert res.status_code == 201, res.text
        if roles:
            assert client.put(f"/api/access/users/{res.json()['user']['id']}/roles", headers=world.admin, json={"roles": roles}).status_code == 200
        return login(client, email)

    world.b1 = person("employees", "b1@hospital.example.com", "Bina Billing", ["BILLING_EXECUTIVE"], designation="Billing")
    world.b2 = person("employees", "b2@hospital.example.com", "Bhanu Billing", ["BILLING_EXECUTIVE"], designation="Billing")
    world.acc = person("employees", "acc@hospital.example.com", "Asha Accounts", ["ACCOUNTANT"], designation="Accountant")
    world.bb1 = person("employees", "bb1@hospital.example.com", "Bela Blood", ["BLOOD_BANK_STAFF"], designation="Technician")
    world.bb2 = person("employees", "bb2@hospital.example.com", "Bimal Blood", ["BLOOD_BANK_STAFF"], designation="Technician")
    other = client.post("/api/patients", headers=world.employee, json={"email": "other@example.com", "full_name": "Other Person", "password": PASSWORD, "gender": "male", "date_of_birth": "1990-01-01", "phone": "8888888888"})
    assert other.status_code == 201, other.text
    world.other_id = other.json()["patient"]["id"]
    world.other = login(client, "other@example.com")
    enc = client.post("/api/opd/walk-in", headers=world.employee, json={"patient_id": world.patient_id, "doctor_id": world.doctor_id})
    world.enc = enc.json()["encounter_id"]
    return world


def final_invoice(client, w, amount=1000.0):
    with SessionLocal() as db:
        c = EncounterCharge(encounter_id=w.enc, patient_id=w.patient_id, description="Consultation", amount=amount, gst_percent=0, status="PENDING")
        db.add(c)
        db.commit()
        cid = c.id
    inv = client.post("/api/finance/invoices", headers=w.b1, json={"patient_id": w.patient_id, "charge_ids": [cid]}).json()
    return client.post(f"/api/finance/invoices/{inv['id']}/finalise", headers=w.b1).json()


def test_a_patient_cannot_reach_another_patients_money_results_or_scans(client, sw):
    inv = final_invoice(client, sw)
    pay = client.post(f"/api/finance/invoices/{inv['id']}/pay", headers=sw.b1, json={"amount": 100, "method": "CASH"}).json()
    assert client.get("/api/finance/my-invoices", headers=sw.other).json() == []
    assert client.get(f"/api/finance/payments/{pay['payment_id']}/receipt", headers=sw.other).status_code == 404
    assert client.get(f"/api/finance/payments/{pay['payment_id']}/receipt", headers=sw.patient).status_code == 200
    for path in (f"/api/finance/invoices/{inv['id']}", "/api/finance/invoices", "/api/claims", "/api/finance/reports/daily-cash"):
        assert client.get(path, headers=sw.other).status_code == 403
    with SessionLocal() as db:
        o = LabTestOrder(encounter_id=sw.enc, patient_id=sw.patient_id, doctor_id=sw.doctor_id, test_name="Panel", status="COMPLETED", result_status="APPROVED", approved_at=utcnow(), doctor_seen_at=utcnow())
        db.add(o)
        db.flush()
        db.add(LabResult(order_id=o.id, analyte_name="Potassium", value_text="4", value_num=4, unit="mmol/L", flag="NORMAL"))
        s = RadiologyOrder(encounter_id=sw.enc, patient_id=sw.patient_id, doctor_id=sw.doctor_id, study="Chest X-ray", modality="XRAY", status="APPROVED", approved_at=utcnow(), doctor_seen_at=utcnow())
        db.add(s)
        db.flush()
        db.add(RadiologyReport(order_id=s.id, findings="Clear", impression="Normal", reported_by=1))
        path = os.path.join(os.path.dirname(__file__), "_scan.png")
        open(path, "wb").write(b"\x89PNG\r\n\x1a\n" + b"0" * 20)
        f = RadiologyAttachment(order_id=s.id, filename="scan.png", stored_path=path, uploaded_by=1)
        db.add(f)
        db.commit()
        fid, oid = f.id, o.id
    try:
        assert client.get(f"/api/radiology/files/{fid}", headers=sw.patient).status_code == 200
        assert client.get(f"/api/radiology/files/{fid}", headers=sw.other).status_code == 403
        assert client.get("/api/radiology/my-studies", headers=sw.other).json() == []
        assert client.get("/api/lab/my-tests", headers=sw.other).json() == []
        assert client.get(f"/api/lab/patient/{sw.patient_id}/tests", headers=sw.other_doctor).status_code == 403
        assert client.get(f"/api/radiology/patient/{sw.patient_id}/studies", headers=sw.other_doctor).status_code == 403
        assert client.get(f"/api/bloodbank/patient/{sw.patient_id}/transfusions", headers=sw.other_doctor).status_code == 403
        assert client.get(f"/api/doctor/patients/{sw.patient_id}/timeline", headers=sw.other_doctor).status_code == 403
        mine = client.get("/api/integrations/fhir/my-bundle", headers=sw.other).json()
        assert [e["resource"]["resourceType"] for e in mine["entry"]] == ["Patient"] and "Other Person" in mine["entry"][0]["resource"]["name"][0]["text"]
        assert client.post(f"/api/lab/tests/{oid}/seen", headers=sw.other_doctor).status_code == 403
    finally:
        os.remove(path)


def test_the_billing_desk_sees_money_and_never_clinical_notes(client, sw):
    for path in (f"/api/doctor/patients/{sw.patient_id}/timeline", f"/api/doctor/patients/{sw.patient_id}/clinical-summary", f"/api/lab/patient/{sw.patient_id}/tests",
                 f"/api/radiology/patient/{sw.patient_id}/studies", f"/api/integrations/fhir/patients/{sw.patient_id}/bundle", f"/api/prescriptions?patient_id={sw.patient_id}"):
        assert client.get(path, headers=sw.b1).status_code in (401, 403, 404, 422), path
    overview = client.get(f"/api/finance/patients/{sw.patient_id}/overview", headers=sw.b1).json()
    assert set(overview["patient"]) == {"id", "full_name", "patient_code", "uhid"}


# ------------------------------------------------------------------ two people at the same moment
def race(fn, count=6):
    results, barrier = [], threading.Barrier(count)

    def go(i):
        c = TestClient(app)
        barrier.wait()
        results.append(fn(c, i))

    threads = [threading.Thread(target=go, args=(i,)) for i in range(count)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    return results


def test_simultaneous_payments_cannot_overpay_a_bill(client, sw):
    inv = final_invoice(client, sw, amount=1000)
    codes = race(lambda c, i: c.post(f"/api/finance/invoices/{inv['id']}/pay", headers=sw.b1 if i % 2 else sw.b2, json={"amount": 400, "method": "CASH"}).status_code)
    after = client.get(f"/api/finance/invoices/{inv['id']}", headers=sw.b1).json()
    assert after["paid"] <= 1000.0 and after["balance"] >= 0.0, (codes, after["paid"])
    assert codes.count(201) == int(after["paid"] // 400)


def test_simultaneous_refund_approvals_pay_a_refund_only_once(client, sw):
    inv = final_invoice(client, sw, amount=1000)
    client.post(f"/api/finance/invoices/{inv['id']}/pay", headers=sw.b1, json={"amount": 1000, "method": "CASH"})
    r = client.post("/api/finance/refunds", headers=sw.b1, json={"invoice_id": inv["id"], "amount": 800, "method": "CASH", "reason": "Service not given"}).json()
    codes = race(lambda c, i: c.post(f"/api/finance/refunds/{r['id']}/decide", headers=sw.acc, json={"approve": True}).status_code)
    assert codes.count(200) == 1, codes
    assert client.get(f"/api/finance/invoices/{inv['id']}", headers=sw.b1).json()["refunded"] == 800.0


def test_one_blood_unit_cannot_be_matched_to_two_requests_at_once(client, sw):
    with SessionLocal() as db:
        db.query(Patient).update({"blood_group": "A+"})
        donor = BloodDonor(donor_no="D-T-1", full_name="Dev Donor", gender="male", date_of_birth=date.today() - timedelta(days=9000), blood_group="O-", created_by=1)
        db.add(donor)
        db.flush()
        don = BloodDonation(donor_id=donor.id, volume_ml=450, haemoglobin=14, weight_kg=70, collected_by=1, screening="CLEARED", screened_by=2)
        db.add(don)
        db.flush()
        unit = BloodUnit(unit_number="U-T-1", donation_id=don.id, blood_group="O-", component="PRBC", volume_ml=450, collected_at=utcnow(), expires_at=utcnow() + timedelta(days=30), status="AVAILABLE")
        db.add(unit)
        db.commit()
        uid = unit.id
    ids = [client.post("/api/bloodbank/requests", headers=sw.doctor, json={"patient_id": sw.patient_id, "component": "PRBC", "units_requested": 1, "indication": "Anaemia"}).json()["id"] for _ in range(4)]
    codes = race(lambda c, i: c.post(f"/api/bloodbank/requests/{ids[i % 4]}/crossmatch", headers=sw.bb1, json={"unit_id": uid, "result": "COMPATIBLE"}).status_code, count=4)
    assert codes.count(201) == 1, codes
    with SessionLocal() as db:
        assert db.get(BloodUnit, uid).status == "RESERVED"
