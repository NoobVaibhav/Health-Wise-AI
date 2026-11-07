# HealthWise AI: Hospital Management and Report Analysis System

> HealthWise AI provides AI-assisted educational analysis of uploaded health reports. It is not a diagnostic
> system. AI analysis must be reviewed by a qualified healthcare professional. Prescriptions are created only
> by authorized doctors.

## 1. Architecture

```
React (Vite, Tailwind, Recharts, Axios, React Router)
   |  JWT in Authorization header, role-based routes
   v
FastAPI  /api/*
   routers/   HTTP only: validation, status codes, role checks
   services/  all logic: pdf, ocr, parser, analysis, ai, comparison, history, dispensing, audit
   schemas/   Pydantic request / response models
   core/      config, security (bcrypt + JWT), permissions (RBAC)
   database/  SQLAlchemy models (PostgreSQL, SQLite for dev)
   |
   v
PostgreSQL            private upload folder (files are served only through an authorised API call)
```

**Hybrid AI rule.** Deterministic code extracts values and decides WITHIN / ABOVE / BELOW / UNKNOWN from the range
printed in the report. The optional LLM only rewrites explanations (after a safety filter). The doctor reviews and has
the final word.

## 2. Role-permission matrix

| Capability | Admin | Doctor | Employee | Patient | Pharmacy |
|---|:-:|:-:|:-:|:-:|:-:|
| Create staff accounts, activate/deactivate users | yes | | | | |
| View audit logs, system statistics | yes | | | | |
| Register / edit patient basic info | yes | | yes | | |
| View patient clinical history | | authorized patients | | own | |
| Upload report | | yes (authorized) | yes | | |
| View extracted values + AI analysis | no (status only) | yes | no (upload status only) | own, after doctor review | |
| Review report, add notes, recommendations | | yes | | | |
| Create prescription | | yes | | | |
| View prescriptions | | own written | | own | authorized (not cancelled) |
| Dispense medicine, manage stock | | | | | yes |
| Appointments | all | own | create / manage | own (create, cancel) | |
| Compare reports / trends | | yes | | own (reviewed) | |
| Open the original uploaded file | | authorized | own uploads | own, after review | |

Patients can never edit notes, analysis, prescriptions or recommendations. Pharmacy can never create or change a prescription.

## 3. Folder structure

```
backend/app/{main.py, core/, database/, schemas/, routers/, services/, utils/}
backend/tests/ ...  backend/schema.sql  backend/seed_demo.py
frontend/src/{components, pages/{auth,admin,doctor,employee,patient,pharmacy,shared}, services, context, routes}
docs/  docker-compose.yml  README.md
```

## 4. Database (ER)

```
users 1--1 patients / doctors / employees / pharmacy_staff      (role column on users; no separate roles table)
departments 1--* doctors, appointments
patients 1--* appointments, health_reports, doctor_notes, doctor_recommendations,
              prescriptions, medical_history, report_comparisons
health_reports 1--* health_parameters
patients 1--* medical_history (doctor-written background entries)
prescriptions 1--* prescription_items 1--* medicine_dispensing
medicine_inventory (stock, deducted when dispensing)
audit_logs (user_id, action, entity_type, entity_id, timestamp, ip)
```

Patient timeline is generated from these tables (nothing hard-coded).

## 5. API

| Area | Endpoints |
|---|---|
| Auth | POST /api/auth/login, GET /api/auth/me, POST /api/auth/change-password, GET /api/auth/setup-status, POST /api/auth/register (first admin only, then closed) |
| Admin | GET /api/admin/dashboard, GET /api/admin/users, POST /api/admin/doctors, /employees, /pharmacy-staff, PUT /api/admin/users/{id}, GET/POST /api/admin/departments, GET /api/admin/audit-logs |
| Patients | POST/GET /api/patients, GET/PUT /api/patients/{id}, GET /api/patients/{id}/comparison, /trends, /trends/{name} |
| Reports | POST /api/reports/upload, GET /api/reports, GET /api/reports/{id}, /analysis, /file |
| Doctor | GET /api/doctor/dashboard, /patients, /patients/{id}/history, POST /notes, /recommendations, /history-entries, PUT /reports/{id}/review, GET /notes, /recommendations |
| Appointments | POST/GET /api/appointments, PUT /api/appointments/{id} |
| Prescriptions | POST/GET /api/prescriptions, GET /{id}, PUT /{id}/cancel |
| Pharmacy | GET /api/pharmacy/dashboard, /prescriptions, /history, POST /dispense, GET/POST/PUT /inventory |
| Patient portal | GET /api/patient/dashboard, /reports, /history, /notes, /recommendations, /prescriptions |
| Employee | GET /api/employee/dashboard |

## 6. Report pipeline

```
upload -> validate (type, size, magic bytes) -> PDF text or OCR -> clean -> parse (name, value, unit, range)
 -> normalize names -> rule-based status -> explanations (template, optional LLM + safety filter)
 -> save ONLY if >= 1 parameter found, status WAITING_FOR_DOCTOR -> doctor review -> patient sees result
```
Failed or non-health files are rejected and never saved.

## 7. Phases

1 Architecture/setup · 2 Auth + RBAC · 3 Patients/staff · 4 Appointments · 5 Upload + OCR · 6 Parameter extraction ·
7 Analysis · 8 Doctor review/notes/recommendations · 9 Prescriptions · 10 Pharmacy · 11 History timeline ·
12 Comparison/trends · 13 Dashboards · 14 Audit/security/tests · 15 Docker/docs.
