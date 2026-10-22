# Patient Clinical Intelligence & History Analyzer

A doctor opens one patient and sees the **documented** history, the changes in laboratory results, the medicines, the emergency
visits and the pending follow-ups. Every statement shows how it is known and links to the record it came from. The system does not
diagnose, does not name a cause for an emergency, and does not say that a patient is healthy.

Where: **Doctor > My Patients > a patient > "Clinical summary"**.

## 1. Architecture (hybrid)

```
 existing records ──► deterministic services (ordinary code) ──► evidence-linked summary ──► doctor
 (reports, notes,        timeline · report comparison ·            statements + label + sources
  prescriptions,         medication history · follow-ups ·                │
  appointments,          emergency review · summary builder               ▼
  history, assessments)                                         optional AI narrative (separate block,
                                                                 only from verified statements, validated)
```

| Layer | Files |
|---|---|
| Records (reused) | `models.py`: Patient, HealthReport, HealthParameter, Appointment, DoctorNote, DoctorRecommendation, Prescription, PrescriptionItem, MedicineDispensing, MedicalHistoryEntry, PatientHistory, PatientMedication, ClinicalAssessment, AuditLog |
| New tables | `EmergencyEvent`, `EmergencyTimelineEntry`, `FollowUpTask`, `SummaryReview`, `ClinicalSummarySnapshot` |
| Services | `clinical_timeline.py`, `report_trends.py`, `medication_history.py`, `follow_ups.py`, `emergency_review.py`, `clinical_summary.py`, `ai_summary.py` |
| API | `routers/clinical_intel.py` (+ schemas `schemas/clinical_intel.py`) |
| Screens | `frontend/src/components/clinical/*` (`ClinicalIntel`, `SummaryTab`, `TimelineTab`, `TrendsTab`, `EmergencyTab`, `MedsFollowTabs`, `Statement`) |
| Tests | `backend/tests/test_clinical_intel.py` (21 tests, synthetic patients only) |

Tables are created automatically at start-up (`create_all`); no manual migration is needed.

## 2. What the doctor sees

1. **Summary**: overview (allergies, conditions, medicines on record, latest report, latest encounter, pending follow-ups, unresolved
   findings), then *What has happened*, *Current status*, *Important changes*, *Red flags*, *Missing or conflicting information*, and an
   optional AI narrative. Print or save as PDF.
2. **Timeline**: searchable, newest first; events without a date are listed last as "Date not recorded".
3. **Report trends**: previous against latest for every parameter (value, date, change, printed range, trend, result, review status) and a chart.
4. **Emergency**: record a visit, then review it (timeline, what happened, cause section, missing information).
5. **Medications**: prescribed, dispensed and taken are shown as different facts; changes, duplicates, allergy matches, missing details.
6. **Follow-ups**: tasks with due date and outcome, recommendations or advised tests with no documented completion, upcoming appointments.
7. **Evidence**: every source record behind the summary.

Doctor actions on any statement: mark reviewed, add an interpretation, correct an extraction error, flag missing information. These are
stored in `summary_reviews` with the doctor and time, shown in a separate "doctor's review" style, and never overwrite the original record.

## 3. Rules the code enforces

* Labels: *Directly documented*, *Calculated from recorded values*, *Requires clinician verification*, *Insufficient information*, and
  *AI-generated summary of documented findings* (AI text only, kept in its own block).
* Dates: the event date, the date printed on a report, the upload date and the review date are different. An upload date is never used as the test date.
* Reports: only the same parameter is compared; units must match or use a validated factor (glucose, creatinine, haemoglobin, cholesterol,
  triglycerides); otherwise "Not comparable". The printed reference range is used; if none is printed it says "reference range not provided".
  "Improved" or "Worsened" only when the printed range supports it; otherwise "Needs clinical interpretation". Duplicates are counted once and conflicts are flagged.
* Emergency cause: *documented cause* (written by the treating clinician), *documented contributing factors*, *possible associations*
  (items for review, "not established as a cause") and *unknown* ("Cause: not established in the available records."). No gap is filled.
* Medicines: a prescription or a dispensing does not show that the patient took the medicine ("Adherence: not documented").
* Urgent notice (very far outside a printed range): "arrange immediate professional assessment according to your clinical protocol".
  These rules must be validated by qualified clinicians before clinical use.

## 4. API (all doctor-only, patient-specific, `Authorization: Bearer <token>`)

| Method and path | Purpose |
|---|---|
| `GET /api/doctor/patients/{id}/clinical-summary` | The evidence-linked summary (audited) |
| `POST /api/doctor/patients/{id}/clinical-summary/generate` | Optional AI narrative (503 if no model, 502 if unusable) |
| `POST /api/doctor/patients/{id}/clinical-summary/review` | Reviewed / interpretation / correction / missing flag |
| `GET /api/doctor/patients/{id}/timeline?q=` | Timeline with search |
| `GET /api/doctor/patients/{id}/report-trends` | Parameter series and comparisons |
| `GET /api/doctor/patients/{id}/medication-history` | Medication history |
| `GET/POST /api/doctor/patients/{id}/follow-ups`, `PATCH .../follow-ups/{task_id}` | Follow-up tracker |
| `GET /api/doctor/patients/{id}/emergency-history` | List of emergency visits, or the "none found" message |
| `POST /api/doctor/patients/{id}/emergency-events` | Record an emergency visit (every field optional) |
| `GET /api/doctor/emergency-events/{event_id}` | Review of one visit (checks the patient's access; audited) |

Interactive documentation: `/docs` on the running backend.

## 5. Privacy and safety

* Roles: only authorised doctors. Pharmacy, employees, administrators, patients, other doctors and anonymous callers are refused (tested on every endpoint).
* Audit log: summary viewed, emergency recorded or viewed, follow-up created or updated, review saved, AI narrative written.
* The AI model (optional, `LLM_API_KEY`) receives only verified statements with personal details removed (no name, phone, address, file names or record ids).
  Its reply is accepted only if every paragraph cites existing statement keys, passes the doctor safety filter (no doses or prescribing) and does not claim a cause. If anything fails there is no AI text and the summary is unchanged.
* Displayed disclaimer: "HealthWise AI assists clinicians by organizing documented patient history and generating evidence-linked summaries. It does not independently diagnose diseases, establish emergency causation, or replace clinical judgment."

## 6. Phases, and how each was verified

| Phase | Done | Checked by |
|---|---|---|
| 1-2 Inspect and map | Existing sources and relationships listed in section 1; missing pieces were the emergency record, timestamped steps, follow-up tasks and doctor reviews | Code reading |
| 3 Timeline | `clinical_timeline.py` | `test_timeline_is_chronological_linked_and_never_guesses_a_date` |
| 4 Comparison | `report_trends.py` | 5 tests: printed ranges, single result, unit conversion, different ranges and missing dates, duplicates and conflicts |
| 5 Summary | `clinical_summary.py` | labels and sources, empty states, urgent notice, no diagnosis wording, no name in payload |
| 6 Emergency | models, `emergency_review.py` | complete, incomplete, documented versus unknown cause, patient check |
| 7 Medicines and follow-ups | `medication_history.py`, `follow_ups.py` | prescribed versus dispensed, changes, duplicates, allergy match, overdue and completion |
| 8 Interface | `components/clinical/*` | Run in a browser on a synthetic patient: no console errors |
| 9 Access, audit, privacy, AI | router, `ai_summary.py` | 403 on all endpoints for every other role, audit actions, AI failure and validation, data minimisation |
| 10 Tests | 21 new tests; the whole suite: 163 passed | `pytest` in `backend` |

## 7. Verify it yourself

```bash
cd backend && .venv/Scripts/python -m pytest -q tests/test_clinical_intel.py
```
Then start the backend and frontend, log in as a doctor (demo account in the README), open a patient and choose **Clinical summary**.

## 8. Known limitations

* The "important findings", "red flag" and association rules are simple and general. They are not a validated clinical rules engine.
* Medication interactions are not checked beyond duplicates and allergy-name matches.
* There is no scheduled export format other than printing or saving as PDF.
* Emergency visits are entered by a doctor; the system does not import records from an external hospital system.
* Not covered yet: an architecture diagram and ER diagram for this module in the SRS, and a retention or deletion policy for the new tables.
