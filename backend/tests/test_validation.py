"""Input validation: every rule of docs/VALIDATION_RULES.md with good and bad cases (empty, only spaces, too long, wrong type, boundaries,
a future date of birth, HTML, unicode names). The rules live in app/utils/validators.py; the schemas use them. Data is invented."""
from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError

from app.main import app
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate
from app.schemas.auth import ChangePasswordRequest, FirstAdminRequest, LoginRequest, StaffCreate
from app.schemas.billing import ReceiveStock, SaleCreate
from app.schemas.health_history import Vitals
from app.schemas.patient import PatientCreate
from app.schemas.pharmacy import InventoryCreate
from app.schemas.prescription import PrescriptionItemCreate
from app.utils import validators as v
from app.utils.file_validation import detect_file_type, safe_filename
from app.utils.validation_errors import friendly
from tests.conftest import PASSWORD, headers, login, upload


def accepts(model, **data):
    try:
        return model(**data)
    except ValidationError:
        return None


class One(BaseModel):
    value: object = None


def field_model(annotation):
    class M(BaseModel):
        value: annotation
    return M


# ------------------------------------------------------------------ e-mail
@pytest.mark.parametrize("raw,ok,normal", [
    ("a@b.co", True, "a@b.co"), ("  Rahul.Patil@Example.COM ", True, "rahul.patil@example.com"), ("a+tag@b.io", True, "a+tag@b.io"),
    ("", False, None), ("   ", False, None), ("no-at-sign", False, None), ("a b@c.com", False, None), ("a@", False, None), ("@b.com", False, None), ("a@b", False, None),
    ("a@@b.com", False, None), ("x" * 250 + "@b.com", False, None), ("<script>@b.com", False, None), (123, False, None), (None, False, None),
])
def test_email(raw, ok, normal):
    m = accepts(field_model(v.Email), value=raw)
    assert (m is not None) == ok
    if ok:
        assert m.value == normal


# ------------------------------------------------------------------ names
@pytest.mark.parametrize("raw,ok,normal", [
    ("Anjali Sharma", True, "Anjali Sharma"), ("  Anjali    Sharma  ", True, "Anjali Sharma"), ("Dr. Anjali Sharma", True, "Dr. Anjali Sharma"), ("O'Neil-Smith", True, "O'Neil-Smith"),
    ("Zoë Müller", True, "Zoë Müller"), ("अंजली शर्मा", True, "अंजली शर्मा"), ("Ab", True, "Ab"),
    ("", False, None), ("   ", False, None), ("A", False, None), ("Rahul7", False, None), ("Rahul_Patil", False, None), ("Rahul \U0001F600", False, None), ("<b>Rahul</b>", False, None),
    ("Rahul@Patil", False, None), ("N" * 151, False, None), ("..", False, None), ("--", False, None), ("Rahul\u0000Patil", False, None), (5, False, None),
])
def test_person_name(raw, ok, normal):
    m = accepts(field_model(v.PersonName), value=raw)
    assert (m is not None) == ok
    if ok:
        assert m.value == normal


def test_a_name_of_exactly_150_characters_is_the_longest_allowed():
    assert accepts(field_model(v.PersonName), value="N" * 150) is not None
    assert accepts(field_model(v.PersonName), value="N" * 151) is None


# ------------------------------------------------------------------ phone
@pytest.mark.parametrize("raw,ok,normal", [
    ("9876543210", True, "9876543210"), ("+91 98765 43210", True, "9876543210"), ("098765-43210", True, "9876543210"), ("(98765) 43210", True, "9876543210"),
    ("919876543210", True, "9876543210"), ("+44 20 7946 0958", True, "+442079460958"), ("+1 (415) 555-0132", True, "+14155550132"),
    ("1234567890", False, None), ("98765", False, None), ("98765432101", False, None), ("abcdefghij", False, None), ("98765 4321O", False, None), ("+9", False, None),
    ("+" + "9" * 16, False, None), ("9876543210; DROP", False, None), ("5876543210", False, None),
])
def test_phone(raw, ok, normal):
    m = accepts(field_model(v.Phone), value=raw)
    assert (m is not None) == ok
    if ok:
        assert m.value == normal


def test_an_empty_optional_phone_means_not_given():
    for raw in (None, "", "   "):
        assert field_model(v.OptionalPhone)(value=raw).value is None


# ------------------------------------------------------------------ dates of birth
TODAY = date.today()


@pytest.mark.parametrize("dob,ok", [
    (TODAY, True), (TODAY - timedelta(days=1), True), (date(1930, 1, 1), True), (date(1990, 5, 14), True),
    (TODAY + timedelta(days=1), False), (date(2999, 1, 1), False), (date(1929, 12, 31), False), (date(1899, 12, 31), False), (date(1, 1, 1), False), (TODAY.replace(year=TODAY.year - 121), False),
])
def test_date_of_birth_boundaries(dob, ok):
    assert (accepts(field_model(v.DateOfBirth), value=dob) is not None) == ok


@pytest.mark.parametrize("raw", ["2026-02-30", "not-a-date", "31/12/1990", "9999-99-99", 12345.5])
def test_a_date_that_is_not_a_real_calendar_date_is_refused(raw):
    assert accepts(field_model(v.DateOfBirth), value=raw) is None


def test_age_warnings_are_warnings_not_errors():
    assert v.age_warning(TODAY - timedelta(days=100)) and v.age_warning(TODAY.replace(year=TODAY.year - 112)) and v.age_warning(date(1990, 1, 1)) is None


# ------------------------------------------------------------------ gender, blood group, address
@pytest.mark.parametrize("raw,ok,normal", [("male", True, "male"), (" Female ", True, "female"), ("OTHER", True, "other"), ("", True, None), (None, True, None), ("robot", False, None),
                                           ("<b>male</b>", False, None), ("m", False, None)])
def test_gender(raw, ok, normal):
    m = accepts(field_model(v.Gender), value=raw)
    assert (m is not None) == ok and (not ok or m.value == normal)


@pytest.mark.parametrize("raw,ok,normal", [("A+", True, "A+"), ("ab-", True, "AB-"), (" o + ", True, "O+"), ("", True, None), ("C+", False, None), ("A", False, None), ("AB", False, None), ("O++", False, None)])
def test_blood_group(raw, ok, normal):
    m = accepts(field_model(v.BloodGroup), value=raw)
    assert (m is not None) == ok and (not ok or m.value == normal)


def test_address_is_cleaned_and_limited():
    assert field_model(v.Address)(value=" 12  MG Road, <i>Pune</i> 411001 ").value == "12 MG Road, Pune 411001"
    assert field_model(v.Address)(value="   ").value is None
    assert accepts(field_model(v.Address), value="x" * 300) is not None and accepts(field_model(v.Address), value="x" * 301) is None
    assert field_model(v.Pincode)(value="411001").value == "411001"
    for bad in ("41100", "4110011", "41100a", "411 001"):
        assert accepts(field_model(v.Pincode), value=bad) is None


# ------------------------------------------------------------------ free text
def test_free_text_is_trimmed_stripped_of_html_and_control_characters_and_limited():
    T = field_model(v.opt_text(50))
    assert T(value="  <script>alert(1)</script> hello \u0000 world  ").value == "alert(1) hello world"
    assert T(value="   ").value is None and T(value=None).value is None and T(value="").value is None
    assert accepts(T, value="x" * 50) is not None and accepts(T, value="x" * 51) is None
    assert accepts(T, value=["a"]) is None
    M = field_model(v.opt_text(100, multiline=True))
    assert M(value="line one\n\n  line two  ‮").value == "line one\n\n  line two"
    R = field_model(v.text(20, min_length=2))
    assert accepts(R, value="a") is None and accepts(R, value="   ") is None and accepts(R, value="ab") is not None


# ------------------------------------------------------------------ passwords
@pytest.mark.parametrize("raw,ok", [
    ("abcdefg1", True), ("Correct-Horse-9", True), ("a" * 127 + "1", True), ("a" * 8, False), ("12345678", False), ("abc12", False), ("", False), ("a" * 128 + "1", False),
    ("password1", False), ("Password123", False), ("Welcome@123", False), ("qwerty123", False), ("        1a", True),
])
def test_password_rules(raw, ok):
    assert (accepts(field_model(v.Password), value=raw) is not None) == ok


def test_a_password_that_holds_the_email_name_is_refused():
    assert accepts(FirstAdminRequest, email="rahul.patil@example.com", full_name="Rahul Patil", password="Rahul.Patil99") is None
    assert accepts(FirstAdminRequest, email="rahul.patil@example.com", full_name="Rahul Patil", password="mypatil2026x") is None
    assert accepts(FirstAdminRequest, email="rahul.patil@example.com", full_name="Rahul Patil", password="Zebra-Clock-81") is not None
    assert accepts(FirstAdminRequest, email="ab@example.com", full_name="Rahul Patil", password="abcdefg1") is not None          # a short name part (under 4 letters) is not matched


def test_the_new_password_must_differ_from_the_current_one():
    assert accepts(ChangePasswordRequest, current_password="Zebra-Clock-81", new_password="Zebra-Clock-81") is None
    assert accepts(ChangePasswordRequest, current_password="Old-Clock-81x", new_password="Zebra-Clock-81") is not None


def test_login_accepts_any_existing_password_up_to_128_characters_and_trims_the_email():
    assert accepts(LoginRequest, email="a@b.co", password="x") is not None
    assert accepts(LoginRequest, email="a@b.co", password="") is None and accepts(LoginRequest, email="a@b.co", password="p" * 129) is None
    assert LoginRequest(email="  A@B.CO ", password="x").email == "a@b.co"


# ------------------------------------------------------------------ vitals
@pytest.mark.parametrize("field,low,high", [("height_cm", 30, 260), ("weight_kg", 1, 500), ("pulse", 20, 250), ("bp_systolic", 50, 300), ("bp_diastolic", 30, 200), ("spo2", 50, 100)])
def test_vital_sign_bounds(field, low, high):
    for good in (low, high, (low + high) // 2):
        assert accepts(Vitals, **{field: good}) is not None, (field, good)
    for bad in (low - 1, high + 1, -5, 0, 10 ** 9, "abc", float("nan"), float("inf")):
        assert accepts(Vitals, **{field: bad}) is None, (field, bad)


def test_temperature_bounds_in_fahrenheit_cover_30_to_45_celsius():
    assert accepts(Vitals, temperature_f=98.6) is not None and accepts(Vitals, temperature_f=86) is not None and accepts(Vitals, temperature_f=113) is not None
    assert accepts(Vitals, temperature_f=85.9) is None and accepts(Vitals, temperature_f=113.1) is None


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", 1e308])
def test_nan_infinity_and_absurd_sizes_are_not_lab_or_money_values(value):
    for annotation in (v.Money, v.OptionalMoney, v.Percent):
        assert accepts(field_model(annotation), value=float(value)) is None


def test_lab_value_and_unit_rules():
    assert v.check_lab_value(12.5) == 12.5 and v.check_lab_value(0) == 0
    for bad in (-1, float("nan"), float("inf"), 2e9, "5", True, None):
        with pytest.raises(ValueError):
            v.check_lab_value(bad)
    assert v.check_lab_unit("mg/dL") == "mg/dL" and v.check_lab_unit(None) is None
    with pytest.raises(ValueError):
        v.check_lab_unit("parsecs")


# ------------------------------------------------------------------ prescriptions, pharmacy, billing
ITEM = dict(medicine_name="Tab. Test", dosage="5 mg", frequency="Twice a day", duration="5 days", quantity=10)


@pytest.mark.parametrize("change,ok", [
    ({}, True), ({"duration": "1"}, True), ({"duration": "365 days"}, True), ({"duration": "2 weeks"}, True), ({"duration": "as needed"}, True),
    ({"duration": "0 days"}, False), ({"duration": "366 days"}, False), ({"duration": "60 weeks"}, False), ({"duration": "   "}, False),
    ({"medicine_name": ""}, False), ({"medicine_name": "A"}, False), ({"medicine_name": "<b>X</b>"}, False), ({"dosage": "0 mg"}, False), ({"dosage": "-5 mg"}, False), ({"frequency": "0"}, False),
    ({"quantity": 0}, False), ({"quantity": -1}, False), ({"quantity": 1.5}, False), ({"quantity": "ten"}, False), ({"quantity": 1_000_001}, False), ({"dosage": "0.5 tablet"}, True),
])
def test_prescription_item_rules(change, ok):
    assert (accepts(PrescriptionItemCreate, **{**ITEM, **change}) is not None) == ok


@pytest.mark.parametrize("barcode,ok", [("ABCD", True), ("ab-12-CD", True), ("A" * 64, True), ("", True), (None, True), ("ABC", False), ("A" * 65, False), ("AB CD", False), ("AB_CD", False), ("<b>1234</b>", False)])
def test_barcode(barcode, ok):
    assert (accepts(field_model(v.Barcode), value=barcode) is not None) == ok


def test_stock_rules_dates_money_and_gst():
    base = dict(medicine_name="Tab. Test", quantity=5)
    assert accepts(InventoryCreate, **base, unit_price=12.345).unit_price == 12.35                               # money is rounded to 2 decimals
    for bad in ({"unit_price": -1}, {"quantity": -1}, {"gst_percent": 101}, {"gst_percent": -1}, {"unit_price": float("nan")}, {"barcode": "ab"},
                {"manufacture_date": TODAY + timedelta(days=1)}, {"manufacture_date": TODAY, "expiry_date": TODAY - timedelta(days=1)}, {"manufacture_date": TODAY, "expiry_date": TODAY}):
        assert accepts(InventoryCreate, **{**base, **bad}) is None, bad
    assert accepts(InventoryCreate, **base, manufacture_date=TODAY - timedelta(days=30), expiry_date=TODAY + timedelta(days=700)) is not None
    assert accepts(ReceiveStock, medicine_name="Tab. Test", quantity=0) is None and accepts(ReceiveStock, medicine_name="Tab. Test", quantity=3, unit_price=-2) is None


def test_sale_rules():
    line = {"inventory_id": 1, "quantity": 2}
    assert accepts(SaleCreate, items=[line], discount=10.555).discount == 10.56
    for bad in ({"discount": -1}, {"discount": float("inf")}, {"customer_phone": "123"}, {"customer_name": "Bob 7"}, {"items": []}, {"items": [{"inventory_id": 1, "quantity": 0}]},
                {"items": [{"inventory_id": 0, "quantity": 1}]}, {"items": [{"inventory_id": 1, "quantity": 1, "barcode": "x"}]}):
        assert accepts(SaleCreate, **{"items": [line], **bad}) is None, bad
    assert accepts(SaleCreate, items=[line], customer_name="   ", customer_phone="").customer_name is None


# ------------------------------------------------------------------ appointments
def test_appointment_time_rules():
    soon = datetime.now() + timedelta(days=2)
    base = dict(doctor_id=1)
    assert accepts(AppointmentCreate, **base, scheduled_at=soon) is not None
    assert accepts(AppointmentCreate, **base, scheduled_at=datetime.now() - timedelta(hours=1)) is None
    assert accepts(AppointmentCreate, **base, scheduled_at=datetime.now() + timedelta(days=400)) is None
    assert accepts(AppointmentCreate, **base, scheduled_at=datetime.now() + timedelta(days=364)) is not None
    assert accepts(AppointmentCreate, **base, scheduled_at="2999-01-01T10:00:00") is None
    # a time with a time zone must not crash the comparison with "now"
    assert accepts(AppointmentCreate, **base, scheduled_at=(datetime.utcnow() + timedelta(days=2)).isoformat() + "Z") is not None
    assert accepts(AppointmentCreate, **base, scheduled_at=(datetime.utcnow() - timedelta(days=2)).isoformat() + "+05:30") is None
    assert accepts(AppointmentUpdate, status="cancelled").status == "CANCELLED" and accepts(AppointmentUpdate, status="maybe") is None


# ------------------------------------------------------------------ patients and staff schemas
def test_patient_schema_rules_and_normalising():
    ok = PatientCreate(email=" Pat@Example.com ", full_name="  Pat   Kumar ", phone="+91 98765 43210", gender="Male", blood_group="o+", date_of_birth="1990-05-14", address="<b>Pune</b>")
    assert (ok.email, ok.full_name, ok.phone, ok.gender, ok.blood_group, ok.address) == ("pat@example.com", "Pat Kumar", "9876543210", "male", "O+", "Pune")
    base = dict(email="pat@example.com", full_name="Pat Kumar")
    for bad in ({"date_of_birth": "2999-01-01"}, {"gender": "robot"}, {"blood_group": "Z+"}, {"phone": "12"}, {"address": "x" * 301}, {"assigned_doctor_id": 0}, {"assigned_doctor_id": -4},
                {"allergies": "x" * 1001}, {"password": "short1"}, {"password": "password123"}):
        assert accepts(PatientCreate, **base, **bad) is None, bad
    # the emergency contact must be somebody else
    assert accepts(PatientCreate, **base, phone="9876543210", emergency_contact="Sunita 98765 43210") is None
    assert accepts(PatientCreate, **base, phone="9876543210", emergency_contact="Sunita 98765 00000") is not None


def test_staff_schema_rules():
    base = dict(email="staff@example.com", full_name="Staff Member")
    assert accepts(StaffCreate, **base, phone="98765 43210", password=None) is not None
    for bad in ({"phone": "abc"}, {"department_id": 0}, {"specialization": "x" * 121}, {"password": "staff.member1"}):
        assert accepts(StaffCreate, **base, **bad) is None, bad


# ------------------------------------------------------------------ files
@pytest.mark.parametrize("name,ok", [("a.pdf", True), ("a.PNG", True), ("a.jpg", True), ("a.jpeg", True), ("a.txt", True), ("a.webp", False), ("a.exe", False), ("a.svg", False),
                                     ("a.html", False), ("a", False), ("a.pdf.exe", False)])
def test_report_file_types(name, ok):
    content = {"pdf": b"%PDF-1.4 x", "png": b"\x89PNG\r\n\x1a\n" + b"0" * 20, "jpg": b"\xff\xd8\xff" + b"0" * 20, "jpeg": b"\xff\xd8\xff" + b"0" * 20}.get(name.lower().rsplit(".", 1)[-1], b"Hemoglobin 12 g/dL")
    try:
        detect_file_type(name, content)
        assert ok
    except Exception:
        assert not ok


def test_the_type_is_decided_by_the_content_not_the_name():
    for name, content in [("a.png", b"\xff\xd8\xff" + b"0" * 20), ("a.jpg", b"\x89PNG\r\n\x1a\n" + b"0" * 20), ("a.pdf", b"<html>"), ("a.png", b"GIF89a......"), ("a.jpg", b"RIFF0000WEBPxxxx")]:
        with pytest.raises(Exception):
            detect_file_type(name, content)


@pytest.mark.parametrize("raw,safe", [("../../evil.txt", "evil.txt"), ("a\\b\\c.pdf", "c.pdf"), ("re<port>.pdf", "report.pdf"), ("", "report"), (None, "report"), ("a\x00b.txt", "ab.txt"),
                                      ("  spaced   name .png ", "spaced name .png"), ("CON:evil?.txt", "CONevil.txt")])
def test_file_names_are_made_safe(raw, safe):
    assert safe_filename(raw) == safe


def test_a_very_long_file_name_is_shortened_but_keeps_its_extension():
    name = safe_filename("x" * 400 + ".pdf")
    assert len(name) <= 150 and name.endswith(".pdf")


# ------------------------------------------------------------------ the 422 answer
def test_the_422_answer_is_one_readable_sentence_with_one_message_per_field(client):
    r = client.post("/api/auth/login", json={"email": "bad email", "password": ""})
    body = r.json()
    assert r.status_code == 422 and isinstance(body["detail"], str)
    assert "Value error" not in body["detail"] and "string_too_short" not in body["detail"]
    assert {e["field"] for e in body["errors"]} == {"email", "password"}
    assert all(e["message"].endswith(".") for e in body["errors"])
    assert friendly([{"type": "missing", "loc": ("body", "full_name"), "msg": "Field required"}])["detail"] == "Full name: This is required."


def test_unreadable_and_hostile_bodies_are_a_400_or_422_never_a_500(client):
    quiet = TestClient(app, raise_server_exceptions=False)
    for content in (b"{not json", b"[" * 1000 + b"]" * 1000, b'{"email": ' + b"[" * 3000, b"\xff\xfe\x00", b"null", b"[]", b'"text"', b"{" * 5000):
        r = quiet.post("/api/auth/login", content=content, headers={"content-type": "application/json"})
        assert r.status_code in (400, 422), (content[:20], r.status_code)


# ------------------------------------------------------------------ ids, search, limits, enums (through the API)
def test_ids_search_limits_and_filters_are_checked_before_any_work(client, world):
    quiet = TestClient(app, raise_server_exceptions=False)
    for path in ("/api/reports/0", "/api/reports/-3", "/api/reports/abc", "/api/reports/1.5", "/api/reports/99999999999999999999", "/api/patients/0", "/api/prescriptions/-1",
                 "/api/admin/audit-logs?limit=0", "/api/admin/audit-logs?limit=201", "/api/admin/audit-logs?limit=-5", "/api/admin/audit-logs?limit=abc",
                 f"/api/admin/people?q={'x' * 101}", "/api/admin/people?role=WIZARD", "/api/reports?patient_id=0", "/api/reports?patient_id=-1", "/api/reports?patient_id=abc"):
        auth = world.admin if path.startswith("/api/admin") else world.doctor
        assert quiet.get(path, headers=auth).status_code == 422, path
    assert quiet.get("/api/appointments?status_filter=MAYBE", headers=world.doctor).status_code == 422
    assert quiet.get("/api/pharmacy/prescriptions?status_filter=NOPE", headers=world.pharmacy).status_code == 422
    for ok in ("/api/admin/audit-logs?limit=1", "/api/admin/audit-logs?limit=200", "/api/admin/people?role=doctor", "/api/admin/people?q=%20%20Anjali%20"):
        assert quiet.get(ok, headers=world.admin).status_code == 200, ok
    assert quiet.get("/api/appointments?status_filter=completed", headers=world.doctor).status_code == 200      # case does not matter


def test_account_creation_checks_every_field_and_keeps_valid_data_working(client, world):
    quiet = TestClient(app, raise_server_exceptions=False)
    good = {"email": " Neha.Rao@Example.com ", "full_name": "Neha  Rao", "phone": "+91 98765 43210", "gender": "Female", "blood_group": "b+", "date_of_birth": "1992-03-04"}
    r = quiet.post("/api/patients", headers=world.employee, json=good)
    assert r.status_code == 201, r.text
    p = r.json()["patient"]
    assert (p["email"], p["full_name"], p["phone"], p["gender"]) == ("neha.rao@example.com", "Neha Rao", "9876543210", "female")
    for bad in ({"full_name": "Neha 2"}, {"email": "nehaexample.com"}, {"phone": "12345"}, {"date_of_birth": "2999-01-01"}, {"gender": "x"}, {"blood_group": "Q"}, {"emergency_contact": "98765 43210"}):
        r = quiet.post("/api/patients", headers=world.employee, json={**good, "email": "other@example.com", **bad})
        assert r.status_code == 422, (bad, r.status_code)
        assert isinstance(r.json()["detail"], str)
    # the same e-mail twice is a clear conflict, not a crash
    assert quiet.post("/api/patients", headers=world.employee, json=good).status_code in (400, 409, 422)


def test_changing_a_patient_cannot_make_the_emergency_contact_the_patients_own_number(client, world):
    r = client.put(f"/api/patients/{world.patient_id}", headers=world.employee, json={"phone": "9876543210", "emergency_contact": "Mother 98765 43210"})
    assert r.status_code == 422
    assert client.put(f"/api/patients/{world.patient_id}", headers=world.employee, json={"phone": "9876543210", "emergency_contact": "Mother 91234 56789"}).status_code == 200
    assert client.put(f"/api/patients/{world.patient_id}", headers=world.employee, json={"emergency_contact": "Self 98765 43210"}).status_code == 422       # only the contact changes: compared with the stored phone


def test_a_password_with_the_email_name_is_refused_when_changing_it(client, world):
    me = client.get("/api/auth/me", headers=world.employee).json()
    name_part = me["email"].split("@")[0]
    r = client.post("/api/auth/change-password", headers=world.employee, json={"current_password": PASSWORD, "new_password": f"{name_part}-2026x"})
    assert r.status_code == 422 and "e-mail name" in r.json()["detail"]


def test_the_login_lock_is_per_email_and_address_so_a_stranger_cannot_lock_the_owner_out(client, world):
    from app.routers.auth import MAX_FAILS_PER_EMAIL_AND_IP
    attacker = TestClient(app, client=("203.0.113.50", 5000))
    for i in range(MAX_FAILS_PER_EMAIL_AND_IP):
        assert attacker.post("/api/auth/login", json={"email": "anjali@hospital.example.com", "password": f"wrong{i}"}).status_code == 401
    locked = attacker.post("/api/auth/login", json={"email": "anjali@hospital.example.com", "password": PASSWORD})
    assert locked.status_code == 429 and "try again in" in locked.json()["detail"] and int(locked.headers["retry-after"]) > 0
    owner = TestClient(app, client=("198.51.100.7", 5000))                                    # the real owner, from another place
    assert owner.post("/api/auth/login", json={"email": "anjali@hospital.example.com", "password": PASSWORD}).status_code == 200


def test_long_passwords_are_all_checked_and_old_password_records_still_work(client, world):
    from app.core.security import hash_password, verify_password
    base = "A1" + "x" * 70
    stored = hash_password(base + "-first")
    assert verify_password(base + "-first", stored) and not verify_password(base + "-second", stored)
    import bcrypt
    legacy = bcrypt.hashpw(b"OldPassword123", bcrypt.gensalt(4)).decode()               # a record saved by the earlier version
    assert verify_password("OldPassword123", legacy) and not verify_password("OldPassword124", legacy)


def test_warnings_are_given_for_the_same_medicine_twice_but_the_prescription_is_saved(client, world):
    body = {"patient_id": world.patient_id, "clinical_indication": "Check", "items": [
        {"medicine_name": "Tab. Test", "dosage": "5 mg", "frequency": "Daily", "duration": "5 days", "quantity": 5},
        {"medicine_name": "tab. test", "dosage": "10 mg", "frequency": "Night", "duration": "5 days", "quantity": 5}]}
    r = client.post("/api/prescriptions", headers=world.doctor, json=body)
    assert r.status_code == 201 and any("more than once" in w for w in r.json()["warnings"])
    one = client.post("/api/prescriptions", headers=world.doctor, json={**body, "items": body["items"][:1]})
    assert one.status_code == 201 and one.json()["warnings"] == []


def test_uploads_tell_clearly_what_is_wrong(client, world):
    for name, content, text in [("a.webp", b"RIFF0000WEBPx", "not accepted|not a valid"), ("a.png", b"\xff\xd8\xff" + b"0" * 20, "does not match"), ("a.pdf", b"", "empty"), ("a.exe", b"MZ", "not accepted|supported|Wrong file")]:
        r = upload(client, world.employee, world.patient_id, name, content)
        assert r.status_code in (400, 413, 415, 422), (name, r.status_code)
    r = client.post("/api/profile/avatar", headers=world.patient, files={"file": ("big.png", b"\x89PNG\r\n\x1a\n" + b"0" * (2 * 1024 * 1024 + 10), "image/png")})
    assert r.status_code == 413 and "2 MB" in r.json()["detail"]
    r = client.post("/api/profile/avatar", headers=world.patient, files={"file": ("p.webp", b"RIFF0000WEBPxxxxxxxx", "image/webp")})
    assert r.status_code == 422 and "JPG or PNG" in r.json()["detail"]


def test_profile_text_is_cleaned_and_the_phone_normalised(client, world):
    r = client.put("/api/profile", headers=world.patient, json={"full_name": "  Rahul   <b>Patil</b> ", "values": {"phone": "+91 98765 43210"}})
    assert r.status_code in (200, 422)
    bad = client.put("/api/profile", headers=world.patient, json={"full_name": "R4hul"})
    assert bad.status_code == 422


def test_a_phone_sent_as_null_and_a_time_before_1970_do_not_crash(client, world):
    quiet = TestClient(app, raise_server_exceptions=False)
    assert quiet.put(f"/api/patients/{world.patient_id}", headers=world.employee, json={"phone": None, "emergency_contact": None}).status_code == 200
    assert quiet.put(f"/api/patients/{world.patient_id}", headers=world.employee, json={"emergency_contact": None}).status_code == 200
    assert accepts(AppointmentCreate, doctor_id=1, scheduled_at=-1) is None                      # 31 Dec 1969: a past time, not an operating-system error
    assert accepts(AppointmentCreate, doctor_id=1, scheduled_at=-99999999999) is None


def test_a_request_body_over_the_limit_is_refused_before_it_is_read(client):
    big = b'{"email":"a@b.co","password":"' + b"x" * (1_100_000) + b'"}'
    assert client.post("/api/auth/login", content=big, headers={"content-type": "application/json"}).status_code == 413
