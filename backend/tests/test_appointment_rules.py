"""Appointment rules, enforced by the server (the page only helps). Every test freezes the hospital clock, so nothing depends on today's date.
The frozen 'now' is given in hospital time (IST); the server's own clock is deliberately set to UTC to prove the rules do not use it."""
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.database.connection import SessionLocal
from app.database.models import Appointment
from app.utils import clock
from tests.conftest import PASSWORD
from tests.test_concurrency_flows import second_patient

IST = timezone(timedelta(hours=5, minutes=30))
NOW = "2026-11-05T12:34:00"           # a Thursday, 12:34 at the hospital = 07:04 UTC


@pytest.fixture()
def freeze(monkeypatch):
    def at(ist_text: str):
        moment = datetime.fromisoformat(ist_text).replace(tzinfo=IST).astimezone(timezone.utc)
        monkeypatch.setattr(clock, "_utc_now", lambda: moment)
    at(NOW)
    return at


def book(client, w, when, who=None, doctor=None, patient=None, **extra):
    body = {"doctor_id": doctor or w.doctor_id, "scheduled_at": when, **extra}
    if who is None:
        who = w.employee
    if who is w.employee:
        body["patient_id"] = patient or w.patient_id
    return client.post("/api/appointments", headers=who, json=body)


# ---------------------------------------------------------------- past, today, grace
def test_a_past_day_is_refused_with_a_clear_message(client, world, freeze):
    r = book(client, world, "2026-11-04T10:00:00")
    assert r.status_code == 422 and "already passed" in r.json()["detail"], r.text


def test_a_time_today_that_has_passed_is_refused_and_a_later_one_is_accepted(client, world, freeze):
    assert book(client, world, "2026-11-05T10:00:00").status_code == 422
    assert book(client, world, "2026-11-05T14:00:00").status_code == 201


def test_walk_in_grace_is_five_minutes_exactly(client, world, freeze):
    assert book(client, world, "2026-11-05T12:30:00").status_code == 201          # 4 minutes after the slot began: a walk-in
    assert book(client, world, "2026-11-05T12:15:00", patient=second_patient(client, world)).status_code == 422     # 19 minutes: too late
    freeze("2026-11-05T12:35:00")
    p3 = client.post("/api/patients", headers=world.employee, json={"email": "c@example.com", "full_name": "Chitra Rao", "password": PASSWORD, "gender": "female", "date_of_birth": "1991-02-03", "phone": "9876500003"}).json()["patient"]["id"]
    assert book(client, world, "2026-11-05T12:30:00", doctor=world.other_doctor_id, patient=p3).status_code == 201     # exactly 5 minutes: still allowed
    freeze("2026-11-05T12:35:01")
    p4 = client.post("/api/patients", headers=world.employee, json={"email": "d@example.com", "full_name": "Deepa Nair", "password": PASSWORD, "gender": "female", "date_of_birth": "1992-02-03", "phone": "9876500004"}).json()["patient"]["id"]
    assert book(client, world, "2026-11-05T12:30:00", doctor=world.other_doctor_id, patient=p4).status_code == 422      # one second over


def test_the_next_slot_after_now_is_accepted(client, world, freeze):
    assert book(client, world, "2026-11-05T12:45:00").status_code == 201


# ---------------------------------------------------------------- time zones
def test_the_servers_utc_clock_is_not_used_a_naive_time_means_hospital_time(client, world, freeze):
    # 09:00 is 3.5 hours ago at the hospital, but it is still ahead of the UTC clock (07:04): a server running in UTC used to accept it
    assert book(client, world, "2026-11-05T09:00:00").status_code == 422


def test_times_with_an_offset_are_converted_and_stored_in_hospital_time(client, world, freeze):
    assert book(client, world, "2026-11-05T05:00:00Z").status_code == 422                     # 10:30 IST: past
    ok = book(client, world, "2026-11-05T08:30:00Z")                                           # 14:00 IST
    assert ok.status_code == 201 and ok.json()["scheduled_at"].startswith("2026-11-05T14:00"), ok.text
    ok2 = book(client, world, "2026-11-06T10:00:00+05:30", patient=second_patient(client, world))
    assert ok2.status_code == 201 and ok2.json()["scheduled_at"].startswith("2026-11-06T10:00"), ok2.text


def test_year_and_month_boundaries(client, world, freeze):
    freeze("2026-12-31T16:50:00")
    assert book(client, world, "2026-12-31T16:00:00").status_code == 422
    assert book(client, world, "2027-01-01T09:00:00").status_code == 201                       # the next minute-of-the-year works
    freeze("2026-11-30T09:00:00")
    assert book(client, world, "2026-12-01T09:30:00", patient=second_patient(client, world)).status_code == 201


def test_leap_day_is_a_real_day_and_29_february_in_a_normal_year_is_refused(client, world, freeze):
    freeze("2028-02-28T10:00:00")
    assert book(client, world, "2028-02-29T10:00:00").status_code == 201
    r = book(client, world, "2027-02-29T10:00:00")
    assert r.status_code == 422, r.text
    assert book(client, world, "2026-13-01T10:00:00").status_code == 422                         # month 13
    assert book(client, world, "2026-11-31T10:00:00").status_code == 422                         # 31 November


# ---------------------------------------------------------------- how far ahead, opening hours, slots
def test_no_more_than_thirty_days_ahead(client, world, freeze):
    assert book(client, world, "2026-12-05T10:00:00").status_code == 201                       # inside 30 days
    r = book(client, world, "2026-12-05T14:00:00", patient=second_patient(client, world))
    assert r.status_code == 422 and "30 days" in r.json()["detail"], r.text
    assert book(client, world, "2027-02-05T10:00:00", doctor=world.other_doctor_id).status_code == 422


@pytest.mark.parametrize("when,ok", [("2026-11-06T08:45:00", False), ("2026-11-06T09:00:00", True), ("2026-11-06T16:45:00", True),
                                      ("2026-11-06T17:00:00", False), ("2026-11-06T03:00:00", False), ("2026-11-06T23:45:00", False)])
def test_only_slots_inside_opening_hours(client, world, freeze, when, ok):
    r = book(client, world, when)
    assert r.status_code == (201 if ok else 422), r.text


@pytest.mark.parametrize("when", ["2026-11-06T10:07:00", "2026-11-06T10:00:30", "2026-11-06T10:00:00.5"])
def test_times_must_start_on_a_slot(client, world, freeze, when):
    r = book(client, world, when)
    assert r.status_code == 422 and "slot" in r.json()["detail"], r.text


def test_the_slot_list_marks_past_and_taken_slots(client, world, freeze):
    assert book(client, world, "2026-11-05T14:00:00").status_code == 201
    body = client.get(f"/api/appointments/slots?doctor_id={world.doctor_id}&day=2026-11-05", headers=world.patient).json()
    by = {s["time"]: s for s in body["slots"]}
    assert len(body["slots"]) == 32 and by["09:00"]["available"] is False and by["09:00"]["reason"] == "unavailable"
    assert by["14:00"]["reason"] == "taken" and by["14:15"]["available"] is True
    assert client.get(f"/api/appointments/slots?doctor_id=0&day=2026-11-05", headers=world.patient).status_code == 422
    assert client.get(f"/api/appointments/slots?doctor_id={world.doctor_id}&day=not-a-date", headers=world.patient).status_code == 422
    assert client.get(f"/api/appointments/slots?doctor_id={world.doctor_id}&day=2026-11-05").status_code == 401


# ---------------------------------------------------------------- double booking
def test_same_doctor_same_slot_is_refused_and_a_cancelled_slot_is_free_again(client, world, freeze):
    p2 = second_patient(client, world)
    first = book(client, world, "2026-11-06T10:00:00")
    assert first.status_code == 201
    assert book(client, world, "2026-11-06T10:00:00", patient=p2).status_code == 409
    assert client.put(f"/api/appointments/{first.json()['id']}", headers=world.employee, json={"status": "CANCELLED"}).status_code == 200
    assert book(client, world, "2026-11-06T10:00:00", patient=p2).status_code == 201


def test_a_patient_cannot_hold_two_appointments_at_the_same_time_with_different_doctors(client, world, freeze):
    assert book(client, world, "2026-11-06T10:00:00").status_code == 201
    r = book(client, world, "2026-11-06T10:00:00", doctor=world.other_doctor_id)
    assert r.status_code == 409 and "patient" in r.json()["detail"].lower(), r.text
    assert book(client, world, "2026-11-06T10:15:00", doctor=world.other_doctor_id).status_code == 201     # a different slot is fine


def test_the_database_itself_refuses_two_open_appointments_of_one_doctor_in_one_slot(client, world, freeze):
    assert book(client, world, "2026-11-06T10:00:00").status_code == 201
    p2 = second_patient(client, world)
    with SessionLocal() as db:
        db.add(Appointment(patient_id=p2, doctor_id=world.doctor_id, scheduled_at=datetime(2026, 11, 6, 10, 0), status="SCHEDULED"))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        db.add(Appointment(patient_id=p2, doctor_id=world.doctor_id, scheduled_at=datetime(2026, 11, 6, 10, 0), status="CANCELLED"))
        db.commit()                                                                                 # a cancelled one may share the slot


# ---------------------------------------------------------------- who books for whom
def test_a_patient_always_books_for_themselves(client, world, freeze):
    p2 = second_patient(client, world)
    r = client.post("/api/appointments", headers=world.patient, json={"patient_id": p2, "doctor_id": world.doctor_id, "scheduled_at": "2026-11-06T10:00:00"})
    assert r.status_code == 201 and r.json()["patient_id"] == world.patient_id, r.text
    assert book(client, world, "2026-11-06T10:15:00", patient=999999).status_code == 404
    assert book(client, world, "2026-11-06T10:15:00", doctor=999999).status_code == 404
    assert client.post("/api/appointments", headers=world.doctor, json={"patient_id": world.patient_id, "doctor_id": world.doctor_id, "scheduled_at": "2026-11-06T11:00:00"}).status_code == 403


# ---------------------------------------------------------------- rescheduling and status
def make(client, world, when="2026-11-06T10:00:00"):
    return book(client, world, when).json()["id"]


def put(client, world, appt, body, who=None):
    return client.put(f"/api/appointments/{appt}", headers=who or world.employee, json=body)


def test_rescheduling_follows_the_same_rules(client, world, freeze):
    a = make(client, world)
    assert put(client, world, a, {"scheduled_at": "2026-11-04T10:00:00"}).status_code == 422             # into the past
    assert put(client, world, a, {"scheduled_at": "2026-11-05T10:00:00"}).status_code == 422             # earlier today
    assert put(client, world, a, {"scheduled_at": "2026-11-06T03:00:00"}).status_code == 422             # outside hours
    assert put(client, world, a, {"scheduled_at": "2027-03-01T10:00:00"}).status_code == 422             # too far ahead
    assert put(client, world, a, {"scheduled_at": "2026-11-06T10:07:00"}).status_code == 422             # not a slot
    assert put(client, world, a, {"scheduled_at": "2026-11-07T10:30:00"}).json()["scheduled_at"].startswith("2026-11-07T10:30")


def test_a_completed_or_cancelled_appointment_cannot_be_moved(client, world, freeze):
    a, b = make(client, world), make(client, world, "2026-11-06T11:00:00")
    assert put(client, world, b, {"status": "CANCELLED"}).status_code == 200
    r = put(client, world, b, {"scheduled_at": "2026-11-07T10:00:00"})
    assert r.status_code == 409, r.text
    assert put(client, world, a, {"status": "CONFIRMED"}).status_code == 200
    freeze("2026-11-06T10:30:00")
    assert put(client, world, a, {"status": "COMPLETED"}).status_code == 200
    assert put(client, world, a, {"scheduled_at": "2026-11-07T10:00:00"}).status_code == 409


def test_status_only_moves_forward(client, world, freeze):
    a = make(client, world)
    assert put(client, world, a, {"status": "COMPLETED"}).status_code == 409                          # not confirmed yet
    assert put(client, world, a, {"status": "CONFIRMED"}).status_code == 200
    r = put(client, world, a, {"status": "COMPLETED"})
    assert r.status_code == 422 and "future" in r.json()["detail"], r.text                             # tomorrow's visit cannot be completed today
    freeze("2026-11-06T10:10:00")
    assert put(client, world, a, {"status": "COMPLETED"}).status_code == 200
    assert put(client, world, a, {"status": "CANCELLED"}).status_code == 409                          # a finished visit cannot be cancelled
    assert put(client, world, a, {"status": "SCHEDULED"}).status_code == 409
    assert put(client, world, a, {"status": "CONFIRMED"}).status_code == 409


def test_a_cancelled_appointment_cannot_come_back(client, world, freeze):
    a = make(client, world)
    assert put(client, world, a, {"status": "CANCELLED"}).status_code == 200
    for target in ("SCHEDULED", "CONFIRMED", "COMPLETED"):
        assert put(client, world, a, {"status": target}).status_code == 409, target


def test_unknown_status_and_bad_bodies_are_422_and_only_the_right_roles_change_status(client, world, freeze):
    a = make(client, world)
    assert put(client, world, a, {"status": "DONE"}).status_code == 422
    assert put(client, world, a, {"status": 5}).status_code == 422
    assert put(client, world, a, {"scheduled_at": "tomorrow"}).status_code == 422
    assert put(client, world, a, {"status": "CONFIRMED"}, who=world.patient).status_code == 403
    assert put(client, world, a, {"status": "CONFIRMED"}, who=world.other_doctor).status_code == 403
    assert put(client, world, a, {"status": "CONFIRMED"}, who=world.pharmacy).status_code == 403
    assert put(client, world, a, {"scheduled_at": "2026-11-07T10:00:00"}, who=world.doctor).status_code == 403
    assert put(client, world, a, {"status": "CONFIRMED"}, who=world.doctor).status_code == 200
    assert put(client, world, a, {"status": "CANCELLED"}, who=world.patient).status_code == 200
