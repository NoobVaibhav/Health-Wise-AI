"""Admin deletes a user: only an account with nothing linked to it can go; everything else must be deactivated. Synthetic data only."""
from app.database.connection import SessionLocal
from app.database.models import AuditLog, Patient, PatientAssistantConversation, User
from tests.conftest import PASSWORD, login
from tests.test_patient_assistant import add_report, report


def new_patient(client, world, email="lyu@example.com"):
    r = client.post("/api/patients", headers=world.employee, json={"email": email, "full_name": "Lyu Bochka"})
    assert r.status_code == 201, r.text
    return r.json()["patient"]["id"], r.json()["temporary_password"]


def user_id_of(email):
    with SessionLocal() as db:
        return db.query(User).filter_by(email=email).one().id


def test_an_account_made_by_mistake_can_be_deleted_completely(client, world):
    pid, password = new_patient(client, world)
    uid = user_id_of("lyu@example.com")
    ok = client.get(f"/api/admin/users/{uid}/delete-check", headers=world.admin).json()
    assert ok["can_delete"] is True and ok["reasons"] == []
    done = client.delete(f"/api/admin/users/{uid}", headers=world.admin)
    assert done.status_code == 200 and done.json()["email"] == "lyu@example.com" and done.json()["role"] == "PATIENT"
    with SessionLocal() as db:
        assert db.get(User, uid) is None and db.get(Patient, pid) is None                         # the account and the patient record are gone
        entry = db.query(AuditLog).filter_by(action="USER_DELETED").one()
        assert "lyu@example.com" in entry.details and "PATIENT" in entry.details                  # and the deletion is recorded
    assert client.post("/api/auth/login", json={"email": "lyu@example.com", "password": password}).status_code == 401
    assert client.get("/api/admin/users", headers=world.admin).json() and all(u["email"] != "lyu@example.com" for u in client.get("/api/admin/users", headers=world.admin).json())
    assert client.delete(f"/api/admin/users/{uid}", headers=world.admin).status_code == 404          # already gone
    # the email can be registered again
    assert client.post("/api/patients", headers=world.employee, json={"email": "lyu@example.com", "full_name": "Lyu Again"}).status_code == 201


def test_a_patient_with_records_cannot_be_deleted_only_deactivated(client, world):
    add_report(client, world, "r.txt", report("03/07/2026", "Hemoglobin 12.1 g/dL 13.0 - 17.0"))
    uid = user_id_of("rahul@example.com")
    check = client.get(f"/api/admin/users/{uid}/delete-check", headers=world.admin).json()
    assert check["can_delete"] is False and "reports" in check["reasons"][0] and "Deactivate it instead" in check["reasons"][0]
    refused = client.delete(f"/api/admin/users/{uid}", headers=world.admin)
    assert refused.status_code == 409 and "Deactivate it instead" in refused.json()["detail"]
    with SessionLocal() as db:
        assert db.get(User, uid) is not None and db.query(Patient).filter_by(user_id=uid).count() == 1     # nothing was removed
    assert client.put(f"/api/admin/users/{uid}", headers=world.admin, json={"is_active": False}).status_code == 200     # deactivating is the way
    assert client.get("/api/patient/dashboard", headers=world.patient).status_code == 401


def test_staff_with_activity_cannot_be_deleted_but_an_unused_staff_account_can(client, world):
    assert client.delete(f"/api/admin/users/{user_id_of('anjali@hospital.example.com')}", headers=world.admin).status_code == 409      # patients are assigned to this doctor
    add_report(client, world, "r.txt", report("03/07/2026", "Hemoglobin 12.1 g/dL 13.0 - 17.0"))
    assert client.delete(f"/api/admin/users/{user_id_of('priya@hospital.example.com')}", headers=world.admin).status_code == 409        # uploaded a report
    spare = client.post("/api/admin/employees", headers=world.admin, json={"email": "spare@hospital.example.com", "full_name": "Spare Clerk"}).json()["user"]["id"]
    assert client.delete(f"/api/admin/users/{spare}", headers=world.admin).status_code == 200
    doctor = client.post("/api/admin/doctors", headers=world.admin, json={"email": "newdoc@hospital.example.com", "full_name": "Dr. New", "department_id": world.department_id}).json()["user"]["id"]
    assert client.delete(f"/api/admin/users/{doctor}", headers=world.admin).status_code == 200                                         # a doctor with no patients or records


def test_an_account_that_only_logged_in_and_chatted_can_be_deleted(client, world):
    pid, password = new_patient(client, world, "chat@example.com")
    first = client.post("/api/auth/login", json={"email": "chat@example.com", "password": password}).json()
    me = {"Authorization": f"Bearer {first['access_token']}"}
    assert client.post("/api/auth/change-password", headers=me, json={"current_password": password, "new_password": "OwnPass1234"}).status_code == 200
    fresh = login(client, "chat@example.com", "OwnPass1234")
    assert client.post("/api/patient-assistant/chat", headers=fresh, json={"message": "hello"}).status_code == 200
    uid = user_id_of("chat@example.com")
    assert client.delete(f"/api/admin/users/{uid}", headers=world.admin).status_code == 200                                            # the chat belongs to the patient and goes with it
    with SessionLocal() as db:
        assert db.query(PatientAssistantConversation).filter_by(patient_id=pid).count() == 0
        assert db.query(AuditLog).filter_by(action="LOGIN").count() > 0 and db.query(AuditLog).filter(AuditLog.user_id == uid).count() == 0      # the audit trail stays, without the link


def test_safeguards_and_permissions(client, world):
    admin_id = user_id_of("admin@hospital.example.com")
    own = client.delete(f"/api/admin/users/{admin_id}", headers=world.admin)
    assert own.status_code == 409 and "cannot delete your own account" in own.json()["detail"]
    other_admin = client.post("/api/admin/employees", headers=world.admin, json={"email": "tmp@hospital.example.com", "full_name": "Tmp"}).json()["user"]["id"]
    for who in (world.doctor, world.employee, world.patient, world.pharmacy):
        assert client.delete(f"/api/admin/users/{other_admin}", headers=who).status_code == 403
        assert client.get(f"/api/admin/users/{other_admin}/delete-check", headers=who).status_code == 403
    assert client.delete(f"/api/admin/users/{other_admin}").status_code == 401
    assert client.delete("/api/admin/users/99999", headers=world.admin).status_code == 404
    assert client.delete("/api/admin/users/99999999999999999999", headers=world.admin).status_code in (404, 422)
    # an administrator can delete another administrator only while one active administrator remains
    second = client.post("/api/admin/employees", headers=world.admin, json={"email": "second@hospital.example.com", "full_name": "Second Admin"}).json()["user"]["id"]
    with SessionLocal() as db:
        db.get(User, second).role = "ADMIN"
        db.commit()
    assert client.delete(f"/api/admin/users/{second}", headers=world.admin).status_code == 200
    with SessionLocal() as db:
        assert db.get(User, admin_id) is not None
