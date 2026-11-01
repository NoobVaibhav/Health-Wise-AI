"""Phase 8: interoperability, only what can honestly work and be verified.

- Notifications: a message is first written to an OUTBOX and then handed to an adapter for its channel. Only the e-mail adapter (SMTP) exists, and only when the SMTP settings
  are filled in; SMS and WhatsApp have no provider in this build, so those messages stay QUEUED. Nothing is ever claimed as sent that was not.
  A message about a result says only that it is ready (never the values).
- FHIR: a read-only, FHIR R4 shaped export (a Bundle) of a patient's finished records. It is NOT validated against a FHIR server or an ABDM profile and carries a tag that says so.
- The status list says plainly which integrations are built, which are only an adapter, and which are not built.
"""
import smtplib
from datetime import timedelta
from email.message import EmailMessage

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.database.models import (
    Admission, Appointment, Diagnosis, DischargeSummary, LabTestOrder, NotificationOutbox, Patient, Prescription, RadiologyOrder, User, utcnow,
)

CHANNELS = ("EMAIL", "SMS", "WHATSAPP")
SENT_LOG: list[tuple[str, str, str]] = []                    # filled by the test adapter only


# ------------------------------------------------------------------ adapters
def adapter_ready(channel: str) -> bool:
    s = get_settings()
    if channel == "EMAIL":
        return bool(s.smtp_host and s.smtp_from) or s.notify_test_adapter
    return s.notify_test_adapter                                # SMS and WhatsApp: no provider in this build


def send_now(channel: str, address: str, subject: str, body: str) -> tuple[bool, str | None]:
    s = get_settings()
    if s.notify_test_adapter:                                   # tests only
        SENT_LOG.append((channel, address, body))
        return True, None
    if channel != "EMAIL" or not (s.smtp_host and s.smtp_from):
        return False, "No delivery service is set up for this channel."
    try:
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = s.smtp_from, address, subject
        msg.set_content(body)
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
            smtp.starttls()
            if s.smtp_user:
                smtp.login(s.smtp_user, s.smtp_password)
            smtp.send_message(msg)
        return True, None
    except Exception as exc:                                    # the reason is kept for the administrator; never raised into a request
        return False, str(exc)[:250]


def queue(db: Session, channel: str, user: User | None, address: str | None, template: str, subject: str, body: str, related_type: str, related_id: int) -> NotificationOutbox | None:
    """Put one message in the outbox, once per (template, record, channel). No address = nothing to send."""
    if not address:
        return None
    if db.scalar(select(NotificationOutbox.id).where(NotificationOutbox.template_key == template, NotificationOutbox.related_type == related_type,
                                                     NotificationOutbox.related_id == related_id, NotificationOutbox.channel == channel)):
        return None
    row = NotificationOutbox(channel=channel, recipient_user_id=user.id if user else None, address=address, template_key=template, subject=subject, body=body, related_type=related_type, related_id=related_id)
    db.add(row)
    return row


def dispatch(db: Session, limit: int = 100) -> dict:
    sent = failed = waiting = 0
    for row in db.scalars(select(NotificationOutbox).where(NotificationOutbox.status == "QUEUED").order_by(NotificationOutbox.id).limit(limit)):
        if not adapter_ready(row.channel):
            waiting += 1
            row.error = "No delivery service is set up for this channel."
            continue
        row.attempts += 1
        ok, err = send_now(row.channel, row.address, row.subject, row.body)
        row.status, row.error, row.sent_at = ("SENT", None, utcnow()) if ok else ("FAILED" if row.attempts >= 3 else "QUEUED", err, None)
        sent, failed = sent + ok, failed + (not ok)
    db.commit()
    return {"sent": sent, "failed": failed, "waiting_for_a_delivery_service": waiting}


# ------------------------------------------------------------------ messages
def queue_appointment_reminders(db: Session, hours_ahead: int = 24) -> dict:
    """A reminder for every appointment in the next hours that has none yet (SMS to the saved phone, e-mail to the saved address)."""
    now = utcnow()
    made = 0
    for a in db.scalars(select(Appointment).where(Appointment.status.in_(("SCHEDULED", "CONFIRMED")), Appointment.scheduled_at >= now, Appointment.scheduled_at <= now + timedelta(hours=hours_ahead))):
        patient = db.get(Patient, a.patient_id)
        doctor = a.doctor.user.full_name
        when = a.scheduled_at.strftime("%d %b %Y, %I:%M %p")
        text = f"Reminder: you have an appointment with {doctor} on {when}. Please arrive 10 minutes early."
        for channel, address in (("SMS", patient.phone), ("EMAIL", patient.user.email)):
            made += bool(queue(db, channel, patient.user, address, "APPOINTMENT_REMINDER", "Appointment reminder", text, "appointment", a.id))
    db.commit()
    return {"queued": made}


def queue_result_ready(db: Session, kind: str, record_id: int) -> None:
    """Tell the patient that a result is ready to see in the app. The message never carries a value or a finding."""
    order = db.get(LabTestOrder if kind == "lab" else RadiologyOrder, record_id)
    if order is None:
        return
    patient = db.get(Patient, order.patient_id)
    text = "Your test result is ready. Please open HealthWise to see it, or ask your doctor."
    for channel, address in (("SMS", patient.phone), ("EMAIL", patient.user.email)):
        queue(db, channel, patient.user, address, "RESULT_READY", "Your result is ready", text, kind, record_id)
    db.commit()


# ------------------------------------------------------------------ FHIR (shaped like R4, not validated)
def _entry(resource: dict) -> dict:
    return {"fullUrl": f"urn:healthwise:{resource['resourceType']}/{resource['id']}", "resource": resource}


def fhir_bundle(db: Session, patient: Patient, released_only: bool) -> dict:
    """`released_only` (the patient's own copy) leaves out a result or a scan the doctor has not seen yet."""
    pid = f"patient-{patient.id}"
    ref = {"reference": f"Patient/{pid}"}
    entries = [_entry({"resourceType": "Patient", "id": pid, "identifier": [{"system": "urn:healthwise:uhid", "value": patient.uhid or patient.patient_code}], "name": [{"text": patient.user.full_name}],
                       "gender": {"male": "male", "female": "female"}.get((patient.gender or "").lower(), "unknown"), **({"birthDate": patient.date_of_birth.isoformat()} if patient.date_of_birth else {}),
                       **({"telecom": [{"system": "phone", "value": patient.phone}]} if patient.phone else {})})]
    for d in db.scalars(select(Diagnosis).where(Diagnosis.patient_id == patient.id, Diagnosis.kind == "FINAL", Diagnosis.is_active.is_(True))):
        entries.append(_entry({"resourceType": "Condition", "id": f"condition-{d.id}", "subject": ref, "code": {"text": d.text, **({"coding": [{"system": "http://hl7.org/fhir/sid/icd-10", "code": d.code}]} if d.code else {})},
                               "recordedDate": d.added_at.date().isoformat(), "verificationStatus": {"text": "confirmed by the treating doctor"}}))
    for o in db.scalars(select(LabTestOrder).where(LabTestOrder.patient_id == patient.id, LabTestOrder.result_status == "APPROVED")):
        if released_only and not o.doctor_seen_at:
            continue
        for r in o.results:
            obs = {"resourceType": "Observation", "id": f"observation-{r.id}", "status": "final", "category": [{"text": "laboratory"}], "code": {"text": r.analyte_name}, "subject": ref,
                   "effectiveDateTime": o.approved_at.isoformat() + "Z", "note": [{"text": f"{o.test_name}. Range and flag are the hospital's own."}]}
            if r.value_num is not None:
                obs["valueQuantity"] = {"value": r.value_num, **({"unit": r.unit} if r.unit else {})}
            else:
                obs["valueString"] = r.value_text
            if r.ref_low is not None or r.ref_high is not None:
                obs["referenceRange"] = [{**({"low": {"value": r.ref_low}} if r.ref_low is not None else {}), **({"high": {"value": r.ref_high}} if r.ref_high is not None else {})}]
            obs["interpretation"] = [{"text": r.flag.replace("_", " ").lower()}]
            entries.append(_entry(obs))
    for o in db.scalars(select(RadiologyOrder).where(RadiologyOrder.patient_id == patient.id, RadiologyOrder.status == "APPROVED")):
        if released_only and not o.doctor_seen_at:
            continue
        entries.append(_entry({"resourceType": "DiagnosticReport", "id": f"diagnosticreport-{o.id}", "status": "final", "category": [{"text": "radiology"}], "code": {"text": o.study}, "subject": ref,
                               "effectiveDateTime": o.approved_at.isoformat() + "Z", **({"conclusion": o.report.impression} if o.report else {})}))
    for rx in db.scalars(select(Prescription).where(Prescription.patient_id == patient.id, Prescription.status.in_(("ACTIVE", "PARTIALLY_DISPENSED", "DISPENSED")))):
        for i in rx.items:
            entries.append(_entry({"resourceType": "MedicationRequest", "id": f"medicationrequest-{i.id}", "status": "active", "intent": "order", "subject": ref, "authoredOn": rx.prescription_date.isoformat(),
                                   "medicationCodeableConcept": {"text": i.medicine_name}, "dosageInstruction": [{"text": f"{i.dosage}, {i.frequency}, {i.duration}"}]}))
    for a in db.scalars(select(Admission).where(Admission.patient_id == patient.id)):
        summary = db.scalar(select(DischargeSummary).where(DischargeSummary.admission_id == a.id, DischargeSummary.status == "APPROVED"))
        entries.append(_entry({"resourceType": "Encounter", "id": f"encounter-{a.id}", "status": "finished" if a.discharged_at else "in-progress", "class": {"code": "IMP", "display": "inpatient encounter"}, "subject": ref,
                               "period": {"start": a.admitted_at.isoformat() + "Z", **({"end": a.discharged_at.isoformat() + "Z"} if a.discharged_at else {})},
                               **({"reasonCode": [{"text": a.admitting_diagnosis}]} if a.admitting_diagnosis else {}), **({"extension": [{"url": "urn:healthwise:discharge-summary", "valueString": summary.final_diagnosis or ""}]} if summary else {})}))
    return {"resourceType": "Bundle", "type": "collection", "timestamp": utcnow().isoformat() + "Z", "meta": {"tag": [{"system": "urn:healthwise:validation", "code": "unvalidated",
            "display": "FHIR-shaped export. Not validated against a FHIR server or an ABDM profile."}]}, "total": len(entries), "entry": entries}


# ------------------------------------------------------------------ the honest list
def status_list(db: Session) -> list[dict]:
    s = get_settings()
    smtp = bool(s.smtp_host and s.smtp_from)
    return [
        {"key": "EMAIL", "name": "E-mail reminders and notices", "state": "READY" if smtp else "ADAPTER_ONLY", "note": "Works when the SMTP settings are filled in (SMTP_HOST, SMTP_FROM...)."},
        {"key": "SMS", "name": "SMS reminders and mobile-code sign-in", "state": "ADAPTER_ONLY", "note": "Messages wait in the outbox. No SMS provider is connected, so nothing is sent. Mobile-code sign-in shows the code on screen only in demo mode."},
        {"key": "WHATSAPP", "name": "WhatsApp messages", "state": "ADAPTER_ONLY", "note": "No provider is connected."},
        {"key": "FHIR", "name": "FHIR R4 export (read only)", "state": "BUILT_UNVERIFIED", "note": "A Bundle of Patient, Condition, Observation, DiagnosticReport, MedicationRequest and Encounter. Not validated against a FHIR server or profile."},
        {"key": "ABDM", "name": "ABDM / ABHA services", "state": "NOT_BUILT", "note": "The ABHA number can be stored with consent. No ABDM gateway, health-information exchange or consent manager is connected."},
        {"key": "DICOM", "name": "DICOM / PACS", "state": "NOT_BUILT", "note": "Scan images are stored as JPG, PNG or PDF files only."},
        {"key": "ANALYSER", "name": "Laboratory analyser link", "state": "NOT_BUILT", "note": "Results are typed in by a technician and approved by a pathologist."},
        {"key": "BARCODE", "name": "Barcode and QR", "state": "PARTIAL", "note": "Sample, medicine and unit numbers are printed as text codes; no scanner or label printer is connected."},
        {"key": "PAYMENT", "name": "Payment gateway", "state": "NOT_BUILT", "note": "Payments are recorded by staff (cash, UPI, card, bank transfer); no online gateway."},
        {"key": "TPA", "name": "Insurance / TPA portal", "state": "NOT_BUILT", "note": "Claims are handled step by step by staff inside the system; no portal is connected."},
        {"key": "EPRESCRIPTION", "name": "E-prescription", "state": "PARTIAL", "note": "A printable prescription PDF exists; it is not sent to an external prescription network."},
    ]
