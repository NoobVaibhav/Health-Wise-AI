"""Test setup: a fresh temporary SQLite database and upload folder for every test run.

`world` builds a small hospital through the REAL API (admin creates staff, employee registers a patient), so the
tests exercise the same paths a user would."""
import os
import tempfile
from datetime import datetime, timedelta

_tmp = tempfile.mkdtemp(prefix="healthwise_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["UPLOAD_DIR"] = f"{_tmp}/uploads"
os.environ["JWT_SECRET"] = "test-secret-key-for-healthwise-ai-tests-0123456789"
os.environ["BCRYPT_ROUNDS"] = "4"  # fast hashing for tests only
os.environ["LLM_API_KEY"] = ""  # tests must work without an LLM

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database.connection import Base, engine  # noqa: E402
from app.main import app  # noqa: E402

PASSWORD = "StrongPass123"


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client


def headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def login(client, email: str, password: str = PASSWORD) -> dict:
    response = client.post("/api/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return headers(response.json()["access_token"])


class World:
    """Holds the logged-in headers and ids of a demo hospital."""


@pytest.fixture()
def world(client) -> World:
    w = World()
    # first admin (public registration works only once)
    r = client.post("/api/auth/register", json={"email": "admin@hospital.example.com", "full_name": "Admin One",
                                                "password": PASSWORD})
    assert r.status_code == 201, r.text
    w.admin = headers(r.json()["access_token"])

    # the default department list is seeded at start-up, so "General Medicine" already exists
    w.department_id = next(d["id"] for d in client.get("/api/catalog/departments", headers=w.admin).json() if d["name"] == "General Medicine")

    def staff(path, email, name, **extra):
        res = client.post(f"/api/admin/{path}", headers=w.admin,
                          json={"email": email, "full_name": name, "password": PASSWORD, **extra})
        assert res.status_code == 201, res.text
        return res.json()["user"]["id"]

    staff("doctors", "anjali@hospital.example.com", "Dr. Anjali Sharma", department_id=w.department_id,
          specialization="Physician")
    staff("doctors", "other.doctor@hospital.example.com", "Dr. Other Doctor", department_id=w.department_id)
    staff("employees", "priya@hospital.example.com", "Priya Joshi", designation="Lab assistant")
    staff("pharmacy-staff", "pharmacy@hospital.example.com", "MediCare Pharmacy Staff", pharmacy_name="MediCare")
    w.doctor = login(client, "anjali@hospital.example.com")
    w.other_doctor = login(client, "other.doctor@hospital.example.com")
    w.employee = login(client, "priya@hospital.example.com")
    w.pharmacy = login(client, "pharmacy@hospital.example.com")

    doctors = client.get("/api/doctors", headers=w.employee).json()
    w.doctor_id = next(d["id"] for d in doctors if d["full_name"] == "Dr. Anjali Sharma")
    w.other_doctor_id = next(d["id"] for d in doctors if d["full_name"] == "Dr. Other Doctor")

    # employee registers the patient and assigns the doctor
    created = client.post("/api/patients", headers=w.employee, json={
        "email": "rahul@example.com", "full_name": "Rahul Patil", "password": PASSWORD, "gender": "male",
        "date_of_birth": "1998-05-14", "phone": "9999999999", "assigned_doctor_id": w.doctor_id,
        "allergies": "None known"})
    assert created.status_code == 201, created.text
    w.patient_id = created.json()["patient"]["id"]
    w.patient = login(client, "rahul@example.com")
    return w


def upload(client, auth, patient_id, filename, content, doctor_id=None):
    data = {"patient_id": str(patient_id)}
    if doctor_id:
        data["doctor_id"] = str(doctor_id)
    return client.post("/api/reports/upload", headers=auth, data=data,
                       files={"file": (filename, content, "application/octet-stream")})


def future(hours: int = 48) -> str:
    """A bookable appointment time about `hours` from now: always a real slot (a quarter hour between 09:00 and 14:45, the day chosen by `hours`),
    so tests that book appointments keep passing the opening-hours and slot rules. Different `hours` give different slots; negative `hours` is in the past."""
    from app.utils.clock import hospital_now
    day = hospital_now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1 + hours // 24)
    return (day + timedelta(hours=9, minutes=15 * (hours % 24))).isoformat()
