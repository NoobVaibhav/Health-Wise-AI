# HMS Phase 2: core foundation

Decisions used (you said "do what is okay", so the recommended answers were taken): encounter spine comes in Phase 3, `users.role` stays the login role with a permission layer beside it, UHID `BRANCH-YY-000123`, branches from the start, SQLite until Phase 5 (then a decision about PostgreSQL).

## What is new
| Area | What it does | Where |
|---|---|---|
| Roles and permissions | 25 hospital roles and 15 permissions, seeded once. Each login role maps to a default hospital role (see the audit). The administrator can give a person extra roles and edit what a role may do. New endpoints check `require_permission(...)`; the older endpoints still use `require_roles(...)` and are unchanged | `services/access_service.py`, `routers/access.py`, admin screen **Hospital > Roles** |
| Hospital profile | name, address, phone, e-mail, registration and GST numbers. Prescriptions use it for the letterhead (the `.env` values are the fallback) | `services/hospital_service.py`, `routers/hospital.py` |
| Branches | code (2 to 8 letters, part of every UHID, never changed), name, address; switch off (one must stay active) | same |
| Settings | typed and checked: emergency access minutes, appointment slot, working hours, currency, invoice prefix, duplicate check on/off; hospital-wide or per branch | same |
| Price list | code, name, category, department, price, GST; switch off instead of delete. Billing (Phase 6) will read it | same |
| UHID | `BRANCH-YY-000123`, numbered per branch and year in the same transaction as the patient (a failed registration gives no number away). Existing patients get one at start-up; `P-0001` codes stay and still work in search | `services/registry_service.py` |
| Duplicate check | same name and date of birth blocks with a clear list unless reception confirms "different person"; same phone is only a warning (families share phones); can be switched off | `registry_service.find_duplicates`, `routers/patients.py` |
| Consent | TREATMENT, DATA_SHARING, ABHA, PHOTO, RESEARCH: recorded with who gave it, withdrawn (never deleted), audited | `routers/patient_registry.py` |
| ABHA | 14-digit number stored only with an active ABHA consent; withdrawing the consent removes the number. **Nothing is sent to any ABDM service** | same |
| Insurance | insurer, TPA, policy, member id, validity; switch off | same |
| Merge | administrator only, written reason, all records of the old patient move to the kept one, the old record is archived (its login is off), `patient_merges` says what moved. A one-per-patient table (standing history) keeps the kept patient's row | `registry_service.merge_patients` |
| Break-glass | a doctor opens one patient with the exact UHID and a written reason (10+ characters) for a limited time (setting, default 60 min); only that doctor; ends by itself; listed for review with a review note; audited | `routers/access.py`, `core/permissions.py` (`has_break_glass`) |

## Database changes (startup migration, idempotent, no data loss)
New tables: `branches`, `hospital_profile`, `hospital_settings`, `service_catalog`, `roles`, `permissions`, `role_permissions`, `user_roles`, `break_glass_grants`, `uhid_counters`, `patient_consents`, `patient_insurance`, `patient_merges`. New nullable columns on `patients`: `uhid`, `branch_id`, `abha_id`, `merged_into_id`. A unique index on `patients.uhid` is created for old databases. `schema.sql` regenerated (55 tables).

## Screens
* Admin: **Hospital** (tabs Profile, Branches, Settings, Price list, Roles, Emergency access).
* Reception and admin: **Patients > Registration** (UHID, consents, ABHA, insurance; merge for the administrator). Register patient shows the possible duplicates before saving, and the UHID after.
* Doctor: **Emergency access**.

## Limits (honest)
* The new permissions guard only the new endpoints. The older endpoints still check the login role, so an extra role (for example Billing Executive given to an employee) adds nothing there yet. The older endpoints will move to permissions phase by phase, as each module is rebuilt.
* A break-glass grant is recorded when it is opened; the later reading of the patient record by that doctor is not logged one by one yet.
* Documents and photo upload for patients, working hours per doctor, rosters, attendance and branch admins scoped to one branch are not built yet (listed for later phases). Branch scoping of data is not enforced yet: every staff member still sees every branch.
* The patient ID `P-0001` counter is not branch-aware; the UHID is.
* Compliance (DPDP Act, ABDM) must be reviewed by qualified professionals.

Tests: `backend/tests/test_hospital_foundation.py` (34), `frontend/src/pages/hospital.test.jsx` (6).
