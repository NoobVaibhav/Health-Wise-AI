"""Laboratory workflow: advised test -> sample -> testing -> result report -> doctor review. Synthetic data only."""
import pytest

from tests import sample_data as sd
from tests.conftest import PASSWORD, login

L = "/api/lab"


@pytest.fixture()
def lab(client, world):
    r = client.post("/api/admin/lab-staff", headers=world.admin, json={"email": "lab@hospital.example.com", "full_name": "Lab Person", "password": PASSWORD})
    assert r.status_code == 201, r.text
    return login(client, "lab@hospital.example.com")


def advise(client, world, tests=("Complete Blood Count (CBC)", "Lipid profile")):
    r = client.post("/api/prescriptions", headers=world.doctor, json={"patient_id": world.patient_id, "clinical_indication": "Fatigue", "tests": list(tests),
                                                                    "items": [{"medicine_name": "Tab. Test", "dosage": "5 mg", "frequency": "Daily", "duration": "5 days", "quantity": 5}]})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def lab_tests(client, who):
    r = client.get(f"{L}/worklist", headers=who)
    assert r.status_code == 200, r.text
    return {t["test_name"]: t for t in r.json()["tests"]}


def result_file(name="Rahul Patil", value="12.1"):
    return sd.lines_to_text(["SYNTHETIC DEMO LABORATORY", f"Patient Name: {name}", "Report Date: 22/10/2026", "", "Test Name Result Unit Reference Range", f"Hemoglobin {value} g/dL 13.0 - 17.0", "Vitamin D 27 ng/mL 30 - 100"])


def post_status(client, who, order_id, status, **extra):
    return client.post(f"{L}/tests/{order_id}/status", headers=who, json={"status": status, **extra})


def test_every_advised_test_becomes_a_work_item_once(client, world, lab):
    advise(client, world)
    first = lab_tests(client, lab)
    assert set(first) == {"Complete Blood Count (CBC)", "Lipid profile"} and all(t["status"] == "ORDERED" and t["status_label"] == "Waiting for the sample" for t in first.values())
    assert first["Lipid profile"]["patient_name"] == "Rahul Patil" and first["Lipid profile"]["reason"] == "Fatigue" and first["Lipid profile"]["prescription_code"].startswith("RX-")
    assert len(lab_tests(client, lab)) == 2                                                  # asking again does not duplicate
    assert "medicine" not in str(first).lower() and "Tab. Test" not in str(first)         # the lab never sees medicines


def test_the_workflow_runs_in_order_and_makes_a_sample_label(client, world, lab):
    advise(client, world)
    cbc = lab_tests(client, lab)["Complete Blood Count (CBC)"]["id"]
    assert post_status(client, lab, cbc, "IN_PROGRESS").status_code == 409                 # no sample yet
    taken = post_status(client, lab, cbc, "SAMPLE_COLLECTED", sample_type="Blood").json()
    assert taken["status"] == "SAMPLE_COLLECTED" and taken["sample_type"] == "Blood" and taken["sample_code"].startswith("LAB-") and taken["collected_at"]
    other = lab_tests(client, lab)["Lipid profile"]["id"]
    second = post_status(client, lab, other, "SAMPLE_COLLECTED", sample_type="Blood").json()
    assert second["sample_code"] != taken["sample_code"]                                   # every sample has its own label
    started = post_status(client, lab, cbc, "IN_PROGRESS").json()
    assert started["status"] == "IN_PROGRESS" and started["started_at"]
    assert post_status(client, lab, cbc, "COMPLETED").status_code == 422                   # done only by uploading the result
    assert post_status(client, lab, cbc, "SAMPLE_COLLECTED").status_code == 409            # no going back
    assert post_status(client, lab, cbc, "SAMPLE_COLLECTED", sample_type="Gold").status_code in (409, 422)


def test_a_rejected_sample_needs_a_reason_and_can_be_ordered_again(client, world, lab):
    advise(client, world, tests=("Lipid profile",))
    oid = lab_tests(client, lab)["Lipid profile"]["id"]
    post_status(client, lab, oid, "SAMPLE_COLLECTED")
    assert post_status(client, lab, oid, "REJECTED").status_code == 422
    assert post_status(client, lab, oid, "REJECTED", note="ab").status_code == 422
    rejected = post_status(client, lab, oid, "REJECTED", note="Sample was haemolysed").json()
    assert rejected["status"] == "REJECTED" and rejected["rejection_reason"] == "Sample was haemolysed"
    mine = client.get(f"{L}/my-tests", headers=world.patient).json()[0]
    assert mine["status"] == "REJECTED" and "give it again" in mine["patient_message"] and mine["rejection_reason"] == "Sample was haemolysed"   # the patient is told to come again
    again = post_status(client, lab, oid, "ORDERED").json()
    assert again["status"] == "ORDERED" and again["sample_code"] is None                   # the old label is not reused
    assert post_status(client, lab, oid, "SAMPLE_COLLECTED").json()["sample_code"]


def test_uploading_the_result_completes_the_test_and_sends_it_to_the_doctor(client, world, lab):
    advise(client, world)
    oid = lab_tests(client, lab)["Complete Blood Count (CBC)"]["id"]
    early = client.post(f"{L}/tests/{oid}/result", headers=lab, files={"file": ("cbc.txt", result_file())})
    assert early.status_code == 409 and "Take the sample first" in early.json()["detail"]
    post_status(client, lab, oid, "SAMPLE_COLLECTED")
    done = client.post(f"{L}/tests/{oid}/result", headers=lab, files={"file": ("cbc.txt", result_file())})
    assert done.status_code == 200, done.text
    body = done.json()
    assert body["status"] == "COMPLETED" and body["completed_at"] and body["parameters_found"] == 2
    # the result is an ordinary report for the prescribing doctor to review
    reports = client.get("/api/reports", headers=world.doctor, params={"patient_id": world.patient_id}).json()
    assert len(reports) == 1 and reports[0]["doctor_review_status"] == "PENDING" and reports[0]["filename"] == "cbc.txt"
    seen_by_doctor = client.get(f"{L}/patient/{world.patient_id}/tests", headers=world.doctor).json()
    row = next(t for t in seen_by_doctor if t["test_name"] == "Complete Blood Count (CBC)")
    assert row["status"] == "COMPLETED" and row["report_id"] == reports[0]["id"]
    # the patient sees "result ready" but not the report until the doctor has reviewed it
    mine = next(t for t in client.get(f"{L}/my-tests", headers=world.patient).json() if t["test_name"] == "Complete Blood Count (CBC)")
    assert mine["status"] == "COMPLETED" and mine["report_id"] is None and "doctor will review" in mine["patient_message"]
    assert client.put(f"/api/doctor/reports/{reports[0]['id']}/review", headers=world.doctor, json={"decision": "APPROVED"}).status_code == 200
    mine = next(t for t in client.get(f"{L}/my-tests", headers=world.patient).json() if t["test_name"] == "Complete Blood Count (CBC)")
    assert mine["report_id"] == reports[0]["id"] and mine["patient_message"] == "Result reviewed by your doctor"
    assert client.post(f"{L}/tests/{oid}/result", headers=lab, files={"file": ("again.txt", result_file())}).status_code == 409       # a finished test takes no second result
    assert post_status(client, lab, oid, "REJECTED", note="too late").status_code == 409


def test_a_result_with_another_patients_name_is_not_saved_unless_confirmed(client, world, lab):
    advise(client, world, tests=("Lipid profile",))
    oid = lab_tests(client, lab)["Lipid profile"]["id"]
    post_status(client, lab, oid, "SAMPLE_COLLECTED")
    wrong = client.post(f"{L}/tests/{oid}/result", headers=lab, files={"file": ("x.txt", result_file(name="Sunita Deshmukh"))})
    assert wrong.status_code == 409 and wrong.json()["detail"]["code"] == "NAME_MISMATCH" and "Sunita Deshmukh" in wrong.json()["detail"]["message"]
    assert client.get("/api/reports", headers=world.doctor, params={"patient_id": world.patient_id}).json() == []         # nothing was saved
    assert lab_tests(client, lab)["Lipid profile"]["status"] == "SAMPLE_COLLECTED"
    ok = client.post(f"{L}/tests/{oid}/result", headers=lab, data={"confirm_mismatch": "true"}, files={"file": ("x.txt", result_file(name="Sunita Deshmukh"))})
    assert ok.status_code == 200 and ok.json()["mismatch_confirmed"] is True


def test_unreadable_files_are_refused_and_the_test_stays_open(client, world, lab):
    advise(client, world, tests=("Lipid profile",))
    oid = lab_tests(client, lab)["Lipid profile"]["id"]
    post_status(client, lab, oid, "SAMPLE_COLLECTED")
    for name, content in (("empty.txt", b""), ("junk.pdf", b"not a pdf"), ("x.exe", b"MZ"), ("note.txt", b"just some words, no laboratory values at all")):
        r = client.post(f"{L}/tests/{oid}/result", headers=lab, files={"file": (name, content)})
        assert 400 <= r.status_code < 500, (name, r.status_code)
    assert lab_tests(client, lab)["Lipid profile"]["status"] == "SAMPLE_COLLECTED"


def test_a_cancelled_prescription_cancels_open_tests(client, world, lab):
    rx = advise(client, world)
    done = lab_tests(client, lab)["Lipid profile"]["id"]
    post_status(client, lab, done, "SAMPLE_COLLECTED")
    assert client.put(f"/api/prescriptions/{rx}/cancel", headers=world.doctor, json={}).status_code == 200
    rows = lab_tests(client, lab)
    assert all(t["status"] == "CANCELLED" for t in rows.values()) and post_status(client, lab, done, "IN_PROGRESS").status_code == 409
    assert client.get(f"{L}/my-tests", headers=world.patient).json()[0]["patient_message"] == "Cancelled by the doctor"


def test_dashboard_search_urgent_and_audit(client, world, lab):
    advise(client, world)
    rows = lab_tests(client, lab)
    a, b = rows["Complete Blood Count (CBC)"]["id"], rows["Lipid profile"]["id"]
    assert client.post(f"{L}/tests/{b}/urgent", headers=lab, json={"urgent": True}).json()["urgent"] is True
    assert client.get(f"{L}/worklist", headers=lab).json()["tests"][0]["test_name"] == "Lipid profile"             # urgent first
    assert [t["test_name"] for t in client.get(f"{L}/worklist", headers=lab, params={"urgent": "true"}).json()["tests"]] == ["Lipid profile"]
    assert [t["test_name"] for t in client.get(f"{L}/worklist", headers=lab, params={"q": "rahul", "status_filter": "OPEN"}).json()["tests"]] != []
    assert client.get(f"{L}/worklist", headers=lab, params={"q": "nobody"}).json()["tests"] == []
    assert client.get(f"{L}/worklist", headers=lab, params={"status_filter": "NONSENSE"}).status_code == 422
    sample = post_status(client, lab, a, "SAMPLE_COLLECTED").json()
    assert [t["test_name"] for t in client.get(f"{L}/worklist", headers=lab, params={"q": sample["sample_code"]}).json()["tests"]] == ["Complete Blood Count (CBC)"]   # find by the sample label
    client.post(f"{L}/tests/{a}/result", headers=lab, files={"file": ("a.txt", result_file())})
    d = client.get(f"{L}/dashboard", headers=lab).json()
    assert d["counts"]["COMPLETED"] == 1 and d["counts"]["ORDERED"] == 1 and d["open"] == 1 and d["urgent_open"] == 1 and d["done_today"] == 1
    assert d["oldest_waiting_hours"] is not None
    from app.database.connection import SessionLocal
    from app.database.models import AuditLog
    with SessionLocal() as db:
        actions = [x.action for x in db.query(AuditLog).all()]
    assert "LAB_TEST_STATUS" in actions and "LAB_RESULT_UPLOADED" in actions and "LAB_TEST_URGENT" in actions


def test_who_may_do_what(client, world, lab):
    advise(client, world)
    oid = lab_tests(client, lab)["Lipid profile"]["id"]
    # the front desk may read the work list but not change anything; nobody else gets in
    assert client.get(f"{L}/worklist", headers=world.employee).status_code == 200
    for who in (world.employee, world.doctor, world.patient, world.pharmacy, world.admin):
        assert post_status(client, who, oid, "SAMPLE_COLLECTED").status_code == 403
        assert client.post(f"{L}/tests/{oid}/result", headers=who, files={"file": ("a.txt", result_file())}).status_code == 403
        assert client.post(f"{L}/tests/{oid}/urgent", headers=who, json={"urgent": True}).status_code == 403
        assert client.get(f"{L}/dashboard", headers=who).status_code == 403
    for who in (world.doctor, world.patient, world.pharmacy, world.admin):
        assert client.get(f"{L}/worklist", headers=who).status_code == 403
    assert client.get(f"{L}/worklist").status_code == 401
    # patients see only their own tests; a doctor only their own patients'
    other = client.post("/api/patients", headers=world.employee, json={"email": "meera@example.com", "full_name": "Meera K", "password": PASSWORD, "assigned_doctor_id": world.other_doctor_id}).json()["patient"]["id"]
    meera = login(client, "meera@example.com")
    assert client.get(f"{L}/my-tests", headers=meera).json() == []
    assert client.get(f"{L}/patient/{world.patient_id}/tests", headers=world.other_doctor).status_code == 403
    assert client.get(f"{L}/patient/{other}/tests", headers=world.doctor).status_code == 403
    assert client.get(f"{L}/patient/{world.patient_id}/tests", headers=world.doctor).status_code == 200
    # the lab cannot read patient reports or medicines
    assert client.get("/api/reports", headers=lab).status_code == 403
    assert client.get("/api/prescriptions", headers=lab).status_code in (403, 404)
    assert "sample_code" not in client.get(f"{L}/my-tests", headers=world.patient).json()[0]          # internal label is not shown to patients
    assert client.post(f"{L}/tests/99999/status", headers=lab, json={"status": "IN_PROGRESS"}).status_code == 404
    assert client.post(f"{L}/tests/{oid}/status", headers=lab, json={"status": "BOGUS"}).status_code == 422


def test_two_requests_creating_the_same_work_items_at_once_do_not_fail(client, world, lab):
    """The work list and the dashboard are asked for together: both may try to create the rows for a new prescription."""
    advise(client, world)
    from app.database.connection import SessionLocal
    from app.services import lab_service
    from app.database.models import LabTestOrder
    with SessionLocal() as first, SessionLocal() as second:
        real_commit = first.commit

        def commit_after_the_other_request():
            first.commit = real_commit
            lab_service.sync_orders(second)                                        # the other request finishes first
            real_commit()

        first.commit = commit_after_the_other_request
        lab_service.sync_orders(first)                                             # must not raise
    with SessionLocal() as check:
        assert check.query(LabTestOrder).count() == 2                              # one row per test, no duplicates
    assert client.get(f"{L}/dashboard", headers=lab).status_code == 200
