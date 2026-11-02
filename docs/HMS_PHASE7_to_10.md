# HMS Phases 7 to 10: AI, interoperability, security and the final integration

## Phase 7: AI that stays inside the records
**Reused:** the patient assistant (rule-based intents in English, Hindi and Marathi, voice, sources on every answer), the report analyser, the clinical summary, the timeline, the comparison of results, the safety filter.

**New**
- The doctor's timeline and summary now include the hospital's own FINISHED records: signed consultations, diagnoses (final, provisional and draft labelled as such), admissions, approved discharge summaries, pathologist-approved lab results (with the count outside the hospital's range and critical values), radiologist-approved scan reports, completed operations and transfusions. A draft, an unsigned note or an unapproved result is never shown as a fact.
- Approved laboratory values join the result comparison next to uploaded reports, with the hospital's own range (never a guessed one). For the patient they count as reviewed only after the doctor has seen them.
- The patient assistant answers about **bills** (from the patient's own final invoices), **scans** (the radiologist's words only after the doctor has seen the report; it never explains a scan) and **hospital stays and operations** (a discharge summary only once approved). When nothing is on record it says so.
- Not changed on purpose: the assistant does not diagnose, prescribe or change treatment; an AI wording service is optional and consent-based.

## Phase 8: interoperability, only what can be verified
- **Notifications:** an outbox with adapters. E-mail works when SMTP is configured. SMS and WhatsApp have no provider, so those messages wait (QUEUED) and are never reported as sent. Reminders for appointments in the next hours; "your result is ready" notices that never contain a value.
- **FHIR R4-shaped export** (Bundle of Patient, Condition, Observation, DiagnosticReport, MedicationRequest, Encounter) for a doctor's authorised patient and as the patient's own released copy. It is tagged **unvalidated**: not checked against a FHIR server or an ABDM profile.
- An administrator's **status list** says plainly what is READY, ADAPTER_ONLY, BUILT_UNVERIFIED, PARTIAL or NOT_BUILT (ABDM, DICOM/PACS, analyser link, payment gateway and TPA portal are not built).
- **Mobile-code sign-in:** a 6-digit code (5 minutes, one use, hashed, 5 tries, 3 codes per 10 minutes, one account per number, the same answer for known and unknown numbers). With `OTP_DEMO_MODE=true` (local demo only) the code is shown on the screen because there is no SMS provider.

## Phase 9: security and critical transactions
- **Audit:** a test lists every route that changes data and fails if one writes no audit line (a short list of routes keeps its own trail, with the reason). Ten routes that lacked an audit line now write one (diagnoses, order status, discharge summary, stock batches, receiving stock, departments, ED timeline, staff assignments).
- **Two people at the same moment:** tests found three real faults that are now fixed with row locking (`app/utils/locking.py`): concurrent payments could overpay a bill, a refund could be approved more than once, and one blood unit could be matched to several requests. The same lock now guards invoices, refunds, advances, claims, requisitions, purchase orders, stock counts, ward medicine requests, theatre bookings and result approvals. SQLite has no row locks, so a no-op write is used (the database lock); PostgreSQL gets `SELECT ... FOR UPDATE`.
- **Isolation:** tests show a patient cannot reach another patient's bills, receipts, results, scans or export, a doctor cannot reach patients that are not theirs, and the billing desk never reaches clinical notes.
- **SQLite honesty:** one writer at a time is fine for a small hospital. A multi-branch or large hospital should move to PostgreSQL (the locking code, `schema.sql` and `DATABASE_URL` already allow it). This is a proposal, not applied.

## Phase 10: the final integration
- `tests/test_acceptance_workflows.py` runs the seven acceptance workflows of the brief end to end across modules: (1) new patient to a paid consultation, (2) lab order to the patient's report, (3) inpatient stay with a scan, a ward medicine request, an advance, discharge and the final bill, (4) emergency to admission with the investigations reaching the lab and radiology lists, (5) prescription to dispensing, billing, stock and a return, (6) the assistant answering from the patient's own records, (7) referral and the plan coming back.
- Full backend and frontend suites, the production build, the schema file (`backend/schema.sql`) and the endpoint matrix (`docs/ENDPOINT_MATRIX.md`) are regenerated.

## What is still not done (and why it matters)
SMS and WhatsApp delivery, an online payment gateway, ABDM/ABHA exchange, DICOM/PACS, laboratory analyser links, TPA portals, GST returns, and pharmacy transfers between stores are not built. Clinical limits (blood bank, reference ranges) and legal compliance must be reviewed by qualified professionals before real use. Demo data and demo passwords are for local testing only.
