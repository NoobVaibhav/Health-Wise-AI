"""The demo doctors seed: every department gets a doctor, running it twice adds nothing, the catalog gains General Surgery, juniors have a supervisor of the
same department, the appointments are valid and in the future, the new doctors can sign in, and the seed refuses a real (non-SQLite) database. Invented data only."""
from datetime import date

import pytest
from sqlalchemy import select

from app import seed_doctors
from app.database.connection import SessionLocal
from app.database.models import Appointment, Department, Doctor, Specialization, User
from app.schemas.patient import PatientCreate
from app.seed_demo import DEMO_PASSWORD
from app.services import user_service
from app.utils import clock
from tests.conftest import login


@pytest.fixture()
def seeded(client):
    with SessionLocal() as db:
        user_service.create_patient(db, PatientCreate(email="rahul.patil@healthwise.demo.com", full_name="Rahul Patil", password=DEMO_PASSWORD, gender="male",
                                                      date_of_birth=date(1998, 5, 14), phone="9000000001"))
        first = seed_doctors.run(db, DEMO_PASSWORD)
        second = seed_doctors.run(db, DEMO_PASSWORD)
    return first, second


def test_the_seed_adds_every_doctor_once_and_a_second_run_adds_nothing(seeded):
    first, second = seeded
    assert first["added"] == len(seed_doctors.DOCTORS) == 25 and first["skipped"] == 0
    assert second["added"] == 0 and second["skipped"] == 25 and second["appointments_added"] == 0
    with SessionLocal() as db:
        assert db.query(Doctor).count() == 25                                             # no duplicates


def test_every_department_has_a_doctor_and_general_surgery_was_added_to_the_catalog(seeded):
    with SessionLocal() as db:
        names = {d.name for d in db.scalars(select(Department))}
        with_doctor = {d.name for d in db.scalars(select(Department).join(Doctor, Doctor.department_id == Department.id).distinct())}
        assert "General Surgery" in names and names == with_doctor
        surgery = db.scalar(select(Department).where(Department.name == "General Surgery"))
        assert {s.name for s in db.scalars(select(Specialization).where(Specialization.department_id == surgery.id))} == {"General Surgeon", "Laparoscopic Surgeon", "Trauma Surgeon"}


def test_specializations_belong_to_the_department_and_juniors_have_a_consultant_of_the_same_department(seeded):
    with SessionLocal() as db:
        doctors = db.scalars(select(Doctor)).all()
        assert all(d.specialization_ref.department_id == d.department_id for d in doctors)
        juniors = [d for d in doctors if d.grade != "CONSULTANT"]
        assert len(juniors) == 3 and sum(d.grade == "PG_RESIDENT" for d in juniors) == 1
        for j in juniors:
            assert j.supervisor.grade == "CONSULTANT" and j.supervisor.department_id == j.department_id
        pg = next(d for d in juniors if d.grade == "PG_RESIDENT")
        assert pg.pg_year == 2 and pg.pg_branch


def test_emails_names_and_phones_are_fictional_and_in_the_demo_range(seeded):
    with SessionLocal() as db:
        users = db.scalars(select(User).where(User.role == "DOCTOR")).all()
        assert len(users) == 25 and all(u.email.endswith("@healthwise.demo.com") and u.full_name.startswith("Dr. ") for u in users)
        phones = sorted(d.phone for d in db.scalars(select(Doctor)))
        assert phones[0] == "9000000201" and phones[-1] == "9000000225"


def test_the_seeded_appointments_are_in_the_future_on_valid_slots_with_no_double_booking(seeded):
    with SessionLocal() as db:
        rows = db.scalars(select(Appointment)).all()
        assert len(rows) == 11 and all(a.status == "SCHEDULED" for a in rows)
        assert all(a.scheduled_at > clock.hospital_now() for a in rows)                       # never a past-dated scheduled appointment
        assert all(a.scheduled_at.minute % 15 == 0 and 9 <= a.scheduled_at.hour < 17 for a in rows)
        assert len({(a.doctor_id, a.scheduled_at) for a in rows}) == len(rows)


def test_new_doctors_sign_in_see_their_dashboard_and_appear_in_the_doctor_list(client, seeded):
    with SessionLocal() as db:
        user_service.create_admin(db, "admin@healthwise.demo.com", "Hospital Admin", DEMO_PASSWORD)
    admin_headers = login(client, "admin@healthwise.demo.com", DEMO_PASSWORD)
    listed = client.get("/api/doctors", headers=admin_headers).json()
    assert len(listed) == 25 and {d["department_name"] for d in listed} >= {"General Surgery", "Cardiology", "Pathology"}
    assert {d["full_name"] for d in listed if d["department_name"] == "Cardiology"} == {"Dr. Kavya Menon", "Dr. Tarun Bose"}
    for email in ("kavya.menon@healthwise.demo.com", "prakash.wagh@healthwise.demo.com"):
        who = login(client, email, DEMO_PASSWORD)
        dash = client.get("/api/doctor/dashboard", headers=who)
        assert dash.status_code == 200, dash.text


def test_the_seed_refuses_a_non_sqlite_database_unless_allowed_on_purpose(monkeypatch):
    class Settings:
        database_url = "postgresql://user@host/db"
    monkeypatch.setattr(seed_doctors, "get_settings", lambda: Settings)
    monkeypatch.delenv("ALLOW_DEMO_SEED", raising=False)
    with pytest.raises(SystemExit):
        seed_doctors.assert_demo_seed_allowed()
    monkeypatch.setenv("ALLOW_DEMO_SEED", "1")
    seed_doctors.assert_demo_seed_allowed()
