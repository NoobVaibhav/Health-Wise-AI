"""The four long lists (patients, reports, a doctor's patients, admin people) are paged: `limit` and `offset` choose the slice, the answer stays a plain list, and the size of the whole
list is in X-Total-Count. Bad values are a clean 422, and a page never leaks rows the user may not see."""
import pathlib

import pytest

from tests.conftest import PASSWORD, upload

SAMPLE = pathlib.Path(__file__).resolve().parent / "fixtures" / "kamal_diagnostic_sample_report.pdf"


@pytest.fixture()
def crowd(client, world):
    """Three more patients of the same doctor, so there are four in all."""
    for i, name in enumerate(["Asha Kulkarni", "Bhavna Desai", "Chetan Rao"]):
        r = client.post("/api/patients", headers=world.employee, json={
            "email": f"page{i}@example.com", "full_name": name, "password": PASSWORD, "gender": "female",
            "date_of_birth": "1990-01-01", "phone": f"98765000{i}1", "assigned_doctor_id": world.doctor_id, "allow_duplicate": True})
        assert r.status_code == 201, r.text
    return world


def ids(response):
    return [row["id"] for row in response.json()]


def test_patients_are_paged_and_the_total_is_in_the_header(client, crowd):
    full = client.get("/api/patients", headers=crowd.employee)
    assert full.status_code == 200 and len(full.json()) == 4 and full.headers["x-total-count"] == "4"
    first = client.get("/api/patients?limit=2", headers=crowd.employee)
    second = client.get("/api/patients?limit=2&offset=2", headers=crowd.employee)
    assert ids(first) + ids(second) == ids(full) and first.headers["x-total-count"] == second.headers["x-total-count"] == "4"
    assert client.get("/api/patients?offset=10", headers=crowd.employee).json() == []


def test_the_total_follows_the_search_not_the_whole_table(client, crowd):
    r = client.get("/api/patients?q=Bhavna&limit=1", headers=crowd.employee)
    assert len(r.json()) == 1 and r.headers["x-total-count"] == "1"


def test_a_doctors_patient_list_is_paged(client, crowd):
    full = client.get("/api/doctor/patients", headers=crowd.doctor)
    assert len(full.json()) == 4 and full.headers["x-total-count"] == "4"
    page = client.get("/api/doctor/patients?limit=3&offset=3", headers=crowd.doctor)
    assert ids(page) == ids(full)[3:] and page.headers["x-total-count"] == "4"


def test_a_page_never_shows_patients_of_another_doctor(client, crowd):
    r = client.get("/api/doctor/patients?limit=500", headers=crowd.other_doctor)
    assert r.json() == [] and r.headers["x-total-count"] == "0"


def test_admin_people_are_paged(client, crowd):
    full = client.get("/api/admin/people", headers=crowd.admin)
    total = len(full.json())
    assert total >= 9 and full.headers["x-total-count"] == str(total)
    page = client.get("/api/admin/people?limit=4&offset=4", headers=crowd.admin)
    assert [p["id"] for p in page.json()] == [p["id"] for p in full.json()][4:8]
    assert client.get("/api/admin/people?role=DOCTOR&limit=1", headers=crowd.admin).headers["x-total-count"] == "2"


def test_reports_are_paged_newest_first(client, crowd):
    for _ in range(3):
        r = upload(client, crowd.employee, crowd.patient_id, SAMPLE.name, SAMPLE.read_bytes(), crowd.doctor_id)
        assert r.status_code in (200, 201), r.text
    full = client.get("/api/reports", headers=crowd.employee)
    assert len(full.json()) == 3 and full.headers["x-total-count"] == "3"
    first, rest = client.get("/api/reports?limit=1", headers=crowd.employee), client.get("/api/reports?limit=5&offset=1", headers=crowd.employee)
    assert ids(first) + ids(rest) == ids(full)
    patient_view = client.get("/api/reports?limit=1", headers=crowd.patient)
    assert patient_view.headers["x-total-count"] == "3" and len(patient_view.json()) == 1


def test_report_filters_are_applied_before_paging(client, crowd):
    for _ in range(2):
        assert upload(client, crowd.employee, crowd.patient_id, SAMPLE.name, SAMPLE.read_bytes(), crowd.doctor_id).status_code in (200, 201)
    pending = client.get("/api/reports?needs_review=true&limit=1", headers=crowd.doctor)
    assert len(pending.json()) == 1 and pending.headers["x-total-count"] == "2"
    first_id = client.get("/api/reports", headers=crowd.doctor).json()[0]["id"]
    assert client.put(f"/api/doctor/reports/{first_id}/review", headers=crowd.doctor, json={"decision": "APPROVED", "comment": "Seen"}).status_code == 200
    assert client.get("/api/reports?needs_review=true", headers=crowd.doctor).headers["x-total-count"] == "1"
    assert client.get("/api/reports?q=rahul", headers=crowd.doctor).headers["x-total-count"] == "2"
    assert client.get("/api/reports?q=nobody-by-this-name", headers=crowd.doctor).json() == []
    assert client.get("/api/reports?needs_review=maybe", headers=crowd.doctor).status_code == 422


@pytest.mark.parametrize("path", ["/api/patients", "/api/reports", "/api/admin/people", "/api/doctor/patients"])
@pytest.mark.parametrize("query", ["limit=0", "limit=501", "limit=-1", "limit=abc", "offset=-1", "offset=99999999999", "limit=1.5"])
def test_bad_paging_values_are_a_clean_422(client, crowd, path, query):
    auth = crowd.admin if "admin" in path else crowd.doctor if "doctor" in path else crowd.employee
    r = client.get(f"{path}?{query}", headers=auth)
    assert r.status_code == 422, (path, query, r.status_code)


def test_the_default_page_is_100_and_the_header_is_visible_to_the_phone_app(client, crowd):
    r = client.options("/api/patients", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"})
    assert r.status_code == 200
    got = client.get("/api/patients", headers={**crowd.employee, "Origin": "http://localhost:5173"})
    assert "x-total-count" in got.headers.get("access-control-expose-headers", "").lower()
