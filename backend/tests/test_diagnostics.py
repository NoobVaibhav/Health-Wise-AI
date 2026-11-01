"""Phase 4 diagnostics: structured lab results with flags and critical values, pathologist approval, doctor then patient visibility, comparison with earlier results,
radiology order -> scan -> report -> radiologist approval, and who may do what."""
import pytest

from app.database.connection import SessionLocal
from app.database.models import ClinicalAlert, LabTestOrder
from tests.conftest import PASSWORD, future, login


@pytest.fixture()
def dx(client, world):
    def staff(path, email, name, **extra):
        res = client.post(f"/api/admin/{path}", headers=world.admin, json={"email": email, "full_name": name, "password": PASSWORD, **extra})
        assert res.status_code == 201, res.text
        return login(client, email)

    world.tech = staff("lab-staff", "tech@hospital.example.com", "Tara Tech", lab_name="Main lab")
    world.tech2 = staff("lab-staff", "tech2@hospital.example.com", "Tina Tech", lab_name="Main lab")
    world.path = staff("lab-staff", "path@hospital.example.com", "Dr. Paul Path", lab_name="Main lab", staff_type="PATHOLOGIST")
    world.rtech = staff("radiology-staff", "rtech@hospital.example.com", "Rita Rad Tech")
    world.rad = staff("radiology-staff", "rad@hospital.example.com", "Dr. Ravi Radiologist", staff_type="RADIOLOGIST")
    kft = client.post("/api/diagnostics/tests", headers=world.admin, json={"kind": "LAB", "name": "Serum Electrolytes", "category": "BIOCHEMISTRY", "sample_type": "Blood"}).json()["id"]
    world.potassium = client.post(f"/api/diagnostics/tests/{kft}/analytes", headers=world.admin,
                                  json={"name": "Potassium", "unit": "mmol/L", "method": "ISE", "ref_low": 3.5, "ref_high": 5.0, "critical_low": 2.8, "critical_high": 6.0}).json()["id"]
    world.sodium = client.post(f"/api/diagnostics/tests/{kft}/analytes", headers=world.admin, json={"name": "Sodium", "unit": "mmol/L", "ref_low": 135, "ref_high": 145}).json()["id"]
    client.post("/api/diagnostics/tests", headers=world.admin, json={"kind": "RADIOLOGY", "name": "Chest X-ray", "category": "XRAY"})
    return world


def walk_in(client, w):
    if getattr(w, "enc", None):
        return w.enc                                                                                         # one visit, several orders
    res = client.post("/api/opd/walk-in", headers=w.employee, json={"patient_id": w.patient_id, "doctor_id": w.doctor_id})
    assert res.status_code == 201, res.text
    w.enc = res.json()["encounter_id"]
    return w.enc


def order(client, w, encounter, kind, text, priority="ROUTINE"):
    res = client.post(f"/api/opd/encounters/{encounter}/orders", headers=w.doctor, json={"kind": kind, "text": text, "priority": priority})
    assert res.status_code == 201, res.text


def lab_test(client, w, text="Serum Electrolytes", encounter=None):
    encounter = encounter or walk_in(client, w)
    order(client, w, encounter, "LAB", text)
    rows = client.get("/api/lab/worklist?status_filter=OPEN", headers=w.tech).json()["tests"]
    return next(r for r in rows if r["test_name"] == text and not r["status"] == "COMPLETED")["id"]


def to_sample(client, w, tid):
    assert client.post(f"/api/lab/tests/{tid}/status", headers=w.tech, json={"status": "SAMPLE_COLLECTED"}).status_code == 200
    return tid


def enter(client, w, tid, k, na=140, submit=True, who=None):
    return client.post(f"/api/lab/tests/{tid}/results", headers=who or w.tech, json={"submit": submit, "results": [
        {"analyte_id": w.potassium, "value": str(k)}, {"analyte_id": w.sodium, "value": str(na)}]})


# ------------------------------------------------------------------ laboratory
def test_encounter_order_reaches_the_lab_and_values_are_flagged_from_the_catalogue(client, dx):
    tid = to_sample(client, dx, lab_test(client, dx))
    res = enter(client, dx, tid, 5.4, 130, submit=False)
    assert res.status_code == 200, res.text
    rows = {r["name"]: r for r in res.json()["results"]}
    assert rows["Potassium"]["flag"] == "HIGH" and rows["Potassium"]["unit"] == "mmol/L" and rows["Potassium"]["method"] == "ISE" and rows["Potassium"]["ref_high"] == 5.0
    assert rows["Sodium"]["flag"] == "LOW" and res.json()["result_status"] == "DRAFT"


def test_a_critical_value_alerts_when_sent_on_and_the_doctor_sees_nothing_until_approval(client, dx):
    tid = to_sample(client, dx, lab_test(client, dx))
    res = enter(client, dx, tid, 6.8)
    assert res.json()["has_critical"] is True and res.json()["result_status"] == "PENDING_APPROVAL"
    with SessionLocal() as db:
        alerts = db.query(ClinicalAlert).filter(ClinicalAlert.level == "CRITICAL").all()
        assert len(alerts) == 1 and "Potassium 6.8" in alerts[0].message
    seen = client.get(f"/api/lab/patient/{dx.patient_id}/tests", headers=dx.doctor).json()
    assert seen[0]["results"] == [] and seen[0]["result_status"] == "PENDING_APPROVAL"


def test_no_range_means_unrated_never_a_guess(client, dx):
    tid = to_sample(client, dx, lab_test(client, dx, "Some Unlisted Test"))
    res = client.post(f"/api/lab/tests/{tid}/results", headers=dx.tech, json={"results": [{"name": "Widget level", "value": "12", "unit": "u"}], "submit": False})
    assert res.status_code == 200 and res.json()["results"][0]["flag"] == "UNRATED"


def test_only_a_pathologist_approves_and_not_the_person_who_entered_it(client, dx):
    tid = to_sample(client, dx, lab_test(client, dx))
    enter(client, dx, tid, 4.2)
    for who in (dx.tech, dx.tech2, dx.doctor, dx.employee, dx.patient, dx.rad):
        assert client.post(f"/api/lab/tests/{tid}/approve", headers=who, json={}).status_code == 403
    assert client.post(f"/api/lab/tests/{tid}/return", headers=dx.path, json={"comment": "x"}).status_code == 422
    assert client.post(f"/api/lab/tests/{tid}/return", headers=dx.path, json={"comment": "Please repeat sodium"}).json()["result_status"] == "DRAFT"
    assert enter(client, dx, tid, 4.2).status_code == 200
    ok = client.post(f"/api/lab/tests/{tid}/approve", headers=dx.path, json={"note": "Checked"})
    assert ok.status_code == 200 and ok.json()["result_status"] == "APPROVED" and ok.json()["status"] == "COMPLETED"
    assert client.post(f"/api/lab/tests/{tid}/approve", headers=dx.path, json={}).status_code == 409
    assert enter(client, dx, tid, 9).status_code == 409                                                     # an approved result is never edited


def test_the_doctor_sees_it_after_approval_and_the_patient_only_after_the_doctor(client, dx):
    tid = to_sample(client, dx, lab_test(client, dx))
    enter(client, dx, tid, 4.2)
    assert client.get("/api/lab/my-tests", headers=dx.patient).json()[0]["results"] == []
    client.post(f"/api/lab/tests/{tid}/approve", headers=dx.path, json={})
    doctor_view = client.get(f"/api/lab/patient/{dx.patient_id}/tests", headers=dx.doctor).json()[0]
    assert {r["name"] for r in doctor_view["results"]} == {"Potassium", "Sodium"}
    assert client.get("/api/lab/my-tests", headers=dx.patient).json()[0]["results"] == []                    # not yet: the doctor has not seen it
    assert client.post(f"/api/lab/tests/{tid}/seen", headers=dx.other_doctor).status_code == 403            # not this doctor's patient
    assert client.post(f"/api/lab/tests/{tid}/seen", headers=dx.doctor).status_code == 200
    mine = client.get("/api/lab/my-tests", headers=dx.patient).json()[0]
    assert {r["name"] for r in mine["results"]} == {"Potassium", "Sodium"} and mine["patient_message"] == "Result reviewed by your doctor"


def test_comparison_uses_only_the_same_value_in_the_same_unit(client, dx):
    first = to_sample(client, dx, lab_test(client, dx))
    enter(client, dx, first, 4.0)
    client.post(f"/api/lab/tests/{first}/approve", headers=dx.path, json={})
    second = to_sample(client, dx, lab_test(client, dx))
    enter(client, dx, second, 4.6)
    client.post(f"/api/lab/tests/{second}/approve", headers=dx.path, json={})
    rows = {r["name"]: r for r in client.get(f"/api/lab/patient/{dx.patient_id}/tests", headers=dx.doctor).json()[0]["results"]}
    assert rows["Potassium"]["previous"]["value"] == "4.0" and rows["Potassium"]["previous"]["change"] == "up"
    older = client.get(f"/api/lab/patient/{dx.patient_id}/tests", headers=dx.doctor).json()[1]["results"]
    assert all(r["previous"] is None for r in older)


def test_validation_of_results(client, dx):
    tid = lab_test(client, dx)
    assert enter(client, dx, tid, 4.2).status_code == 409                                                    # sample not taken yet
    to_sample(client, dx, tid)
    bad = client.post(f"/api/lab/tests/{tid}/results", headers=dx.tech, json={"submit": True, "results": [{"analyte_id": dx.potassium, "value": "high"}]})
    assert bad.status_code == 422
    assert client.post(f"/api/lab/tests/{tid}/results", headers=dx.tech, json={"submit": True, "results": []}).status_code == 422
    assert client.post(f"/api/lab/tests/{tid}/results", headers=dx.tech, json={"submit": True, "results": [{"analyte_id": 99999, "value": "1"}]}).status_code == 422
    for who in (dx.doctor, dx.employee, dx.patient, dx.pharmacy, dx.rtech):
        assert client.post(f"/api/lab/tests/{tid}/results", headers=who, json={"submit": False, "results": [{"analyte_id": dx.potassium, "value": "4"}]}).status_code == 403


def test_catalogue_limits_must_be_in_order_and_only_admin_changes_it(client, dx):
    kft = client.get("/api/diagnostics/tests?kind=LAB", headers=dx.tech).json()[0]["id"]
    assert client.post(f"/api/diagnostics/tests/{kft}/analytes", headers=dx.admin, json={"name": "Urea", "ref_low": 50, "ref_high": 10}).status_code == 422
    assert client.post(f"/api/diagnostics/tests/{kft}/analytes", headers=dx.doctor, json={"name": "Urea"}).status_code == 403
    assert client.post("/api/diagnostics/tests", headers=dx.admin, json={"kind": "LAB", "name": "Odd", "category": "XRAY"}).status_code == 422


# ------------------------------------------------------------------ radiology
def study(client, w, text="Chest X-ray", priority="ROUTINE"):
    order(client, w, walk_in(client, w), "RADIOLOGY", text, priority)
    return next(s for s in client.get("/api/radiology/worklist", headers=w.rtech).json()["studies"] if s["study"] == text and s["status"] != "APPROVED")["id"]


def test_radiology_flow_from_order_to_patient(client, dx):
    sid = study(client, dx)
    assert client.get("/api/radiology/orders/%d" % sid, headers=dx.rtech).json()["modality"] == "XRAY"
    assert client.post(f"/api/radiology/orders/{sid}/report", headers=dx.rad, json={"findings": "Clear lungs.", "impression": "Normal"}).status_code == 409     # scan not done
    assert client.post(f"/api/radiology/orders/{sid}/schedule", headers=dx.rtech, json={"scheduled_at": future(2)}).json()["status"] == "SCHEDULED"
    assert client.post(f"/api/radiology/orders/{sid}/start", headers=dx.rtech).json()["status"] == "IN_PROGRESS"
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 100
    added = client.post(f"/api/radiology/orders/{sid}/files", headers=dx.rtech, files={"file": ("cxr.png", png, "image/png")})
    assert added.status_code == 201, added.text
    assert client.post(f"/api/radiology/orders/{sid}/files", headers=dx.rtech, files={"file": ("x.png", b"not an image", "image/png")}).status_code in (400, 415, 422)
    assert client.post(f"/api/radiology/orders/{sid}/report", headers=dx.rtech, json={"findings": "Clear lungs.", "impression": "Normal"}).status_code == 403          # a technician does not report
    assert client.post(f"/api/radiology/orders/{sid}/report", headers=dx.rad, json={"findings": "Clear lungs.", "impression": "Normal chest"}).json()["status"] == "REPORTED"
    assert client.get(f"/api/radiology/patient/{dx.patient_id}/studies", headers=dx.doctor).json()[0]["report"] is None                      # not approved yet
    assert client.post(f"/api/radiology/orders/{sid}/approve", headers=dx.rtech).status_code == 403
    assert client.post(f"/api/radiology/orders/{sid}/approve", headers=dx.rad).json()["status"] == "APPROVED"
    assert client.post(f"/api/radiology/orders/{sid}/report", headers=dx.rad, json={"findings": "Changed", "impression": "Changed"}).status_code == 409
    fid = added.json()["id"]
    doctor_view = client.get(f"/api/radiology/patient/{dx.patient_id}/studies", headers=dx.doctor).json()[0]
    assert doctor_view["report"]["impression"] == "Normal chest" and client.get(f"/api/radiology/files/{fid}", headers=dx.doctor).status_code == 200
    assert client.get("/api/radiology/my-studies", headers=dx.patient).json()[0]["report"] is None
    assert client.get(f"/api/radiology/files/{fid}", headers=dx.patient).status_code == 403
    assert client.post(f"/api/radiology/orders/{sid}/seen", headers=dx.doctor).status_code == 200
    assert client.get("/api/radiology/my-studies", headers=dx.patient).json()[0]["report"]["impression"] == "Normal chest"
    assert client.get(f"/api/radiology/files/{fid}", headers=dx.patient).status_code == 200
    assert client.get(f"/api/radiology/files/{fid}", headers=dx.other_doctor).status_code == 403


def test_a_second_study_is_compared_with_the_earlier_approved_one(client, dx):
    def finish(sid, impression):
        client.post(f"/api/radiology/orders/{sid}/start", headers=dx.rtech)
        client.post(f"/api/radiology/orders/{sid}/report", headers=dx.rad, json={"findings": "Findings text", "impression": impression})
        client.post(f"/api/radiology/orders/{sid}/approve", headers=dx.rad)
    finish(study(client, dx), "Small right effusion")
    second = study(client, dx)
    finish(second, "Effusion resolved")
    prior = client.get(f"/api/radiology/orders/{second}", headers=dx.rtech).json()["previous_studies"]
    assert [p["impression"] for p in prior] == ["Small right effusion"]


def test_radiology_access_is_closed_to_other_roles(client, dx):
    sid = study(client, dx)
    for who in (dx.patient, dx.pharmacy, dx.tech, dx.doctor):
        assert client.get("/api/radiology/dashboard", headers=who).status_code == 403
        assert client.post(f"/api/radiology/orders/{sid}/start", headers=who).status_code == 403
    assert client.get("/api/radiology/dashboard", headers=dx.rtech).json()["open"] == 1
    assert client.get("/api/auth/me", headers=dx.rtech).json()["role"] == "RADIOLOGY"


def test_cancelling_the_order_cancels_open_lab_and_radiology_work(client, dx):
    enc = walk_in(client, dx)
    order(client, dx, enc, "LAB", "Serum Electrolytes")
    order(client, dx, enc, "RADIOLOGY", "Chest X-ray")
    client.get("/api/lab/worklist", headers=dx.tech)
    client.get("/api/radiology/worklist", headers=dx.rtech)
    ws = client.get(f"/api/opd/encounters/{enc}", headers=dx.doctor).json()
    for o in ws["orders"]:
        assert client.post(f"/api/opd/orders/{o['id']}/status", headers=dx.doctor, json={"status": "CANCELLED"}).status_code == 200
    assert client.get("/api/radiology/worklist?status_filter=CANCELLED", headers=dx.rtech).json()["studies"][0]["status"] == "CANCELLED"
    assert client.get("/api/lab/worklist?status_filter=CANCELLED", headers=dx.tech).json()["tests"][0]["status"] == "CANCELLED"


def test_an_old_database_with_a_required_prescription_column_is_rebuilt_once(client, world):
    from sqlalchemy import text
    from app.database.connection import engine
    from app.services import diagnostic_service
    with engine.begin() as c:
        c.execute(text("PRAGMA foreign_keys=OFF"))
        c.execute(text("DROP TABLE lab_results"))
        c.execute(text("DROP TABLE lab_test_orders"))
        c.execute(text("CREATE TABLE lab_test_orders (id INTEGER PRIMARY KEY, prescription_id INTEGER NOT NULL, patient_id INTEGER NOT NULL, doctor_id INTEGER NOT NULL, test_name VARCHAR(200) NOT NULL, "
                       "status VARCHAR(20) NOT NULL, urgent BOOLEAN, sample_type VARCHAR(40), sample_code VARCHAR(30), collected_at DATETIME, collected_by INTEGER, started_at DATETIME, completed_at DATETIME, "
                       "completed_by INTEGER, report_id INTEGER, note TEXT, rejection_reason TEXT, created_at DATETIME NOT NULL, updated_at DATETIME, updated_by INTEGER, clinical_order_id INTEGER, encounter_id INTEGER, "
                       "test_id INTEGER, assigned_to INTEGER, result_status VARCHAR(16), has_critical BOOLEAN, approved_by INTEGER, approved_at DATETIME, approval_note VARCHAR(500), doctor_seen_at DATETIME)"))
        c.execute(text("INSERT INTO lab_test_orders (id, prescription_id, patient_id, doctor_id, test_name, status, created_at, updated_at) VALUES (7, 1, 1, 1, 'CBC', 'ORDERED', '2026-01-01 10:00:00', '2026-01-01 10:00:00')"))
    with SessionLocal() as db:
        diagnostic_service.migrate(db)
        diagnostic_service.migrate(db)                                                                       # a second run changes nothing
        assert db.execute(text("SELECT test_name FROM lab_test_orders WHERE id=7")).scalar() == "CBC"
        assert not any(r[1] == "prescription_id" and r[3] == 1 for r in db.execute(text("PRAGMA table_info(lab_test_orders)")).all())
    from app.database.models import LabResult
    LabResult.__table__.create(engine, checkfirst=True)
