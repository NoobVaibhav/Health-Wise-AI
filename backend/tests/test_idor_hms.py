"""Cross-account probing of the hospital modules (diagnostics, radiology, IPD, OPD, finance): another patient, an unrelated doctor, and staff roles outside the workflow
try ids that belong to patient 1. None of them may read or change those records. Data is built through the real API by the acceptance-workflow fixture; all invented."""
import pytest

from tests.conftest import PASSWORD, login
from tests.test_acceptance_workflows import hw, invoice_and_pay          # noqa: F401  (hw is a fixture)

REFUSED = (401, 403, 404)


@pytest.fixture()
def rec(client, hw):                       # noqa: F811
    r = type("R", (), {})()
    r.encounter = client.post("/api/opd/walk-in", headers=hw.employee, json={"patient_id": hw.patient_id, "doctor_id": hw.doctor_id}).json()["encounter_id"]
    client.put(f"/api/opd/encounters/{r.encounter}/consultation", headers=hw.doctor, json={"complaint": "Fever", "assessment": "Viral", "plan": "Rest"})
    client.post(f"/api/opd/encounters/{r.encounter}/orders", headers=hw.doctor, json={"kind": "LAB", "text": "Serum Electrolytes", "priority": "ROUTINE"})
    r.lab = next(t for t in client.get("/api/lab/worklist?status_filter=OPEN", headers=hw.tech).json()["tests"] if t["test_name"] == "Serum Electrolytes")["id"]
    adm = client.post("/api/ipd/admissions", headers=hw.doctor, json={"patient_id": hw.patient_id, "diagnosis": "Pneumonia", "bed_id": hw.beds[0]}).json()
    r.admission = adm["id"] if "id" in adm else adm["admission"]["id"]
    client.post(f"/api/ipd/admissions/{r.admission}/orders", headers=hw.doctor, json={"kind": "RADIOLOGY", "text": "Chest X-ray", "priority": "ROUTINE"})
    r.scan = next(s for s in client.get("/api/radiology/worklist", headers=hw.rtech).json()["studies"] if s["study"] == "Chest X-ray")["id"]
    r.invoice = invoice_and_pay(client, hw, pay=False)["id"]            # the OPD and lab charges of patient 1, made final but not paid
    other = client.post("/api/patients", headers=hw.employee, json={"email": "meera@example.com", "full_name": "Meera Kulkarni", "password": PASSWORD, "gender": "female", "date_of_birth": "1990-01-01", "phone": "9876500001"})
    assert other.status_code == 201, other.text
    r.other_patient = login(client, "meera@example.com")
    return r


def attempts(hw, r):
    pid = hw.patient_id
    rows = [
        ("get", f"/api/lab/patient/{pid}/tests", None),
        ("post", f"/api/lab/tests/{r.lab}/results", {"submit": True, "results": [{"analyte_id": hw.k, "value": "6.4"}]}),
        ("post", f"/api/lab/tests/{r.lab}/seen", None),
        ("get", f"/api/ipd/admissions/{r.admission}", None),
        ("post", f"/api/ipd/admissions/{r.admission}/notes", {"note": "tampered"}),
        ("post", f"/api/ipd/admissions/{r.admission}/discharge", {}),
        ("put", f"/api/ipd/admissions/{r.admission}/discharge-summary", {"final_diagnosis": "tampered"}),
        ("put", f"/api/opd/encounters/{r.encounter}/consultation", {"complaint": "tampered"}),
        ("post", f"/api/opd/encounters/{r.encounter}/sign", None),
        ("post", f"/api/opd/encounters/{r.encounter}/orders", {"kind": "LAB", "text": "Serum Electrolytes", "priority": "ROUTINE"}),
        ("post", f"/api/radiology/orders/{r.scan}/seen", None),
        ("get", f"/api/finance/patients/{pid}/overview", None),
    ]
    rows += [("get", f"/api/finance/invoices/{r.invoice}", None), ("post", f"/api/finance/invoices/{r.invoice}/cancel", {"reason": "tampered"}),
             ("post", f"/api/finance/invoices/{r.invoice}/pay", {"amount": 1, "method": "CASH"})]
    return rows


def call(client, who, rows):
    bad = []
    for method, path, body in rows:
        kw = {"json": body} if body is not None else {}
        res = getattr(client, method)(path, headers=who, **kw)
        if res.status_code not in REFUSED:
            bad.append(f"{method.upper()} {path} -> {res.status_code} {res.text[:120]}")
    return bad


def test_another_patient_reaches_nothing_of_patient_1(client, hw, rec):          # noqa: F811
    bad = call(client, rec.other_patient, attempts(hw, rec))
    assert not bad, "\n".join(bad)


def test_the_patient_cannot_use_staff_actions_on_own_records(client, hw, rec):      # noqa: F811
    rows = [r for r in attempts(hw, rec) if r[0] != "get"]
    bad = call(client, hw.patient, rows)
    assert not bad, "\n".join(bad)


@pytest.mark.parametrize("role", ["pharmacy", "b1", "tech"])
def test_staff_outside_the_clinical_workflow_cannot_write_clinical_records(client, hw, rec, role):    # noqa: F811
    writes = [r for r in attempts(hw, rec) if r[0] != "get" and "/finance/" not in r[1] and "/lab/" not in r[1]]
    bad = call(client, getattr(hw, role), writes)
    assert not bad, "\n".join(bad)


def test_the_pharmacy_cannot_read_lab_results_and_billing_cannot_read_clinical_notes(client, hw, rec):    # noqa: F811
    assert client.get(f"/api/lab/patient/{hw.patient_id}/tests", headers=hw.pharmacy).status_code in REFUSED
    seen = client.get(f"/api/ipd/admissions/{rec.admission}", headers=hw.b1)          # the billing desk may see the stay itself (bed, dates), never the clinical part
    assert seen.status_code in REFUSED or (seen.status_code == 200 and seen.json().get("clinical") is False
                                           and not any(k in seen.json() for k in ("notes", "medications", "orders", "alerts", "discharge_summary")))
    assert client.get(f"/api/doctor/patients/{hw.patient_id}/history", headers=hw.b1).status_code in REFUSED
