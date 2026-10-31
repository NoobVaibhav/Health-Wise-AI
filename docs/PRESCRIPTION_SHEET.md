# The prescription sheet

`frontend/src/components/PrescriptionSheet.jsx` draws one prescription the way an Indian doctor's prescription pad looks. The patient, the doctor and the medical shop all use it (`variant="patient"` or `variant="pharmacy"`).

| Part | What it shows | If the data is missing |
|---|---|---|
| Letterhead | hospital name (settings), "Dr." + doctor name, qualification, specialization and department, registration number; address, phone, e-mail | each line is left out; a dashed logo placeholder stays |
| Patient strip | name, age / sex (from the date of birth), patient ID, phone, prescription no., date, valid until | the box is left out; allergies in a red bordered line that also says "ALLERGY" in words |
| Clinical | diagnosis / reason | left out |
| Rx | a large Rx sign and a numbered table: medicine (bold, instructions in italics under it), dose, frequency (with the 1-0-1 shorthand only when it is clear), duration, quantity | on a phone the table becomes one card per medicine |
| Advice and tests | "Advice / Notes" box; "Investigations advised" (**patient variant only**: the pharmacy variant never shows tests, even if they were sent) | left out |
| Footer | valid until, barcode of the prescription code, "Computer-generated prescription. Not valid without the doctor's signature.", stamp and signature space with the doctor's name | |

* **Patient variant:** a "Collected / Partly collected / Not in stock / Pending" badge per medicine (on screen only) and a Print / Download PDF button.
* **Pharmacy variant:** an on-screen-only "Dispensing status" table (prescribed, given, remaining, status). The dispensing and billing steps on the page are unchanged. A banner above the sheet says EXPIRED, FULLY DISPENSED or CANCELLED.
* **Print:** A4, black and white (nothing depends on colour), about 17 mm margins, only the sheet is printed, a long prescription continues on page 2 with a small line (patient name, Rx no., date) repeated at the top, and rows are not split between pages.
* **Letterhead settings:** `HOSPITAL_NAME`, `HOSPITAL_ADDRESS`, `HOSPITAL_PHONE`, `HOSPITAL_EMAIL` in `backend/.env` (empty = not shown).
* **Not shown because they are not stored:** the patient's weight and blood pressure (they exist only inside visit records), a hospital logo (a placeholder box is drawn).
* **What the pharmacy sees:** unchanged: age and sex, but not the patient's phone or allergies.
