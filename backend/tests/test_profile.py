"""My profile for every role: details, editable fields, and the profile picture."""
import io

from PIL import Image

from tests.conftest import login


def png(width=600, height=400, color=(200, 30, 30), mode="RGB", fmt="PNG"):
    buffer = io.BytesIO()
    Image.new(mode, (width, height), color).save(buffer, fmt)
    return buffer.getvalue()


def upload(client, who, content, name="me.png", kind="image/png"):
    return client.post("/api/profile/avatar", headers=who, files={"file": (name, content, kind)})


def all_roles(world):
    return {"ADMIN": world.admin, "DOCTOR": world.doctor, "EMPLOYEE": world.employee, "PATIENT": world.patient,
            "PHARMACY": world.pharmacy}


def test_every_role_has_a_profile_with_its_own_details(client, world):
    for role, who in all_roles(world).items():
        r = client.get("/api/profile", headers=who)
        assert r.status_code == 200, (role, r.text)
        body = r.json()
        assert body["user"]["role"] == role and body["user"]["role_label"] and body["user"]["has_avatar"] is False
        assert body["user"]["created_at"]
    doctor = {f["key"]: f for f in client.get("/api/profile", headers=world.doctor).json()["fields"]}
    assert doctor["specialization"]["value"] == "Physician" and doctor["specialization"]["editable"] is False
    assert doctor["qualification"]["editable"] is True
    patient = {f["key"]: f for f in client.get("/api/profile", headers=world.patient).json()["fields"]}
    assert patient["patient_code"]["value"] and patient["patient_code"]["editable"] is False
    assert patient["allergies"]["editable"] is False and patient["phone"]["editable"] is True


def test_a_person_can_edit_only_their_own_contact_and_professional_details(client, world):
    r = client.put("/api/profile", headers=world.doctor, json={
        "full_name": "  Dr.  Anjali   Sharma  ", "values": {"phone": "+91 98765 43210", "qualification": "MBBS, MD", "experience_years": 12}})
    assert r.status_code == 200, r.text
    assert r.json()["user"]["full_name"] == "Dr. Anjali Sharma"
    fields = {f["key"]: f["value"] for f in r.json()["fields"]}
    assert fields["phone"] == "9876543210" and fields["qualification"] == "MBBS, MD" and fields["experience_years"] == 12
    # the new name is what the app shows from now on
    assert client.get("/api/auth/me", headers=world.doctor).json()["full_name"] == "Dr. Anjali Sharma"

    # things the hospital assigns, or the doctor decides, cannot be changed from the profile
    for key in ("specialization", "department", "email", "role"):
        assert client.put("/api/profile", headers=world.doctor, json={"values": {key: "x"}}).status_code == 422
    assert client.put("/api/profile", headers=world.patient, json={"values": {"allergies": "none", "assigned_doctor": "x"}}).status_code == 422
    assert client.put("/api/profile", headers=world.patient, json={"values": {"phone": "9876543210", "address": "Pune"}}).status_code == 200

    # checks
    assert client.put("/api/profile", headers=world.doctor, json={"values": {"phone": "abc"}}).status_code == 422
    assert client.put("/api/profile", headers=world.doctor, json={"values": {"experience_years": 200}}).status_code == 422
    assert client.put("/api/profile", headers=world.doctor, json={"full_name": "A"}).status_code == 422
    assert client.put("/api/profile", headers=world.admin, json={"values": {"phone": "9876543210"}}).status_code == 422  # admin has none
    assert client.put("/api/profile", headers=world.admin, json={"full_name": "Admin Two"}).status_code == 200
    assert client.put("/api/profile", json={"values": {}}).status_code == 401


def test_profile_picture_is_checked_resized_and_replaced(client, world):
    r = upload(client, world.doctor, png(1200, 800))
    assert r.status_code == 200, r.text
    first = r.json()["user"]
    assert first["has_avatar"] is True and first["avatar_version"]
    assert client.get("/api/auth/me", headers=world.doctor).json()["has_avatar"] is True

    shown = client.get(f"/api/profile/avatar/{first['id']}", headers=world.doctor)
    assert shown.status_code == 200 and shown.headers["content-type"] == "image/jpeg"
    picture = Image.open(io.BytesIO(shown.content))
    assert picture.size == (256, 256)                                    # cropped square and resized

    second = upload(client, world.doctor, png(300, 300, (10, 10, 200), fmt="JPEG"), "x.jpg", "image/jpeg").json()["user"]
    assert second["avatar_version"] != first["avatar_version"]          # browsers will reload it
    transparent = upload(client, world.doctor, png(50, 50, (0, 0, 0, 0), mode="RGBA")).json()
    assert transparent["user"]["has_avatar"] is True                      # transparent PNG is accepted

    removed = client.delete("/api/profile/avatar", headers=world.doctor)
    assert removed.json()["user"]["has_avatar"] is False
    assert client.get(f"/api/profile/avatar/{first['id']}", headers=world.doctor).status_code == 404


def test_bad_pictures_are_refused(client, world):
    assert upload(client, world.doctor, b"not a picture", "a.png").status_code == 422
    assert upload(client, world.doctor, b"", "a.png").status_code == 422
    assert upload(client, world.doctor, b"<?php echo 1; ?>", "shell.png", "image/png").status_code == 422   # name and type are not trusted
    gif = io.BytesIO()
    Image.new("RGB", (10, 10)).save(gif, "GIF")
    assert upload(client, world.doctor, gif.getvalue(), "a.gif", "image/gif").status_code == 422             # only JPG, PNG, WEBP
    assert upload(client, world.doctor, png() + b"0" * (5 * 1024 * 1024), "big.png").status_code == 413
    assert client.get("/api/auth/me", headers=world.doctor).json()["has_avatar"] is False
    assert client.post("/api/profile/avatar", files={"file": ("a.png", png(), "image/png")}).status_code == 401


def test_who_may_see_a_picture(client, world):
    patient_id = client.get("/api/profile", headers=world.patient).json()["user"]["id"]
    doctor_id = client.get("/api/profile", headers=world.doctor).json()["user"]["id"]
    upload(client, world.patient, png())
    upload(client, world.doctor, png())
    get = lambda who, uid: client.get(f"/api/profile/avatar/{uid}", headers=who).status_code
    # a patient's picture: the patient, the admin, doctors and employees
    assert [get(w, patient_id) for w in (world.patient, world.admin, world.doctor, world.employee)] == [200, 200, 200, 200]
    assert get(world.pharmacy, patient_id) == 403
    other_patient = client.post("/api/patients", headers=world.employee, json={
        "email": "asha@example.com", "full_name": "Asha Kulkarni", "password": "StrongPass123", "gender": "female",
        "date_of_birth": "1990-01-01", "phone": "9999999998", "assigned_doctor_id": world.doctor_id})
    assert other_patient.status_code == 201, other_patient.text
    assert get(login(client, "asha@example.com"), patient_id) == 403          # another patient cannot see it
    # a staff picture is visible to anyone who is logged in
    assert get(world.patient, doctor_id) == 200 and get(world.pharmacy, doctor_id) == 200
    assert client.get(f"/api/profile/avatar/{doctor_id}").status_code == 401   # but never without logging in
    assert client.get("/api/profile/avatar/99999", headers=world.admin).status_code == 404


def test_people_list_tells_which_people_have_a_picture(client, world):
    upload(client, world.doctor, png())
    people = client.get("/api/admin/people", params={"role": "DOCTOR"}, headers=world.admin).json()
    flags = {p["full_name"]: p["has_avatar"] for p in people}
    assert flags["Dr. Anjali Sharma"] is True and flags["Dr. Other Doctor"] is False
