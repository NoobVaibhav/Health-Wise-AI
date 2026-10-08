"""Report comparison, trends, doctor history view, dashboards and the safety text."""
from app.services.safety_filter import DISCLAIMER, filter_text, is_safe
from tests import sample_data as sd
from tests.conftest import upload


def two_reports(client, world, review=True):
    ids = []
    for name, lines in (("A.pdf", sd.REPORT_A_LINES), ("B.pdf", sd.REPORT_B_LINES)):
        ids.append(upload(client, world.employee, world.patient_id, name, sd.lines_to_pdf(lines)).json()["id"])
        if review:
            client.put(f"/api/doctor/reports/{ids[-1]}/review", headers=world.doctor, json={"decision": "APPROVED"})
    return ids


def test_comparison_of_two_reports(client, world):
    assert client.get(f"/api/patients/{world.patient_id}/comparison", headers=world.doctor).json()["available"] is False
    a, b = two_reports(client, world)
    data = client.get(f"/api/patients/{world.patient_id}/comparison", headers=world.doctor).json()
    assert data["available"] and data["previous"]["id"] == a and data["latest"]["id"] == b
    rows = {r["parameter"]: r for r in data["rows"]}
    assert (rows["HbA1c"]["previous"], rows["HbA1c"]["latest"], rows["HbA1c"]["change"]) == (7.2, 6.8, -0.4)
    assert rows["LDL"]["change"] == -30 and rows["Vitamin D"]["change"] == 10
    assert rows["HbA1c"]["trend"] == "STILL_OUTSIDE_RANGE"       # moved closer, still above the printed range
    assert rows["Total Cholesterol"]["trend"] == "IMPROVED"      # moved into the printed range
    assert rows["Hemoglobin"]["trend"] == "STABLE"
    assert "cured" not in str(data).lower()
    explicit = client.get(f"/api/patients/{world.patient_id}/comparison?previous={a}&latest={b}", headers=world.patient).json()
    assert explicit["matched_count"] == data["matched_count"]


def test_patient_comparison_only_uses_reviewed_reports(client, world):
    two_reports(client, world, review=False)
    assert client.get(f"/api/patients/{world.patient_id}/comparison", headers=world.patient).json()["available"] is False
    assert client.get(f"/api/patients/{world.patient_id}/trends", headers=world.patient).json() == []
    assert client.get(f"/api/patients/{world.patient_id}/comparison", headers=world.doctor).json()["available"] is True


def test_trend_series(client, world):
    two_reports(client, world)
    names = [t["name"] for t in client.get(f"/api/patients/{world.patient_id}/trends", headers=world.doctor).json()]
    assert "HbA1c" in names
    series = client.get(f"/api/patients/{world.patient_id}/trends/HbA1c", headers=world.patient).json()
    assert [p["value"] for p in series["points"]] == [7.2, 6.8]
    assert [p["date"] for p in series["points"]] == ["2026-07-03", "2026-10-06"]
    assert series["unit"] == "%" and series["points"][0]["reference_high"] == 5.6


def test_comparison_trend_logic_units():
    from types import SimpleNamespace as NS
    from app.services.comparison_engine import compare_parameter

    def p(value, ref="4.0 - 5.6", status="X", unit="%", name="HbA1c"):
        return NS(value=value, unit=unit, reference_text=ref, status=status, normalized_name=name)

    assert compare_parameter(p(5.0), p(5.1))["trend"] == "STABLE"
    assert compare_parameter(p(5.0), p(6.5))["trend"] == "REQUIRES_PROFESSIONAL_FOLLOW_UP"
    assert compare_parameter(p(6.0), p(7.5))["trend"] == "REQUIRES_PROFESSIONAL_FOLLOW_UP"
    assert compare_parameter(p(5.0, unit="%"), p(5.0, unit="mg/dL"))["trend"] == "UNABLE_TO_DETERMINE"
    neutral = compare_parameter(p(10, ref=None, name="Platelets"), p(14, ref=None, name="Platelets"))
    assert neutral["trend"] == "INCREASED" and "Changed" in neutral["note"]
    favorable = compare_parameter(p(7.2, ref=None), p(6.8, ref=None))
    assert favorable["trend"] == "IMPROVED" and "not a diagnosis" in favorable["note"]


def test_doctor_sees_full_history_before_reviewing(client, world):
    a, b = two_reports(client, world, review=False)
    client.post("/api/doctor/history-entries", headers=world.doctor, json={
        "patient_id": world.patient_id, "entry_date": "2025-03-10", "entry_type": "Past illness",
        "description": "Viral fever, recovered."})
    history = client.get(f"/api/doctor/patients/{world.patient_id}/history", headers=world.doctor).json()
    assert history["patient"]["full_name"] == "Rahul Patil" and history["patient"]["allergies"] == "None known"
    assert [r["id"] for r in history["reports"]] == [b, a]
    assert history["history_entries"][0]["entry_type"] == "Past illness"
    assert "HISTORY_ENTRY" in [e["type"] for e in history["timeline"]]
    searched = client.get(f"/api/doctor/patients/{world.patient_id}/history?q=viral", headers=world.doctor).json()
    assert [e["type"] for e in searched["timeline"]] == ["HISTORY_ENTRY"]
    patient_history = client.get("/api/patient/history", headers=world.patient).json()
    assert patient_history["history_entries"][0]["description"] == "Viral fever, recovered."


def test_dashboards_have_real_numbers(client, world):
    empty = client.get("/api/admin/dashboard", headers=world.admin).json()
    assert empty["total_patients"] == 1 and empty["total_doctors"] == 2 and empty["total_reports"] == 0
    assert client.get("/api/patient/dashboard", headers=world.patient).json()["latest_report"] is None
    assert client.get("/api/doctor/dashboard", headers=world.doctor).json()["recent_reports"] == []
    two_reports(client, world, review=False)
    admin = client.get("/api/admin/dashboard", headers=world.admin).json()
    assert admin["total_reports"] == 2 and admin["reports_pending_review"] == 2
    assert admin["total_employees"] == 1 and admin["total_pharmacy_staff"] == 1
    assert admin["report_processing"]["by_method"] == {"pdf_text": 2}
    employee = client.get("/api/employee/dashboard", headers=world.employee).json()
    assert employee["awaiting_review_count"] == 2 and len(employee["my_recent_uploads"]) == 2
    generic = client.get("/api/dashboard", headers=world.doctor).json()
    assert generic["role"] == "DOCTOR" and generic["reports_waiting_count"] == 2


def test_patient_search(client, world):
    assert [p["full_name"] for p in client.get("/api/patients?q=rahul", headers=world.employee).json()] == ["Rahul Patil"]
    assert client.get("/api/patients?q=P-0001", headers=world.employee).json()[0]["patient_code"] == "P-0001"
    assert client.get("/api/patients?q=zzzz", headers=world.employee).json() == []


def test_disclaimer_and_safety_filter(client):
    assert "not a diagnostic system" in client.get("/api/health").json()["disclaimer"]
    assert "Prescriptions are created only by authorized doctors" in DISCLAIMER
    assert not is_safe("You have diabetes and need a diagnosis")
    assert not is_safe("Stop taking your medication")
    assert not is_safe("You are 80% healthy")
    assert is_safe("HbA1c is a blood test related to average blood glucose.")
    assert filter_text("You have diabetes.", "fallback text") == "fallback text"
    assert filter_text(None, "fallback text") == "fallback text"
