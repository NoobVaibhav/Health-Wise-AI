# HMS Phase 3: clinical workflows

## The idea
One **encounter** (a visit) is the shared spine: an OPD visit, an emergency visit or an admission. Appointments, prescriptions, vital signs, consultations, orders, charges and referrals all point to it, so OPD, nursing, emergency and IPD work on the same patient record. Old rows are untouched (the new `encounter_id` columns are optional).

## What was built
| Area | What it does | Where |
|---|---|---|
| OPD | Check-in of an appointment or a walk-in gives a **token** (a doctor's number for the day, never repeated: a unique rule in the database). The queue shows waiting time; urgent patients go first; reception marks no-shows | `routers/opd.py`, `services/encounter_service.py`, screens **OPD desk** (reception) and **Today's queue** (doctor) |
| Consultation | Complaint, history, examination, assessment, plan, advice, follow-up date and the department's **template fields** (the administrator edits templates). Saved as a draft by itself; the doctor signs. After signing it is locked: only dated **addenda**. Signing closes the OPD visit, ends the token, adds the consultation fee from the price list as a **pending charge** (none is invented when the price list has no price) and creates the follow-up task | `Consultation.jsx` |
| Vitals and alerts | Any nurse or doctor saves vitals. Plain threshold rules (the hospital edits them; defaults are only a starting point and must be reviewed by your clinical team) raise WARNING or CRITICAL alerts at once. **No AI is involved.** | `EscalationRule`, `ClinicalAlert` |
| Nursing | Nurse login role. Ward worklist (alerts first, overdue medicines first), chart per inpatient: vitals, **medication administration record** (given, refused, held; refusal and hold need a reason; a recorded dose cannot be changed; overdue after 30 minutes), intake and output with the balance, nursing notes, care plan and shift handover | `routers/nursing.py`, `Nurse.jsx` |
| Emergency | Rapid registration (a known patient, or an **unidentified person** who gets a real record and UHID at once and no login), triage category 1 to 5 (1 and 2 raise an alert), doctor assignment, timeline of assessment, treatment and orders, outcome: discharge, admit, ICU, transfer, left against advice, death. Admit and ICU open the admission (and the bed) in the same transaction | `routers/emergency.py`, `Emergency.jsx` |
| Wards and beds | Ward types: general, private, semi-private, ICU, NICU, PICU, emergency, isolation, recovery. Bed states: free, occupied, reserved, cleaning, maintenance. **Two partial unique indexes make it impossible for a bed to hold two active patients and for a patient to lie in two beds, whatever any screen or API does.** A transfer sends the old bed to cleaning | `Ward`, `Bed`, `BedAssignment`, `BedBoard.jsx` |
| IPD | Admission number `ADM-<BRANCH>-<YY>-<6 digits>`, attending doctor, consulting doctors and nurses assigned (a consulting doctor gets access to the patient while assigned), progress notes (never edited: a correction is a new note), medication orders (these make the MAR), orders, one active admission per patient (database rule) | `routers/ipd.py`, `Inpatients.jsx` |
| Discharge | The doctor writes the summary; **only the treating (attending) doctor approves it**; an approved summary is locked; discharge needs the approved summary, frees the bed (to cleaning), stops active medicines, cancels open orders, closes the visit and tells how many charges are still pending. (Bill clearance becomes a hard check in Phase 6, when payments exist.) | same |
| Referral to another department | Doctor A asks a department (or a named doctor). A named doctor sees the records at once; a department request opens the records only when a doctor **accepts** (which also makes a consult visit and a token). The specialist's signed consult is the "updated plan" that the asker sees | `routers/referral_requests.py`, `ReferralRequests.jsx` |
| Trainee flow | A trainee referral now also puts the patient in the doctor's OPD queue (urgent first) | `trainee_service.create_referral` |

## Database (startup migration, no data loss)
New tables: `encounters`, `queue_tokens`, `vital_sets`, `consultation_templates`, `consultations`, `consultation_addenda`, `diagnoses`, `clinical_orders`, `encounter_charges`, `nurses`, `nursing_notes`, `escalation_rules`, `clinical_alerts`, `medication_orders`, `mar_entries`, `intake_output`, `ed_visits`, `ed_timeline`, `wards`, `beds`, `admissions`, `admission_staff`, `bed_assignments`, `progress_notes`, `discharge_summaries`, `referral_requests`, `number_counters`. New optional columns: `appointments.encounter_id`, `prescriptions.encounter_id`, `referrals.encounter_id`. The older `hospital_admissions` table is earlier stays at other hospitals; the live table is `admissions`. Default alert rules, one default consultation template and a few department templates are added once when none exist.

## Access
New login role **NURSE** (admin creates nurses under **Nurses**). New permissions (`opd.checkin`, `consult.write`, `nursing.chart`, `ipd.bed`, `discharge.approve`, `ward.manage` ...) are given to the default roles; roles that already exist receive only the new permissions meant for them. A doctor reaches a patient through an assignment, open visit, emergency visit, admission (attending or consulting), or a referral that names them (`care_team_patient_ids`). A nurse reaches patients who are admitted or have an open visit. Reception sees queues, beds and the admission summary, never the clinical content.

## Limits (honest)
* Consultation charges are only **pending**; invoices, payments and the bill-clearance check come in Phase 6.
* Orders (lab, radiology) are recorded and tracked by status; the lab and radiology workflows that process them are Phase 4.
* Dose times are the ward's local clock; there is no per-ward time zone setting.
* A nurse sees every inpatient (no ward or shift assignment filter yet); the "assigned nurse" list is information.
* Alert thresholds are generic defaults, not a validated early-warning score. The hospital's clinical team must review them.
* The doctor's `AdmitDialog` offers free beds only; reserving beds is done from the bed board API (no reservation screen).
* No discharge summary print layout yet.
* Compliance (clinical establishment rules, DPDP Act) must be reviewed by qualified professionals; a clinician remains responsible for every clinical decision.

Tests: `backend/tests/test_clinical_workflows.py` (48), `frontend/src/pages/clinical.test.jsx` (11), and the access matrix and fuzz suites now include the nurse and every new endpoint.
