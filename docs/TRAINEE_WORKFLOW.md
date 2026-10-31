# Interns and PG students (trainees)

A **trainee** is not a doctor. They take the patient's history and then send the patient to the right doctor. They cannot prescribe, order tests, or see reports, billing, pharmacy, laboratory data or other departments' patients.

## Accounts
* Role `TRAINEE`. Table `trainees`: `department_id` (required), `trainee_type` (`INTERN` or `PG_STUDENT`), `year_branch` (PG only, for example "MD Medicine, Year 2"), `supervisor_id` (optional doctor of the same department), `phone`.
* The admin creates them on **Interns & PG** (`POST /api/admin/trainees`). In the form: name, e-mail, password (empty = starting password), phone, Type, Department (required), Year and branch (PG only, required), Supervising doctor (only doctors of the chosen department). No Specialization.
* Demo logins (after `python -m app.seed_demo`, password `Demo@12345`): `intern@healthwise.demo.com`, `pg.student@healthwise.demo.com` (supervised by Dr. Anjali Sharma). On the login page in dev mode there are Intern and PG student buttons.
* Startup migration: `create_all` makes `trainees`, `trainee_histories`, `trainee_history_revisions`, `referrals`; nothing existing is changed. `schema.sql` was regenerated from the models.

## What a trainee does
1. **Dashboard**: patients waiting for a history, histories done today, referrals sent today, drafts to continue.
2. **Take History**: choose a patient, fill the form. It is saved as a **draft** automatically (a failed save keeps everything on the screen and offers *Try again*). *Mark complete* needs the main complaint, the duration and an explicit allergy answer (**None** is an answer). Vitals must be in the usual ranges (same as the doctors' form). The menstrual and obstetric box appears only for female patients.
3. **Choose a doctor**: the department that fits the complaint is suggested **with the reason**; the trainee may choose any other department (Department, Specialization, Doctor). Each doctor shows today's appointments and waiting referrals. *Urgent* puts the referral first in the doctor's list. An appointment time can be booked at the same moment (optional).
4. **My referrals**: Sent, Seen by doctor, Completed.

Patients a trainee may work on: patients whose doctor works in the trainee's department, patients with no doctor yet (just registered by reception), and patients the trainee already started a history for. Everything else is 403 (404 for an id that does not exist). Only basic details are shown (name, patient ID, age, sex, phone).

## What the doctor sees
* **Trainee referrals** page and a block on the dashboard (urgent and unseen first): *Taken by Neha Kulkarni (Intern), pending your review*.
* On the patient page: *Histories taken by interns and PG students*.
* The doctor can **Verify** (the trainee can no longer change it), **Correct or add a note** (the trainee's original is kept under *Earlier versions*), mark *seen* and *completed*.
* A PG student's **supervising doctor** also sees the referrals, and can approve or correct them (a note, and optionally another doctor).
* The referral gives the referred doctor access to that patient. A patient who already has a doctor keeps that doctor; a patient without one is assigned to the referred doctor.
* A trainee history is **not** merged into the patient's permanent health history. It is a separate record that the doctor reviews; the doctor copies what is right into the permanent record with the usual history form.

## Which complaint goes to which department (`services/referral_rules.py`)
The first rule whose words appear in the complaint or the ticked symptoms wins (words match at the start of a word, so "cold" does not match "scold"):

| Words | Department |
|---|---|
| chest pain, chest tightness, palpitation, angina | Cardiology |
| seizure, fits, stroke, paralysis, tingling, numbness, migraine, headache, giddiness, vertigo, fainting | Neurology |
| pregnan, antenatal, missed period, menstrual, periods, vaginal, white discharge, labour, infertility | Gynecology & Obstetrics (a male patient goes to General Medicine instead) |
| rash, itching, skin, acne, hair fall, eczema, psoriasis, fungal, boils | Dermatology |
| fracture, joint pain, knee/back/neck/shoulder pain, swollen joint, sprain, bone | Orthopedics |
| ear pain, hearing, sore throat, tonsil, sinus, nose bleed, blocked nose, hoarse | ENT |
| eye pain, red eye, blurred vision, cataract | Ophthalmology |
| anxiety, depression, low mood, insomnia, panic, hallucination, addiction | Psychiatry |
| breathless, shortness of breath, wheeze, asthma, chronic cough, tuberculosis | Pulmonology |
| abdominal/stomach pain, vomiting, diarrhoea, constipation, acidity, jaundice, blood in stool | Gastroenterology |
| burning urine, kidney stone, blood in urine, urinary, prostate | Urology |
| diabetes, thyroid, weight gain, excessive thirst | Endocrinology |
| lump, cancer, tumour, weight loss | Oncology |
| toothache, tooth, gum, dental | Dentistry |
| fever, cough, cold, body ache, weakness, tiredness, viral, loose motion | General Medicine |
| nothing matches | General Medicine |

A patient under 12 goes to **Pediatrics** (except for chest or brain symptoms, and teeth). The suggestion is only a help; the trainee always can choose another department.

## Permissions (enforced on the server)
* Trainee endpoints: `/api/trainee/*` (TRAINEE only; the admin has one read-only overview, `GET /api/trainee/admin/overview`, without any medical content).
* Doctor endpoints: `/api/referrals/*` (DOCTOR only). A referral is visible only to the referred doctor and to the trainee's supervisor; anything else is 404.
* A trainee can read or change only their **own** histories (someone else's id gives 404). After a doctor verifies a history, a change by the trainee is 409.
* Audit log: `TRAINEE_HISTORY_STARTED`, `TRAINEE_HISTORY_COMPLETED`, `TRAINEE_HISTORY_EDITED`, `TRAINEE_HISTORY_VERIFIED`, `REFERRAL_CREATED`, `REFERRAL_UPDATED`.
* The access matrix (`docs/ENDPOINT_MATRIX.md`) now has a TRAINEE column and is rewritten by the matrix test.
* A trainee with histories or referrals cannot be deleted, only deactivated.

Tests: `backend/tests/test_trainee.py`, the access matrix and fuzz suites, `frontend/src/pages/trainee/trainee.test.jsx`, `pages/admin/StaffManager.test.jsx`.
