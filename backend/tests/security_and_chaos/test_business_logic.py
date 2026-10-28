"""Business logic, concurrency, boundary data and the audit trail. A malicious patient, a curious employee, a rogue pharmacist and a careless doctor."""
import threading
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.database.connection import SessionLocal
from app.database.models import Prescription
from app.main import app
from tests.conftest import PASSWORD, headers, login, upload
from tests.security_and_chaos._helpers import all_actors, bust
from tests.test_patient_assistant import add_report, report

ITEM = {"medicine_name": "Tab. Test", "dosage": "5 mg", "frequency": "Daily", "duration": "5 days", "quantity": 5}


def make_rx(client, world, qty=5):
    r = client.post("/api/prescriptions", headers=world.doctor, json={"patient_id": world.patient_id, "clinical_indication": "Check", "items": [{**ITEM, "quantity": qty}]})
    assert r.status_code == 201, r.text
    return r.json()


def audit(client, world, action=None):
    return client.get("/api/admin/audit-logs?limit=1000" + (f"&action={action}" if action else ""), headers=world.admin).json()


def stock(client, world, name="Tab. Test", quantity=100, price=2.0):
    r = client.post("/api/pharmacy/inventory", headers=world.pharmacy, json={"medicine_name": name, "quantity": quantity, "unit_price": price, "batch_number": "B1"})
    assert r.status_code == 201, r.text
    return r.json()


# ------------------------------------------------------------------ prescriptions and dispensing
def test_a_prescription_cannot_be_dispensed_more_than_prescribed_or_after_it_is_cancelled_or_expired(client, world):
    rx = make_rx(client, world, qty=5)
    item = rx["items"][0]["id"]
    stock(client, world)
    assert client.post("/api/pharmacy/dispense", headers=world.pharmacy, json={"prescription_item_id": item, "quantity": 3}).status_code == 200
    for qty in (3, 99, 0, -1):
        assert client.post("/api/pharmacy/dispense", headers=world.pharmacy, json={"prescription_item_id": item, "quantity": qty}).status_code in (409, 422), qty
    assert client.post("/api/pharmacy/dispense", headers=world.pharmacy, json={"prescription_item_id": item, "quantity": 2}).status_code == 200
    assert client.post("/api/pharmacy/dispense", headers=world.pharmacy, json={"prescription_item_id": item, "quantity": 1}).status_code == 409      # fully dispensed
    second = make_rx(client, world)
    assert client.put(f"/api/prescriptions/{second['id']}/cancel", headers=world.doctor, json={}).status_code == 200
    assert client.post("/api/pharmacy/dispense", headers=world.pharmacy, json={"prescription_item_id": second["items"][0]["id"], "quantity": 1}).status_code == 409
    third = make_rx(client, world)
    with SessionLocal() as db:
        db.get(Prescription, third["id"]).prescription_date = date.today() - timedelta(days=400)
        db.commit()
    assert client.post("/api/pharmacy/dispense", headers=world.pharmacy, json={"prescription_item_id": third["items"][0]["id"], "quantity": 1}).status_code == 409


@bust("B-01")
def test_two_pharmacists_dispensing_the_same_item_at_the_same_moment_cannot_give_out_more_than_was_prescribed(client, world):
    rx = make_rx(client, world, qty=5)
    item = rx["items"][0]["id"]
    stock(client, world, quantity=1000)
    other = None
    client.post("/api/admin/pharmacy-staff", headers=world.admin, json={"email": "ph2@hospital.example.com", "full_name": "Second Pharmacist", "password": PASSWORD, "pharmacy_name": "MediCare"})
    other = login(client, "ph2@hospital.example.com")
    results, barrier = [], threading.Barrier(8)

    def go(auth):
        c = TestClient(app)
        barrier.wait()
        results.append(c.post("/api/pharmacy/dispense", headers=auth, json={"prescription_item_id": item, "quantity": 5}).status_code)

    threads = [threading.Thread(target=go, args=(world.pharmacy if i % 2 else other,)) for i in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert results.count(200) == 1, results
    rx_after = client.get(f"/api/prescriptions/{rx['id']}", headers=world.doctor).json()
    assert rx_after["items"][0]["dispensed_quantity"] == 5


def test_a_bill_cannot_have_a_negative_total_or_sell_what_is_not_in_stock(client, world):
    item = stock(client, world, quantity=3, price=10.0)
    base = {"payment_method": "CASH", "items": [{"inventory_id": item["id"], "quantity": 1}]}
    assert client.post("/api/pharmacy/sales", headers=world.pharmacy, json={**base, "items": [{"inventory_id": item["id"], "quantity": 4}]}).status_code in (409, 422)
    assert client.post("/api/pharmacy/sales", headers=world.pharmacy, json={**base, "items": [{"inventory_id": item["id"], "quantity": -1}]}).status_code == 422
    assert client.post("/api/pharmacy/sales", headers=world.pharmacy, json={**base, "discount": -5}).status_code == 422
    big = client.post("/api/pharmacy/sales", headers=world.pharmacy, json={**base, "discount": 1_000_000})
    assert big.status_code in (409, 422) or big.json()["total"] >= 0, big.text


def test_a_prescription_cannot_be_billed_twice(client, world):
    rx = make_rx(client, world, qty=2)
    stock(client, world, quantity=50, price=5.0)
    assert client.post("/api/pharmacy/dispense", headers=world.pharmacy, json={"prescription_item_id": rx["items"][0]["id"], "quantity": 2}).status_code == 200
    first = client.post(f"/api/pharmacy/prescriptions/{rx['id']}/bill", headers=world.pharmacy, json={})
    assert first.status_code == 201, first.text
    again = client.post(f"/api/pharmacy/prescriptions/{rx['id']}/bill", headers=world.pharmacy, json={})
    assert again.status_code in (409, 422), again.text


# ------------------------------------------------------------------ reports: workflow
def test_a_second_doctor_cannot_review_a_report_that_was_sent_to_someone_else(client, world):
    rid = upload(client, world.employee, world.patient_id, "r.txt", report("03/07/2026", "Hemoglobin 12.1 g/dL 13.0 - 17.0")).json()["id"]
    assert client.put(f"/api/doctor/reports/{rid}/review", headers=world.other_doctor, json={"decision": "APPROVED", "comment": "ok"}).status_code in (403, 404)
    assert client.put(f"/api/doctor/reports/{rid}/review", headers=world.doctor, json={"decision": "APPROVED", "comment": "ok"}).status_code == 200


@bust("B-02")
def test_a_report_that_was_reviewed_cannot_be_quietly_reviewed_again_with_a_different_decision(client, world):
    """After the patient has seen the result, a second review that changes the decision silently replaces the first (no conflict, no history of
    the earlier decision, and no audit entry that says what it was before)."""
    rid = upload(client, world.employee, world.patient_id, "r.txt", report("03/07/2026", "Hemoglobin 12.1 g/dL 13.0 - 17.0")).json()["id"]
    assert client.put(f"/api/doctor/reports/{rid}/review", headers=world.doctor, json={"decision": "APPROVED", "comment": "ok"}).status_code == 200
    again = client.put(f"/api/doctor/reports/{rid}/review", headers=world.doctor, json={"decision": "MODIFIED", "comment": "changed my mind"})
    assert again.status_code in (409, 422)


def test_the_patient_cannot_review_upload_or_delete_reports(client, world):
    rid = add_report(client, world, "r.txt", report("03/07/2026", "Hemoglobin 12.1 g/dL 13.0 - 17.0"))["id"]
    assert client.put(f"/api/doctor/reports/{rid}/review", headers=world.patient, json={"decision": "APPROVED"}).status_code == 403
    assert upload(client, world.patient, world.patient_id, "r.txt", b"Hemoglobin 12 g/dL 13-17").status_code == 403
    assert client.delete(f"/api/reports/{rid}", headers=world.patient).status_code == 403


def test_the_same_report_uploaded_twice_and_in_parallel_does_not_crash_or_lose_data(client, world):
    content = report("03/07/2026", "Hemoglobin 12.1 g/dL 13.0 - 17.0", "Vitamin D 12 ng/mL 30 - 100")
    results, barrier = [], threading.Barrier(6)

    def go():
        c = TestClient(app, raise_server_exceptions=False)
        barrier.wait()
        results.append(upload(c, world.employee, world.patient_id, "same.txt", content).status_code)

    threads = [threading.Thread(target=go) for _ in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert all(code in (201, 409) for code in results), results
    assert len(client.get(f"/api/reports?patient_id={world.patient_id}", headers=world.doctor).json()) == results.count(201)


# ------------------------------------------------------------------ boundary data
ODD = [   # id, field, value, must be refused
    ("name-10k-chars", "full_name", "N" * 10_000, True), ("name-nul-byte", "full_name", "Z\u0000ero", True), ("name-rtl-override", "full_name", "‮evil", False),
    ("name-emoji", "full_name", "😀 Smile", False), ("name-script-tag", "full_name", "<script>alert(1)</script>", False), ("name-sql", "full_name", "'; DROP TABLE users;--", False),
    ("phone-300-digits", "phone", "9" * 300, True), ("dob-year-9999", "date_of_birth", "9999-12-31", True), ("dob-year-0001", "date_of_birth", "0001-01-01", True),
    ("dob-year-1800", "date_of_birth", "1800-01-01", True), ("dob-future-2999", "date_of_birth", "2999-01-01", True), ("address-100k-chars", "address", "x" * 100_000, True),
]
MARKS = {"name-nul-byte": bust("X-02"), "dob-year-9999": bust("X-01"), "dob-year-0001": bust("X-01"), "dob-year-1800": bust("X-01"), "dob-future-2999": bust("X-01")}


@pytest.mark.parametrize("field,value,refused", [pytest.param(f, v, r, id=i, marks=MARKS.get(i, [])) for i, f, v, r in ODD])
def test_odd_values_are_stored_safely_or_refused_never_a_crash(client, world, field, value, refused):
    quiet = TestClient(app, raise_server_exceptions=False)
    body = {"email": "boundary@example.com", "full_name": "Boundary Case", "password": PASSWORD, "gender": "male", "date_of_birth": "1990-01-01", "phone": "9999999991", field: value}
    r = quiet.post("/api/patients", headers=world.employee, json=body)
    assert r.status_code < 500, (field, r.status_code, r.text[:120])
    if refused:
        assert r.status_code in (400, 422), (field, value[:20], r.status_code)


@pytest.mark.parametrize("value", ["1e308", "-1e308", "1e-320", "NaN", "Infinity", "-0", "0.0000000001", "99999999999999999999"])
def test_absurd_lab_values_do_not_crash_the_analysis(client, world, value):
    quiet = TestClient(app, raise_server_exceptions=False)
    r = upload(quiet, world.employee, world.patient_id, "r.txt", report("03/07/2026", f"Hemoglobin {value} g/dL 13.0 - 17.0", "Vitamin D 12 ng/mL 30 - 100"))
    assert r.status_code < 500, (value, r.status_code, r.text[:150])


def test_a_lab_report_for_a_dead_or_inactive_patient_and_other_edge_accounts_does_not_crash(client, world):
    uid = client.get("/api/auth/me", headers=world.patient).json()["id"]
    assert client.put(f"/api/admin/users/{uid}", headers=world.admin, json={"is_active": False}).status_code in (200, 204)
    quiet = TestClient(app, raise_server_exceptions=False)
    r = upload(quiet, world.employee, world.patient_id, "r.txt", report("03/07/2026", "Hemoglobin 12.1 g/dL 13.0 - 17.0"))
    assert r.status_code < 500
    for path in ("/api/doctor/patients", f"/api/patients/{world.patient_id}", "/api/reports", "/api/appointments"):
        assert quiet.get(path, headers=world.doctor).status_code < 500, path


def test_deleting_or_deactivating_staff_with_records_never_crashes_or_leaks(client, world):
    quiet = TestClient(app, raise_server_exceptions=False)
    add_report(client, world, "r.txt", report("03/07/2026", "Hemoglobin 12.1 g/dL 13.0 - 17.0"))
    make_rx(client, world)
    for who in ("anjali@hospital.example.com", "priya@hospital.example.com", "pharmacy@hospital.example.com"):
        users = client.get("/api/admin/users", headers=world.admin).json()
        uid = next(u["id"] for u in users if u["email"] == who)
        check = quiet.get(f"/api/admin/users/{uid}/delete-check", headers=world.admin)
        assert check.status_code == 200
        r = quiet.delete(f"/api/admin/users/{uid}", headers=world.admin)
        assert r.status_code in (200, 204, 409), (who, r.status_code, r.text[:150])
        assert quiet.put(f"/api/admin/users/{uid}", headers=world.admin, json={"is_active": False}).status_code < 500
    for path in ("/api/reports", "/api/prescriptions", "/api/admin/audit-logs", "/api/admin/people", "/api/admin/dashboard"):
        assert quiet.get(path, headers=world.admin).status_code < 500, path


# ------------------------------------------------------------------ the audit trail
def test_the_audit_log_cannot_be_changed_or_deleted_through_the_api(client, world):
    for method in ("put", "patch", "delete", "post"):
        for path in ("/api/admin/audit-logs", "/api/admin/audit-logs/1"):
            assert client.request(method, path, headers=world.admin, json={}).status_code in (404, 405), (method, path)


def test_important_actions_are_in_the_audit_log(client, world):
    rid = add_report(client, world, "r.txt", report("03/07/2026", "Hemoglobin 12.1 g/dL 13.0 - 17.0"))["id"]
    client.get(f"/api/reports/{rid}/file", headers=world.doctor)
    rx = make_rx(client, world)
    stock(client, world)
    client.post("/api/pharmacy/dispense", headers=world.pharmacy, json={"prescription_item_id": rx["items"][0]["id"], "quantity": 1})
    client.post("/api/auth/login", json={"email": "priya@hospital.example.com", "password": "wrong"})
    client.post("/api/auth/change-password", headers=world.employee, json={"current_password": PASSWORD, "new_password": "NewPass12345"})
    actions = {a["action"] for a in audit(client, world)}
    for expected in ("LOGIN", "LOGIN_FAILED", "REPORT_UPLOADED", "REPORT_REVIEWED", "REPORT_FILE_VIEWED", "PRESCRIPTION_CREATED", "MEDICINE_DISPENSED", "PASSWORD_CHANGED", "PATIENT_CREATED", "USER_CREATED"):
        assert expected in actions, expected


@bust("B-03")
def test_changes_to_the_medicine_stock_and_prices_are_in_the_audit_log(client, world):
    """A rogue pharmacist can change quantities and prices, or receive stock, and nothing is recorded: sales and dispensing are audited, stock is not."""
    item = stock(client, world, quantity=50, price=10.0)
    assert client.put(f"/api/pharmacy/inventory/{item['id']}", headers=world.pharmacy, json={"quantity": 0, "unit_price": 0}).status_code == 200
    assert client.post("/api/pharmacy/inventory/receive", headers=world.pharmacy, json={"medicine_name": "Tab. Other", "quantity": 5, "unit_price": 1}).status_code == 201
    entries = [a for a in audit(client, world) if a["user_role"] == "PHARMACY" and a["entity_type"] in ("inventory", "stock", "medicine")]
    assert len(entries) >= 3


@bust("B-04")
def test_attempts_to_reach_someone_elses_data_leave_a_trace(client, world):
    """A patient who tries other patients' records (every attempt is refused) is not recorded anywhere: only failed logins are."""
    before = len(audit(client, world))
    for rid in range(1, 15):
        client.get(f"/api/reports/{rid}", headers=world.patient)
        client.get(f"/api/patients/{rid + 1}", headers=world.patient)
    denied = [a for a in audit(client, world)[: len(audit(client, world)) - before] if "DENIED" in a["action"] or "FORBIDDEN" in a["action"]]
    assert denied


@bust("B-05")
def test_deleting_a_user_does_not_make_their_audit_trail_anonymous(client, world):
    """USER_DELETED sets audit_logs.user_id to NULL for everything that person did: afterwards nobody can say who uploaded or reviewed what."""
    created = client.post("/api/admin/employees", headers=world.admin, json={"email": "temp.clerk@hospital.example.com", "full_name": "Temp Clerk", "designation": "Clerk"})
    uid = created.json()["user"]["id"]
    token = login(client, "temp.clerk@hospital.example.com", "Welcome@123") if False else None
    client.post("/api/auth/login", json={"email": "temp.clerk@hospital.example.com", "password": "Welcome@123"})
    assert client.delete(f"/api/admin/users/{uid}", headers=world.admin).status_code in (200, 204)
    rows = [a for a in audit(client, world) if a["action"] in ("LOGIN", "USER_CREATED") and a.get("entity_id") == uid or a["action"] == "LOGIN" and "temp.clerk" in (a["details"] or "")]
    deleted_rows = [a for a in audit(client, world) if a["action"] == "LOGIN" and a["user_id"] is None]
    assert not deleted_rows, "login entries of the deleted user have no user any more"
