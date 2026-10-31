# HealthWise AI to Multispeciality HMS: Phase 1 audit

Read-only audit of the repo as of commit `afc01b7`. Nothing was changed except this document. Statuses are from reading the models, routers and pages and from the test runs (backend 741 passed + 24 expected failures; frontend 203 passed). "Working" means it exists as a real backend + database + screen and has tests; it does not mean it covers everything in the brief.

## 1. What exists today (the base we extend)

**Size.** 42 tables, 21 routers, 45 services, about 10,400 lines in `routers/` and `services/`. Frontend: role areas admin, doctor, employee, lab, pharmacy, patient, trainee.

**Roles today (7):** ADMIN, DOCTOR, EMPLOYEE (reception), PATIENT, PHARMACY, LAB, TRAINEE. One `users.role` string; `require_roles(...)` per endpoint; `get_accessible_patient` for patient-level scope; temporary-password lock; login lockout; audit log.

**Tables by domain**
| Domain | Tables |
|---|---|
| Identity | `users`, `doctors`, `employees`, `pharmacy_staff`, `lab_staff`, `trainees` |
| Org | `departments` (name, active), `specializations` |
| Patients | `patients` (patient_code `P-0001`, demographics, assigned doctor) |
| Visits | `appointments` (patient, doctor, time, reason, status) |
| History | `patient_history`, `patient_medications`, `chronic_conditions`, `hospital_admissions` and `surgery_records` (**earlier stays and operations, written by a doctor, not live inpatient records**), `emergency_events` + `emergency_timeline_entries` (**earlier emergency visits, doctor-written**), `clinical_assessments`, `medical_history`, `history_revisions`, `follow_up_tasks`, `clinical_summary_snapshots`, `summary_reviews` |
| Clinical notes | `doctor_notes`, `doctor_recommendations` |
| Prescriptions | `prescriptions`, `prescription_items`, `medicine_dispensing` |
| Lab / reports | `lab_test_orders` (status flow, sample code), `health_reports`, `health_parameters`, `report_comparisons` |
| Pharmacy / billing | `medicine_inventory` (one row = one batch), `sales`, `sale_items` (GST) |
| Trainee | `trainees`, `trainee_histories`, `trainee_history_revisions`, `referrals` |
| AI | `patient_assistant_conversations`, `_messages`, `_evidence` |
| Audit | `audit_logs` |

## 2. Feature inventory against the brief

Legend: **W** working, **P** partial, **M** missing.

| Module | Status | What is there | What is missing |
|---|---|---|---|
| A Administration | **P** | staff accounts, departments and specializations (admin screen), audit log screen, admin dashboard counts, letterhead from `.env` | hospital profile in the database, branches, rosters, attendance, working hours, fees and service price list, permissions editor, hospital settings, operational reports |
| B Registration | **P** | reception registers a patient (name, DOB, gender, phone, address, blood group, allergies, emergency contact, assigned doctor), validated; search by name, patient ID, phone, e-mail; `P-0001` code; avatar photo for every user | UHID that is branch/format-configurable (the code is a plain counter), duplicate detection (only e-mail is unique), merge, insurance, ABHA (with consent), documents, consents, one-record guarantee across branches |
| C OPD | **P** | appointments (doctor clash check, status, patient symptoms), pharmacy bill of a prescription | slots and availability, walk-in tokens, queue and waiting time, a visit/encounter record, vitals at the visit, consultation billing, follow-up scheduling tied to a visit |
| D Doctor workspace | **P** | dashboard (reports to review, today's appointments, follow-ups, trainee referrals), patient page (timeline, reports, comparison, trends, notes, recommendations, medication history, history), clinical assessment form, fast history form, prescriptions with tests | a single consultation form (complaint, HPI, examination, diagnosis, orders, plan) that the doctor signs and finalises; today's queue; pending results panel |
| E Departments | **P** | departments + specializations with admin management | consultation templates, exam fields per department, department investigation workflows, cross-specialty consult requests, department reports |
| F Nursing | **M** | none (no nurse role) | everything |
| G Emergency | **P** | doctor-written past emergency events and timeline; patient emergency card; AI-free emergency review | live emergency workflow: quick registration, triage, arrival time, vitals, assignment, orders, treatment record, ICU referral, ADT, event board, configurable escalation rules |
| H IPD | **M** | (past admissions exist only as history records of other stays) | admission number, ward, attending/consulting doctors, progress notes, treatment chart, orders, daily summary, discharge, final bill |
| I Wards, beds, ICU | **M** | none | wards, beds, board, one-active-patient-per-bed constraint, occupancy, ICU charts |
| J Laboratory | **P** | orders from prescriptions with lifecycle ORDERED, SAMPLE_COLLECTED, IN_PROGRESS, COMPLETED, REJECTED; sample code; urgent flag; lab worklist; result attached as a report; value extraction with ranges printed in the report; doctor review | test catalogue with categories, reference range, unit, method per test; analyte-level result entry; critical flags; technician assignment; pathologist approval; QR/barcode label print; stand-alone (non-prescription) orders |
| K Radiology | **P** | report upload and measure extraction for X-ray, CT, MRI, ultrasound, echo and others | orders, scheduling, status, technician and radiologist assignment, structured reports, image storage, approval, comparison with previous studies, delivery. DICOM/PACS: none |
| L Operation theatre | **M** | (past surgeries exist only as history records) | OT rooms, scheduling and conflict prevention, pre-op, consent, checklist, notes, anaesthesia, recovery, consumables, billing |
| M Pharmacy | **W/P** | stock receipt with batch and expiry, barcode lookup, dispensing against a valid prescription (partial dispensing), GST sales, bill of a prescription, stock never negative, expired stock blocked, dispensing history, dashboard | medicine catalogue (generic and brand), suppliers, purchases, stock movement ledger, returns, transfers, low-stock and expiry alerts, recall, IPD medicine requests, reports |
| N Blood bank | **M** | none | everything |
| O Billing | **P** | pharmacy sales with GST, bill list and summary, printable bill | OPD/IPD/lab/radiology/OT/bed charges, service price list, packages, advances, refunds, discounts, receipts, outstanding, daily cash report, payment methods, invoice settings |
| P Insurance/TPA | **M** | none | everything |
| Q Inventory and procurement | **M** | (pharmacy stock only) | equipment, consumables, requisitions, POs, GRN, stock audits, reorder alerts |
| R Appointments and referrals | **P** | appointments, trainee referral to a doctor | doctor availability and slots, rescheduling, reminders (SMS/WhatsApp/e-mail adapters), inter-department referral tracking |
| S Discharge | **M** | none | discharge summary approved by the treating doctor, bill clearance |
| Trainee flow (asked for) | **W** | role, history drafts, department suggestion, referral, doctor verification, supervisor review (see `TRAINEE_WORKFLOW.md`) | links to the future encounter model |

**AI**
| Feature | Status | Notes |
|---|---|---|
| History assistant | **P** | `clinical_summary`: sourced statements with dates, rule-based, optional LLM narrative kept as a draft; no cross-module sources yet (no encounters, admissions, labs as analytes) |
| Patient chatbot | **W/P** | answers only from the signed-in patient's own records with evidence rows; "not available" when unknown; rule-based first, optional LLM. Knowledge grows when new modules exist |
| Voice | **W/P** | browser speech recognition and speech synthesis (free), English, Hindi, Marathi language tags, hands-free mode, playback controls. Depends on the browser/OS voices; Hindi and Marathi voice quality is not under our control |
| Report analyzer | **P** | PDF text extraction, parser, units, printed ranges, flags, doctor review, compare only compatible tests, per-upload isolation. **Scanned images and photos are unreadable: OCR (Tesseract) is not installed** |
| Clinical decision support | **P** | points to check, suggested tests, medication-history reconciliation hints, missing-information; labelled as rule-made; no diagnosing or prescribing |
| Emergency summary | **W** | `emergency_review` and emergency card, sourced |
| AI safety | **W** | safety filter, no invented values, original source kept, LLM optional (no key in repo) |

## 3. Dependency map

```
users/roles ─┬─ doctors ──┬─ departments ── specializations
             │            ├─ appointments ── patients
             │            ├─ prescriptions ─┬─ prescription_items ── medicine_dispensing ── sales/sale_items ── medicine_inventory
             │            │                 └─ lab_test_orders ── health_reports ── health_parameters ── report_comparisons
             │            ├─ doctor_notes / recommendations / follow_up_tasks / clinical_assessments
             │            └─ referrals ◄─ trainees ◄─ trainee_histories
             ├─ patients ── patient_history, medications, conditions, hospital_admissions(past), surgery_records(past), emergency_events(past)
             └─ audit_logs (everything writes here)
AI layer (read-only over the above): clinical_summary, patient_assistant, emergency_review, history_insights
```
Key observation: **there is no encounter (visit) object.** Appointments, notes, assessments, prescriptions and lab orders each hang directly on the patient/doctor. All new modules (OPD, IPD, emergency, nursing, billing) need one shared `encounters` spine, otherwise they cannot "talk to each other".

## 4. Role mapping (existing logins keep working)

The existing `users.role` string stays as the **primary role** (so every login, JWT and test keeps working). A new `roles`, `permissions`, `role_permissions` and `user_roles` set is added next to it; Phase 2 maps each current role to a default set and `require_roles` is extended to accept permission names.

| Today | New role(s) it maps to | Note |
|---|---|---|
| ADMIN | Hospital Admin (+ Super Admin for the first admin) | Branch Admin is new, scoped to one branch |
| DOCTOR | Doctor (Specialist Doctor = Doctor with a specialization) | no separate login type needed |
| EMPLOYEE | Receptionist (designation decides: Billing Executive, Insurance/TPA Executive, HR Manager, Inventory Manager, Accountant, Ward Staff, OT Staff, ICU Staff, Blood Bank Staff are new role records, assignable to employees) | keeps the `employees` row |
| PATIENT | Patient | unchanged |
| PHARMACY | Pharmacist (Pharmacy Assistant is a restricted variant) | unchanged login |
| LAB | Lab Technician (Pathologist new, approval permission) | unchanged login |
| TRAINEE | Intern / PG Student | unchanged |
| new | Nurse, Radiology Technician, Radiologist, Hospital Auditor (read-only audit) | new accounts |

## 5. Proposed new tables (by domain; nothing is built yet)

| Domain | Tables |
|---|---|
| Hospital | `hospital_profile`, `branches`, `hospital_settings` (key/value, per branch), `service_catalog` (price list), `working_hours`, `holidays` |
| Access | `roles`, `permissions`, `role_permissions`, `user_roles`, `break_glass_grants` |
| Staff | `staff_profiles` (user, branch, designation, registration no.), `rosters`, `attendance` |
| Patients | `patient_identifiers` (UHID per branch, ABHA), `patient_consents`, `patient_documents`, `patient_insurance`, `patient_merges` (audited), duplicate-check index |
| Encounters | `encounters` (type OPD/IPD/ED, patient, branch, department, attending, status, start/end), `queue_tokens`, `doctor_slots`, `consultations` (structured form, draft/final, signed by, signed at), `consultation_templates`, `diagnoses` (coded optional), `orders` (generic order: lab, radiology, procedure, diet, nursing), `referral_requests` (department to department) |
| Vitals | `vital_sets` (any encounter, any role, with source) |
| Wards/beds | `wards`, `beds` (type, status), `bed_assignments` with a **partial unique index: one active assignment per bed and one per patient**, `bed_events` |
| Nursing | `nursing_notes`, `care_plans`, `medication_orders`, `mar_entries` (scheduled/given/refused, by whom), `intake_output`, `observation_charts`, `shift_handovers`, `nursing_tasks` |
| Emergency | `ed_visits` (triage, arrival, outcome), `triage_rules` (configurable), `ed_timeline` |
| IPD | `admissions`, `progress_notes`, `discharge_summaries` (doctor-approved) |
| Lab | `lab_tests` (catalogue: category, unit, method, ranges by age/sex), `lab_order_items`, `lab_samples` (barcode), `lab_results` (value, unit, range, method, flag), `lab_approvals` |
| Radiology | `rad_studies` (catalogue), `rad_orders`, `rad_reports`, `rad_files` |
| OT | `operating_theatres`, `ot_bookings` (exclusion by room and time), `ot_records`, `ot_checklists`, `ot_consumables` |
| Pharmacy | `drug_catalog` (generic/brand), `suppliers`, `purchase_orders`, `stock_batches`, `stock_movements` (ledger), `pharmacy_returns`, `ipd_medicine_requests` |
| Blood bank | `donors`, `donations`, `blood_components`, `blood_requests`, `crossmatches`, `transfusions` |
| Billing | `charges` (from any service), `invoices`, `invoice_lines`, `payments`, `advances`, `refunds`, `packages` |
| Insurance | `insurers`, `policies`, `preauths`, `claims`, `claim_documents` |
| Procurement | `inventory_items`, `requisitions`, `grn`, `stock_audits` |
| AI | `ai_drafts` (status: draft/approved/rejected, approved by), existing assistant tables reused |
| Audit | `audit_logs` kept and extended (branch, patient, reason) |

Existing tables are **kept**: `patients`, `appointments`, `prescriptions`, `lab_test_orders`, `sales` and friends gain a nullable `encounter_id` (added by the idempotent startup migration, no data loss). New modules write into the same patient record.

## 6. Honest points

**SQLite limits.** Fine for one branch and one server. Limits for a large or multi-branch hospital: a single writer (concurrent billing, nursing and ED entries will queue and can hit "database is locked"), no real server-side access control or encryption at rest, no row-level security, weak support for exclusion constraints (bed and OT double-booking would rely on partial unique indexes and transactions; PostgreSQL gives range-exclusion constraints), no point-in-time recovery, no read replicas, and the database file lives on the app server. **Recommendation (not applied):** keep SQLite through Phases 2-3 for speed, move to PostgreSQL before Phase 5 (beds, OT, stock). The code already uses SQLAlchemy and a `schema.sql` for PostgreSQL, so the move is mostly the migration tool (Alembic is the technical reason to add it) and testing. I will not do it without your approval.

**Known open security findings** (from `BUST_REPORT.md`, still open): quadratic regexes on report text (R-01), no text cap (R-02), dispensing race (B-01), PII to the AI service when a key is set (P-01), vulnerable Pillow/pypdf (D-02), compose default secret (O-01), unpinned packages (O-03), first-admin race (A-04), audit gaps (B-02..B-05). A hospital system must close these in Phase 9 at the latest; the dispensing race and audit gaps matter earlier because Phases 5-6 build on them.

**Not present today:** MFA, break-glass access, consent records, retention policy, encryption at rest, database backups, notification adapters, OCR for scanned reports (Tesseract not installed; RapidOCR is an option).

**Interoperability** (ABDM/ABHA, FHIR, DICOM/PACS, payment, insurance, SMS/WhatsApp): nothing exists; none will be claimed until built and verified. Designed as adapter interfaces in Phase 8.

**Compliance.** Indian healthcare privacy and regulation (DPDP Act 2023, ABDM policies, clinical establishment rules) are design inputs only. A qualified professional must review compliance. A qualified clinician remains responsible for every clinical decision.

## 7. Decisions needed from you before Phase 2

1. **Encounter spine.** OK to add `encounters` and a nullable `encounter_id` on existing clinical tables (recommended)?
2. **Roles.** OK to keep `users.role` as the primary role and add a permission layer beside it (recommended), rather than replacing it?
3. **UHID format.** Example: `<BRANCH>-<YY>-<6 digits>` (for example `PUN-26-000123`), generated in a transaction; existing `P-0001` codes are kept and also work as search keys. Which format do you want?
4. **PostgreSQL.** Move before Phase 5, or stay on SQLite for now?
5. **Branches.** Single hospital with branches from the start (recommended, `branch_id` on new tables) or single branch first?
6. **Scope of Phase 2** as I would plan it: roles and permissions + hospital profile and settings + branches + service/price catalogue + patient registration upgrade (UHID, duplicate detection, consent, insurance fields, ABHA with consent) + audited merge + break-glass. Anything to add or drop?

Phase 1 ends here. I have not started Phase 2.
