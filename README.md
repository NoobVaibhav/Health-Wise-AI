<p align="center"><img src="frontend/public/brand/logo-horizontal.svg" alt="HealthWise AI" height="72"></p>

# HealthWise AI

**AI-Powered Hospital Management and Patient Health Report Analysis & History Tracking System**
*AI-Assisted Health Reports, Doctor Review and Patient History Management*

B.Tech Data Science Engineering final-year project.

> HealthWise AI provides AI-assisted educational analysis of uploaded health reports. It is not a diagnostic system.
> AI analysis must be reviewed by a qualified healthcare professional. Prescriptions are created only by authorized doctors.

Brand files (logo, app icons, splash, colours and usage rules): `frontend/public/brand/`.

## 1. What it does

A multi-user hospital system with five roles: **Admin, Doctor, Hospital Employee, Patient, Pharmacy staff**.

```
Employee registers patient -> uploads report -> backend REALLY reads it (PDF text / OCR)
 -> rule engine compares each value with the range printed in the report -> AI explains in simple words
 -> status "Waiting for doctor review" -> Doctor reviews, adds note + recommendation + prescription
 -> Patient sees the reviewed result -> Pharmacy dispenses -> Patient sees dispensing status
```

Rules that run through the whole project:
- **No fake data.** Every upload is processed; failed or non-health files are rejected and never saved. An empty database shows empty states.
- **AI never decides.** Status (above / below / within / unknown) comes from deterministic code using the range in the report. The optional LLM only rewrites explanations, behind a safety filter. The app works without an LLM.
- **Doctor has the final word.** AI text is labelled "AI-generated"; doctor content is labelled "Doctor's Note / Recommendation".
- **Strict role-based access** (see matrix in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)) and an **audit log** of important actions.

### Any kind of report, with suggestions for doctors and tips for patients

Uploads are not limited to lab tables. The system also reads **X-ray / CT / MRI / ultrasound reports, ECGs, biopsy reports, discharge
summaries, prescriptions and clinical notes** (PDF, photo with OCR, or text). Documents that are not medical (invoices, letters) are still rejected.

For every saved report the doctor gets:
- **Key statements** from the report, each marked "looks normal" or "worth a look" (negation is understood: "no evidence of mass" is normal).
- **Flagged for prompt attention** when the wording suggests urgency (for example "pulmonary embolism").
- **Suggestions for the doctor**: points to consider (compare with earlier studies, reconcile medicines, follow-up tests ...). Never orders.
- **Draft tips for the patient**, which the doctor can turn into their own official advice with one click ("Use as my advice").

The patient sees **general tips only after the doctor has reviewed the report**, clearly labelled as computer-generated, and never sees the
doctor-only suggestions or flags. Employees and admins see no clinical content.

How it works: rules first (report type by keywords, sections, wording lists, negation check), so it works with **no AI at all**. If `LLM_API_KEY`
is set, an AI model improves the wording, but only after names, phones, emails and addresses are removed from the text; every AI sentence passes a
safety filter (no diagnosis, no doses, no "you have ...") and the rule-based result is the fallback. Code: `backend/app/services/insight_service.py`.

## 2. Tech stack

Backend: Python, FastAPI, SQLAlchemy, Pydantic, JWT + bcrypt, pypdf / pypdfium2, Tesseract OCR (pytesseract), PostgreSQL (SQLite for dev).
Frontend: React, Vite, Tailwind CSS, React Router, Axios, Recharts.

## 3. Folder structure

```
backend/app/{main.py, core/, database/, schemas/, routers/, services/, utils/, seed_demo.py}
backend/tests/       106 automated tests          backend/schema.sql   PostgreSQL schema
frontend/src/{components, pages/{auth,admin,doctor,employee,patient,pharmacy,shared}, services, context, routes}
docs/                ARCHITECTURE.md, SRS.md, PROJECT_REPORT.md
```

## 4. Run locally

Requirements: Python 3.11+, Node 20+, (optional) Tesseract OCR.

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m app.seed_demo         # creates demo accounts (see below)
uvicorn app.main:app --reload   # API docs: http://localhost:8000/docs
```

```bash
cd frontend
npm install
npm run dev                     # http://localhost:5173  (proxies /api to port 8000)
```

In VS Code: Ctrl+Shift+P -> "Tasks: Run Task" -> "Run everything (backend + frontend)".

### Demo accounts (password for all: `Demo@12345`)

Created by `python -m app.seed_demo`. They are people only: **no reports, history or prescriptions are created**.

| Role | Email |
|---|---|
| Admin | admin@healthwise.demo.com |
| Doctor (Dr. Anjali Sharma) | anjali.sharma@healthwise.demo.com |
| Employee (Priya Joshi) | priya.joshi@healthwise.demo.com |
| Patient (Rahul Patil) | rahul.patil@healthwise.demo.com |
| Pharmacy (MediCare Pharmacy Staff) | pharmacy@healthwise.demo.com |

Public sign-up is closed. On a brand new database with no users, the login page offers to create the first administrator.

### Environment variables (`backend/.env`, see `.env.example`)

`DATABASE_URL` (empty = SQLite; PostgreSQL: `postgresql+psycopg2://user:pass@host:5432/db`), `JWT_SECRET`, `LLM_API_KEY` (optional),
`UPLOAD_DIR`, `MAX_FILE_SIZE`, `TESSERACT_CMD` (optional), `CORS_ORIGINS`.

### OCR (only for scans and photos)

Install Tesseract (Windows installer: github.com/UB-Mannheim/tesseract/wiki; Ubuntu `sudo apt install tesseract-ocr`; the Docker image includes it).
`GET /api/health` shows `ocr_available`. Without OCR, text PDFs and TXT files still work and scans return "OCR is not configured".

## 5. Demo script (about 5 minutes)

1. Log in as **Employee** -> *Upload Report* -> pick Rahul Patil -> upload a real-format laboratory report (for example `backend/tests/fixtures/kamal_diagnostic_sample_report.pdf`, or any open-licence sample report PDF you have). A file that is not a health report is rejected and not saved.
2. Log in as **Patient**: the reports show "Waiting for doctor review" and no values yet.
3. Log in as **Doctor**: dashboard shows 2 reports waiting -> open one: extracted values, AI analysis, comparison with the earlier report, trends. Click *Mark as Reviewed*, add a note, a recommendation and a prescription.
4. **Patient** again: sees the analysis, the doctor's note, recommendation, prescription and the timeline.
5. **Pharmacy**: open the prescription, dispense part of it (stock goes down). **Patient** sees the status.
6. **Admin**: dashboard statistics and the audit log of every step.
7. **Any report type**: as Employee upload other real-format reports (an X-ray or CT report, an ECG report, a discharge summary, a prescription). No generated text reports are shipped with the project.
   As Doctor open each one: type label, key statements, red flags, suggestions and draft patient tips ("Use as my advice").
   As Patient (after the doctor reviews) only the general tips appear. A file that is not a health report is still rejected.

## 6. Tests

```bash
cd backend
python -m pytest -q
```
Covers authentication, role permissions, patient privacy, upload (PDF, OCR path, invalid files), parameter and reference-range extraction,
status rules, doctor review, notes, recommendations, prescriptions, dispensing and stock, appointments, comparison, trends, timeline, dashboards, audit log, safety filter.

## 7. Docker

```bash
docker compose up --build       # open http://localhost:8080
```
Services: `frontend` (nginx), `backend` (FastAPI + Tesseract), `postgres`. Seed demo accounts with
`docker compose exec backend python -m app.seed_demo`.

## 8. Limitations

- Free-text analysis is wording-based: it can miss or misread a statement, so it supports the doctor and never replaces reading the original.
  Reports are read in English only.
- Only numeric lab results are analysed ("Negative", "<0.5" are skipped); the parser knows about 45 common parameters (add more in `services/parameter_catalog.py`).
- OCR quality depends on the scan; a name-mismatch warning helps catch wrong-patient uploads, but doctors must verify values against the original.
- Logout is client-side (no token blacklist); no password reset by email.
- Prescriptions expire 30 days after issue (configurable constant); stock tracking is simple.

## 9. Future scope

Mobile app, telemedicine, online appointment booking, lab/insurance/billing integration, multilingual support, voice assistant, hospital-wide analytics, e-prescription signing.
