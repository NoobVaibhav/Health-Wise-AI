"""Phase 8: the honest integration list, the notification outbox (nothing is claimed as sent that was not), reminders, result-ready notices without values, and the FHIR-shaped export."""
from datetime import timedelta

import pytest

from app.core.config import get_settings
from app.database.connection import SessionLocal
from app.database.models import Appointment, Diagnosis, LabResult, LabTestOrder, NotificationOutbox, RadiologyOrder, RadiologyReport, utcnow
from app.services import integration_service


@pytest.fixture()
def iw(client, world):
    res = client.post("/api/opd/walk-in", headers=world.employee, json={"patient_id": world.patient_id, "doctor_id": world.doctor_id})
    world.enc = res.json()["encounter_id"]
    return world


def appointment(w, hours=5, status="SCHEDULED"):
    with SessionLocal() as db:
        a = Appointment(patient_id=w.patient_id, doctor_id=w.doctor_id, scheduled_at=utcnow() + timedelta(hours=hours), status=status)
        db.add(a)
        db.commit()
        return a.id


def outbox(client, w, **params):
    return client.get("/api/integrations/outbox", headers=w.admin, params=params).json()


def test_the_status_list_is_honest_and_for_the_administrator(client, iw):
    rows = {r["key"]: r for r in client.get("/api/integrations/status", headers=iw.admin).json()}
    assert rows["SMS"]["state"] == "ADAPTER_ONLY" and "No SMS provider" in rows["SMS"]["note"]
    assert rows["FHIR"]["state"] == "BUILT_UNVERIFIED" and "Not validated" in rows["FHIR"]["note"]
    assert all(rows[k]["state"] == "NOT_BUILT" for k in ("ABDM", "DICOM", "ANALYSER", "PAYMENT", "TPA"))
    for who in (iw.doctor, iw.employee, iw.patient, iw.pharmacy):
        assert client.get("/api/integrations/status", headers=who).status_code == 403
        assert client.get("/api/integrations/outbox", headers=who).status_code == 403
        assert client.post("/api/integrations/reminders/run", headers=who, json={}).status_code == 403


def test_reminders_are_queued_once_and_stay_queued_without_a_delivery_service(client, iw):
    appointment(iw, hours=5)
    appointment(iw, hours=60)                                                      # too far away
    appointment(iw, hours=6, status="CANCELLED")
    first = client.post("/api/integrations/reminders/run", headers=iw.admin, json={"hours_ahead": 24}).json()
    assert first == {"queued": 2}                                                  # one SMS (phone saved) and one e-mail
    assert client.post("/api/integrations/reminders/run", headers=iw.admin, json={"hours_ahead": 24}).json() == {"queued": 0}
    rows = outbox(client, iw)
    assert {r["channel"] for r in rows} == {"SMS", "EMAIL"} and all(r["status"] == "QUEUED" for r in rows)
    assert client.post("/api/integrations/reminders/run", headers=iw.admin, json={"hours_ahead": 0}).status_code == 422
    result = client.post("/api/integrations/outbox/dispatch", headers=iw.admin).json()
    assert result == {"sent": 0, "failed": 0, "waiting_for_a_delivery_service": 2}
    assert all(r["status"] == "QUEUED" and "No delivery service" in r["error"] for r in outbox(client, iw))


def test_with_a_delivery_service_the_messages_are_sent_and_marked_so(client, iw, monkeypatch):
    monkeypatch.setattr(get_settings(), "notify_test_adapter", True)
    integration_service.SENT_LOG.clear()
    appointment(iw)
    client.post("/api/integrations/reminders/run", headers=iw.admin, json={})
    result = client.post("/api/integrations/outbox/dispatch", headers=iw.admin).json()
    assert result["sent"] == 2 and result["failed"] == 0
    assert {c for c, _, _ in integration_service.SENT_LOG} == {"SMS", "EMAIL"} and "appointment with Dr. Anjali Sharma" in integration_service.SENT_LOG[0][2]
    assert all(r["status"] == "SENT" and r["sent_at"] for r in outbox(client, iw))
    assert client.post("/api/integrations/outbox/dispatch", headers=iw.admin).json()["sent"] == 0              # nothing is sent twice


def test_a_failing_adapter_is_retried_then_marked_failed(client, iw, monkeypatch):
    monkeypatch.setattr(get_settings(), "notify_test_adapter", True)
    monkeypatch.setattr(integration_service, "send_now", lambda *a: (False, "mailbox full"))
    appointment(iw)
    client.post("/api/integrations/reminders/run", headers=iw.admin, json={})
    for _ in range(3):
        client.post("/api/integrations/outbox/dispatch", headers=iw.admin)
    rows = outbox(client, iw)
    assert all(r["status"] == "FAILED" and r["attempts"] == 3 and r["error"] == "mailbox full" for r in rows)


def test_a_result_ready_notice_never_carries_a_value(client, iw):
    with SessionLocal() as db:
        o = LabTestOrder(encounter_id=iw.enc, patient_id=iw.patient_id, doctor_id=iw.doctor_id, test_name="Serum Electrolytes", status="COMPLETED", result_status="APPROVED", approved_at=utcnow())
        db.add(o)
        db.flush()
        db.add(LabResult(order_id=o.id, analyte_name="Potassium", value_text="6.8", value_num=6.8, unit="mmol/L", flag="CRITICAL_HIGH"))
        db.commit()
        oid = o.id
    assert client.post(f"/api/lab/tests/{oid}/seen", headers=iw.doctor).status_code == 200
    rows = outbox(client, iw)
    assert {r["template"] for r in rows} == {"RESULT_READY"}
    with SessionLocal() as db:
        bodies = [r.body for r in db.query(NotificationOutbox).all()]
    assert bodies and all("6.8" not in b and "Potassium" not in b for b in bodies)
    client.post(f"/api/lab/tests/{oid}/seen", headers=iw.doctor)
    assert len(outbox(client, iw)) == len(rows)                                       # a second "seen" queues nothing new


def seed_records(w):
    with SessionLocal() as db:
        db.add(Diagnosis(encounter_id=w.enc, patient_id=w.patient_id, text="Hypertension", code="I10", kind="FINAL", added_by=1, is_active=True))
        db.add(Diagnosis(encounter_id=w.enc, patient_id=w.patient_id, text="Draft thing", kind="DRAFT", added_by=1, is_active=True))
        for name, seen in (("Seen panel", True), ("Unseen panel", False)):
            o = LabTestOrder(encounter_id=w.enc, patient_id=w.patient_id, doctor_id=w.doctor_id, test_name=name, status="COMPLETED", result_status="APPROVED", approved_at=utcnow(), doctor_seen_at=utcnow() if seen else None)
            db.add(o)
            db.flush()
            db.add(LabResult(order_id=o.id, analyte_name=f"{name} value", value_text="4.2", value_num=4.2, unit="mmol/L", ref_low=3.5, ref_high=5.0, flag="NORMAL"))
        s = RadiologyOrder(encounter_id=w.enc, patient_id=w.patient_id, doctor_id=w.doctor_id, study="Chest X-ray", modality="XRAY", status="APPROVED", approved_at=utcnow())
        db.add(s)
        db.flush()
        db.add(RadiologyReport(order_id=s.id, findings="Clear", impression="Normal chest", reported_by=1))
        db.commit()


def kinds(bundle):
    return sorted(e["resource"]["resourceType"] for e in bundle["entry"])


def test_the_fhir_export_for_the_doctor_and_the_patients_own_released_copy(client, iw):
    seed_records(iw)
    doc = client.get(f"/api/integrations/fhir/patients/{iw.patient_id}/bundle", headers=iw.doctor).json()
    assert doc["resourceType"] == "Bundle" and doc["meta"]["tag"][0]["code"] == "unvalidated" and doc["total"] == len(doc["entry"])
    conditions = [e["resource"] for e in doc["entry"] if e["resource"]["resourceType"] == "Condition"]
    assert [c["code"]["text"] for c in conditions] == ["Hypertension"]                                  # a draft is not exported
    assert conditions[0]["code"]["coding"][0]["code"] == "I10"
    obs = [e["resource"] for e in doc["entry"] if e["resource"]["resourceType"] == "Observation"]
    assert len(obs) == 2 and obs[0]["valueQuantity"]["unit"] == "mmol/L" and obs[0]["referenceRange"][0]["low"]["value"] == 3.5
    assert "DiagnosticReport" in kinds(doc) and "Patient" in kinds(doc)
    mine = client.get("/api/integrations/fhir/my-bundle", headers=iw.patient).json()
    assert [e["resource"]["code"]["text"] for e in mine["entry"] if e["resource"]["resourceType"] == "Observation"] == ["Seen panel value"]     # the unseen result is held back
    assert "DiagnosticReport" not in kinds(mine)                                                          # the scan was not seen by the doctor yet
    assert client.get(f"/api/integrations/fhir/patients/{iw.patient_id}/bundle", headers=iw.other_doctor).status_code == 403
    for who in (iw.patient, iw.employee, iw.pharmacy):
        assert client.get(f"/api/integrations/fhir/patients/{iw.patient_id}/bundle", headers=who).status_code == 403
    assert client.get("/api/integrations/fhir/my-bundle", headers=iw.doctor).status_code == 403
