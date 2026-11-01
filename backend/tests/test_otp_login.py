"""Sign in with a mobile number and a 6-digit code: one answer for known and unknown numbers, a short life, a limit of tries and requests, one account per number."""
from datetime import timedelta

import pytest

from app.core.config import get_settings
from app.database.connection import SessionLocal
from app.database.models import LoginOtp, utcnow
from tests.conftest import PASSWORD

PHONE = "9999999999"                     # the patient Rahul of the demo world
MESSAGE = "If this number belongs to an account, a code has been sent."


@pytest.fixture()
def demo(monkeypatch):
    monkeypatch.setattr(get_settings(), "otp_demo_mode", True)


def ask(client, phone=PHONE):
    return client.post("/api/auth/otp/request", json={"phone": phone})


def verify(client, code, phone=PHONE):
    return client.post("/api/auth/otp/verify", json={"phone": phone, "code": code})


def test_a_registered_number_gets_a_code_that_signs_in_once(client, world, demo):
    r = ask(client)
    assert r.status_code == 200 and r.json()["message"] == MESSAGE and r.json()["expires_in"] == 300
    code = r.json()["demo_code"]
    assert len(code) == 6 and code.isdigit()
    ok = verify(client, code)
    assert ok.status_code == 200 and ok.json()["user"]["role"] == "PATIENT" and ok.json()["user"]["email"] == "rahul@example.com"
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {ok.json()['access_token']}"})
    assert me.status_code == 200
    assert verify(client, code).status_code == 401                                       # a code works once


def test_the_number_can_be_written_in_any_style(client, world, demo):
    code = ask(client, "+91 99999 99999").json()["demo_code"]
    assert verify(client, code, "099999-99999").status_code == 200


def test_unknown_and_registered_numbers_get_the_same_answer_and_no_code_without_demo_mode(client, world, monkeypatch):
    monkeypatch.setattr(get_settings(), "otp_demo_mode", False)
    known, unknown = ask(client), ask(client, "9111111111")
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json() == {"message": MESSAGE, "expires_in": 300}       # nothing to tell them apart, and no code on the screen
    assert verify(client, "123456", "9111111111").status_code == 401


def test_demo_mode_shows_the_code_only_for_a_real_account(client, world, demo):
    assert "demo_code" in ask(client).json() and "demo_code" not in ask(client, "9111111111").json()


def test_wrong_codes_are_counted_and_five_of_them_kill_the_code(client, world, demo):
    code = ask(client).json()["demo_code"]
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        r = verify(client, wrong)
        assert r.status_code == 401 and r.json()["detail"] == "That code is incorrect or has expired."
    assert verify(client, code).status_code == 401                                        # the right code is too late now


def test_an_old_code_expires_and_a_new_request_cancels_the_earlier_code(client, world, demo):
    first = ask(client).json()["demo_code"]
    second = ask(client).json()["demo_code"]
    if first != second:
        assert verify(client, first).status_code == 401                                   # the earlier code was cancelled
    with SessionLocal() as db:
        row = db.query(LoginOtp).order_by(LoginOtp.id.desc()).first()
        row.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    assert verify(client, second).status_code == 401


def test_too_many_codes_in_a_short_time_are_refused(client, world, demo):
    for _ in range(3):
        assert ask(client).status_code == 200
    r = ask(client)
    assert r.status_code == 429 and "Please try again in" in r.json()["detail"]


def test_a_number_shared_by_two_accounts_cannot_be_used(client, world, demo):
    res = client.post("/api/admin/employees", headers=world.admin, json={"email": "twin@hospital.example.com", "full_name": "Twin Phone", "password": PASSWORD, "designation": "Clerk", "phone": PHONE})
    assert res.status_code == 201, res.text
    r = ask(client)
    assert r.status_code == 200 and "demo_code" not in r.json()
    assert verify(client, "123456").status_code == 401


def test_a_deactivated_account_gets_no_code(client, world, demo):
    uid = client.get("/api/auth/me", headers=world.patient).json()["id"]
    assert client.put(f"/api/admin/users/{uid}", headers=world.admin, json={"is_active": False}).status_code == 200
    assert "demo_code" not in ask(client).json()


def test_bad_input_is_a_422(client, world, demo):
    assert ask(client, "abc").status_code == 422
    assert ask(client, "123").status_code == 422
    assert client.post("/api/auth/otp/verify", json={"phone": PHONE, "code": "12345"}).status_code == 422
    assert client.post("/api/auth/otp/verify", json={"phone": PHONE, "code": "abcdef"}).status_code == 422
    assert client.post("/api/auth/otp/verify", json={"phone": PHONE}).status_code == 422


def test_the_code_is_stored_only_as_a_hash(client, world, demo):
    code = ask(client).json()["demo_code"]
    with SessionLocal() as db:
        row = db.query(LoginOtp).order_by(LoginOtp.id.desc()).first()
        assert code not in row.code_hash and len(row.code_hash) == 64 and row.phone_tail == "9999"


def test_a_staff_member_can_sign_in_with_the_phone_in_their_profile(client, world, demo):
    res = client.post("/api/admin/nurses", headers=world.admin, json={"email": "nurse@hospital.example.com", "full_name": "Nina Nurse", "password": PASSWORD, "designation": "Staff nurse", "phone": "98765 43210"})
    assert res.status_code == 201, res.text
    code = ask(client, "9876543210").json()["demo_code"]
    ok = verify(client, code, "9876543210")
    assert ok.status_code == 200 and ok.json()["user"]["role"] == "NURSE" and "nursing.chart" in ok.json()["user"]["permissions"]
