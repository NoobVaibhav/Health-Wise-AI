"""Step 4, flow 7: things two people (or one impatient person) do at the same moment, on the real API and database. Each test releases its threads together with a barrier.
Outcome rules: exactly one of two competing bookings wins, a double click creates one record, two admins editing one record never crash and leave a record that is one of the two
versions (never a mix of nothing). No sleeps; invented data."""
import threading

from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import PASSWORD, future, login


def race(n, make_call):
    """Run make_call(i) -> (method, path, kwargs) in n threads at once; returns the list of (status, body)."""
    out, barrier = [], threading.Barrier(n)

    def go(i):
        c = TestClient(app, raise_server_exceptions=False)
        method, path, kw = make_call(i)
        barrier.wait()
        r = getattr(c, method)(path, **kw)
        out.append((r.status_code, r.text))

    threads = [threading.Thread(target=go, args=(i,)) for i in range(n)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    return out


def second_patient(client, world):
    r = client.post("/api/patients", headers=world.employee, json={"email": "meera@example.com", "full_name": "Meera Kulkarni", "password": PASSWORD, "gender": "female",
                                                                  "date_of_birth": "1990-01-01", "phone": "9876500001"})
    assert r.status_code == 201, r.text
    return r.json()["patient"]["id"]


def test_two_users_booking_the_same_doctor_and_time_get_exactly_one_appointment(client, world):
    p2 = second_patient(client, world)
    when = future(72)
    results = race(2, lambda i: ("post", "/api/appointments", {"headers": world.employee, "json": {"patient_id": (world.patient_id, p2)[i], "doctor_id": world.doctor_id, "scheduled_at": when, "reason": "Fever"}}))
    codes = sorted(c for c, _ in results)
    assert codes == [201, 409], results
    mine = client.get("/api/appointments", headers=world.doctor).json()
    assert sum(1 for a in mine if a["scheduled_at"].startswith(when[:16])) == 1


def test_a_form_sent_eight_times_at_once_creates_one_record(client, world):
    body = {"patient_id": world.patient_id, "doctor_id": world.doctor_id, "scheduled_at": future(96), "reason": "Checkup"}
    results = race(8, lambda i: ("post", "/api/appointments", {"headers": world.employee, "json": body}))
    assert [c for c, _ in results].count(201) == 1, results
    assert all(c in (201, 409) for c, _ in results), results                    # the others get a clear conflict, never a 500


def test_registering_the_same_email_at_the_same_moment_creates_one_account(client, world):
    body = {"email": "dup@example.com", "full_name": "Dup Person", "password": PASSWORD, "gender": "male", "date_of_birth": "1991-01-01", "phone": "9876500002"}
    results = race(6, lambda i: ("post", "/api/patients", {"headers": world.employee, "json": body}))
    assert [c for c, _ in results].count(201) == 1, results
    assert all(c in (201, 409, 422) for c, _ in results), results


def test_two_admins_editing_the_same_person_at_once_never_crash_and_leave_one_of_the_two_versions(client, world):
    client.post("/api/admin/employees", headers=world.admin, json={"email": "admin2@hospital.example.com", "full_name": "Second Admin", "password": PASSWORD, "designation": "Manager"})
    uid = next(p["id"] for p in client.get("/api/admin/people", headers=world.admin).json() if p["email"] == "priya@hospital.example.com")
    names = ["Priya Joshi One", "Priya Joshi Two"]
    results = race(2, lambda i: ("put", f"/api/admin/users/{uid}", {"headers": world.admin, "json": {"full_name": names[i]}}))
    assert all(c in (200, 409) for c, _ in results), results
    final = next(p for p in client.get("/api/admin/people", headers=world.admin).json() if p["id"] == uid)
    assert final["full_name"] in names


def test_two_doctors_saving_the_same_consultation_at_once_never_crash(client, world):
    visit = client.post("/api/opd/walk-in", headers=world.employee, json={"patient_id": world.patient_id, "doctor_id": world.doctor_id})
    assert visit.status_code in (200, 201), visit.text
    eid = visit.json()["encounter_id"]
    notes = ["Fever for two days", "Cough for a week"]
    results = race(2, lambda i: ("put", f"/api/opd/encounters/{eid}/consultation", {"headers": world.doctor, "json": {"complaint": notes[i], "assessment": "Viral", "plan": "Rest"}}))
    assert all(c in (200, 409) for c, _ in results), results
    saved = client.get(f"/api/opd/encounters/{eid}", headers=world.doctor)
    if saved.status_code == 200:
        assert (saved.json().get("consultation") or saved.json()).get("complaint", notes[0]) in notes


def test_an_appointment_cannot_be_moved_onto_a_time_the_doctor_already_has(client, world):
    p2 = second_patient(client, world)
    a = client.post("/api/appointments", headers=world.employee, json={"patient_id": world.patient_id, "doctor_id": world.doctor_id, "scheduled_at": future(120), "reason": "A"}).json()
    b = client.post("/api/appointments", headers=world.employee, json={"patient_id": p2, "doctor_id": world.doctor_id, "scheduled_at": future(121), "reason": "B"}).json()
    clash = client.put(f"/api/appointments/{b['id']}", headers=world.employee, json={"scheduled_at": a["scheduled_at"]})
    assert clash.status_code == 409, clash.text
    assert client.put(f"/api/appointments/{b['id']}", headers=world.employee, json={"scheduled_at": future(130)}).status_code == 200      # a free time is fine
    assert client.put(f"/api/appointments/{a['id']}", headers=world.employee, json={"status": "CANCELLED"}).status_code == 200
    c = client.post("/api/appointments", headers=world.employee, json={"patient_id": p2, "doctor_id": world.doctor_id, "scheduled_at": a["scheduled_at"], "reason": "C"})
    assert c.status_code == 201                                                                         # a cancelled slot is free again
    revive = client.put(f"/api/appointments/{a['id']}", headers=world.employee, json={"status": "SCHEDULED"})
    assert revive.status_code == 409, revive.text                                                        # the cancelled one cannot come back onto the taken slot
