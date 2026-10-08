# Software Requirements Specification: HealthWise AI (Hospital Management)

## 1. Introduction
**Purpose:** specify HealthWise AI, a web system for hospital patient records, laboratory report analysis, doctor review, prescriptions and pharmacy dispensing.
**Scope:** five user roles; real processing of uploaded reports; rule-based analysis with AI explanations; doctor review; prescriptions; dispensing; patient history timeline; comparison; appointments; audit.
**Out of scope:** diagnosis or disease prediction, medicine suggestion by the system, billing, telemedicine.
**Definitions:** OCR (optical character recognition), JWT (JSON Web Token), RBAC (role-based access control), reference range (normal range printed in a report).

## 2. Overall description
Users: Admin, Doctor, Hospital Employee, Patient, Pharmacy staff. Environment: browser client, FastAPI server, PostgreSQL/SQLite, optional Tesseract OCR and LLM.
Assumptions: reports contain numeric results with units; doctors verify AI output; the hospital creates all accounts.

## 3. Functional requirements
| ID | Requirement |
|---|---|
| FR-01 | Users log in with email/password (bcrypt-hashed); a JWT is issued. No public sign-up; the first admin can be created once on an empty system. |
| FR-02 | Invalid credentials get a generic message; deactivated users cannot log in or use old tokens. |
| FR-03 | Accounts created with a generated password must change it at first login. |
| FR-04 | Admin creates doctors, employees and pharmacy staff, manages departments, and activates/deactivates users. |
| FR-05 | Employees/admin register patients (account created with the patient) and edit basic information only. |
| FR-06 | Role-based access: every endpoint is limited to its roles; the message "You do not have permission to access this information." is returned otherwise. |
| FR-07 | Patient data is private: patients see only their own data; doctors only authorized patients; employees/admin never see clinical values; pharmacy sees only authorized prescriptions. |
| FR-08 | Employees and authorized doctors upload PDF, JPG, JPEG, PNG, WEBP (optional TXT, CSV); type, content and size are validated. |
| FR-09 | Text PDFs are read via text extraction; scanned PDFs and images use OCR; a clear error is shown if OCR is unavailable. |
| FR-10 | Name, value, unit and reference range are extracted from the actual file; names are normalized and the original name is kept. |
| FR-11 | Reference ranges (a-b, <x, >x) come only from the report; none are invented. |
| FR-12 | Status WITHIN / ABOVE / BELOW / UNKNOWN is decided by deterministic rules. |
| FR-13 | Files without recognizable laboratory parameters, or unreadable files, are rejected and not saved. |
| FR-14 | AI explanations are non-diagnostic, pass a safety filter, and have a template fallback without an LLM. |
| FR-15 | A saved report has status WAITING_FOR_DOCTOR; the assigned doctor sees it on the dashboard. |
| FR-16 | A warning is shown when the name printed on the report does not match the selected patient. |
| FR-17 | The doctor reviews a report (approve / modify / clarify) and marks it Reviewed; comments are required for modify/clarify. |
| FR-18 | Patients see report analysis only after the doctor has reviewed it. |
| FR-19 | Doctors add notes (Normal / Important / Follow-up required) and recommendations (with optional follow-up date), labelled as the doctor's. |
| FR-20 | Doctors add medical-history entries and see the full patient history before reviewing. |
| FR-21 | Only doctors create prescriptions (medicine, dosage, frequency, duration, quantity); only the writing doctor can cancel one. |
| FR-22 | Pharmacy searches prescriptions, dispenses (partial or full) or marks unavailable; it can never create or edit a prescription. |
| FR-23 | Dispensing cannot exceed the remaining quantity, is blocked for cancelled/expired prescriptions, and deducts stock when the medicine is tracked. |
| FR-24 | Pharmacy manages medicine inventory; the dashboard shows low stock and expiring items. |
| FR-25 | Patients see prescription status and dispensing progress. |
| FR-26 | Appointments: create (employee/admin/patient), list per role, status updates (doctor, employee, patient may only cancel), clash and past-time checks. |
| FR-27 | A patient timeline is generated from the database (appointments, reports, AI analysis, reviews, notes, recommendations, prescriptions, dispensing, history entries) and is searchable; each item shows its source. |
| FR-28 | Reports of one patient can be compared (previous, latest, change, parameter-aware trend); trend charts show values over time. |
| FR-29 | Each role has a dashboard computed from the database; empty states are honest. |
| FR-30 | Important actions (login, creation, upload, analysis, review, notes, prescriptions, viewing, dispensing, user changes) are written to an audit log visible to admin. |
| FR-31 | The medical disclaimer is displayed on every page and in the API health response. |
| FR-32 | Original uploaded files are private and served only to authorized users. |

| FR-33 | Reports that are not lab tables (imaging, ECG, pathology, discharge summary, prescription, clinical note) are accepted when they look like medical documents; non-medical documents are rejected. |
| FR-34 | For every report the system produces key statements (normal / worth a look, with negation handled), red flags for urgent wording, suggestions for the doctor and general tips for the patient. |
| FR-35 | Doctor-only content (suggestions, red flags) is shown to the doctor only; patients see general tips only after doctor review; employees and admins see none. The doctor can turn a draft tip into official advice and can regenerate the suggestions (audited). |
| FR-36 | An optional AI model may improve the insights only after personal details are removed; its output is safety-filtered and the rule-based result is the fallback. |
| FR-37 | The database is upgraded automatically at start-up when new columns are added (existing data is kept). |

## 4. Non-functional requirements
Security (bcrypt, JWT, RBAC, per-record checks, content-type validation, private uploads, audit); reliability (typed errors, no fallback to demo data);
usability (responsive UI, friendly messages); maintainability (modular services, catalog-driven parameters, type hints, tests); portability (Docker, SQLite/PostgreSQL);
performance (a text report is processed in seconds; OCR is slower).

## 5. External interfaces
UI: React SPA. API: REST/JSON under `/api` (see ARCHITECTURE.md; interactive docs at `/docs`). Software: PostgreSQL, Tesseract, optional LLM HTTP API.

## 6. Use cases
UC-1 Log in / change password · UC-2 Create staff (admin) · UC-3 Register patient · UC-4 Upload and analyze report · UC-5 Doctor reviews report ·
UC-6 Add note / recommendation / prescription · UC-7 View reviewed result and history (patient) · UC-8 Dispense medicine · UC-9 Compare reports · UC-10 Manage appointments · UC-11 View audit log.

## 7. System models
Architecture, role matrix, ER design, API: [ARCHITECTURE.md](ARCHITECTURE.md). UML/DFD diagrams: [PROJECT_REPORT.md](PROJECT_REPORT.md).

## 8. Data requirements
18 tables (see `backend/schema.sql`): users, departments, patients, doctors, employees, pharmacy_staff, appointments, health_reports, health_parameters, report_comparisons,
doctor_notes, doctor_recommendations, medical_history, prescriptions, prescription_items, medicine_inventory, medicine_dispensing, audit_logs.

## 9. Constraints
Educational/demonstration use; no diagnosis; reference ranges only from the report; maximum file size 10 MB; OCR needs Tesseract; prescriptions valid 30 days.

## 10. Acceptance criteria
The full workflow (employee upload -> doctor review -> patient view -> pharmacy dispensing -> patient sees status) works; different files give different extracted values;
invalid files are rejected and not saved; each role sees only permitted data; all automated tests pass.

## 11. Requirements traceability matrix
| Requirement | Implementation | Tests |
|---|---|---|
| FR-01..03 | routers/auth.py, core/security.py | test_auth_rbac.py (first admin, login, hashing, generated password, deactivation) |
| FR-04 | routers/admin.py, services/user_service.py | test_only_admin_manages_staff_and_audit, test_deactivated_user_cannot_log_in |
| FR-05 | routers/patients.py | test_employee_cannot_change_clinical_fields, test_patient_search |
| FR-06, FR-07 | core/permissions.py, every router | test_role_matrix_on_core_endpoints, test_access_control.py |
| FR-08, FR-09 | routers/reports.py, utils/file_validation.py, services/pdf_service.py, ocr_service.py | test_extraction_analysis.py (pipeline), test_failed_or_invalid_upload_is_not_saved |
| FR-10, FR-11 | services/report_parser.py, normalization_service.py | test_reference_parsing, test_extracts_value_unit_reference |
| FR-12 | services/analysis_engine.py | test_range_classification, test_less/greater_than, test_unknown_when_no_reference |
| FR-13 | services/report_processor.py | test_invalid_document_rejected, test_failed_or_invalid_upload_is_not_saved |
| FR-14 | analysis_engine.build_explanation, safety_filter.py, llm_service.py | test_disclaimer_and_safety_filter |
| FR-15, FR-16 | routers/reports.py | test_complete_hospital_workflow, test_name_mismatch_warning... |
| FR-17, FR-18 | routers/doctors.py, services/report_service.py, serializers.py | test_complete_hospital_workflow, test_unreviewed_analysis_hidden_from_patient_until_review |
| FR-19, FR-20 | routers/doctors.py | test_doctor_content_validation, test_doctor_sees_full_history_before_reviewing |
| FR-21 | routers/prescriptions.py, services/prescription_service.py | test_complete_hospital_workflow (step 11), test_doctor_sees_only_their_own_prescriptions |
| FR-22, FR-23, FR-24 | routers/pharmacy.py, services/dispensing_service.py | test_pharmacy_sees_only_open_prescriptions..., test_expired_prescription..., test_inventory_and_stock_deduction, test_unavailable_medicine_is_recorded |
| FR-25 | routers/patient_portal.py | test_complete_hospital_workflow (step 8) |
| FR-26 | routers/appointments.py | test_appointment_flow |
| FR-27 | services/history_service.py | test_complete_hospital_workflow (step 9), test_doctor_sees_full_history_before_reviewing |
| FR-28 | services/comparison_engine.py, routers/patients.py | test_comparison_of_two_reports, test_trend_series, test_comparison_trend_logic_units |
| FR-29 | services/dashboard_service.py | test_dashboards_have_real_numbers |
| FR-30 | services/audit_service.py | test_complete_hospital_workflow (step 10) |
| FR-31 | DisclaimerBanner.jsx, safety_filter.DISCLAIMER | test_disclaimer_and_safety_filter |
| FR-32 | routers/reports.py (file endpoint) | test_complete_hospital_workflow, test_admin_has_no_clinical_access |
| FR-33 | services/report_processor.py, insight_service.looks_medical / detect_report_type | test_insights.py: test_report_type_is_detected, test_non_medical_documents_are_still_rejected, test_all_kinds_of_files_are_accepted_and_invoice_is_not |
| FR-34 | services/insight_service.py | test_statement_classification, test_urgent_wording_is_flagged_for_the_doctor, test_xray_gives_findings..., test_lab_insights_group_by_body_system... |
| FR-35 | services/serializers.insights_for_role, routers/reports.py (refresh), components/InsightsPanel.jsx | test_any_report_workflow_and_role_visibility, test_refresh_insights_is_doctor_only |
| FR-36 | services/llm_service.py (redact_text, enhance_insights), safety_filter.py | test_redaction_removes_personal_details, test_ai_output_is_filtered_and_personal_data_is_not_sent, test_bad_ai_reply_falls_back_to_rules |
| FR-37 | database/connection.add_missing_columns | test_new_columns_are_added_to_an_existing_database |

## 12. Appendices
Sample reports: `sample_reports/`. Supported parameters: `backend/app/services/parameter_catalog.py`. Demo accounts: README.
