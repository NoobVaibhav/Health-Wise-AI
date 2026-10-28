"""Authentication attacks: forged, tampered, expired and replayed tokens; brute force and lockout; password flows; mass assignment."""
import base64
import json
import time
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from app.core.config import get_settings
from tests.conftest import PASSWORD, headers, login
from tests.security_and_chaos._helpers import bust


def token_for(user_id, secret=None, alg="HS256", **extra):
    payload = {"sub": str(user_id), "exp": datetime.now(timezone.utc) + timedelta(hours=1), **extra}
    return jwt.encode(payload, secret or get_settings().jwt_secret, algorithm=alg)


def me(client, token):
    return client.get("/api/auth/me", headers=headers(token) if token else {})


def admin_id(client, world):
    return client.get("/api/auth/me", headers=world.admin).json()["id"]


def test_tokens_that_must_be_refused(client, world):
    uid = admin_id(client, world)
    real = world.admin["Authorization"].split()[1]
    assert me(client, real).status_code == 200
    bad = {
        "wrong secret": token_for(uid, secret="not-the-secret-not-the-secret-not-the-secret"),
        "the documented default secret": token_for(uid, secret="change-me-in-production"),
        "expired": jwt.encode({"sub": str(uid), "exp": datetime.now(timezone.utc) - timedelta(seconds=5), "pv": "x"}, get_settings().jwt_secret, algorithm="HS256"),
        "no pv claim": token_for(uid),
        "wrong pv claim": token_for(uid, pv="000000000000"),
        "no exp": jwt.encode({"sub": str(uid)}, get_settings().jwt_secret, algorithm="HS256"),
        "sub is a string of letters": token_for("abc"),
        "sub negative": token_for(-1),
        "garbage": "not.a.jwt",
        "empty": "",
    }
    # alg=none, written by hand because the library refuses to create it
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(json.dumps({"sub": str(uid), "exp": int(time.time()) + 3600}).encode()).rstrip(b"=").decode()
    bad["alg none"] = f"{header}.{body}."
    bad["alg none, signature junk"] = f"{header}.{body}.AAAA"
    for name, token in bad.items():
        assert me(client, token).status_code == 401, name
    # tampered payload: change the subject but keep the old signature
    h, p, s = real.split(".")
    other = base64.urlsafe_b64encode(json.dumps({**json.loads(base64.urlsafe_b64decode(p + "==")), "sub": "999"}).encode()).rstrip(b"=").decode()
    assert me(client, f"{h}.{other}.{s}").status_code == 401
    # HS256 token whose header claims RS256 / HS512 must not be accepted
    for alg in ("HS512", "HS384"):
        assert me(client, jwt.encode({"sub": str(uid), "exp": datetime.now(timezone.utc) + timedelta(hours=1), "pv": "x"}, get_settings().jwt_secret, algorithm=alg)).status_code == 401


def test_a_role_claim_in_the_token_changes_nothing(client, world):
    patient_id = client.get("/api/auth/me", headers=world.patient).json()["id"]
    from app.core.security import password_fingerprint
    from app.database.connection import SessionLocal
    from app.database.models import User
    with SessionLocal() as db:
        pv = password_fingerprint(db.get(User, patient_id).password_hash)
    forged = token_for(patient_id, pv=pv, role="ADMIN", is_admin=True)           # a valid signature is needed to make this one: only the server can, so this proves the claim is ignored
    assert client.get("/api/admin/users", headers=headers(forged)).status_code == 403


def test_a_deactivated_user_loses_access_at_once_even_with_a_valid_token(client, world):
    uid = client.get("/api/auth/me", headers=world.pharmacy).json()["id"]
    assert client.get("/api/pharmacy/prescriptions", headers=world.pharmacy).status_code in (200, 404)
    assert client.put(f"/api/admin/users/{uid}", headers=world.admin, json={"is_active": False}).status_code in (200, 204)
    assert me(client, world.pharmacy["Authorization"].split()[1]).status_code == 401
    r = client.post("/api/auth/login", json={"email": "pharmacy@hospital.example.com", "password": PASSWORD})
    assert r.status_code == 403 and "deactivated" in r.text


def test_the_old_token_dies_when_the_password_changes_and_the_old_password_is_required(client, world):
    token = world.employee["Authorization"].split()[1]
    assert client.post("/api/auth/change-password", headers=world.employee, json={"new_password": "BrandNew1234"}).status_code == 422       # no current password
    assert client.post("/api/auth/change-password", headers=world.employee, json={"current_password": "wrong", "new_password": "BrandNew1234"}).status_code == 400
    assert client.post("/api/auth/change-password", headers=world.employee, json={"current_password": PASSWORD, "new_password": "BrandNew1234"}).status_code == 200
    assert me(client, token).status_code == 401
    assert client.post("/api/auth/login", json={"email": "priya@hospital.example.com", "password": PASSWORD}).status_code == 401


def test_brute_force_is_stopped_and_the_attacker_cannot_tell_which_emails_exist(client, world):
    codes = [client.post("/api/auth/login", json={"email": "priya@hospital.example.com", "password": f"wrong{i}"}).status_code for i in range(12)]
    assert 429 in codes and codes[0] == 401
    known = client.post("/api/auth/login", json={"email": "nobody.here@hospital.example.com", "password": "wrong"})
    exists = client.post("/api/auth/login", json={"email": "anjali@hospital.example.com", "password": "wrong"})
    assert known.json() == exists.json() and known.status_code == exists.status_code == 401


@bust("A-01")
def test_the_lockout_cannot_be_used_to_lock_the_real_owner_out_from_anywhere(client, world):
    """Locking is per email: anyone can lock a victim out by sending wrong passwords. The correct password of the owner must still get in
    (or the lock must be per source). Today it does not."""
    for i in range(12):
        client.post("/api/auth/login", json={"email": "anjali@hospital.example.com", "password": f"wrong{i}"})
    assert client.post("/api/auth/login", json={"email": "anjali@hospital.example.com", "password": PASSWORD}).status_code == 200


@bust("A-02")
def test_two_passwords_that_share_their_first_72_bytes_are_not_the_same_password(client, world):
    long_pw = "A1" + "x" * 70
    assert client.post("/api/auth/change-password", headers=world.employee, json={"current_password": PASSWORD, "new_password": long_pw + "-original"}).status_code == 200
    r = client.post("/api/auth/login", json={"email": "priya@hospital.example.com", "password": long_pw + "-SOMETHING-ELSE-ENTIRELY"})
    assert r.status_code == 401


@bust("A-03")
def test_an_absurdly_long_password_is_refused_before_it_reaches_the_hasher(client, world):
    r = client.post("/api/auth/login", json={"email": "priya@hospital.example.com", "password": "p" * 2_000_000})
    assert r.status_code == 422


def test_extra_fields_cannot_make_an_account_more_powerful(client, world):
    created = client.post("/api/patients", headers=world.employee, json={
        "email": "mass@example.com", "full_name": "Mass Assign", "password": PASSWORD, "gender": "male", "date_of_birth": "1990-01-01", "phone": "9999999999",
        "role": "ADMIN", "is_active": True, "must_change_password": False, "user_id": 1, "id": 9999})
    assert created.status_code in (201, 422)
    if created.status_code == 201:
        me_ = client.post("/api/auth/login", json={"email": "mass@example.com", "password": PASSWORD}).json()
        assert me_["user"]["role"] == "PATIENT"
    pid = client.get("/api/auth/me", headers=world.patient).json()["id"]
    client.put("/api/profile", headers=world.patient, json={"role": "ADMIN", "is_active": True, "email": "evil@example.com"})
    after = client.get("/api/auth/me", headers=world.patient).json()
    assert after["role"] == "PATIENT" and after["email"] != "evil@example.com" and after["id"] == pid


def test_public_registration_works_only_for_the_first_administrator(client):
    ok = client.post("/api/auth/register", json={"email": "first@example.com", "full_name": "First Admin", "password": PASSWORD})
    assert ok.status_code == 201
    again = client.post("/api/auth/register", json={"email": "second@example.com", "full_name": "Second Admin", "password": PASSWORD})
    assert again.status_code in (403, 409)


@bust("A-04")
def test_two_people_registering_at_the_same_moment_cannot_both_become_the_first_administrator(client):
    import threading

    from fastapi.testclient import TestClient

    from app.main import app
    results, barrier = [], threading.Barrier(6)

    def go(i):
        c = TestClient(app)
        barrier.wait()
        results.append(c.post("/api/auth/register", json={"email": f"race{i}@example.com", "full_name": f"Racer {i}", "password": PASSWORD}).status_code)

    threads = [threading.Thread(target=go, args=(i,)) for i in range(6)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert results.count(201) == 1, results


def test_a_user_who_still_has_the_temporary_password_can_reach_nothing_but_the_password_pages(client, world):
    created = client.post("/api/patients", headers=world.employee, json={"email": "temp@example.com", "full_name": "Temp User", "gender": "male", "date_of_birth": "1990-01-01", "phone": "9999999990"})
    assert created.status_code == 201
    token = client.post("/api/auth/login", json={"email": "temp@example.com", "password": get_settings().default_password}).json()["access_token"]
    assert client.get("/api/auth/me", headers=headers(token)).status_code == 200
    for path in ("/api/patient-assistant/suggestions", "/api/patient/reports", "/api/auth/me/../patient/reports", "/api/health-history/me", "/api/profile"):
        assert client.get(path, headers=headers(token)).status_code in (403, 404), path
