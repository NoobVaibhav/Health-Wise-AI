"""Step 2 (part 2): the validation rules checked through the real API. Auth, files, query parameters, hostile text. A failing test is a confirmed gap.
Invalid input must answer 4xx with a readable message, never 500. Data is invented."""
import pytest

from tests.conftest import PASSWORD, headers, login, upload

HOSTILE = ["<script>alert(1)</script>", "<img src=x onerror=alert(1)>", "'; DROP TABLE users;--", "x\x00y", "A" * 5000, "   "]


def new_patient(client, world, **over):
    body = {"email": "p1@example.com", "full_name": "Test Person", "password": PASSWORD, "gender": "male", "date_of_birth": "1990-01-01", "phone": "9876543210", **over}
    return client.post("/api/patients", headers=world.employee, json=body)


# --------------------------------------------------------------------------- auth
@pytest.mark.parametrize("pw", ["short1", "aaaaaaaa", "12345678", "password123", "A" * 200])
def test_weak_or_oversized_password_is_refused_with_422(client, world, pw):
    assert new_patient(client, world, password=pw).status_code == 422


@pytest.mark.parametrize("email", ["not-an-email", "a@b", "a b@c.com", "x" * 300 + "@c.com", "", "<s>@c.com", "a@@c.com"])
def test_bad_email_is_422(client, world, email):
    assert new_patient(client, world, email=email).status_code == 422


def test_login_trims_and_lowercases_email_and_hides_which_part_was_wrong(client, world):
    ok = client.post("/api/auth/login", json={"email": "  RAHUL@Example.COM ", "password": PASSWORD})
    assert ok.status_code == 200
    wrong_pw = client.post("/api/auth/login", json={"email": "rahul@example.com", "password": "Wrong-pass-1"})
    wrong_user = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "Wrong-pass-1"})
    assert wrong_pw.status_code == wrong_user.status_code == 401
    assert wrong_pw.json()["detail"] == wrong_user.json()["detail"]


def test_new_password_must_differ_and_be_strong(client, world):
    same = client.post("/api/auth/change-password", headers=world.patient, json={"current_password": PASSWORD, "new_password": PASSWORD, "confirm_password": PASSWORD})
    assert same.status_code == 422
    weak = client.post("/api/auth/change-password", headers=world.patient, json={"current_password": PASSWORD, "new_password": "aaaaaaaa", "confirm_password": "aaaaaaaa"})
    assert weak.status_code == 422


def test_lockout_after_repeated_failures_answers_429(client, world):
    codes = [client.post("/api/auth/login", json={"email": "rahul@example.com", "password": f"Wrong-pass-{i}"}).status_code for i in range(8)]
    assert 429 in codes and 500 not in codes


@pytest.mark.parametrize("code", ["12345", "1234567", "abcdef", "12 456", "١٢٣٤٥٦"])
def test_otp_code_must_be_six_ascii_digits(client, world, code):
    assert client.post("/api/auth/otp/verify", json={"phone": "9876543210", "code": code}).status_code == 422


# --------------------------------------------------------------------------- text and identity fields
@pytest.mark.parametrize("name", ["Rahul 123", "Rahul 😀", "<b>Rahul</b>", "R", "x" * 400, "   ", "Rahul\x00Patil"])
def test_names_with_digits_emoji_markup_or_wrong_length_are_refused(client, world, name):
    r = new_patient(client, world, full_name=name)
    if r.status_code == 201:       # markup may be stripped instead of refused: then no tag may remain
        assert "<" not in r.json()["patient"]["full_name"] and "\x00" not in r.json()["patient"]["full_name"] and r.json()["patient"]["full_name"].strip()
    else:
        assert r.status_code == 422


@pytest.mark.parametrize("field,value", [("gender", "robot"), ("blood_group", "Z+"), ("phone", "12345"), ("phone", "abcdefghij"), ("date_of_birth", "2999-01-01"),
                                         ("date_of_birth", "1800-01-01"), ("date_of_birth", "not-a-date"), ("address", "A" * 5000)])
def test_fixed_list_and_format_fields_refuse_bad_values(client, world, field, value):
    assert new_patient(client, world, **{field: value}).status_code == 422


@pytest.mark.parametrize("hostile", HOSTILE)
def test_hostile_text_in_free_fields_is_never_stored_as_markup_and_never_500(client, world, hostile):
    r = client.put(f"/api/patients/{world.patient_id}", headers=world.employee, json={"allergies": hostile, "address": hostile[:300]})
    assert r.status_code in (200, 422), r.text
    if r.status_code == 200:
        got = client.get(f"/api/patients/{world.patient_id}", headers=world.employee).json()
        for field in ("allergies", "address"):
            assert "<script" not in (got.get(field) or "").lower() and "onerror" not in (got.get(field) or "").lower() and "\x00" not in (got.get(field) or "")


def test_wrong_content_type_malformed_json_and_extra_fields(client, world):
    assert client.post("/api/auth/login", content="email=a&password=b", headers={"Content-Type": "application/x-www-form-urlencoded"}).status_code in (415, 422)
    assert client.post("/api/auth/login", content="{not json", headers={"Content-Type": "application/json"}).status_code in (400, 422)
    assert client.post("/api/auth/login", content="[]", headers={"Content-Type": "application/json"}).status_code == 422
    extra = client.post("/api/auth/login", json={"email": "rahul@example.com", "password": PASSWORD, "role": "ADMIN", "is_admin": True})
    assert extra.status_code == 200 and extra.json()["user"]["role"] == "PATIENT"        # an extra field never changes who you are


# --------------------------------------------------------------------------- ids and query parameters
@pytest.mark.parametrize("bad", ["abc", "0", "-1", "99999999999999999999", "1.5", "%00"])
def test_ids_in_the_path_are_positive_whole_numbers(client, world, bad):
    assert client.get(f"/api/patients/{bad}", headers=world.employee).status_code in (404, 405, 422)


@pytest.mark.parametrize("limit", ["0", "-5", "abc", "1000000000", "99999999999999999999", "1.5"])
def test_limit_is_bounded_everywhere_it_exists(client, world, limit):
    assert client.get("/api/admin/audit-logs", headers=world.admin, params={"limit": limit}).status_code in (200, 422)
    r = client.get("/api/pharmacy/stock/movements", headers=world.pharmacy, params={"limit": limit})
    assert r.status_code in (200, 404, 422), r.text
    if r.status_code == 200:
        assert len(r.json()) <= 300                       # an oversized limit is clamped, never honoured


@pytest.mark.parametrize("path", ["/api/patients", "/api/admin/people", "/api/doctor/patients"])
def test_search_text_is_bounded(client, world, path):
    auth = world.doctor if "doctor/" in path else (world.admin if "admin" in path else world.employee)
    assert client.get(path, headers=auth, params={"q": "x" * 5000}).status_code in (200, 422)
    assert client.get(path, headers=auth, params={"q": "' OR 1=1 --"}).status_code == 200


def test_filters_use_fixed_words(client, world):
    r = client.get("/api/finance/invoices", headers=world.admin, params={"status_filter": "<script>"})
    assert r.status_code in (403, 404, 422), r.text            # a wrong word is refused, not silently ignored
    r = client.get("/api/finance/invoices", headers=world.admin, params={"patient_id": "-3"})
    assert r.status_code in (403, 404, 422), r.text


# --------------------------------------------------------------------------- files
GOOD_TXT = b"Patient: Rahul Patil\nHemoglobin 13.5 g/dL 13.0 - 17.0\n"


@pytest.mark.parametrize("name,content", [
    ("empty.txt", b""),
    ("report.pdf.exe", b"MZ\x90\x00" + b"\x00" * 200),
    ("report.pdf", b"MZ\x90\x00" + b"\x00" * 200),              # an executable renamed to .pdf
    ("report.png", b"%PDF-1.4\n" + b"0" * 100),                  # a PDF renamed to .png
    ("../../etc/passwd.pdf", b"%PDF-1.4\n" + b"0" * 100),
    ("a" * 400 + ".pdf", b"%PDF-1.4\n" + b"0" * 100),
    ("<script>.pdf", b"%PDF-1.4\n" + b"0" * 100),
])
def test_bad_uploads_are_refused_without_500(client, world, name, content):
    r = upload(client, world.employee, world.patient_id, name, content, world.doctor_id)
    assert r.status_code in (400, 413, 415, 422), (name, r.status_code, r.text)


def test_upload_with_a_traversal_name_never_stores_or_shows_the_path(client, world):
    r = upload(client, world.employee, world.patient_id, "..\\..\\evil.txt", GOOD_TXT, world.doctor_id)
    assert r.status_code in (200, 201, 400, 415, 422)
    if r.status_code in (200, 201):
        assert ".." not in r.text and "\\" not in r.json().get("original_filename", r.json().get("file_name", ""))


def test_oversized_upload_is_refused_with_413_not_read_whole(client, world):
    r = upload(client, world.employee, world.patient_id, "big.pdf", b"%PDF-1.4\n" + b"0" * (11 * 1024 * 1024), world.doctor_id)
    assert r.status_code in (400, 413, 422)
