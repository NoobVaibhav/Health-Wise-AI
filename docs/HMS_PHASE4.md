# HMS Phase 4: diagnostics (laboratory and radiology)

## What was reused
`LabTestOrder` and the lab worklist (order, sample, barcode label, rejection), `ClinicalOrder` of kind LAB and RADIOLOGY from Phase 3, `ClinicalAlert`, the report upload and review flow, the audit log, the doctor patient scope checks.

## What is new
**Catalogue** (`diagnostic_tests`, `diagnostic_analytes`): the hospital's own list of tests and scans, with the unit, method, reference range and critical limits of every measured value. Only the administrator changes it (`/api/diagnostics`). **AI never supplies a range.** A value without limits is shown as "No range set", never guessed. The demo catalogue in `seed_demo.py` holds typical adult limits for demonstration only. A hospital must set its own with its pathologist.

**Laboratory results** (`lab_results`): the technician enters values against the catalogue. Unit, method and range are copied at entry time, so a later catalogue change never alters an old report. Flags: normal, low, high, critically low, critically high, no range set.
- A critical value raises a CRITICAL `ClinicalAlert` the moment the result is sent on. It is plain number comparison, no AI.
- Only a pathologist approves (`staff_type` PATHOLOGIST), and never the person who entered the result. A result can be sent back with a comment. An approved result is never edited.
- The doctor sees values only after approval and marks the result "seen"; only then does the patient see them.
- Comparison: each value shows the patient's latest earlier approved value of the same test in the same unit (a different unit is not compared).
- The old way (upload a result file) still works.

**Radiology** (`radiology_orders`, `radiology_reports`, `radiology_attachments`): ordered, scheduled, scan done, reported, approved. A technician schedules, does the scan and attaches the image or document (JPG, PNG or PDF, checked by content). Only a radiologist writes and approves the report. The same doctor-then-patient visibility applies. The report shows earlier approved studies of the same modality. **This is not DICOM or PACS.**

**Encounter orders reach the labs:** every LAB and RADIOLOGY order placed in an encounter becomes lab or radiology work once (idempotent). Cancelling the order cancels open work.

## Roles (assumption)
Pathologist and radiologist are not separate logins families. Like doctor grades, they are one role with a type: Lab staff is a technician or a pathologist, and the new **Radiology** role is a technician or a radiologist. The admin chooses this when creating the person (`staff_type`).

## Database changes (idempotent, run at start-up)
- New tables: `radiology_staff`, `diagnostic_tests`, `diagnostic_analytes`, `lab_results`, `radiology_orders`, `radiology_reports`, `radiology_attachments`.
- `lab_test_orders` gains: clinical_order_id, encounter_id, test_id, assigned_to, result_status, has_critical, approved_by, approved_at, approval_note, doctor_seen_at. `prescription_id` becomes optional: an old database is rebuilt once with the rows copied unchanged (tested). `lab_staff.staff_type` is added.

## APIs
`/api/lab`: `GET /pending-approval`, `GET /tests/{id}`, `POST /tests/{id}/results`, `/approve`, `/return`, `/seen`. `/api/radiology`: `dashboard`, `worklist`, `orders/{id}` (`schedule`, `start`, `files`, `report`, `approve`, `seen`), `files/{id}`, `my-studies`, `patient/{id}/studies`. `/api/diagnostics`: `GET/POST tests`, `POST tests/{id}/analytes`. `POST /api/admin/radiology-staff`.

## Limits
Not DICOM or PACS. No barcode scanner or analyser link. Reference ranges are by test only (no age or sex bands yet). Billing of tests is Phase 6. Compliance and clinical limits must be reviewed by qualified professionals.
