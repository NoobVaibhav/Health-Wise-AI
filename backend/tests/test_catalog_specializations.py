"""Department -> Specialization catalog: the lists, who may change them, the rules for a doctor's choice, and the start-up migration."""
from sqlalchemy import text

from app.database import connection
from app.database.connection import SessionLocal
from app.database.models import Department, Doctor, Specialization
from app.services import catalog_service
from tests.conftest import PASSWORD, login


def departments(client, auth, **params):
    return client.get("/api/catalog/departments", headers=auth, params=params).json()


def specializations(client, auth, **params):
    return client.get("/api/catalog/specializations", headers=auth, params=params).json()


def department_id(client, auth, name):
    return next(d["id"] for d in departments(client, auth) if d["name"] == name)


def new_doctor(client, world, email="new.doctor@hospital.example.com", **extra):
    return client.post("/api/admin/doctors", headers=world.admin, json={"email": email, "full_name": "Dr New Doctor", "password": PASSWORD, **extra})


# ------------------------------------------------------------------ the lists
def test_default_list_is_seeded_and_every_department_has_a_specialization(client, world):
    names = [d["name"] for d in departments(client, world.admin)]
    for expected in ("General Medicine", "Cardiology", "Neurology", "Orthopedics", "Pediatrics", "Gynecology & Obstetrics", "Dermatology", "ENT",
                     "Ophthalmology", "Psychiatry", "Pulmonology", "Gastroenterology", "Nephrology", "Urology", "Endocrinology", "Oncology",
                     "Dentistry", "Radiology", "Pathology", "Emergency Medicine"):
        assert expected in names
    for d in departments(client, world.admin):
        assert specializations(client, world.admin, department_id=d["id"]), d["name"]


def test_specializations_are_filtered_by_department(client, world):
    cardiology = department_id(client, world.admin, "Cardiology")
    got = [s["name"] for s in specializations(client, world.admin, department_id=cardiology)]
    assert got == ["Cardiac Electrophysiologist", "Interventional Cardiologist"]
    assert specializations(client, world.admin, department_id=999999) == []


def test_every_signed_in_role_can_read_but_nobody_else(client, world):
    for who in (world.admin, world.doctor, world.employee, world.pharmacy, world.patient):
        assert client.get("/api/catalog/departments", headers=who).status_code == 200
        assert client.get("/api/catalog/specializations", headers=who).status_code == 200
    assert client.get("/api/catalog/departments").status_code == 401


def test_bad_department_id_in_the_query_is_422_not_500(client, world):
    for bad in ("abc", "-1", "0", "99999999999"):
        assert client.get("/api/catalog/specializations", headers=world.admin, params={"department_id": bad}).status_code == 422


# ------------------------------------------------------------------ who may change them
def test_only_the_admin_changes_the_lists(client, world):
    cardiology = department_id(client, world.admin, "Cardiology")
    for who in (world.doctor, world.employee, world.pharmacy, world.patient):
        assert client.post("/api/catalog/departments", headers=who, json={"name": "Genetics"}).status_code == 403
        assert client.put(f"/api/catalog/departments/{cardiology}", headers=who, json={"name": "Heart"}).status_code == 403
        assert client.patch(f"/api/catalog/departments/{cardiology}", headers=who, json={"is_active": False}).status_code == 403
        assert client.post("/api/catalog/specializations", headers=who, json={"name": "X-Ray", "department_id": cardiology}).status_code == 403
    assert client.post("/api/catalog/departments", json={"name": "Genetics"}).status_code == 401


def test_admin_adds_renames_and_deactivates(client, world):
    made = client.post("/api/catalog/departments", headers=world.admin, json={"name": "  Genetics  "})
    assert made.status_code == 201 and made.json()["name"] == "Genetics"
    dep = made.json()["id"]
    assert client.put(f"/api/catalog/departments/{dep}", headers=world.admin, json={"name": "Medical Genetics"}).json()["name"] == "Medical Genetics"
    spec = client.post("/api/catalog/specializations", headers=world.admin, json={"name": "Genetic Counsellor", "department_id": dep})
    assert spec.status_code == 201 and spec.json()["department_id"] == dep
    sid = spec.json()["id"]
    assert client.put(f"/api/catalog/specializations/{sid}", headers=world.admin, json={"name": "Genetic Counselor"}).json()["name"] == "Genetic Counselor"

    assert client.patch(f"/api/catalog/specializations/{sid}", headers=world.admin, json={"is_active": False}).json()["is_active"] is False
    assert sid not in [s["id"] for s in specializations(client, world.doctor, department_id=dep)]                       # hidden from the dropdowns
    assert sid in [s["id"] for s in specializations(client, world.admin, department_id=dep, include_inactive=True)]       # the admin still sees it
    assert sid not in [s["id"] for s in specializations(client, world.doctor, department_id=dep, include_inactive=True)]   # the flag is for the admin only
    client.patch(f"/api/catalog/departments/{dep}", headers=world.admin, json={"is_active": False})
    assert dep not in [d["id"] for d in departments(client, world.employee)]
    assert dep in [d["id"] for d in departments(client, world.admin, include_inactive=True)]


def test_names_are_checked(client, world):
    cardiology = department_id(client, world.admin, "Cardiology")
    for bad in ("", " ", "A", "x" * 101, "<b></b>", "<script>"):
        assert client.post("/api/catalog/departments", headers=world.admin, json={"name": bad}).status_code == 422, bad
        assert client.post("/api/catalog/specializations", headers=world.admin, json={"name": bad, "department_id": cardiology}).status_code == 422, bad
    assert "<" not in client.post("/api/catalog/departments", headers=world.admin, json={"name": "Sleep <b>Medicine</b>"}).json()["name"]
    assert client.post("/api/catalog/departments", headers=world.admin, json={"name": 5}).status_code == 422


def test_duplicates_are_refused_ignoring_case(client, world):
    cardiology = department_id(client, world.admin, "Cardiology")
    assert client.post("/api/catalog/departments", headers=world.admin, json={"name": "CARDIOLOGY"}).status_code == 409
    assert client.post("/api/catalog/specializations", headers=world.admin,
                       json={"name": " interventional   cardiologist ", "department_id": cardiology}).status_code == 409
    neurology = department_id(client, world.admin, "Neurology")                              # the same name in another department is fine
    assert client.post("/api/catalog/specializations", headers=world.admin, json={"name": "Interventional Cardiologist", "department_id": neurology}).status_code == 201
    other = client.post("/api/catalog/departments", headers=world.admin, json={"name": "Genetics"}).json()["id"]
    assert client.put(f"/api/catalog/departments/{other}", headers=world.admin, json={"name": "cardiology"}).status_code == 409
    assert client.put(f"/api/catalog/departments/{other}", headers=world.admin, json={"name": "GENETICS"}).status_code == 200        # its own name, other case


def test_unknown_ids_are_404_or_422_never_500(client, world):
    assert client.put("/api/catalog/departments/999999", headers=world.admin, json={"name": "Nothing"}).status_code == 404
    assert client.patch("/api/catalog/specializations/999999", headers=world.admin, json={"is_active": False}).status_code == 404
    assert client.post("/api/catalog/specializations", headers=world.admin, json={"name": "Nothing", "department_id": 999999}).status_code == 404
    assert client.put("/api/catalog/departments/abc", headers=world.admin, json={"name": "Nothing"}).status_code == 422


# ------------------------------------------------------------------ the choice on a doctor
def test_doctor_is_created_with_a_department_and_a_specialization(client, world):
    cardiology = department_id(client, world.admin, "Cardiology")
    spec = specializations(client, world.admin, department_id=cardiology)[0]
    res = new_doctor(client, world, department_id=cardiology, specialization_id=spec["id"])
    assert res.status_code == 201, res.text
    listed = next(d for d in client.get("/api/doctors", headers=world.employee).json() if d["full_name"] == "Dr New Doctor")
    assert (listed["department_name"], listed["specialization_name"], listed["specialization_id"]) == ("Cardiology", spec["name"], spec["id"])


def test_specialization_from_another_department_is_422(client, world):
    cardiology = department_id(client, world.admin, "Cardiology")
    neuro = specializations(client, world.admin, department_id=department_id(client, world.admin, "Neurology"))[0]
    res = new_doctor(client, world, department_id=cardiology, specialization_id=neuro["id"])
    assert res.status_code == 422 and "does not belong" in res.json()["detail"]


def test_specialization_without_a_department_is_422(client, world):
    spec = specializations(client, world.admin)[0]
    res = new_doctor(client, world, specialization_id=spec["id"])
    assert res.status_code == 422 and "department" in res.json()["detail"].lower()


def test_unknown_ids_on_a_doctor_are_422_not_500(client, world):
    cardiology = department_id(client, world.admin, "Cardiology")
    assert new_doctor(client, world, department_id=999999).status_code == 422
    assert new_doctor(client, world, email="b@hospital.example.com", department_id=cardiology, specialization_id=999999).status_code == 422
    for bad in (0, -5, "abc", 10 ** 12, [], {}):
        assert new_doctor(client, world, email="c@hospital.example.com", department_id=bad).status_code == 422
        assert new_doctor(client, world, email="d@hospital.example.com", department_id=cardiology, specialization_id=bad).status_code == 422


def test_inactive_department_or_specialization_cannot_be_chosen_for_a_new_doctor(client, world):
    cardiology = department_id(client, world.admin, "Cardiology")
    spec = specializations(client, world.admin, department_id=cardiology)[0]
    client.patch(f"/api/catalog/specializations/{spec['id']}", headers=world.admin, json={"is_active": False})
    assert new_doctor(client, world, department_id=cardiology, specialization_id=spec["id"]).status_code == 422
    client.patch(f"/api/catalog/departments/{cardiology}", headers=world.admin, json={"is_active": False})
    assert new_doctor(client, world, email="e@hospital.example.com", department_id=cardiology).status_code == 422


def test_admin_edits_a_doctors_choice_and_a_deactivated_choice_is_kept(client, world):
    cardiology = department_id(client, world.admin, "Cardiology")
    spec = specializations(client, world.admin, department_id=cardiology)[0]
    other = specializations(client, world.admin, department_id=cardiology)[1]
    created = new_doctor(client, world, department_id=cardiology, specialization_id=spec["id"]).json()["user"]["id"]
    assert client.put(f"/api/admin/users/{created}", headers=world.admin, json={"department_id": cardiology, "specialization_id": other["id"]}).status_code == 200
    client.patch(f"/api/catalog/specializations/{other['id']}", headers=world.admin, json={"is_active": False})
    # nothing is hard-deleted, so the doctor still shows the deactivated specialization
    doc = next(d for d in client.get("/api/doctors", headers=world.employee).json() if d["full_name"] == "Dr New Doctor")
    assert doc["specialization_name"] == other["name"]
    assert client.put(f"/api/admin/users/{created}", headers=world.admin, json={"department_id": cardiology, "specialization_id": other["id"]}).status_code == 200   # unchanged is fine
    neuro_spec = specializations(client, world.admin, department_id=department_id(client, world.admin, "Neurology"))[0]
    assert client.put(f"/api/admin/users/{created}", headers=world.admin, json={"department_id": cardiology, "specialization_id": neuro_spec["id"]}).status_code == 422
    employee_id = client.get("/api/admin/people?role=EMPLOYEE", headers=world.admin).json()[0]["id"]
    assert client.put(f"/api/admin/users/{employee_id}", headers=world.admin, json={"department_id": cardiology}).status_code == 422


def test_the_doctors_profile_and_people_list_show_the_names(client, world):
    cardiology = department_id(client, world.admin, "Cardiology")
    spec = specializations(client, world.admin, department_id=cardiology)[0]
    new_doctor(client, world, department_id=cardiology, specialization_id=spec["id"])
    me = login(client, "new.doctor@hospital.example.com")
    fields = {f["key"]: f for f in client.get("/api/profile", headers=me).json()["fields"]}
    assert fields["specialization"]["value"] == spec["name"] and fields["department"]["value"] == "Cardiology"
    assert fields["specialization"]["editable"] is False and fields["department"]["editable"] is False            # set by the admin, as before


# ------------------------------------------------------------------ the migration
def test_old_free_text_is_matched_by_name_ignoring_case_and_the_rest_is_kept_as_legacy(client, world):
    cardiology = department_id(client, world.admin, "Cardiology")
    new_doctor(client, world, email="match@hospital.example.com", department_id=cardiology, specialization="interventional CARDIOLOGIST")
    new_doctor(client, world, email="legacy@hospital.example.com", department_id=cardiology, specialization="Homeopathy Advisor")
    docs = {d["id"]: d for d in client.get("/api/doctors", headers=world.employee).json()}
    matched = [d for d in docs.values() if d["specialization_name"] == "Interventional Cardiologist"]
    assert len(matched) == 1 and matched[0]["specialization_id"] is not None
    legacy = [d for d in docs.values() if d["specialization_name"] == "Homeopathy Advisor"]
    assert len(legacy) == 1 and legacy[0]["specialization_id"] is None                          # kept as the old text ("Other (legacy)")


def test_startup_migration_adds_the_table_and_column_without_losing_data_and_is_idempotent(client, world):
    # the anjali doctor of the fixture has the old text "Physician": it matches nothing, so it stays as text
    with SessionLocal() as db:
        before_specs = db.query(Specialization).count()
        before_departments = db.query(Department).count()
        old = db.query(Doctor).filter(Doctor.specialization == "Physician").one()
        assert old.specialization_id is None
    # simulate a database from before this feature: drop the new column's table and the flag column
    with connection.engine.begin() as c:
        c.execute(text("UPDATE doctors SET specialization_id = NULL"))
        c.execute(text("DELETE FROM specializations"))
    connection.init_db()
    connection.init_db()                                                                      # twice: nothing is duplicated
    with SessionLocal() as db:
        assert db.query(Specialization).count() == before_specs
        assert db.query(Department).count() == before_departments
        assert db.query(Doctor).filter(Doctor.specialization == "Physician").count() == 1    # the old row and its text survive
    assert departments(client, world.admin)                                                  # the dropdown still has its data


def test_seed_does_not_run_again_when_the_admin_already_has_specializations(client, world):
    cardiology = department_id(client, world.admin, "Cardiology")
    sid = specializations(client, world.admin, department_id=cardiology)[0]["id"]
    client.patch(f"/api/catalog/specializations/{sid}", headers=world.admin, json={"is_active": False})
    with SessionLocal() as db:
        catalog_service.ensure_catalog(db)
    assert sid not in [s["id"] for s in specializations(client, world.admin, department_id=cardiology)]                     # not switched back on
    assert sid in [s["id"] for s in specializations(client, world.admin, department_id=cardiology, include_inactive=True)]
