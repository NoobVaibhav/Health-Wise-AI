"""The complete hospital workflow, exactly as described in the project brief:

employee uploads -> real analysis -> doctor reviews -> note + recommendation + prescription
-> patient sees everything -> pharmacy dispenses -> patient sees dispensing status."""
from tests import sample_data as sd
from tests.conftest import future, login, upload

RX_BODY = {
    "clinical_indication": "Follow-up of report values",
    "items": [
        {"medicine_name": "Medicine A", "dosage": "500 mg", "frequency": "Twice daily", "duration": "5 days",
         "quantity": 10, "instructions": "After food"},
        {"medicine_name": "Medicine B", "dosage": "10 mg", "frequency": "Once daily", "duration": "5 days",
         "quantity": 5},
    ],
}


def test_complete_hospital_workflow(client, world):
    # 1. Employee uploads Rahul's report. The backend really reads the PDF.
    response = upload(client, world.employee, world.patient_id, "Rahul_July.pdf", sd.lines_to_pdf(sd.REPORT_A_LINES))
    assert response.status_code == 201, response.text
    report = response.json()
    report_id = report["id"]
    assert report["display_status"] == "WAITING_FOR_DOCTOR" and report["parameter_count"] == 6
    assert report["warnings"] == [] and report["processing_method"] == "pdf_text"
    # the employee never sees clinical values
    assert report["analysis_visible"] is False and report["parameters"] == []

    # 2. The patient can see that a report exists, but no analysis yet (a doctor must review first)
    patient_view = client.get(f"/api/reports/{report_id}", headers=world.patient).json()
    assert patient_view["display_status"] == "WAITING_FOR_DOCTOR" and patient_view["parameters"] == []
    assert client.get(f"/api/reports/{report_id}/file", headers=world.patient).status_code == 403

    # 3. The doctor sees the report waiting, with the AI analysis built from the REAL values
    dash = client.get("/api/doctor/dashboard", headers=world.doctor).json()
    assert dash["reports_waiting_count"] == 1 and dash["my_patients_count"] == 1
    doctor_view = client.get(f"/api/reports/{report_id}", headers=world.doctor).json()
    by_name = {p["normalized_name"]: p for p in doctor_view["parameters"]}
    assert (by_name["HbA1c"]["value"], by_name["HbA1c"]["status"]) == (7.2, "ABOVE_RANGE")
    assert (by_name["LDL"]["value"], by_name["LDL"]["status"]) == (148, "ABOVE_RANGE")
    assert (by_name["Vitamin D"]["value"], by_name["Vitamin D"]["status"]) == (17, "BELOW_RANGE")
    assert "blood glucose" in by_name["HbA1c"]["ai_explanation"]["simple"].lower()
    assert "diabetes" not in str(doctor_view).lower()                  # the system never names a disease
    assert client.get(f"/api/reports/{report_id}/file", headers=world.doctor).status_code == 200

    # 4. Doctor reviews: a comment is required when modifying the AI analysis
    bad = client.put(f"/api/doctor/reports/{report_id}/review", headers=world.doctor, json={"decision": "MODIFIED"})
    assert bad.status_code == 422
    reviewed = client.put(f"/api/doctor/reports/{report_id}/review", headers=world.doctor,
                          json={"decision": "APPROVED", "comment": "Values match the report."})
    assert reviewed.status_code == 200 and reviewed.json()["display_status"] == "DOCTOR_REVIEWED"
    assert reviewed.json()["reviewed_by_name"] == "Dr. Anjali Sharma"

    # 5. Doctor adds a note, a recommendation and a prescription
    note = client.post("/api/doctor/notes", headers=world.doctor, json={
        "patient_id": world.patient_id, "report_id": report_id, "priority": "FOLLOW_UP_REQUIRED",
        "note": "Please discuss these results during consultation and follow the recommended follow-up plan."})
    assert note.status_code == 201 and note.json()["label"] == "Doctor's Note"
    rec = client.post("/api/doctor/recommendations", headers=world.doctor, json={
        "patient_id": world.patient_id, "report_id": report_id, "title": "Follow-up monitoring",
        "recommendation": "Follow the prescribed follow-up schedule.", "follow_up_date": "2030-01-15"})
    assert rec.status_code == 201
    rx = client.post("/api/prescriptions", headers=world.doctor, json={**RX_BODY, "patient_id": world.patient_id,
                                                                       "report_id": report_id})
    assert rx.status_code == 201, rx.text
    rx_id, rx_code = rx.json()["id"], rx.json()["code"]
    assert rx.json()["status"] == "ACTIVE" and rx_code.startswith("RX-")

    # 6. Patient logs in and sees everything, clearly labelled
    dash = client.get("/api/patient/dashboard", headers=world.patient).json()
    assert dash["latest_report"]["display_status"] == "DOCTOR_REVIEWED"
    assert dash["doctor_notes"][0]["label"] == "Doctor's Note"
    assert dash["recommendations"][0]["title"] == "Follow-up monitoring"
    assert dash["active_prescriptions"][0]["code"] == rx_code
    full = client.get(f"/api/reports/{report_id}", headers=world.patient).json()
    assert full["analysis_visible"] and len(full["parameters"]) == 6
    assert client.get(f"/api/reports/{report_id}/file", headers=world.patient).status_code == 200

    # 7. Pharmacy sees the valid prescription and dispenses it step by step
    found = client.get("/api/pharmacy/prescriptions?q=Rahul", headers=world.pharmacy).json()
    assert [r["code"] for r in found] == [rx_code]
    opened = client.get(f"/api/prescriptions/{rx_id}", headers=world.pharmacy)  # pharmacy opens it (audited)
    assert opened.status_code == 200 and opened.json()["doctor_name"] == "Dr. Anjali Sharma"
    items = {i["medicine_name"]: i for i in found[0]["items"]}
    a, b = items["Medicine A"]["id"], items["Medicine B"]["id"]
    partial = client.post("/api/pharmacy/dispense", headers=world.pharmacy, json={"prescription_item_id": a, "quantity": 4})
    assert partial.status_code == 200 and partial.json()["status"] == "PARTIALLY_DISPENSED"
    over = client.post("/api/pharmacy/dispense", headers=world.pharmacy, json={"prescription_item_id": a, "quantity": 7})
    assert over.status_code == 409 and "6 remaining" in over.json()["detail"]
    client.post("/api/pharmacy/dispense", headers=world.pharmacy, json={"prescription_item_id": a, "quantity": 6})
    done = client.post("/api/pharmacy/dispense", headers=world.pharmacy, json={"prescription_item_id": b, "quantity": 5})
    assert done.json()["status"] == "DISPENSED"
    again = client.post("/api/pharmacy/dispense", headers=world.pharmacy, json={"prescription_item_id": b, "quantity": 1})
    assert again.status_code == 409

    # 8. Patient sees the dispensing status
    mine = client.get("/api/patient/prescriptions", headers=world.patient).json()[0]
    assert mine["status"] == "DISPENSED"
    assert {i["dispense_status"] for i in mine["items"]} == {"DISPENSED"}
    assert all(i["remaining_quantity"] == 0 for i in mine["items"])

    # 9. The timeline is generated from the database and shows each step
    timeline = client.get("/api/patient/history", headers=world.patient).json()["timeline"]
    kinds = [e["type"] for e in timeline]
    for expected in ("REPORT_UPLOADED", "AI_ANALYSIS", "DOCTOR_REVIEW", "DOCTOR_NOTE", "RECOMMENDATION",
                     "PRESCRIPTION", "DISPENSING"):
        assert expected in kinds, expected
    assert timeline == sorted(timeline, key=lambda e: e["timestamp"], reverse=True)

    # 10. Everything important was written to the audit log
    logs = client.get("/api/admin/audit-logs?limit=200", headers=world.admin).json()
    actions = {entry["action"] for entry in logs}
    assert {"LOGIN", "USER_CREATED", "PATIENT_CREATED", "REPORT_UPLOADED", "REPORT_ANALYZED", "REPORT_REVIEWED",
            "NOTE_ADDED", "RECOMMENDATION_ADDED", "PRESCRIPTION_CREATED", "PRESCRIPTION_VIEWED",
            "MEDICINE_DISPENSED", "REPORT_FILE_VIEWED"} <= actions

    # 11. The pharmacy can never change a prescription
    assert client.put(f"/api/prescriptions/{rx_id}/cancel", headers=world.pharmacy).status_code == 403
    assert client.post("/api/prescriptions", headers=world.pharmacy,
                       json={**RX_BODY, "patient_id": world.patient_id}).status_code == 403
    assert client.post("/api/prescriptions", headers=world.patient,
                       json={**RX_BODY, "patient_id": world.patient_id}).status_code == 403


def test_failed_or_invalid_upload_is_not_saved(client, world):
    bad = upload(client, world.employee, world.patient_id, "invoice.txt", sd.lines_to_text(sd.NOT_A_REPORT_LINES))
    assert bad.status_code == 422 and "recognizable laboratory" in bad.json()["detail"]
    assert upload(client, world.employee, world.patient_id, "x.exe", b"MZ").status_code == 415
    assert client.get("/api/reports", headers=world.employee).json() == []
    assert client.get("/api/reports", headers=world.doctor).json() == []


def test_scanned_pdf_without_ocr_gives_clear_error(client, world, monkeypatch):
    from app.services import ocr_service
    monkeypatch.setattr(ocr_service, "ocr_is_available", lambda: False)
    response = upload(client, world.employee, world.patient_id, "scan.pdf", sd.blank_scanned_pdf())
    assert response.status_code == 503 and "OCR is not configured" in response.json()["detail"]
    assert client.get("/api/reports", headers=world.employee).json() == []


def test_name_mismatch_warning_and_report_values_come_from_each_file(client, world):
    other = upload(client, world.employee, world.patient_id, "wrong.txt", sd.lines_to_text(sd.REPORT_C_LINES))
    assert other.status_code == 201
    assert any("Sunita Kulkarni" in w for w in other.json()["warnings"])
    # a different file gives different values (never the same demo result)
    doc = client.get(f"/api/reports/{other.json()['id']}", headers=world.doctor).json()
    names = {p["normalized_name"] for p in doc["parameters"]}
    assert "TSH" in names and "HbA1c" not in names


def test_doctor_must_be_chosen_when_patient_has_none(client, world):
    created = client.post("/api/patients", headers=world.employee, json={
        "email": "nodoc@example.com", "full_name": "No Doctor Yet"}).json()
    pid = created["patient"]["id"]
    assert created["temporary_password"]  # login credentials generated for the patient
    pdf = sd.lines_to_pdf(sd.REPORT_A_LINES)
    assert upload(client, world.employee, pid, "a.pdf", pdf).status_code == 422
    ok = upload(client, world.employee, pid, "a.pdf", pdf, doctor_id=world.other_doctor_id)
    assert ok.status_code == 201 and ok.json()["assigned_doctor_name"] == "Dr. Other Doctor"
    assert client.get("/api/doctor/dashboard", headers=world.other_doctor).json()["reports_waiting_count"] == 1
    assert client.get("/api/doctor/dashboard", headers=world.doctor).json()["reports_waiting_count"] == 0


def test_doctor_can_upload_for_authorized_patient(client, world):
    ok = upload(client, world.doctor, world.patient_id, "d.pdf", sd.lines_to_pdf(sd.REPORT_B_LINES))
    assert ok.status_code == 201 and ok.json()["analysis_visible"] is True
    assert upload(client, world.other_doctor, world.patient_id, "d.pdf", sd.lines_to_pdf(sd.REPORT_B_LINES)).status_code == 403


def test_appointment_flow(client, world):
    created = client.post("/api/appointments", headers=world.employee, json={
        "patient_id": world.patient_id, "doctor_id": world.doctor_id, "scheduled_at": future(24),
        "reason": "Report discussion"})
    assert created.status_code == 201, created.text
    appt = created.json()
    assert appt["status"] == "SCHEDULED" and appt["department_name"] == "General Medicine"
    clash = client.post("/api/appointments", headers=world.employee, json={
        "patient_id": world.patient_id, "doctor_id": world.doctor_id, "scheduled_at": appt["scheduled_at"]})
    assert clash.status_code == 409
    past = client.post("/api/appointments", headers=world.employee, json={
        "patient_id": world.patient_id, "doctor_id": world.doctor_id, "scheduled_at": future(-48)})
    assert past.status_code == 422

    assert client.get("/api/appointments", headers=world.doctor).json()[0]["id"] == appt["id"]
    assert client.get("/api/appointments", headers=world.other_doctor).json() == []
    assert client.get("/api/patient/dashboard", headers=world.patient).json()["next_appointment"]["id"] == appt["id"]

    # status updates: doctor confirms; patient may only cancel their own
    assert client.put(f"/api/appointments/{appt['id']}", headers=world.doctor,
                      json={"status": "CONFIRMED"}).json()["status"] == "CONFIRMED"
    assert client.put(f"/api/appointments/{appt['id']}", headers=world.patient,
                      json={"status": "COMPLETED"}).status_code == 403
    assert client.put(f"/api/appointments/{appt['id']}", headers=world.other_doctor,
                      json={"status": "COMPLETED"}).status_code == 403
    assert client.put(f"/api/appointments/{appt['id']}", headers=world.patient,
                      json={"status": "CANCELLED"}).json()["status"] == "CANCELLED"
    # the doctor is authorized for the patient because of the appointment too
    other_patient = client.post("/api/patients", headers=world.employee, json={
        "email": "p2@example.com", "full_name": "Second Patient"}).json()["patient"]["id"]
    self_booked = client.post("/api/appointments", headers=login_patient(client, "p2@example.com"), json={
        "doctor_id": world.other_doctor_id, "scheduled_at": future(30)})
    assert self_booked.status_code == 201
    assert client.get(f"/api/doctor/patients/{other_patient}/history", headers=world.other_doctor).status_code == 200


def login_patient(client, email):
    """The second patient was created without a password, so reset it through the admin-free path: look it up."""
    from app.core.security import hash_password
    from app.database.connection import SessionLocal
    from app.database.models import User
    with SessionLocal() as db:
        user = db.query(User).filter_by(email=email).one()
        user.password_hash = hash_password("StrongPass123")
        user.must_change_password = False
        db.commit()
    return login(client, email)


def test_delete_report_rules_and_cleanup(client, world):
    import os
    first = upload(client, world.employee, world.patient_id, "wrong.pdf", sd.lines_to_pdf(sd.REPORT_A_LINES)).json()
    second = upload(client, world.employee, world.patient_id, "right.pdf", sd.lines_to_pdf(sd.REPORT_B_LINES)).json()
    # the patient and the administrator can never delete a report
    assert client.delete(f"/api/reports/{first['id']}", headers=world.patient).status_code == 403
    assert client.delete(f"/api/reports/{first['id']}", headers=world.admin).status_code == 403
    # the employee who uploaded it can delete it while it is waiting for the doctor
    stored = client.get("/api/reports", headers=world.doctor).json()
    assert len(stored) == 2
    done = client.delete(f"/api/reports/{first['id']}", headers=world.employee)
    assert done.status_code == 200 and done.json()["filename"] == "wrong.pdf"
    assert client.get(f"/api/reports/{first['id']}", headers=world.doctor).status_code == 404
    assert [r["id"] for r in client.get("/api/reports", headers=world.doctor).json()] == [second["id"]]
    # once the doctor has reviewed a report, an employee can no longer delete it, but the doctor can
    client.put(f"/api/doctor/reports/{second['id']}/review", headers=world.doctor, json={"decision": "APPROVED"})
    assert client.delete(f"/api/reports/{second['id']}", headers=world.employee).status_code == 403
    note = client.post("/api/doctor/notes", headers=world.doctor, json={
        "patient_id": world.patient_id, "report_id": second["id"], "priority": "NORMAL", "note": "Please discuss the results at the visit."})
    assert note.status_code == 201
    assert client.delete(f"/api/reports/{second['id']}", headers=world.doctor).status_code == 200
    assert client.get("/api/reports", headers=world.doctor).json() == []
    # the note written about the report stays in the patient's history
    assert len(client.get("/api/doctor/notes", headers=world.doctor).json()) == 1
    # the deletions are in the audit log, with the file names
    logs = client.get("/api/admin/audit-logs?action=REPORT_DELETED", headers=world.admin).json()
    assert {l["details"].split(" (")[0] for l in logs} == {"wrong.pdf", "right.pdf"}


def test_doctor_pick_lists_for_medicines_and_tests(client, world):
    meds = client.get("/api/catalog/medicines", headers=world.doctor)
    assert meds.status_code == 200
    names = [m["name"] for m in meds.json()]
    assert "Paracetamol 500 mg tablet" in names and all("in_stock" in m for m in meds.json())
    tests = client.get("/api/catalog/tests", headers=world.doctor)
    assert tests.status_code == 200
    test_names = [t["name"] for t in tests.json()]
    assert "HbA1c (glycated haemoglobin)" in test_names and "ECG" in test_names
    # only doctors may use the pick-lists
    assert client.get("/api/catalog/medicines", headers=world.employee).status_code == 403
    assert client.get("/api/catalog/medicines", headers=world.pharmacy).status_code == 200    # names only, for adding stock
    assert client.get("/api/catalog/tests", headers=world.pharmacy).status_code == 403          # the pharmacy never sees tests
    assert client.get("/api/catalog/tests", headers=world.patient).status_code == 403


def test_tests_advised_reach_lab_and_employee_but_never_the_pharmacy(client, world):
    # admin creates a laboratory staff account
    created = client.post("/api/admin/lab-staff", headers=world.admin, json={
        "email": "lab@hospital.example.com", "full_name": "Lab Tech", "password": "StrongPass123", "lab_name": "City Lab"})
    assert created.status_code == 201, created.text
    assert created.json()["user"]["role"] == "LAB"
    lab = login(client, "lab@hospital.example.com")

    # the doctor prescribes a medicine and advises two tests
    rx = client.post("/api/prescriptions", headers=world.doctor, json={
        "patient_id": world.patient_id, "notes": "Take rest",
        "items": [{"medicine_name": "Paracetamol 500 mg tablet", "dosage": "1 tablet", "frequency": "Twice daily",
                   "duration": "5 days", "quantity": 10}],
        "tests": ["2D Echo", "Lipid profile", "2d echo"]})
    assert rx.status_code == 201, rx.text
    assert rx.json()["tests"] == ["2D Echo", "Lipid profile"]       # duplicates removed
    rx_id = rx.json()["id"]

    # lab and employee see the order; searching by test name works
    for who in (lab, world.employee):
        orders = client.get("/api/lab/test-orders", headers=who).json()
        assert [o["id"] for o in orders] == [rx_id] and orders[0]["tests"] == ["2D Echo", "Lipid profile"]
        assert len(client.get("/api/lab/test-orders", params={"q": "echo"}, headers=who).json()) == 1
        assert client.get("/api/lab/test-orders", params={"q": "xray"}, headers=who).json() == []

    # the pharmacy gets the medicine but no tests, in every endpoint it can use
    for response in (client.get("/api/pharmacy/prescriptions", headers=world.pharmacy),
                     client.get("/api/prescriptions", headers=world.pharmacy)):
        assert response.status_code == 200
        rows = response.json()
        assert rows and all(r["tests"] == [] for r in rows)
        assert "2D Echo" not in response.text
    assert client.get(f"/api/prescriptions/{rx_id}", headers=world.pharmacy).json()["tests"] == []
    # the pharmacy, the patient and the doctor-only catalog are not allowed to use the lab list
    assert client.get("/api/lab/test-orders", headers=world.pharmacy).status_code == 403
    assert client.get("/api/lab/test-orders", headers=world.patient).status_code == 403
    # the lab cannot see medicine data
    assert client.get("/api/pharmacy/prescriptions", headers=lab).status_code == 403
    assert client.get("/api/prescriptions", headers=lab).status_code == 403
    # the doctor still sees the tests
    assert client.get(f"/api/prescriptions/{rx_id}", headers=world.doctor).json()["tests"] == ["2D Echo", "Lipid profile"]


def test_patient_says_what_is_happening_when_booking(client, world):
    told = {"patient_id": world.patient_id, "doctor_id": world.doctor_id, "scheduled_at": future(24), "reason": "Giddiness and fainting",
            "symptoms": ["Giddiness", "Sweating"], "duration": "1 day", "details": "Two episodes last night, each lasted about ten minutes."}
    made = client.post("/api/appointments", headers=world.patient, json=told)
    assert made.status_code == 201, made.text
    seen_by_patient = made.json()
    assert seen_by_patient["symptoms"] == ["Giddiness", "Sweating"] and seen_by_patient["duration"] == "1 day" and "ten minutes" in seen_by_patient["details"]
    # the doctor reads it; the front desk and the administrator see only the short reason
    doctor_view = client.get("/api/appointments", headers=world.doctor).json()[0]
    assert doctor_view["symptoms"] == ["Giddiness", "Sweating"] and doctor_view["details"]
    for who in (world.employee, world.admin):
        row = client.get("/api/appointments", headers=who).json()[0]
        assert row["reason"] == "Giddiness and fainting" and row["symptoms"] == [] and row["details"] is None and row["duration"] is None
    # the dashboards follow the same rule
    assert client.get("/api/patient/dashboard", headers=world.patient).json()["next_appointment"]["details"]
    # the doctor starts the history from it
    view = client.get(f"/api/health-history/patient/{world.patient_id}", headers=world.doctor).json()
    assert view["appointment_problem"]["symptoms"] == ["Giddiness", "Sweating"] and view["appointment_problem"]["duration"] == "1 day"
    # too long or too many symptoms are refused
    assert client.post("/api/appointments", headers=world.patient, json={**told, "scheduled_at": future(30), "details": "x" * 1001}).status_code == 422


def test_a_prescription_carries_what_the_printed_sheet_needs_and_the_pharmacy_sees_no_more_than_before(client, world, monkeypatch):
    from app.core.config import get_settings
    monkeypatch.setattr(get_settings(), "hospital_name", "Test Hospital")
    monkeypatch.setattr(get_settings(), "hospital_phone", "")
    client.put(f"/api/patients/{world.patient_id}", headers=world.employee, json={"phone": "9876543210", "gender": "male", "date_of_birth": "1990-05-14"})
    rx = client.post("/api/prescriptions", headers=world.doctor, json={"patient_id": world.patient_id, "clinical_indication": "Cough", "tests": ["Chest X-ray"], "items": [
        {"medicine_name": "Tab. Test", "dosage": "5 mg", "frequency": "Twice a day", "duration": "5 days", "quantity": 10}]}).json()
    mine = client.get(f"/api/prescriptions/{rx['id']}", headers=world.patient).json()
    assert mine["hospital"]["name"] == "Test Hospital" and mine["hospital"]["phone"] is None and mine["tests"] == ["Chest X-ray"]
    assert mine["patient_info"]["phone"] == "9876543210" and mine["patient_info"]["gender"] == "male" and mine["patient_info"]["age"] >= 30
    assert mine["doctor_info"]["specialization"] == "Physician"
    shop = client.get(f"/api/prescriptions/{rx['id']}", headers=world.pharmacy).json()
    assert shop["tests"] == [] and shop["patient_info"]["phone"] is None and shop["patient_info"]["allergies"] is None and shop["patient_info"]["gender"] == "male"
    listed = client.get("/api/pharmacy/prescriptions", headers=world.pharmacy).json()[0]
    assert listed["tests"] == [] and listed["patient_info"]["phone"] is None
