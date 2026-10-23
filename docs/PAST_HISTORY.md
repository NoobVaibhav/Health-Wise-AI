# Detailed past medical history and the printed history sheet

Doctor: **My Patients > a patient > Medical history** (or *Take history / examine*, step 1). Patient: **My Health History** (read only).
A sample printout with fictional data is in [Sample_Medical_History_Print.pdf](Sample_Medical_History_Print.pdf).

## What was added

| Part | Contents |
|---|---|
| **Section 1: Detailed medical history** (most prominent) | **A. Diabetes**: type, duration, year, current medicines, reported sugar values with their date, latest lab values from reports (shown apart, with report dates), six complication questions, earlier hospital stay (reason, date, treatment, outcome), other details. **B. Hypertension**: the same for blood pressure (usual range, recent reading, stroke / heart / kidney questions). **C. Other chronic illnesses**: any number, with duration, year, medicines, control, complications, hospital stays, notes. **D. Medication history**: name, dose, frequency, route, since, prescriber, adherence, and the illness each medicine is **linked to** (a medicine is stored once and shown under its illness and in the table). |
| **Section 2: Previous hospital admissions** (any number) | A. Admission details (hospital, admission and discharge date and time, **length of stay calculated** only from both times, type, complaints, provisional and final diagnosis, reason, referrer). B. Clinical history (symptoms, story, earlier illnesses, **vital signs measured at admission**, examination, tests and imaging, complications). C. Treatment (treatment, medicines with name, dose, frequency, route and duration, antibiotics, painkillers, IV fluids and oxygen, procedures, medication changes, response, complications). D. **Operations** (name, reason, site, date or year, surgeon, hospital, anaesthesia, findings, **implant** type, material, serial number, post-operative X-ray, treatment, complications, recovery). E. Discharge summary (condition, treatment completed, discharge medicines and instructions, wound care or rehabilitation, follow-up date, specialist review, recovery, remaining symptoms, readmission). |
| **Printed sheet, 11 sections in this order** | 1 Identification, 2 Detailed medical history, 3 Previous hospital admissions, 4 Allergies and medication reconciliation, 5 Family history and habits, 6 Current complaint, 7 Current vital signs and latest lab results, 8 Examination, 9 Assessment and diagnosis (with the computer's "points to check", clearly separate), 10 Current treatment, 11 Follow-up and doctor's notes, signature. Past sections are marked **PAST HISTORY**, this visit's **TODAY**. |

Layout: A4, long sections flow over any number of pages (only single table rows and short cards are kept whole), table headings repeat, no clipped text, empty items are one short line, and illnesses with nothing recorded but a name print compactly.

## Safety and data integrity

* **Nothing is invented.** Every field is optional. Unknown shows as *Not recorded* (an unanswered yes/no question is "Not recorded", never "No"). An implant is "Not documented" unless a doctor states it. Length of stay is "Not recorded" if a time is missing. **Today's vital signs are never copied into an old admission.**
* **Source and verification on every record**: *Told by the patient*, *Checked by a doctor* (with the doctor's name and date), *From a hospital record*, or *Entered earlier (source not recorded)*. A doctor confirms a record with **Mark as checked** (or by choosing that source in the form). Every edit re-stamps the record with the source chosen in the form, so a record whose source is changed to anything else is no longer shown as checked. The printed sheet tags each record and says that unchecked items must be confirmed.
* **Nothing is deleted or overwritten.** "Remove" only hides a record; every create, change, hide and check stores the earlier version in an append-only change log (`/api/health-history/patient/{id}/revisions`: who, when, what it was before). The earlier one-form screen no longer deletes anything either: it matches records by name, and an empty list means "not touched".
* **Access**: only a doctor authorised for the patient can read the full detailed history or change it. The patient can read their own (no edit or add buttons). Front desk, administrator, pharmacy, lab, other doctors and anonymous callers are refused; a record id of one patient does not work under another patient's address (all tested).
* **Existing records are migrated safely**: older "illnesses" and "operations" are copied once into the new records, labelled "entered earlier", the older lists are left untouched, and diabetes or hypertension entries become the matching sections. A second diabetes or hypertension entry stays visible as an ordinary illness.

## Database (created / extended automatically at start-up)

New tables: `chronic_conditions`, `hospital_admissions`, `surgery_records`, `history_revisions`. New optional columns on `patient_medications`: route, prescriber, adherence, condition link, source, verified by and at, hidden flag. Existing columns and rows are unchanged.

## API (doctor writes; every answer is the full updated history)

`GET /api/health-history/patient/{id}/past`, `GET .../revisions`; `POST` / `PUT` / `DELETE` on `.../conditions[/{id}]`, `.../medicines[/{id}]`, `.../admissions[/{id}]`, `.../surgeries[/{id}]`; `POST .../verify/{condition|medication|admission|surgery}/{id}`. The patient's `GET /api/health-history/me` and the doctor's `GET .../patient/{id}` now also return `past` (and, for the doctor, the medicine reconciliation and the follow-up block used by the sheet).

Validation: no future dates, discharge not before admission, vital signs in plausible ranges, implant details only if an implant was used, one diabetes and one hypertension record per patient, links only to the same patient's records.

## Medication reconciliation (section 4 of the sheet)

The medicines in the history are compared with the hospital's open prescriptions by name. Rows are *same in both*, *dose differs*, *not on a prescription here*, *not in the history*. Each difference says to confirm with the patient; nothing is merged or assumed, and allergy-name matches are listed "for review".

## Tests

`backend/tests/test_past_history.py` (13): details kept, one-per-patient, validation, linking, length of stay, vitals not copied, implants, change log and hiding, verification, access control, migration once and kept, one-form compatibility without deletion, reconciliation. `frontend/src/components/history/PastHistory.test.jsx` (4): order and prominence, "Not recorded" labelling, read-only for patients, doctor controls, no invented stay. Checked in a browser with a fictional patient (6 illnesses, 12 medicines, 3 admissions with an implant operation): screens, forms, validation messages and an 8-page printed sheet.

## Limits

* The sheet uses the browser's print / "Save as PDF" (as before), not a server-made PDF.
* Admission vital signs are entered as numbers: images, scanned discharge summaries and X-rays are not attached to an admission yet.
* Laboratory values typed under an illness are the patient's or doctor's report; the dated results from uploaded reports are shown beside them, never merged.
* The medicine name list in the form is only a typing aid; any name can be typed.
