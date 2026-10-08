"""Who may see or change what. Each test is one rule from the role-permission matrix."""
from datetime import date, timedelta

from tests import sample_data as sd
from tests.conftest import login, upload

RX = {"items": [{"medicine_name": "Medicine A", "dosage": "500 mg", "frequency": "Twice daily",
                 "duration": "5 days", "quantity": 10}]}


def make_report(client, world, review=False):
    report = upload(client, world.employee, world.patient_id, "a.pdf", sd.lines_to_pdf(sd.REPORT_A_LINES)).json()
    if review:
        client.put(f"/api/doctor/reports/{report['id']}/review", headers=world.doctor, json={"decision": "APPROVED"})
    return report["id"]


def second_patient(client, world, email="other@example.com"):
    created = client.post("/api/patients", headers=world.employee, json={
        "email": email, "full_name": "Other Patient", "password": "StrongPass123"}).json()
    return created["patient"]["id"], login(client, email)


def test_patient_sees_only_own_records(client, world):
    report_id = make_report(client, world, review=True)
    other_id, other_auth = second_patient(client, world)
    assert client.get(f"/api/reports/{report_id}", headers=other_auth).status_code == 403
    assert client.get(f"/api/reports/{report_id}/file", headers=other_auth).status_code == 403
    assert client.get("/api/reports", headers=other_auth).json() == []
    assert client.get(f"/api/patients/{world.patient_id}", headers=other_auth).status_code == 403
    assert client.get(f"/api/patients/{world.patient_id}/comparison", headers=other_auth).status_code == 403
    assert client.get("/api/patient/history", headers=other_auth).json()["timeline"] == []


def test_doctor_sees_only_authorized_patients(client, world):
    report_id = make_report(client, world)
    assert client.get(f"/api/reports/{report_id}", headers=world.other_doctor).status_code == 403
    assert client.get(f"/api/doctor/patients/{world.patient_id}/history", headers=world.other_doctor).status_code == 403
    assert client.get("/api/doctor/patients", headers=world.other_doctor).json() == []
    assert client.get("/api/patients", headers=world.other_doctor).json() == []
    for path, body in (("/api/doctor/notes", {"patient_id": world.patient_id, "note": "hello there"}),
                       ("/api/prescriptions", {**RX, "patient_id": world.patient_id})):
        assert client.post(path, headers=world.other_doctor, json=body).status_code == 403
    assert client.put(f"/api/doctor/reports/{report_id}/review", headers=world.other_doctor,
                      json={"decision": "APPROVED"}).status_code == 403
    # the assigned doctor sees the patient
    assert len(client.get("/api/doctor/patients", headers=world.doctor).json()) == 1


def test_employee_sees_basic_info_but_never_clinical_data(client, world):
    report_id = make_report(client, world)
    basic = client.get(f"/api/patients/{world.patient_id}", headers=world.employee).json()
    assert basic["full_name"] == "Rahul Patil" and "allergies" not in basic and "current_medications" not in basic
    clinical = client.get(f"/api/patients/{world.patient_id}", headers=world.doctor).json()
    assert clinical["allergies"] == "None known"
    detail = client.get(f"/api/reports/{report_id}", headers=world.employee).json()
    assert detail["parameters"] == [] and detail["ai_summary"] is None
    assert client.get(f"/api/reports/{report_id}/file", headers=world.employee).status_code == 200  # own upload
    assert client.get(f"/api/doctor/patients/{world.patient_id}/history", headers=world.employee).status_code == 403
    assert client.get(f"/api/patients/{world.patient_id}/comparison", headers=world.employee).status_code == 403
    assert client.get("/api/prescriptions", headers=world.employee).status_code == 403
    assert client.post("/api/doctor/notes", headers=world.employee,
                       json={"patient_id": world.patient_id, "note": "nope nope"}).status_code == 403


def test_admin_has_no_clinical_access(client, world):
    report_id = make_report(client, world)
    assert client.get(f"/api/reports/{report_id}", headers=world.admin).json()["parameters"] == []
    assert client.get(f"/api/reports/{report_id}/file", headers=world.admin).status_code == 403
    assert client.get(f"/api/patients/{world.patient_id}/comparison", headers=world.admin).status_code == 403


def test_employee_cannot_change_clinical_fields(client, world):
    changed = client.put(f"/api/patients/{world.patient_id}", headers=world.employee, json={
        "phone": "1111111111", "allergies": "Changed!", "current_medications": "Changed!"})
    assert changed.status_code == 200 and changed.json()["phone"] == "1111111111"
    clinical = client.get(f"/api/patients/{world.patient_id}", headers=world.doctor).json()
    assert clinical["allergies"] == "None known" and clinical["current_medications"] is None


def test_unreviewed_analysis_hidden_from_patient_until_review(client, world):
    report_id = make_report(client, world, review=False)
    before = client.get(f"/api/reports/{report_id}", headers=world.patient).json()
    assert before["parameters"] == [] and before["ai_summary"] is None
    timeline = client.get("/api/patient/history", headers=world.patient).json()["timeline"]
    assert "AI_ANALYSIS" not in [e["type"] for e in timeline]  # AI step also hidden in the timeline
    client.put(f"/api/doctor/reports/{report_id}/review", headers=world.doctor, json={"decision": "APPROVED"})
    after = client.get(f"/api/reports/{report_id}", headers=world.patient).json()
    assert len(after["parameters"]) == 6 and after["ai_summary"]


def test_patient_cannot_edit_doctor_content(client, world):
    for method, path in (("post", "/api/doctor/notes"), ("post", "/api/doctor/recommendations"),
                         ("post", "/api/prescriptions"), ("put", "/api/doctor/reports/1/review")):
        assert getattr(client, method)(path, headers=world.patient, json={}).status_code == 403


def test_doctor_content_validation(client, world):
    bad_priority = client.post("/api/doctor/notes", headers=world.doctor, json={
        "patient_id": world.patient_id, "note": "valid note", "priority": "URGENT!!"})
    assert bad_priority.status_code == 422
    other_id, _ = second_patient(client, world)
    report_id = make_report(client, world)
    wrong_report = client.post("/api/doctor/notes", headers=world.doctor, json={
        "patient_id": other_id, "report_id": report_id, "note": "mismatch"})
    assert wrong_report.status_code in (403, 404)
    empty_rx = client.post("/api/prescriptions", headers=world.doctor, json={"patient_id": world.patient_id, "items": []})
    assert empty_rx.status_code == 422


def test_pharmacy_sees_only_open_prescriptions_with_limited_data(client, world):
    rx = client.post("/api/prescriptions", headers=world.doctor, json={**RX, "patient_id": world.patient_id}).json()
    listing = client.get("/api/pharmacy/prescriptions", headers=world.pharmacy).json()
    assert [r["id"] for r in listing] == [rx["id"]]
    assert "allergies" not in listing[0] and "phone" not in listing[0]
    assert client.put(f"/api/prescriptions/{rx['id']}/cancel", headers=world.doctor).json()["status"] == "CANCELLED"
    assert client.get("/api/pharmacy/prescriptions", headers=world.pharmacy).json() == []
    assert client.get(f"/api/prescriptions/{rx['id']}", headers=world.pharmacy).status_code == 404
    item_id = rx["items"][0]["id"]
    blocked = client.post("/api/pharmacy/dispense", headers=world.pharmacy, json={"prescription_item_id": item_id, "quantity": 1})
    assert blocked.status_code == 409 and "cancelled" in blocked.json()["detail"]
    assert client.get("/api/prescriptions/9999", headers=world.pharmacy).json()["detail"] == "No active prescription found."


def test_doctor_sees_only_their_own_prescriptions(client, world):
    rx = client.post("/api/prescriptions", headers=world.doctor, json={**RX, "patient_id": world.patient_id}).json()
    assert client.get(f"/api/prescriptions/{rx['id']}", headers=world.other_doctor).status_code == 403
    assert client.get("/api/prescriptions", headers=world.other_doctor).json() == []
    assert len(client.get("/api/prescriptions", headers=world.doctor).json()) == 1


def test_expired_prescription_cannot_be_dispensed(client, world):
    from app.database.connection import SessionLocal
    from app.database.models import Prescription
    rx = client.post("/api/prescriptions", headers=world.doctor, json={**RX, "patient_id": world.patient_id}).json()
    with SessionLocal() as db:
        row = db.get(Prescription, rx["id"])
        row.prescription_date = date.today() - timedelta(days=45)
        db.commit()
    assert client.get(f"/api/prescriptions/{rx['id']}", headers=world.doctor).json()["status"] == "EXPIRED"
    blocked = client.post("/api/pharmacy/dispense", headers=world.pharmacy,
                          json={"prescription_item_id": rx["items"][0]["id"], "quantity": 1})
    assert blocked.status_code == 409 and "expired" in blocked.json()["detail"]


def test_inventory_and_stock_deduction(client, world):
    stock = client.post("/api/pharmacy/inventory", headers=world.pharmacy, json={
        "medicine_name": "Medicine A", "batch_number": "B1", "quantity": 8, "unit_price": 2.5,
        "expiry_date": str(date.today() + timedelta(days=200)), "manufacturer": "Demo Pharma"})
    assert stock.status_code == 201
    rx = client.post("/api/prescriptions", headers=world.doctor, json={**RX, "patient_id": world.patient_id}).json()
    item_id = rx["items"][0]["id"]
    # 10 prescribed but only 8 in stock -> cannot dispense 10
    short = client.post("/api/pharmacy/dispense", headers=world.pharmacy, json={"prescription_item_id": item_id, "quantity": 10})
    assert short.status_code == 409 and "Not enough stock" in short.json()["detail"]
    ok = client.post("/api/pharmacy/dispense", headers=world.pharmacy, json={"prescription_item_id": item_id, "quantity": 5})
    assert ok.status_code == 200
    left = client.get("/api/pharmacy/inventory", headers=world.pharmacy).json()[0]
    assert left["quantity"] == 3
    restock = client.put(f"/api/pharmacy/inventory/{left['id']}", headers=world.pharmacy, json={"quantity": 50})
    assert restock.json()["quantity"] == 50
    # others cannot touch the inventory
    for who in (world.doctor, world.patient, world.employee):
        assert client.get("/api/pharmacy/inventory", headers=who).status_code == 403
    dash = client.get("/api/pharmacy/dashboard", headers=world.pharmacy).json()
    assert dash["partially_dispensed"] == 1 and dash["todays_prescriptions"] == 1


def test_unavailable_medicine_is_recorded(client, world):
    rx = client.post("/api/prescriptions", headers=world.doctor, json={**RX, "patient_id": world.patient_id}).json()
    res = client.post("/api/pharmacy/dispense", headers=world.pharmacy, json={
        "prescription_item_id": rx["items"][0]["id"], "quantity": 0, "mark_unavailable": True, "notes": "Out of stock"})
    assert res.status_code == 200 and res.json()["items"][0]["dispense_status"] == "UNAVAILABLE"
    history = client.get("/api/pharmacy/history", headers=world.pharmacy).json()
    assert history[0]["status"] == "UNAVAILABLE" and history[0]["notes"] == "Out of stock"
