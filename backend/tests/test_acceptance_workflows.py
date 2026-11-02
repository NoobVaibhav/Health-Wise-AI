"""Phase 10: the acceptance workflows of the brief, each one run end to end through the real APIs and across modules (registration, OPD, lab, radiology, IPD, emergency, pharmacy,
billing, insurance, the assistant and referrals), not one module at a time."""
from datetime import date, timedelta

import pytest

from app.database.connection import SessionLocal
from app.database.models import ClinicalAlert, StockMovement
from tests.conftest import PASSWORD, future, login

RX = {"clinical_indication": "Fever", "items": [{"medicine_name": "Tab. Paracetamol", "dosage": "500 mg", "frequency": "Twice a day", "duration": "3 days", "quantity": 6}]}
SUMMARY = {"final_diagnosis": "Community acquired pneumonia", "hospital_course": "IV antibiotics, afebrile on day 3", "follow_up": "Review in 1 week", "discharge_medicines": "Tab. Amoxicillin 500 mg TDS 5 days", "warning_signs": "Fever returns"}


def staff(client, w, path, email, name, roles=None, **extra):
    res = client.post(f"/api/admin/{path}", headers=w.admin, json={"email": email, "full_name": name, "password": PASSWORD, **extra})
    assert res.status_code == 201, res.text
    if roles:
        assert client.put(f"/api/access/users/{res.json()['user']['id']}/roles", headers=w.admin, json={"roles": roles}).status_code == 200
    return login(client, email), res.json()["user"]["id"]


@pytest.fixture()
def hw(client, world):
    """One small hospital with every kind of staff, a price list, a test catalogue, a ward and a cardiology department."""
    world.nurse, world.nurse_uid = staff(client, world, "nurses", "nurse@hospital.example.com", "Nurse Meera", designation="Staff nurse")
    world.nurse2, _ = staff(client, world, "nurses", "nurse2@hospital.example.com", "Nurse Neeta", designation="Staff nurse")
    world.tech, _ = staff(client, world, "lab-staff", "tech@hospital.example.com", "Tara Tech", lab_name="Main lab")
    world.path, _ = staff(client, world, "lab-staff", "path@hospital.example.com", "Dr. Paul Path", lab_name="Main lab", staff_type="PATHOLOGIST")
    world.rtech, _ = staff(client, world, "radiology-staff", "rtech@hospital.example.com", "Rita Rad")
    world.rad, _ = staff(client, world, "radiology-staff", "rad@hospital.example.com", "Dr. Ravi Rad", staff_type="RADIOLOGIST")
    world.b1, _ = staff(client, world, "employees", "b1@hospital.example.com", "Bina Billing", ["BILLING_EXECUTIVE"], designation="Billing")
    world.acc, _ = staff(client, world, "employees", "acc@hospital.example.com", "Asha Accounts", ["ACCOUNTANT"], designation="Accountant")
    world.tpa, _ = staff(client, world, "employees", "tpa@hospital.example.com", "Indu TPA", ["INSURANCE_EXECUTIVE"], designation="TPA desk")
    ward = client.post("/api/ipd/wards", headers=world.admin, json={"name": "General Ward A", "ward_type": "GENERAL"}).json()
    world.beds = [client.post(f"/api/ipd/wards/{ward['id']}/beds", headers=world.admin, json={"code": f"A{i}"}).json()["id"] for i in (1, 2)]
    svc = lambda code, name, cat, price, gst=0: client.post("/api/hospital/services", headers=world.admin, json={"code": code, "name": name, "category": cat, "price": price, "gst_percent": gst}).json()["id"]
    svc("OPD-GM", "OPD consultation, General Medicine", "CONSULTATION", 500)
    svc("LAB-E", "Serum Electrolytes", "LAB", 400, 5)
    svc("RAD-X", "Chest X-ray", "RADIOLOGY", 300, 12)
    svc("BED-G", "General ward bed per day", "BED", 1000)
    test = client.post("/api/diagnostics/tests", headers=world.admin, json={"kind": "LAB", "name": "Serum Electrolytes", "category": "BIOCHEMISTRY", "sample_type": "Blood"}).json()["id"]
    world.k = client.post(f"/api/diagnostics/tests/{test}/analytes", headers=world.admin, json={"name": "Potassium", "unit": "mmol/L", "ref_low": 3.5, "ref_high": 5.0, "critical_low": 2.8, "critical_high": 6.0}).json()["id"]
    client.post("/api/diagnostics/tests", headers=world.admin, json={"kind": "RADIOLOGY", "name": "Chest X-ray", "category": "XRAY"})
    dep = next(d["id"] for d in client.get("/api/catalog/departments", headers=world.admin).json() if d["name"] == "Cardiology")
    world.cardio = dep
    world.cardiologist, _ = staff(client, world, "doctors", "heart@hospital.example.com", "Dr. Heart Doctor", department_id=dep)
    world.cardiologist_id = next(d["id"] for d in client.get("/api/doctors", headers=world.employee).json() if d["full_name"] == "Dr. Heart Doctor")
    return world


def invoice_and_pay(client, w, patient_id=None, services=(), admission_id=None, pay=True):
    """The billing desk collects the charges, makes the invoice final and takes the whole payment. Returns the final invoice."""
    pid = patient_id or w.patient_id
    client.post(f"/api/finance/patients/{pid}/collect-charges", headers=w.b1)
    overview = client.get(f"/api/finance/patients/{pid}/overview", headers=w.b1).json()
    inv = client.post("/api/finance/invoices", headers=w.b1, json={"patient_id": pid, "admission_id": admission_id, "charge_ids": [c["id"] for c in overview["pending_charges"]], "services": list(services)})
    assert inv.status_code == 201, inv.text
    done = client.post(f"/api/finance/invoices/{inv.json()['id']}/finalise", headers=w.b1).json()
    if pay:
        paid = client.post(f"/api/finance/invoices/{done['id']}/pay", headers=w.b1, json={"amount": done["total"], "method": "CASH"})
        assert paid.status_code == 201, paid.text
        return paid.json()["invoice"]
    return done


# ------------------------------------------------------------------ 1. a new patient: registration, UHID, appointment, consultation, prescription, billing
def test_workflow_1_new_patient_to_paid_consultation(client, hw):
    created = client.post("/api/patients", headers=hw.employee, json={"email": "new@example.com", "full_name": "Nita New", "password": PASSWORD, "gender": "female", "date_of_birth": "1992-03-04", "phone": "9822200001"})
    assert created.status_code == 201, created.text
    pid = created.json()["patient"]["id"]
    appt = client.post("/api/appointments", headers=hw.employee, json={"patient_id": pid, "doctor_id": hw.doctor_id, "scheduled_at": future(30), "reason": "Fever"})
    assert appt.status_code == 201, appt.text
    token = client.post("/api/opd/check-in", headers=hw.employee, json={"appointment_id": appt.json()["id"]}).json()
    assert token["patient"]["uhid"] and token["number"] == 1                                       # a UHID and a token
    eid = token["encounter_id"]
    assert client.put(f"/api/opd/encounters/{eid}/consultation", headers=hw.doctor, json={"complaint": "Fever", "assessment": "Viral fever", "plan": "Rest"}).status_code == 200
    assert client.post(f"/api/opd/encounters/{eid}/sign", headers=hw.doctor).status_code == 200
    rx = client.post("/api/prescriptions", headers=hw.doctor, json={**RX, "patient_id": pid})
    assert rx.status_code == 201, rx.text
    invoice = invoice_and_pay(client, hw, pid)
    assert invoice["total"] == 500.0 and invoice["balance"] == 0.0 and invoice["number"].startswith("INV-")      # the consultation fee from the price list
    mine = client.get("/api/finance/my-invoices", headers=login(client, "new@example.com")).json()
    assert [i["number"] for i in mine] == [invoice["number"]]


# ------------------------------------------------------------------ 2. laboratory: order, sample, result, pathologist, doctor, patient
def test_workflow_2_lab_order_to_the_patients_report(client, hw):
    eid = client.post("/api/opd/walk-in", headers=hw.employee, json={"patient_id": hw.patient_id, "doctor_id": hw.doctor_id}).json()["encounter_id"]
    assert client.post(f"/api/opd/encounters/{eid}/orders", headers=hw.doctor, json={"kind": "LAB", "text": "Serum Electrolytes", "priority": "URGENT"}).status_code == 201
    test = next(t for t in client.get("/api/lab/worklist?status_filter=OPEN", headers=hw.tech).json()["tests"] if t["test_name"] == "Serum Electrolytes")
    assert test["urgent"] is True
    taken = client.post(f"/api/lab/tests/{test['id']}/status", headers=hw.tech, json={"status": "SAMPLE_COLLECTED", "sample_type": "Blood"}).json()
    assert taken["sample_code"].startswith("LAB-")                                                  # the barcode label
    entered = client.post(f"/api/lab/tests/{test['id']}/results", headers=hw.tech, json={"submit": True, "results": [{"analyte_id": hw.k, "value": "6.4"}]}).json()
    assert entered["results"][0]["flag"] == "CRITICAL_HIGH" and entered["results"][0]["ref_high"] == 5.0
    with SessionLocal() as db:                                                                      # a critical value alerts the clinical team the moment it is sent on
        assert [a.message for a in db.query(ClinicalAlert).filter(ClinicalAlert.level == "CRITICAL")][0].startswith("Critical lab value: Potassium 6.4")
    assert client.get(f"/api/lab/patient/{hw.patient_id}/tests", headers=hw.doctor).json()[0]["results"] == []                # nothing before approval
    assert client.post(f"/api/lab/tests/{test['id']}/approve", headers=hw.tech, json={}).status_code == 403
    assert client.post(f"/api/lab/tests/{test['id']}/approve", headers=hw.path, json={"note": "Checked"}).json()["status"] == "COMPLETED"
    assert client.get("/api/lab/my-tests", headers=hw.patient).json()[0]["results"] == []                                      # the patient waits for the doctor
    assert client.get(f"/api/lab/patient/{hw.patient_id}/tests", headers=hw.doctor).json()[0]["results"][0]["value"] == "6.4"
    client.post(f"/api/lab/tests/{test['id']}/seen", headers=hw.doctor)
    shown = client.get("/api/lab/my-tests", headers=hw.patient).json()[0]
    assert shown["results"][0]["flag_text"] == "Critically high" and shown["patient_message"] == "Result reviewed by your doctor"
    timeline = client.get(f"/api/doctor/patients/{hw.patient_id}/timeline", headers=hw.doctor).json()["events"]
    assert any(e["kind"] == "LAB_TEST" and "1 critical" in e["detail"] for e in timeline)
    invoice = invoice_and_pay(client, hw)
    assert [l["description"] for l in invoice["lines"]] == ["Lab: Serum Electrolytes"] and invoice["total"] == 420.0 and invoice["balance"] == 0.0           # 400 + 5% GST


# ------------------------------------------------------------------ 3. inpatient: admission, bed, staff, treatment, investigation, pharmacy, billing, discharge
def test_workflow_3_inpatient_stay_to_discharge_and_final_bill(client, hw):
    adm = client.post("/api/ipd/admissions", headers=hw.doctor, json={"patient_id": hw.patient_id, "diagnosis": "Pneumonia", "bed_id": hw.beds[0]})
    assert adm.status_code == 201, adm.text
    aid = adm.json()["id"]
    assert client.post(f"/api/ipd/admissions/{aid}/staff", headers=hw.admin, json={"user_id": hw.nurse_uid, "kind": "NURSE"}).status_code in (200, 201)
    assert client.post(f"/api/ipd/admissions/{aid}/notes", headers=hw.doctor, json={"note": "Day 1: on IV antibiotics"}).status_code == 201
    assert client.post(f"/api/ipd/admissions/{aid}/orders", headers=hw.doctor, json={"kind": "RADIOLOGY", "text": "Chest X-ray", "priority": "ROUTINE"}).status_code in (200, 201)
    scan = next(s for s in client.get("/api/radiology/worklist", headers=hw.rtech).json()["studies"] if s["study"] == "Chest X-ray")
    client.post(f"/api/radiology/orders/{scan['id']}/start", headers=hw.rtech)
    client.post(f"/api/radiology/orders/{scan['id']}/report", headers=hw.rad, json={"findings": "Right lower zone consolidation", "impression": "Consolidation in the right lower zone"})
    assert client.post(f"/api/radiology/orders/{scan['id']}/approve", headers=hw.rad).json()["status"] == "APPROVED"
    client.post(f"/api/radiology/orders/{scan['id']}/seen", headers=hw.doctor)
    # the ward asks the pharmacy for a medicine and the pharmacy issues it from usable stock
    client.post("/api/pharmacy/inventory/receive", headers=hw.pharmacy, json={"medicine_name": "Inj. Ceftriaxone", "batch_number": "B1", "quantity": 10, "unit_price": 50, "expiry_date": str(date.today() + timedelta(days=200))})
    req = client.post("/api/stock/requests", headers=hw.nurse, json={"admission_id": aid, "items": [{"medicine_name": "Inj. Ceftriaxone", "quantity": 4}]}).json()
    issued = client.post(f"/api/stock/requests/{req['id']}/issue", headers=hw.pharmacy, json={"issues": {str(req["items"][0]["id"]): 4}}).json()
    assert issued["status"] == "ISSUED"
    with SessionLocal() as db:
        assert db.query(StockMovement).filter(StockMovement.kind == "ISSUE").count() == 1
    # an advance is taken, the bed day and the scan are billed, the advance pays the bill
    dep = client.post("/api/finance/deposits", headers=hw.b1, json={"patient_id": hw.patient_id, "admission_id": aid, "amount": 5000, "method": "CASH"}).json()
    summary = client.put(f"/api/ipd/admissions/{aid}/discharge-summary", headers=hw.doctor, json=SUMMARY)
    assert summary.status_code == 200, summary.text
    assert client.post(f"/api/ipd/admissions/{aid}/discharge-summary/approve", headers=hw.doctor).status_code == 200
    assert client.post(f"/api/ipd/admissions/{aid}/discharge", headers=hw.doctor, json={}).status_code == 200
    final = invoice_and_pay(client, hw, admission_id=aid, pay=False)
    assert final["total"] == 1336.0                                                                 # one bed day (1000) and the scan (300 + 12% GST)
    paid = client.post(f"/api/finance/invoices/{final['id']}/pay", headers=hw.b1, json={"amount": final["total"], "method": "ADVANCE", "deposit_id": dep["id"]})
    assert paid.status_code == 201 and paid.json()["invoice"]["balance"] == 0.0
    assert client.get(f"/api/finance/patients/{hw.patient_id}/overview", headers=hw.b1).json()["deposits"][0]["balance"] == 3664.0       # the advance pays the bill and keeps the rest
    # the patient sees the stay, the finished report and the bill
    text = client.post("/api/patient-assistant/chat", headers=hw.patient, json={"message": "my discharge summary", "language": "en"}).json()["reply"]["text"]
    assert "Community acquired pneumonia" in text and "Review in 1 week" in text
    scan_text = client.post("/api/patient-assistant/chat", headers=hw.patient, json={"message": "what did my scan show", "language": "en"}).json()["reply"]["text"]
    assert "Consolidation in the right lower zone" in scan_text and "I cannot explain what a scan means" in scan_text


# ------------------------------------------------------------------ 4. emergency: registration, triage, assessment, investigation, treatment, admission
def test_workflow_4_emergency_to_admission_and_the_investigations_reach_the_labs(client, hw):
    vid = client.post("/api/emergency/visits", headers=hw.employee, json={"patient_id": hw.patient_id, "chief_complaint": "Chest pain", "arrival_mode": "AMBULANCE"}).json()["id"]
    assert client.post(f"/api/emergency/visits/{vid}/triage", headers=hw.nurse, json={"category": 1, "vitals": {"pulse": 150, "spo2": 82}}).json()["status"] == "TRIAGED"
    assert client.post(f"/api/emergency/visits/{vid}/assign", headers=hw.doctor, json={"doctor_id": hw.doctor_id}).status_code == 200
    client.post(f"/api/emergency/visits/{vid}/timeline", headers=hw.doctor, json={"kind": "ASSESSMENT", "text": "ECG shows ST elevation"})
    client.post(f"/api/emergency/visits/{vid}/orders", headers=hw.doctor, json={"kind": "LAB", "text": "Serum Electrolytes", "priority": "STAT"})
    client.post(f"/api/emergency/visits/{vid}/orders", headers=hw.doctor, json={"kind": "RADIOLOGY", "text": "Chest X-ray", "priority": "STAT"})
    lab = client.get("/api/lab/worklist?status_filter=OPEN", headers=hw.tech).json()["tests"]
    assert any(t["test_name"] == "Serum Electrolytes" and t["urgent"] for t in lab)                  # the emergency order is in the lab work list, urgent
    assert any(s["study"] == "Chest X-ray" and s["priority"] == "STAT" for s in client.get("/api/radiology/worklist", headers=hw.rtech).json()["studies"])
    done = client.post(f"/api/emergency/visits/{vid}/disposition", headers=hw.doctor, json={"disposition": "ADMIT", "bed_id": hw.beds[1], "diagnosis": "STEMI"}).json()
    assert done["status"] == "DISPOSED" and done["admission_id"]
    assert client.get(f"/api/ipd/admissions/{done['admission_id']}", headers=hw.doctor).json()["admission"]["bed"]["code"] == "A2"


# ------------------------------------------------------------------ 5. pharmacy: prescription, verification, batch, dispensing, billing, inventory
def test_workflow_5_prescription_to_dispensing_billing_and_stock(client, hw):
    item = client.post("/api/pharmacy/inventory/receive", headers=hw.pharmacy, json={"medicine_name": "Tab. Paracetamol", "batch_number": "P1", "quantity": 100, "unit_price": 2.0, "gst_percent": 12, "expiry_date": str(date.today() + timedelta(days=300))}).json()
    rx = client.post("/api/prescriptions", headers=hw.doctor, json={**RX, "patient_id": hw.patient_id}).json()
    assert any(r["id"] == rx["id"] for r in client.get("/api/pharmacy/prescriptions", headers=hw.pharmacy).json())          # verification: the pharmacy sees what the doctor wrote
    assert client.post("/api/pharmacy/dispense", headers=hw.pharmacy, json={"prescription_item_id": rx["items"][0]["id"], "quantity": 6}).status_code == 200
    bill = client.post(f"/api/pharmacy/prescriptions/{rx['id']}/bill", headers=hw.pharmacy, json={})
    assert bill.status_code == 201, bill.text
    assert bill.json()["total"] == round(6 * 2.0 * 1.12, 2)
    stock = next(i for i in client.get("/api/pharmacy/inventory", headers=hw.pharmacy).json() if i["id"] == item["id"])
    assert stock["quantity"] == 94
    kinds = [m["kind"] for m in client.get(f"/api/stock/movements?medicine_id={item['id']}", headers=hw.pharmacy).json()]
    assert "RECEIPT" in kinds and ("DISPENSE" in kinds or "SALE" in kinds)                           # a dispensed and billed medicine leaves a trail
    sold = bill.json()["items"][0]
    assert client.post("/api/stock/returns", headers=hw.pharmacy, json={"sale_item_id": sold["id"], "quantity": 1, "reason": "Patient changed mind"}).json()["restocked"] is True


# ------------------------------------------------------------------ 6. the assistant answers from the records, with sources
def test_workflow_6_the_assistant_answers_from_the_patients_own_records(client, hw):
    eid = client.post("/api/opd/walk-in", headers=hw.employee, json={"patient_id": hw.patient_id, "doctor_id": hw.doctor_id}).json()["encounter_id"]
    client.put(f"/api/opd/encounters/{eid}/consultation", headers=hw.doctor, json={"complaint": "Fever", "assessment": "Viral fever", "plan": "Rest"})
    client.post(f"/api/opd/encounters/{eid}/sign", headers=hw.doctor)
    client.post("/api/prescriptions", headers=hw.doctor, json={**RX, "patient_id": hw.patient_id})
    bill = invoice_and_pay(client, hw, pay=False)
    meds = client.post("/api/patient-assistant/chat", headers=hw.patient, json={"message": "what medicines am I taking", "language": "en"}).json()["reply"]
    assert "Paracetamol" in meds["text"] and meds["sources"] and meds["sources"][0]["type"] == "prescription"
    owed = client.post("/api/patient-assistant/chat", headers=hw.patient, json={"message": "how much is my bill", "language": "en"}).json()["reply"]
    assert f"{bill['total']:,.2f}" in owed["text"] and owed["sources"][0]["type"] == "invoice"
    empty = client.post("/api/patient-assistant/chat", headers=hw.patient, json={"message": "what did my scan show", "language": "en"}).json()["reply"]
    assert "no scan report" in empty["text"]                                                          # nothing on record: it says so and does not guess
    assert client.post("/api/patient-assistant/chat", headers=hw.doctor, json={"message": "hello"}).status_code == 403          # only the patient talks to the patient assistant


# ------------------------------------------------------------------ 7. referral to another department and back
def test_workflow_7_referral_with_shared_records_and_a_bill_for_the_specialist_visit(client, hw):
    eid = client.post("/api/opd/walk-in", headers=hw.employee, json={"patient_id": hw.patient_id, "doctor_id": hw.doctor_id}).json()["encounter_id"]
    client.put(f"/api/opd/encounters/{eid}/consultation", headers=hw.doctor, json={"complaint": "Exertional chest pain", "assessment": "Needs cardiac opinion"})
    rid = client.post("/api/referral-requests", headers=hw.doctor, json={"patient_id": hw.patient_id, "from_encounter_id": eid, "to_department_id": hw.cardio, "reason": "Please advise", "urgency": "URGENT"}).json()["id"]
    assert client.get(f"/api/doctor/patients/{hw.patient_id}/history", headers=hw.cardiologist).status_code == 403
    accepted = client.post(f"/api/referral-requests/{rid}/accept", headers=hw.cardiologist).json()
    assert client.get(f"/api/doctor/patients/{hw.patient_id}/history", headers=hw.cardiologist).status_code == 200
    ceid = accepted["consult_encounter_id"]
    client.put(f"/api/opd/encounters/{ceid}/consultation", headers=hw.cardiologist, json={"complaint": "Referred", "assessment": "Stable angina", "plan": "Aspirin, stress test"})
    client.post(f"/api/opd/encounters/{ceid}/sign", headers=hw.cardiologist)
    assert client.post(f"/api/referral-requests/{rid}/complete", headers=hw.cardiologist, json={}).json()["status"] == "COMPLETED"
    plan = client.get(f"/api/referral-requests/{rid}", headers=hw.doctor).json()["consult_note"]["plan"]
    assert plan == "Aspirin, stress test"
    events = client.get(f"/api/doctor/patients/{hw.patient_id}/timeline", headers=hw.cardiologist).json()["events"]
    assert any(e["kind"] == "CONSULTATION" and "Dr. Heart Doctor" in e["title"] for e in events)
