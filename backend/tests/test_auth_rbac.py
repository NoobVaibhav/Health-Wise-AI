"""Authentication and role-based access control."""
from tests.conftest import PASSWORD, headers, login, upload
from tests import sample_data as sd


def test_first_admin_only_once(client):
    assert client.get("/api/auth/setup-status").json()["needs_setup"] is True
    body = {"email": "a@example.com", "full_name": "Admin", "password": PASSWORD}
    assert client.post("/api/auth/register", json=body).status_code == 201
    assert client.get("/api/auth/setup-status").json()["needs_setup"] is False
    body["email"] = "b@example.com"
    assert client.post("/api/auth/register", json=body).status_code == 403  # public sign-up is closed


def test_login_me_and_invalid_login(client, world):
    me = client.get("/api/auth/me", headers=world.doctor).json()
    assert me["role"] == "DOCTOR" and me["full_name"] == "Dr. Anjali Sharma"
    wrong = client.post("/api/auth/login", json={"email": "anjali@hospital.example.com", "password": "WrongPass999"})
    unknown = client.post("/api/auth/login", json={"email": "nobody@hospital.example.com", "password": PASSWORD})
    assert wrong.status_code == 401 and unknown.status_code == 401
    assert wrong.json()["detail"] == unknown.json()["detail"]


def test_passwords_are_hashed(client, world):
    from app.database.connection import SessionLocal
    from app.database.models import User
    with SessionLocal() as db:
        user = db.query(User).filter_by(email="anjali@hospital.example.com").one()
        assert user.password_hash != PASSWORD and user.password_hash.startswith("$2")


def test_private_endpoints_need_a_token(client, world):
    for path in ("/api/dashboard", "/api/reports", "/api/patients", "/api/appointments", "/api/prescriptions"):
        assert client.get(path).status_code == 401
    assert client.get("/api/reports", headers=headers("garbage")).status_code == 401


def test_generated_password_is_returned_once_and_must_be_changed(client, world):
    created = client.post("/api/admin/employees", headers=world.admin,
                          json={"email": "new@hospital.example.com", "full_name": "New Employee"}).json()
    temp = created["temporary_password"]
    assert temp and created["user"]["must_change_password"] is True
    auth = login(client, "new@hospital.example.com", temp)
    changed = client.post("/api/auth/change-password", headers=auth,
                          json={"current_password": temp, "new_password": "BrandNewPass99"})
    assert changed.status_code == 200
    assert client.get("/api/auth/me", headers=auth).json()["must_change_password"] is False
    assert client.post("/api/auth/login", json={"email": "new@hospital.example.com", "password": temp}).status_code == 401


def test_deactivated_user_cannot_log_in(client, world):
    users = client.get("/api/admin/users?role=EMPLOYEE", headers=world.admin).json()
    employee_id = users[0]["id"]
    assert client.put(f"/api/admin/users/{employee_id}", headers=world.admin, json={"is_active": False}).status_code == 200
    assert client.post("/api/auth/login", json={"email": "priya@hospital.example.com", "password": PASSWORD}).status_code == 403
    assert client.get("/api/auth/me", headers=world.employee).status_code == 401  # old token stops working too


def test_admin_cannot_deactivate_self(client, world):
    me = client.get("/api/auth/me", headers=world.admin).json()
    assert client.put(f"/api/admin/users/{me['id']}", headers=world.admin, json={"is_active": False}).status_code == 400


def test_only_admin_manages_staff_and_audit(client, world):
    body = {"email": "x@hospital.example.com", "full_name": "Someone"}
    for who in (world.doctor, world.employee, world.patient, world.pharmacy):
        assert client.post("/api/admin/doctors", headers=who, json=body).status_code == 403
        assert client.get("/api/admin/audit-logs", headers=who).status_code == 403
        assert client.get("/api/admin/dashboard", headers=who).status_code == 403
    assert client.post("/api/admin/doctors", headers=world.admin, json=body).status_code == 201
    assert client.post("/api/admin/doctors", headers=world.admin, json=body).status_code == 409  # duplicate email


def test_permission_message(client, world):
    response = client.get("/api/admin/dashboard", headers=world.patient)
    assert response.status_code == 403
    assert response.json()["detail"] == "You do not have permission to access this information."


def test_role_matrix_on_core_endpoints(client, world):
    pdf = sd.lines_to_pdf(sd.REPORT_A_LINES)
    # uploads: employee and doctor only
    assert upload(client, world.patient, world.patient_id, "a.pdf", pdf).status_code == 403
    assert upload(client, world.pharmacy, world.patient_id, "a.pdf", pdf).status_code == 403
    assert upload(client, world.admin, world.patient_id, "a.pdf", pdf).status_code == 403
    # patient registration: employee and admin only
    new_patient = {"email": "n@example.com", "full_name": "New Patient"}
    assert client.post("/api/patients", headers=world.doctor, json=new_patient).status_code == 403
    assert client.post("/api/patients", headers=world.patient, json=new_patient).status_code == 403
    # pharmacy has no access to reports or patients lists
    assert client.get("/api/reports", headers=world.pharmacy).status_code == 403
    assert client.get("/api/patients", headers=world.pharmacy).status_code == 403
    # patient portal and doctor module are separate
    assert client.get("/api/doctor/dashboard", headers=world.patient).status_code == 403
    assert client.get("/api/patient/dashboard", headers=world.doctor).status_code == 403
    assert client.get("/api/pharmacy/dashboard", headers=world.doctor).status_code == 403
    assert client.get("/api/employee/dashboard", headers=world.doctor).status_code == 403


def test_people_list_and_readable_audit_labels(client, world):
    people = client.get("/api/admin/people?role=DOCTOR", headers=world.admin).json()
    anjali = next(p for p in people if p["full_name"] == "Dr. Anjali Sharma")
    assert ["Specialization", "Physician"] in anjali["details"] and ["Department", "General Medicine"] in anjali["details"]
    assert anjali["last_login"] is not None                     # she logged in during the world fixture
    patient = client.get("/api/admin/people?role=PATIENT", headers=world.admin).json()[0]
    assert ["Patient ID", "P-0001"] in patient["details"] and ["Doctor", "Dr. Anjali Sharma"] in patient["details"]
    assert [p["full_name"] for p in client.get("/api/admin/people?q=priya", headers=world.admin).json()] == ["Priya Joshi"]
    assert client.get("/api/admin/people", headers=world.doctor).status_code == 403

    upload(client, world.employee, world.patient_id, "a.pdf", sd.lines_to_pdf(sd.REPORT_A_LINES))
    logs = client.get("/api/admin/audit-logs?limit=500", headers=world.admin).json()
    uploaded = next(l for l in logs if l["action"] == "REPORT_UPLOADED")
    assert uploaded["entity_label"] == "a.pdf (patient Rahul Patil)" and uploaded["user_name"] == "Priya Joshi"
    created = next(l for l in logs if l["action"] == "PATIENT_CREATED")
    assert created["entity_label"] == "Rahul Patil"
