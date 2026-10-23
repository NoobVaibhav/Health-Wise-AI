"""Cross-account probing: another patient and a doctor who is NOT authorised for the patient try every id-based endpoint.
None of them may read or change patient 1's data. Synthetic records only."""
import pytest

from tests import sample_data as sd
from tests.conftest import PASSWORD, login, upload
from tests.test_patient_assistant import add_report, report


@pytest.fixture()
def data(client, world):
    d = type("D", (), {})()
    d.report = add_report(client, world, "r.txt", report("03/07/2026", "Hemoglobin 12.1 g/dL 13.0 - 17.0"))["id"]
    d.rx = client.post("/api/prescriptions", headers=world.doctor, json={"patient_id": world.patient_id, "clinical_indication": "Check", "items": [
        {"medicine_name": "Tab. Test", "dosage": "5 mg", "frequency": "Daily", "duration": "5 days", "quantity": 5}]}).json()["id"]
    d.appt = client.post("/api/appointments", headers=world.employee, json={"patient_id": world.patient_id, "doctor_id": world.doctor_id, "scheduled_at": __import__("tests.conftest", fromlist=["future"]).future(48)}).json()["id"]
    d.conv = client.post("/api/patient-assistant/chat", headers=world.patient, json={"message": "My allergies"}).json()["conversation_id"]
    d.event = client.post(f"/api/doctor/patients/{world.patient_id}/emergency-events", headers=world.doctor, json={"chief_complaint": "Test"}).json()["id"]
    d.task = client.post(f"/api/doctor/patients/{world.patient_id}/follow-ups", headers=world.doctor, json={"title": "Repeat test"}).json()["tasks"][0]["id"]
    created = client.post("/api/patients", headers=world.employee, json={"email": "meera@example.com", "full_name": "Meera Kulkarni", "password": PASSWORD, "gender": "female", "date_of_birth": "1990-01-01", "phone": "8888888888", "assigned_doctor_id": world.other_doctor_id})
    d.other_patient = login(client, "meera@example.com")
    return d


def attempts(world, d):
    pid = world.patient_id
    return [
        ("get", f"/api/patients/{pid}", None), ("put", f"/api/patients/{pid}", {"phone": "1"}),
        ("get", f"/api/patients/{pid}/comparison", None), ("get", f"/api/patients/{pid}/trends", None), ("get", f"/api/patients/{pid}/trends/Hemoglobin", None),
        ("get", f"/api/doctor/patients/{pid}/history", None),
        ("get", f"/api/reports/{d.report}", None), ("get", f"/api/reports/{d.report}/analysis", None), ("get", f"/api/reports/{d.report}/file", None),
        ("delete", f"/api/reports/{d.report}", None), ("post", f"/api/reports/{d.report}/insights/refresh", None),
        ("put", f"/api/doctor/reports/{d.report}/review", {"decision": "APPROVED"}),
        ("put", f"/api/appointments/{d.appt}", {"status": "CANCELLED"}),
        ("get", f"/api/prescriptions/{d.rx}", None), ("put", f"/api/prescriptions/{d.rx}/cancel", {}),
        ("get", f"/api/health-history/patient/{pid}", None), ("put", f"/api/health-history/patient/{pid}", {"allergies": [{"name": "Dust", "kind": "OTHER"}]}),
        ("post", f"/api/health-history/patient/{pid}/preview", {"history": {}}), ("post", f"/api/health-history/patient/{pid}/assessments", {"chief_complaint": "x"}),
        ("get", f"/api/doctor/patients/{pid}/clinical-summary", None), ("post", f"/api/doctor/patients/{pid}/clinical-summary/generate", None),
        ("post", f"/api/doctor/patients/{pid}/clinical-summary/review", {"item_key": "report:1", "action": "REVIEWED"}),
        ("get", f"/api/doctor/patients/{pid}/timeline", None), ("get", f"/api/doctor/patients/{pid}/report-trends", None), ("get", f"/api/doctor/patients/{pid}/medication-history", None),
        ("get", f"/api/doctor/patients/{pid}/follow-ups", None), ("post", f"/api/doctor/patients/{pid}/follow-ups", {"title": "x y z"}),
        ("patch", f"/api/doctor/patients/{pid}/follow-ups/{d.task}", {"status": "DONE"}),
        ("get", f"/api/doctor/patients/{pid}/emergency-history", None), ("post", f"/api/doctor/patients/{pid}/emergency-events", {"chief_complaint": "x"}),
        ("get", f"/api/doctor/emergency-events/{d.event}", None),
        ("get", f"/api/patient-assistant/conversations/{d.conv}", None), ("delete", f"/api/patient-assistant/conversations/{d.conv}", None),
    ]


@pytest.mark.parametrize("who", ["other_patient", "other_doctor"])
def test_outsiders_cannot_read_or_change_a_patients_data(client, world, data, who):
    auth = data.other_patient if who == "other_patient" else world.other_doctor
    for method, url, body in attempts(world, data):
        r = client.request(method, url, headers=auth, **({"json": body} if body is not None else {}))
        assert r.status_code in (403, 404), f"{who} got {r.status_code} on {method.upper()} {url}: {r.text[:120]}"
    # nothing was changed by the attempts
    assert client.get(f"/api/appointments", headers=world.doctor).json()[0]["status"] != "CANCELLED"
    assert client.get(f"/api/reports/{data.report}", headers=world.doctor).status_code == 200
    assert client.get(f"/api/patient-assistant/conversations/{data.conv}", headers=world.patient).status_code == 200


def test_staff_roles_cannot_reach_clinical_data(client, world, data):
    """Front desk, administrator and pharmacy never read reports, history or the clinical summary."""
    pid = world.patient_id
    for who in (world.employee, world.admin, world.pharmacy):
        for url in (f"/api/health-history/patient/{pid}", f"/api/doctor/patients/{pid}/clinical-summary",
                    f"/api/doctor/patients/{pid}/timeline", f"/api/doctor/patients/{pid}/medication-history", f"/api/patient-assistant/conversations/{data.conv}"):
            assert client.get(url, headers=who).status_code in (403, 404), url
    for who in (world.employee, world.admin):                                              # the report page opens, but without any clinical value
        seen = client.get(f"/api/reports/{data.report}/analysis", headers=who)
        assert seen.status_code == 200 and seen.json()["parameters"] == [] and seen.json()["analysis_visible"] is False and not seen.json()["insights"]
    assert client.get(f"/api/reports/{data.report}/file", headers=world.admin).status_code == 403
    assert client.get(f"/api/reports/{data.report}/file", headers=world.pharmacy).status_code in (403, 404)


def test_ids_that_do_not_exist_or_are_hostile_do_not_crash(client, world, data):
    for url in ("/api/reports/999999", "/api/reports/-1", "/api/prescriptions/0", "/api/reports/abc"):
        r = client.get(url, headers=world.doctor)
        assert r.status_code in (403, 404, 422), (url, r.status_code)
    odd = client.get(f"/api/patients/{world.patient_id}/trends/%27%3B%20DROP%20TABLE%20users%3B--", headers=world.doctor)
    assert odd.status_code in (200, 404) and not odd.json().get("points")                 # an odd name is just a name that matches nothing
    assert client.get("/api/auth/me", headers=world.doctor).status_code == 200            # the database is still fine
