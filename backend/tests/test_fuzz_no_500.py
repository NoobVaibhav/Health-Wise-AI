"""Robustness sweep: every write endpoint, called by every role with malformed, extreme and hostile values, must answer with a
normal 4xx and never crash (500). The patient, doctor, pharmacy and other records are synthetic."""
import itertools
import re

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import PASSWORD, login
from tests.test_patient_assistant import add_report, report

BAD_VALUES = ["", None, -1, 0, 10 ** 12, 1.5e308, "x" * 6000, "'; DROP TABLE users;--", "<script>alert(1)</script>", "%", "\u0000", [], {}, [{}], True, "9999-12-31", "0001-01-01", "not-a-date"]


def resolve(schema, spec):
    while "$ref" in schema:
        schema = spec["components"]["schemas"][schema["$ref"].split("/")[-1]]
    return schema


def body_variants(schema, spec):
    """A few broken bodies built from the endpoint's own field names."""
    schema = resolve(schema, spec)
    names = list(schema.get("properties", {}))
    yield {}
    yield []
    yield "text"
    for bad in BAD_VALUES:
        yield {n: bad for n in names}
    for n, bad in itertools.product(names[:6], BAD_VALUES[:12]):
        yield {n: bad}


def fill_path(path, value="1"):
    return re.sub(r"\{[^}]+\}", value, path)


@pytest.fixture()
def tokens(client, world):
    client.post("/api/admin/lab-staff", headers=world.admin, json={"email": "lab@hospital.example.com", "full_name": "Lab Person", "password": PASSWORD})
    add_report(client, world, "r.txt", report("03/07/2026", "Hemoglobin 12.1 g/dL 13.0 - 17.0"))
    client.post("/api/prescriptions", headers=world.doctor, json={"patient_id": world.patient_id, "clinical_indication": "Check", "items": [
        {"medicine_name": "Tab. Test", "dosage": "5 mg", "frequency": "Daily", "duration": "5 days", "quantity": 5}]})
    return [world.admin, world.doctor, world.employee, world.pharmacy, world.patient, login(client, "lab@hospital.example.com")]


def test_no_write_endpoint_crashes_on_bad_input(client, world, tokens):
    spec = app.openapi()
    quiet = TestClient(app, raise_server_exceptions=False)          # a crash shows up as a 500 instead of an exception
    skipped_prefix = ("/api/auth/register",)
    crashes = []
    for path, ops in spec["paths"].items():
        if path.startswith(skipped_prefix):
            continue
        for method, op in ops.items():
            if method not in ("post", "put", "patch", "delete"):
                continue
            content = (op.get("requestBody") or {}).get("content", {})
            json_schema = content.get("application/json", {}).get("schema")
            if "multipart/form-data" in content:
                continue                                                 # uploads are fuzzed separately
            bodies = list(body_variants(json_schema, spec)) if json_schema else [None]
            for auth in tokens:
                for body in bodies[:45]:
                    kw = {"json": body} if body is not None else {}
                    r = quiet.request(method.upper(), fill_path(path), headers=auth, **kw)
                    if r.status_code >= 500:
                        crashes.append((method.upper(), path, r.status_code, str(body)[:80]))
                        break
    assert not crashes, f"{len(crashes)} crashes, first ones: {crashes[:8]}"


def test_uploads_with_hostile_files_never_crash(client, world):
    quiet = TestClient(app, raise_server_exceptions=False)
    files = [("a.pdf", b"%PDF-1.4 broken"), ("a.pdf", b""), ("../../evil.txt", b"hello"), ("a.png", b"\x89PNG\r\n\x1a\n" + b"0" * 50), ("a.jpg", b"\xff\xd8\xff" + b"\x00" * 100),
             ("a.txt", b"\xff\xfe\x00\x00" * 100), ("a.txt", b"x" * 2000), ("a.exe", b"MZ"), ("a", b"data"), ("a.txt\x00.png", b"data"), ("a.csv", b"a,b\n1,2"), ("a.webp", b"RIFF0000WEBPjunk")]
    for name, content in files:
        for auth in (world.employee, world.doctor):
            r = quiet.post("/api/reports/upload", headers=auth, data={"patient_id": str(world.patient_id), "doctor_id": str(world.doctor_id)}, files={"file": (name, content)})
            assert r.status_code < 500, (name, r.status_code, r.text[:150])
    for content in (b"not an image", b"\x89PNG\r\n\x1a\n" + b"0" * 30, b"\xff\xd8\xff" + b"0" * 30):
        r = quiet.post("/api/profile/avatar", headers=world.patient, files={"file": ("p.png", content)})
        assert r.status_code < 500, (content[:10], r.status_code)


def test_no_read_endpoint_crashes_on_bad_query_values(client, world, tokens):
    spec = app.openapi()
    quiet = TestClient(app, raise_server_exceptions=False)
    odd = ["", "%", "_", "x" * 5000, "'; DROP TABLE users;--", "-1", "99999999999999999999", "9999-99-99", "\u0000", "<b>", "null"]
    crashes = []
    for path, ops in spec["paths"].items():
        get = ops.get("get")
        if not get:
            continue
        names = [p["name"] for p in get.get("parameters", []) if p["in"] == "query"]
        for auth in tokens:
            for value in odd:
                r = quiet.get(fill_path(path), headers=auth, params={n: value for n in names})
                if r.status_code >= 500:
                    crashes.append((path, r.status_code, value[:20]))
                    break
    assert not crashes, f"crashes: {crashes[:8]}"


def test_huge_ids_in_the_path_are_a_client_error(client, world, tokens):
    spec = app.openapi()
    quiet = TestClient(app, raise_server_exceptions=False)
    crashes = []
    for path, ops in spec["paths"].items():
        if "{" not in path:
            continue
        for method in ops:
            for auth in tokens:
                r = quiet.request(method.upper(), fill_path(path, "99999999999999999999"), headers=auth, **({"json": {}} if method in ("post", "put", "patch") else {}))
                if r.status_code >= 500:
                    crashes.append((method.upper(), path, r.status_code))
                    break
    assert not crashes, f"crashes: {crashes[:8]}"
