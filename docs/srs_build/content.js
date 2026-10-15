// All the words of the SRS, kept apart from the layout code. Everything here comes from the real project.
const fs = require("fs");
const schema = JSON.parse(fs.readFileSync(__dirname + "/schema.json", "utf8"));

const TITLE = "HealthWise AI: Hospital Management System with Report Analysis";

// ---------------------------------------------------------------- 1. Introduction
const definitions = [
  ["SRS", "Software Requirements Specification"],
  ["Admin", "System Administrator"],
  ["UI", "User Interface"],
  ["DB", "Database"],
  ["API", "Application Programming Interface"],
  ["REST", "Representational State Transfer, a style of web API that exchanges JSON over HTTP"],
  ["JWT", "JSON Web Token, the signed token a user receives after logging in"],
  ["RBAC", "Role-Based Access Control: what a user may see or do depends on the user's role"],
  ["OCR", "Optical Character Recognition: reading text from a scanned page or a photo"],
  ["LLM", "Large Language Model: an optional AI service used only to reword text"],
  ["Reference range", "The normal range printed next to a result in the original report"],
  ["Insight", "A plain-language statement the system produces about a report: key findings, red flags, doctor suggestions and patient tips"],
  ["Red flag", "A statement in a report that uses urgent wording and is therefore shown to the doctor first"],
  ["FR / NFR", "Functional Requirement / Non-Functional Requirement"],
  ["UC", "Use Case"],
  ["DFD", "Data Flow Diagram"],
  ["ER", "Entity-Relationship"],
  ["RTM", "Requirements Traceability Matrix"],
  ["HTTP / HTTPS", "Hypertext Transfer Protocol / its encrypted form"],
  ["PDF", "Portable Document Format"],
  ["SPA", "Single-Page Application"],
];

const references = [
  "IEEE Std 830-1998, IEEE Recommended Practice for Software Requirements Specifications.",
  "ISO/IEC/IEEE 29148:2018, Systems and software engineering: Life cycle processes: Requirements engineering.",
  "I. Sommerville, Software Engineering, 10th ed., Pearson, 2015.",
  "R. S. Pressman and B. R. Maxim, Software Engineering: A Practitioner's Approach, 8th ed., McGraw-Hill, 2014.",
  "M. Jones, J. Bradley and N. Sakimura, JSON Web Token (JWT), RFC 7519, IETF, 2015.",
  "N. Provos and D. Mazieres, A Future-Adaptable Password Scheme, USENIX Annual Technical Conference, 1999 (the bcrypt algorithm).",
  "FastAPI documentation, https://fastapi.tiangolo.com",
  "SQLAlchemy 2.0 documentation, https://docs.sqlalchemy.org",
  "React documentation, https://react.dev",
  "Tesseract OCR project, https://github.com/tesseract-ocr/tesseract",
  "OWASP Application Security Verification Standard (ASVS), https://owasp.org/www-project-application-security-verification-standard/",
  "Project documents: docs/ARCHITECTURE.md, docs/PROJECT_REPORT.md and README.md in the HealthWise AI repository.",
];

// ---------------------------------------------------------------- 2. Overall description
const productFunctions = [
  ["Accounts and access", "Login, forced password change, five roles, role-based access, staff creation, activate / deactivate."],
  ["Patients and appointments", "Register and search patients, book appointments with clash checks, confirm / complete / cancel."],
  ["Report upload and reading", "Upload PDF, photo or text; read text or run OCR; find tests, values, units and printed ranges."],
  ["Rule-based analysis", "Mark every result Within, Above, Below or Unknown using only the range printed in the report."],
  ["Any-report insights", "For lab, imaging, ECG, pathology, discharge, prescription and clinical-note reports: key numbers at a glance, key findings, red flags, suggestions for doctors and tips for patients."],
  ["Doctor review", "Approve, modify or ask for clarification; notes, recommendations and medical history. Patients see results only after this step."],
  ["Prescriptions and pharmacy", "Doctor writes prescriptions; pharmacy dispenses in part or in full, marks medicines unavailable and keeps stock."],
  ["History and trends", "Searchable patient timeline, side-by-side report comparison and trend charts."],
  ["Dashboards and audit", "A dashboard for each role built from live data (for the doctor, a list of waiting reports that need attention first) and an audit log of important actions for the administrator."],
];

const userClasses = [
  ["Admin", "Creates and deactivates staff accounts, manages departments, reads the audit log. Never sees clinical values."],
  ["Doctor", "Reviews reports and the system's suggestions, writes notes, advice and prescriptions, sees authorised patients' history."],
  ["Hospital Employee", "Registers patients, uploads reports, books appointments. Never sees clinical values."],
  ["Patient", "Views own reviewed reports, tips, notes, prescriptions, appointments, timeline and trends."],
  ["Pharmacy Staff", "Opens active prescriptions, dispenses medicine, records unavailable items, manages stock."],
];

const techTable = [
  ["Frontend", "React 18, Vite 6, Tailwind CSS 4, React Router 6, Axios, Recharts"],
  ["Backend", "Python 3, FastAPI, Pydantic v2, SQLAlchemy 2"],
  ["Security", "JWT (PyJWT) and bcrypt password hashing"],
  ["Document reading", "pypdf and pypdfium2 for PDFs; Pillow and Tesseract (pytesseract) for OCR"],
  ["Database", "SQLite for development; PostgreSQL for production"],
  ["Optional AI", "Any HTTP-based language model, used only to reword text"],
  ["Testing", "pytest (108 automated tests)"],
  ["Browser", "Google Chrome, Microsoft Edge, Firefox (current versions)"],
  ["Operating system", "Windows 10/11 or Linux (server and client); any OS with a modern browser (client)"],
];

// ---------------------------------------------------------------- 3. Functional requirements
// Each requirement: [id, text, useCase, tests]. Test names are real pytest functions in backend/tests.
let n = 0;
const fr = (text, uc, tests) => [`FR-${String(++n).padStart(2, "0")}`, text, uc, tests];
const modules = [
  ["3.1 Authentication", [
    fr("The system shall allow registered users to log in with email and password.", "UC-01", ["test_login_me_and_invalid_login"]),
    fr("The system shall validate the entered credentials and show a general error message, which does not reveal which part was wrong, for invalid credentials.", "UC-01", ["test_login_me_and_invalid_login"]),
    fr("The system shall issue a signed token at login and shall refuse every private request that has no valid token.", "UC-01", ["test_private_endpoints_need_a_token"]),
    fr("The system shall allow users to log out, which ends the session in the browser.", "UC-01", ["Manual test: log out and press Back"]),
    fr("The system shall have no public sign-up. The first administrator can be created only once, on an empty system.", "UC-03", ["test_first_admin_only_once"]),
    fr("The system shall refuse login, and stop honouring old tokens, for deactivated users.", "UC-01, UC-03", ["test_deactivated_user_cannot_log_in"]),
    fr("The system shall store passwords only as bcrypt hashes and shall force a password change at first login when the password was generated by the system.", "UC-02", ["test_passwords_are_hashed", "test_generated_password_is_returned_once_and_must_be_changed"]),
    fr("The system shall let a logged-in user change their own password after entering the current one.", "UC-02", ["test_generated_password_is_returned_once_and_must_be_changed"]),
  ]],
  ["3.2 User Management", [
    fr("The administrator shall be able to create doctors, employees and pharmacy staff, and the system shall show the generated password once.", "UC-03", ["test_only_admin_manages_staff_and_audit"]),
    fr("The administrator shall be able to manage departments (create and list).", "UC-03", ["Fixture in conftest.py creates a department through the API"]),
    fr("The administrator shall be able to activate or deactivate a user, but not their own account.", "UC-03", ["test_admin_cannot_deactivate_self", "test_deactivated_user_cannot_log_in"]),
    fr("Employees and the administrator shall be able to register a patient (the login account is created together with the patient) and edit only basic information.", "UC-04", ["test_employee_cannot_change_clinical_fields"]),
    fr("The system shall allow searching patients by name, patient code, phone number or email.", "UC-04", ["test_patient_search"]),
    fr("The system shall limit every function to its roles and shall answer others with the message 'You do not have permission to access this information.'", "UC-01", ["test_permission_message", "test_role_matrix_on_core_endpoints"]),
    fr("The system shall keep patient data private: a patient sees only their own data, a doctor only authorised patients, and employees and the administrator never see clinical values.", "UC-13, UC-14", ["test_patient_sees_only_own_records", "test_doctor_sees_only_authorized_patients", "test_employee_sees_basic_info_but_never_clinical_data", "test_admin_has_no_clinical_access"]),
    fr("The administrator shall be able to view a readable list of all people in the system.", "UC-03", ["test_people_list_and_readable_audit_labels"]),
  ]],
  ["3.3 Report Upload and Analysis (Main Module)", [
    fr("The system shall accept PDF, JPG, JPEG, PNG and WEBP files (and optionally TXT and CSV) up to 10 MB, and shall check the real content type, not only the file name.", "UC-06", ["test_unsupported_and_fake_files_rejected"]),
    fr("The system shall read the text of text-based PDFs directly, without OCR.", "UC-06", ["test_text_pdf_is_read_without_ocr"]),
    fr("The system shall use OCR for scanned PDFs and images, and shall show a clear message when OCR is not available.", "UC-06", ["test_scanned_pdf_uses_ocr_pathway", "test_image_uses_ocr_pathway", "test_ocr_unavailable_error", "test_scanned_pdf_without_ocr_gives_clear_error"]),
    fr("The system shall extract test name, value, unit and reference range from the real file, whatever the layout, and shall keep the original test name.", "UC-06", ["test_extracts_value_unit_reference", "test_real_world_layouts", "test_different_layout_and_missing_reference"]),
    fr("The system shall take reference ranges only from the report (forms a-b, below x, above x) and shall never invent a range.", "UC-06", ["test_reference_parsing", "test_reference_none_when_absent"]),
    fr("The system shall decide Within, Above, Below or Unknown by fixed rules, and Unknown when no range is printed.", "UC-06", ["test_range_classification", "test_less_than_classification", "test_greater_than_classification", "test_unknown_when_no_reference"]),
    fr("The system shall reject unreadable files and non-medical documents with a clear message, and shall save nothing in that case.", "UC-06", ["test_invalid_document_rejected", "test_failed_or_invalid_upload_is_not_saved"]),
    fr("The system shall save an accepted report as 'Waiting for doctor' and show it on the assigned doctor's dashboard.", "UC-06, UC-17", ["test_complete_hospital_workflow"]),
    fr("The system shall warn when the name printed on the report does not match the selected patient.", "UC-06", ["test_name_mismatch_warning_and_report_values_come_from_each_file"]),
    fr("A doctor shall be able to upload a report for an authorised patient; when the patient has no assigned doctor the employee must choose one.", "UC-06", ["test_doctor_can_upload_for_authorized_patient", "test_doctor_must_be_chosen_when_patient_has_none"]),
    fr("The system shall write explanations that do not diagnose or prescribe, pass them through a safety filter, and fall back to built-in text when no AI model is configured.", "UC-06", ["test_disclaimer_and_safety_filter", "test_built_in_texts_never_diagnose_or_prescribe"]),
    fr("The system shall keep original files private and give them only to authorised users.", "UC-08, UC-13", ["test_complete_hospital_workflow", "test_admin_has_no_clinical_access"]),
  ]],
  ["3.4 Insights for Any Type of Report", [
    fr("The system shall accept other medical documents (imaging, ECG, pathology, discharge summary, prescription, clinical note), detect their type, and reject non-medical documents such as invoices.", "UC-06", ["test_report_type_is_detected", "test_all_kinds_of_files_are_accepted_and_invoice_is_not", "test_non_medical_documents_are_still_rejected"]),
    fr("For every report the system shall produce key findings (normal or worth a look, with negation such as 'no evidence of' handled), red flags for urgent wording, suggestions for the doctor and general tips for the patient.", "UC-07", ["test_statement_classification", "test_urgent_wording_is_flagged_for_the_doctor", "test_xray_gives_findings_and_suggestions_for_doctor_and_patient", "test_normal_ecg_has_no_attention_items"]),
    fr("For laboratory reports the insights shall be grouped by body system and use only printed ranges; a value without a printed range shall not be judged.", "UC-07", ["test_lab_insights_group_by_body_system_and_use_only_printed_ranges", "test_value_without_printed_range_is_not_judged"]),
    fr("Doctor-only content (suggestions, red flags) shall be shown only to the doctor; patients shall see general tips only after the doctor's review; employees and administrators shall see none.", "UC-07, UC-13", ["test_any_report_workflow_and_role_visibility", "test_lab_report_insights_visible_to_doctor_and_patient_tips_after_review"]),
    fr("A doctor shall be able to regenerate the insights of a report (recorded in the audit log); older reports without saved insights shall get them when opened.", "UC-07", ["test_refresh_insights_is_doctor_only", "test_old_lab_reports_without_saved_insights_still_get_them"]),
    fr("An optional AI model may improve the wording only after personal details are removed; its answer shall pass the safety filter, otherwise the rule-based text is used.", "UC-07", ["test_redaction_removes_personal_details", "test_ai_output_is_filtered_and_personal_data_is_not_sent", "test_bad_ai_reply_falls_back_to_rules", "test_doctor_filter_blocks_doses_and_patient_filter_blocks_diagnosis"]),
  ]],
  ["3.5 Doctor Review and Clinical Notes", [
    fr("The doctor shall be able to review a report (approve, modify or ask for clarification); a comment is required for modify and clarify; the report is then marked Reviewed.", "UC-08", ["test_complete_hospital_workflow", "test_doctor_content_validation"]),
    fr("The system shall show a report's analysis to the patient only after the doctor has reviewed it.", "UC-08, UC-13", ["test_unreviewed_analysis_hidden_from_patient_until_review"]),
    fr("The doctor shall be able to add notes (Normal, Important, Follow-up required) and recommendations (with an optional follow-up date); patients shall not be able to edit them.", "UC-09", ["test_patient_cannot_edit_doctor_content", "test_doctor_content_validation"]),
    fr("The doctor shall be able to add medical-history entries and shall see the patient's full history before reviewing.", "UC-09", ["test_doctor_sees_full_history_before_reviewing"]),
  ]],
  ["3.6 Prescriptions and Pharmacy", [
    fr("Only doctors shall create prescriptions (medicine, dosage, frequency, duration, quantity); a doctor shall see only their own prescriptions.", "UC-10", ["test_doctor_sees_only_their_own_prescriptions"]),
    fr("Pharmacy staff shall see prescriptions (cancelled ones are hidden) with only the data they need, and shall never create or edit a prescription.", "UC-11", ["test_pharmacy_sees_only_open_prescriptions_with_limited_data"]),
    fr("Pharmacy staff shall be able to dispense in part or in full; the system shall not allow more than the remaining quantity, shall block cancelled or expired prescriptions, and shall lower stock for tracked medicines (earliest expiry first, never expired stock) and refuse when the stock is not enough.", "UC-11", ["test_expired_prescription_cannot_be_dispensed", "test_inventory_and_stock_deduction"]),
    fr("Pharmacy staff shall be able to mark a medicine as unavailable, and the system shall record it.", "UC-11", ["test_unavailable_medicine_is_recorded"]),
    fr("Pharmacy staff shall be able to manage medicine stock, and the dashboard shall show low-stock and soon-to-expire items.", "UC-12", ["test_inventory_and_stock_deduction", "test_dashboards_have_real_numbers"]),
    fr("The patient shall be able to see the status of each prescription and how much has been dispensed.", "UC-13", ["test_complete_hospital_workflow"]),
  ]],
  ["3.7 Appointments", [
    fr("The system shall let the administrator, employees and patients book appointments, list them per role, and update their status (the doctor, employee and administrator may confirm, complete or cancel; a patient may only cancel); it shall refuse past times and clashes.", "UC-05", ["test_appointment_flow"]),
  ]],
  ["3.8 History, Comparison and Trends", [
    fr("The system shall build a searchable patient timeline from the database (appointments, reports, analysis, reviews, notes, recommendations, prescriptions, dispensing, history) and show the source of each item.", "UC-14", ["test_complete_hospital_workflow", "test_doctor_sees_full_history_before_reviewing"]),
    fr("The system shall compare two reports of one patient (previous, latest, change) with a trend that understands the direction of each parameter.", "UC-15", ["test_comparison_of_two_reports", "test_comparison_trend_logic_units"]),
    fr("The system shall draw trend charts of each parameter over time.", "UC-15", ["test_trend_series"]),
    fr("A patient's comparison shall use only reviewed reports.", "UC-15", ["test_patient_comparison_only_uses_reviewed_reports"]),
  ]],
  ["3.9 Dashboards, Notifications and Audit", [
    fr("Each role shall have a dashboard computed from the database, with honest empty states.", "UC-17", ["test_dashboards_have_real_numbers"]),
    fr("The system shall show in-app notifications on the dashboards: reports waiting for review, upcoming appointments, low stock and expiring medicine. (Email and SMS are not part of this version.)", "UC-17", ["test_dashboards_have_real_numbers"]),
    fr("The system shall write important actions (login, creation, upload, analysis, review, notes, prescriptions, opening a report file or a prescription, dispensing, user changes) to an audit log that only the administrator can read, in plain sentences.", "UC-16", ["test_complete_hospital_workflow", "test_people_list_and_readable_audit_labels"]),
    fr("The system shall display a medical disclaimer on every page and in the health response of the API.", "UC-17", ["test_disclaimer_and_safety_filter"]),
    fr("The system shall upgrade an existing database automatically at start-up when new columns are added, keeping the data.", "UC-17", ["test_new_columns_are_added_to_an_existing_database"]),
  ]],
  ["3.10 Key Numbers and Doctor Attention List", [
    fr("For a laboratory report the system shall show, at the top of the report, the number of tests read, in range, outside the range and without a range, and a card for each value outside the printed range with its difference from the limit, largest first.", "UC-07", ["Manual test: open a lab report as a doctor"]),
    fr("For other reports (Holter, ECG, scans and so on) the system shall read the label and number pairs of the text (counts, measurements, values with a printed range) and show them as tiles; it shall mark a tile only when the report prints a range for it or when it counts events above zero, shall leave out personal fields such as age, date or phone, and shall show each number once.", "UC-07", ["test_table_rows_become_numbers_not_broken_sentences", "test_extract_metrics_ignores_ids_and_repeats"]),
    fr("The key findings of a report shall be real sentences only: an abbreviation such as 'No.' shall not end a sentence, table rows shall not appear as sentences, and a repeated sentence shall appear once.", "UC-07", ["test_table_rows_become_numbers_not_broken_sentences"]),
    fr("The doctor's dashboard shall show how many waiting reports have urgent wording and how many values are outside the range, and a 'look at these first' list of the waiting reports with the most important values pulled out, ordered by urgent wording and then by values outside the range.", "UC-17", ["Manual test: doctor dashboard with waiting reports"]),
  ]],
];

// ---------------------------------------------------------------- 4. Non-functional requirements
const nfr = [
  ["4.1 Performance", "p", "Target values for a normal server (2 CPU cores, 4 GB RAM):", [
    "The system should answer normal page and list requests within 3 seconds.",
    "A text-based report (up to 10 MB) should be read, analysed and saved within 10 seconds.",
    "OCR of a scanned page may take longer; the screen shows that work is in progress and never freezes.",
    "Lists of people, reports and appointments are paged or limited so that screens stay fast as data grows."]],
  ["4.2 Security", "b", "", [
    "Passwords shall be stored only as salted bcrypt hashes, never as plain text.",
    "Every private request shall carry a signed token; a deactivated user's token stops working at once.",
    "Access shall be role-based, and a second check shall confirm that the record belongs to the user (for example, a patient only sees their own record).",
    "Uploaded files shall be checked by real content type and size, stored privately and served only to authorised users.",
    "Personal details shall be removed before any text is sent to the optional AI model.",
    "Important actions shall be written to an audit log."]],
  ["4.3 Usability", "b", "", [
    "The interface shall use plain words for non-technical users (for example 'Waiting for doctor' instead of status codes) and show dates as 'Today' or '2 hours ago'.",
    "Important tasks (upload a report, book an appointment, dispense medicine) shall need only a few clicks from the dashboard.",
    "Error messages shall say what went wrong and what to do next.",
    "Screens shall work on desktop, tablet and phone widths."]],
  ["4.4 Reliability", "b", "", [
    "The system shall keep data consistent: a failed upload saves nothing, and a database change is committed or rolled back as a whole.",
    "The system shall never fall back to demo or invented data when something fails; it shall show a clear error.",
    "The database can be backed up with the standard tools of SQLite or PostgreSQL.",
    "Unexpected errors shall be answered with a typed, readable message and not a crash."]],
  ["4.5 Availability", "p", "The system should be available during hospital working hours, with a target of 99% availability in a month for a production deployment. Planned maintenance should be announced in advance. The optional AI model and OCR engine are not required for the system to stay available: the system continues with built-in text and shows a clear message for scanned files when OCR is missing.", []],
  ["4.6 Maintainability", "b", "", [
    "The code shall be modular: routers (web layer), services (business rules), database models and utilities are separate.",
    "Supported lab parameters shall be defined in one catalogue file, so a new test can be added without changing the parser.",
    "A change to one module shall have minimal effect on others; 108 automated tests protect against regressions.",
    "Documentation shall be kept in the docs folder and in the README."]],
  ["4.7 Scalability", "p", "The system should support a growing number of patients, reports and users without a change of architecture. The same code runs on SQLite for small installations and on PostgreSQL for larger ones, and the web and database tiers can be moved to separate servers. Uploaded files are kept in a configurable folder that can be moved to shared storage.", []],
  ["4.8 Portability", "b", "", [
    "The web application shall run on current versions of Chrome, Edge and Firefox.",
    "The server shall run on Windows or Linux and can be packaged with the supplied Dockerfile.",
    "Settings (database address, secret key, AI model, file limits) shall come from environment variables."]],
];

// ---------------------------------------------------------------- 5. External interfaces
const screens = [
  ["Login page", "Email and password; first-time setup of the administrator on an empty system."],
  ["Change password", "Required after a generated password is used."],
  ["Admin dashboard", "People counts, recent activity, quick actions."],
  ["Staff and users", "Create doctors, employees and pharmacy staff; activate or deactivate; departments."],
  ["Audit log", "A day-by-day feed of who did what, in plain sentences."],
  ["Employee dashboard", "Register patient, upload report and appointment shortcuts."],
  ["Register patient", "Form for the patient's basic details."],
  ["Upload report", "Choose patient (and doctor), choose file, see the result or a clear error."],
  ["Doctor dashboard", "Look-at-these-first list with the important values, reports waiting for review, today's appointments, patients."],
  ["Report review", "Key numbers at a glance, result cards with range gauges, key findings, red flags, suggestions, history, review form."],
  ["Patient details (doctor)", "History, reports, notes, recommendations, prescriptions, timeline, trends."],
  ["Notes, advice and prescriptions", "Cards for the doctor's notes, follow-up advice and prescriptions."],
  ["Patient dashboard and My reports", "Reviewed reports in plain language, tips and status chips."],
  ["Health history and trends", "Timeline, report comparison and charts."],
  ["Appointments", "Cards grouped by day, with date tile, countdown chip and status."],
  ["Pharmacy dashboard", "Open prescriptions, low stock, expiring medicines."],
  ["Dispensing and inventory", "Dispense in part or in full, mark unavailable, stock meters, dispensing history."],
];

// ---------------------------------------------------------------- 6. Use cases
const actors = [
  ["Admin", "Hospital administrator.", "Creates staff accounts, manages departments, reads the audit log; has no access to clinical values."],
  ["Doctor", "Treating doctor.", "Reviews reports and insights, writes notes, advice and prescriptions."],
  ["Employee", "Front-desk or records staff.", "Registers patients, uploads reports, books appointments; has no access to clinical values."],
  ["Patient", "Person receiving care.", "Sees own reviewed reports, tips, prescriptions, appointments and history."],
  ["Pharmacy Staff", "Pharmacist or assistant.", "Dispenses prescribed medicine and keeps stock."],
  ["OCR engine (system actor)", "Tesseract.", "Reads text from scans and photos when the system asks."],
  ["AI model (system actor, optional)", "External language model.", "Rewords text after personal details are removed."],
];

const uc = (id, name, actor, pre, main, alt, post) => ({ id, name, actor, pre, main, alt, post });
const useCases = [
  uc("UC-01", "Login", "Admin / Doctor / Employee / Patient / Pharmacy Staff", "The user has an active account.",
    "Enter email, then password, then the system validates them, then the dashboard of the user's role opens.",
    "Wrong credentials or deactivated account: a general error is shown and nothing is revealed. If the password was generated, the user is sent to Change password first.",
    "The user is logged in; the login is written to the audit log."),
  uc("UC-02", "Change password", "All users", "The user is logged in.",
    "Open Change password, then enter the current and the new password, then the system checks them and saves the new hash.",
    "Wrong current password or a new password shorter than 8 characters: an error is shown and nothing changes.",
    "The new password is active and the 'must change' flag is cleared."),
  uc("UC-03", "Manage staff accounts", "Admin", "The administrator is logged in.",
    "Open Staff, then choose a role, then enter name, email and role details, then the system creates the account and shows a generated password once. The administrator can also activate or deactivate people and manage departments.",
    "Email already used: an error is shown. The administrator cannot deactivate their own account.",
    "The account exists and can log in; the action is audited."),
  uc("UC-04", "Register patient", "Admin / Employee", "The user is logged in.",
    "Open Register patient, then fill in the basic details, then the system creates the patient's account and a patient code.",
    "Invalid or duplicate email: an error is shown. Employees cannot enter clinical details.",
    "The patient appears in the patient list and can log in."),
  uc("UC-05", "Manage appointments", "Admin / Employee / Doctor / Patient", "The user is logged in; the patient and doctor exist.",
    "Choose patient, doctor, date, time and reason, then the system checks the time is not in the past and does not clash, then saves it as Scheduled. The doctor, employee or administrator can confirm, complete or cancel it; a patient can only cancel.",
    "Past time or clash: the system explains and does not save.",
    "The appointment shows on the dashboards of the people involved."),
  uc("UC-06", "Upload report", "Employee / Doctor (OCR engine)", "The user is logged in; the patient exists.",
    "Open Upload report, then choose the patient (and the doctor if needed), then add the file, then the system checks type, size and content, reads the text or runs OCR, finds the results and insights, and saves the report as Waiting for doctor.",
    "Wrong file type, too large, unreadable, or not a medical document: a clear message is shown and nothing is saved. OCR missing for a scan: a clear message. Name on the report differs from the patient: a warning.",
    "The report is saved with its results and insights and shows on the doctor's dashboard."),
  uc("UC-07", "View insights and suggestions", "Doctor (AI model)", "A report has been uploaded for one of the doctor's patients.",
    "Open the report, then read the key numbers at a glance, the key findings, the red flags and the suggestions for the doctor. The doctor can regenerate the insights.",
    "A report saved before insights existed: they are created when it is opened.",
    "The doctor has the information needed to review; regeneration is audited."),
  uc("UC-08", "Review report", "Doctor", "A report is Waiting for doctor.",
    "Open the report, read the values, history and insights, then choose approve, modify or clarify, then add a comment (required for modify and clarify), then save.",
    "Comment missing for modify or clarify: the system asks for it.",
    "The report is marked Reviewed; the patient can now see it."),
  uc("UC-09", "Write notes and advice", "Doctor", "The doctor is logged in and the patient is authorised.",
    "Open the patient or report, then add a note with its priority, or a recommendation with an optional follow-up date, or a medical-history entry. A suggested tip can be turned into official advice.",
    "Empty text: validation message.",
    "The note or advice is saved under the doctor's name and shown to the patient (advice and notes)."),
  uc("UC-10", "Create prescription", "Doctor", "The doctor is logged in and the patient is authorised.",
    "Open New prescription, then add each medicine with dosage, frequency, duration and quantity, then save.",
    "A missing field: validation message. Only the writing doctor may cancel it later.",
    "The prescription is Active for 30 days and appears for pharmacy and the patient."),
  uc("UC-11", "Dispense medicine", "Pharmacy Staff", "An active prescription exists.",
    "Search the prescription, then open it, then enter the quantity (part or all), or mark a medicine unavailable, then the system checks the remaining quantity and the expiry, saves the dispensing and lowers stock.",
    "More than remaining, or the prescription is cancelled or expired: the system refuses and says why.",
    "The prescription status is updated (partly or fully dispensed); stock is reduced; the action is audited."),
  uc("UC-12", "Manage medicine stock", "Pharmacy Staff", "The user is logged in.",
    "Open Inventory, then add or update a medicine with batch, quantity and expiry date.",
    "Negative quantity or missing name: validation message.",
    "Stock is current; low-stock and expiring items show on the dashboard."),
  uc("UC-13", "View reviewed report and tips", "Patient", "The doctor has reviewed the report.",
    "Open My reports, then choose a report, then read the plain-language results, the doctor's notes and the general tips.",
    "Report not yet reviewed: the patient is told it is waiting for the doctor and sees no analysis.",
    "The patient understands the result. Opening the original file is recorded in the audit log."),
  uc("UC-14", "View health timeline", "Doctor / Patient", "The user is allowed to see the patient.",
    "Open Health history, then scroll or search the timeline of appointments, reports, reviews, notes, prescriptions and dispensing.",
    "No data yet: an honest empty message.",
    "The user sees the history with the source of each item."),
  uc("UC-15", "Compare reports and trends", "Doctor / Patient", "The patient has at least two reports (reviewed ones for a patient).",
    "Open Compare, then choose two reports, then the system shows the change of each value and a trend chart.",
    "Fewer than two reports: the screen explains that a second report is needed.",
    "Changes and trends are displayed in plain words."),
  uc("UC-16", "View activity log", "Admin", "The administrator is logged in.",
    "Open Audit log, then read the day-by-day feed of who did what.",
    "No actions yet: an empty message.",
    "The administrator can see an accountable record of activity."),
  uc("UC-17", "View dashboard", "All users", "The user is logged in.",
    "Open the dashboard; the system shows numbers, lists and notifications computed from the database for the user's role.",
    "No data yet: an honest empty state is shown instead of sample numbers.",
    "The user sees the current state and quick actions."),
];

// ---------------------------------------------------------------- 7. Diagram captions
const figures = {
  usecase: ["Figure 6.1 Use case diagram", "use_case.png"],
  context: ["Figure 7.1 Context diagram", "context.png"],
  dfd0: ["Figure 7.2 Data flow diagram, level 0", "dfd0.png"],
  dfd1: ["Figure 7.3 Data flow diagram, level 1 (process 3.0, Report Analysis)", "dfd1.png"],
  activity: ["Figure 7.4 Activity diagram: report upload to dispensing", "activity.png"],
  sequence: ["Figure 7.5 Sequence diagram: report upload, review and dispensing", "sequence.png"],
  classa: ["Figure 7.6 Class diagram, part 1: people and roles", "class_a.png"],
  classb: ["Figure 7.7 Class diagram, part 2: reports, prescriptions and pharmacy", "class_b.png"],
  era: ["Figure 7.8 ER diagram, part 1: people, patients and appointments", "er_a.png"],
  erb: ["Figure 7.9 ER diagram, part 2: reports, notes, prescriptions and pharmacy", "er_b.png"],
};

// ---------------------------------------------------------------- 8. Data requirements
const tableInfo = {
  users: "Login accounts of everyone in the system, with the role.",
  departments: "Hospital departments.",
  doctors: "Extra details of users with the Doctor role.",
  employees: "Extra details of users with the Employee role.",
  pharmacy_staff: "Extra details of users with the Pharmacy role.",
  patients: "Patient profile: demographics and basic history.",
  appointments: "Booked visits between a patient and a doctor.",
  health_reports: "Uploaded reports, their processing and review state, and the insights.",
  health_parameters: "One row per test result found in a report.",
  report_comparisons: "Saved comparisons between two reports of a patient.",
  doctor_notes: "Notes written by a doctor.",
  doctor_recommendations: "Follow-up advice written by a doctor.",
  medical_history: "Medical-history entries added by a doctor.",
  prescriptions: "Prescriptions written by a doctor.",
  prescription_items: "Medicines listed in a prescription.",
  medicine_inventory: "Pharmacy stock of each medicine batch.",
  medicine_dispensing: "Every handing-out (or 'unavailable' record) of a prescribed medicine.",
  audit_logs: "Record of important actions.",
};
const colDesc = {
  id: "Unique number of the record", created_at: "When the record was created", user_id: "Login account",
  patient_id: "Patient the record belongs to", doctor_id: "Doctor responsible", department_id: "Department", report_id: "Report the record relates to",
  email: "Login email, unique", password_hash: "Password stored as a bcrypt hash", full_name: "Full name", role: "ADMIN, DOCTOR, EMPLOYEE, PATIENT or PHARMACY",
  is_active: "False when the account is deactivated", must_change_password: "True until the generated password is changed",
  name: "Department name", specialization: "Doctor's speciality", phone: "Contact number", designation: "Job title", pharmacy_name: "Name of the pharmacy",
  patient_code: "Readable patient number, unique", date_of_birth: "Date of birth", gender: "Gender", address: "Home address", emergency_contact: "Emergency contact person and number",
  blood_group: "Blood group", allergies: "Known allergies", medical_history_text: "Short history written at registration", current_medications: "Medicines currently taken",
  assigned_doctor_id: "Doctor looking after the patient or report", scheduled_at: "Date and time of the visit", reason: "Reason for the visit",
  status: "Current state", created_by: "User who created the record", uploaded_by: "User who uploaded the file", filename: "Original file name", file_path: "Private storage path of the file",
  report_date: "Date printed on the report", uploaded_at: "When the file was uploaded", processing_status: "ANALYZED (only successfully read reports are stored)", doctor_review_status: "PENDING (waiting for doctor) or REVIEWED",
  reviewed_by: "Doctor who reviewed", reviewed_at: "When it was reviewed", review_decision: "APPROVED, MODIFIED or CLARIFIED", review_comment: "Doctor's comment",
  extracted_text: "Text read from the file", processing_method: "How the text was read: pdf_text, ocr or text", ai_summary: "Short plain-language summary", report_type: "Detected type (lab, imaging, ECG ...)", insights_json: "Saved insights (findings, key numbers, red flags, suggestions, tips) as JSON",
  entry_date: "Date of the entry", entry_type: "Kind of entry", description: "Free text", note: "Text of the note", priority: "Normal, Important or Follow-up required",
  title: "Short heading", recommendation: "Text of the advice", follow_up_date: "Suggested date of the next visit",
  test_name: "Test name as printed", normalized_name: "Standard name of the test", value: "Measured value", unit: "Unit of measure", reference_text: "Reference range as printed",
  reference_low: "Lower limit of the range", reference_high: "Upper limit of the range", ai_explanation: "Plain-language explanation",
  prescription_date: "Date written (valid for 30 days)", clinical_indication: "Why it was prescribed", notes: "Extra notes",
  previous_report_id: "Earlier report", latest_report_id: "Later report", result_json: "Comparison result as JSON",
  prescription_id: "Prescription", medicine_name: "Name of the medicine", dosage: "Dose per intake", frequency: "How often", duration: "For how long", quantity: "Number of units",
  instructions: "How to take it", dispense_status: "PENDING, PARTIALLY_DISPENSED, DISPENSED or UNAVAILABLE", prescription_item_id: "Medicine line being dispensed", pharmacy_staff_id: "Pharmacy user who dispensed",
  quantity_prescribed: "Quantity asked for", quantity_dispensed: "Quantity handed out", dispensed_at: "When it was dispensed",
  batch_number: "Batch number", expiry_date: "Expiry date", manufacturer: "Manufacturer", unit_price: "Price per unit",
  action: "What was done", entity_type: "Kind of record touched", entity_id: "Number of the record touched", details: "Readable details", ip_address: "Address the request came from", timestamp: "When it happened",
};
const colOverride = {
  "medicine_inventory.quantity": "Units in stock", "medicine_inventory.name": "", "appointments.status": "SCHEDULED, CONFIRMED, COMPLETED or CANCELLED",
  "prescriptions.status": "ACTIVE, PARTIALLY_DISPENSED, DISPENSED, CANCELLED or EXPIRED", "medicine_dispensing.status": "Status of the medicine line after this dispensing",
  "health_parameters.status": "WITHIN_RANGE, ABOVE_RANGE, BELOW_RANGE or UNKNOWN", "prescription_items.quantity": "Quantity prescribed", "doctor_notes.created_at": "When the note was written",
  "patients.created_at": "When the patient was registered", "health_parameters.value": "Measured value in the report", "users.created_at": "When the account was created",
};
const describeCol = (t, c) => colOverride[`${t}.${c}`] || colDesc[c] || c.replace(/_/g, " ");

// ---------------------------------------------------------------- 10. Acceptance criteria
const acceptance = [
  ["Login", "Valid credentials open the dashboard of the user's role.", "FR-01"],
  ["Login", "Invalid credentials show a general error and no dashboard.", "FR-02"],
  ["Login", "A deactivated user cannot log in and an old token stops working.", "FR-06"],
  ["Security", "A user with no valid token is refused (HTTP 401) on every private function.", "FR-03"],
  ["Security", "Passwords are stored only as hashes; a generated password must be changed at first login.", "FR-07"],
  ["Roles", "A patient sees only their own data; a doctor sees only authorised patients; employees and the administrator never see clinical values.", "FR-14, FR-15"],
  ["Upload", "A readable PDF, photo or text report is accepted and saved as 'Waiting for doctor'.", "FR-17, FR-24"],
  ["Upload", "A non-medical or unreadable file is rejected with a clear message and nothing is saved.", "FR-23, FR-29"],
  ["Upload", "Two different reports give different extracted values.", "FR-20"],
  ["Analysis", "Each result is Within, Above or Below only when the report prints a range; otherwise Unknown.", "FR-21, FR-22"],
  ["Insights", "Doctors see findings, red flags and suggestions; patients see tips only after review.", "FR-30, FR-32"],
  ["Insights", "A normal statement such as 'no evidence of ...' is not flagged as a problem.", "FR-30"],
  ["Review", "A report marked Reviewed becomes visible to the patient; before that, the patient sees no analysis.", "FR-35, FR-36"],
  ["Prescription", "Only a doctor can create a prescription; pharmacy cannot edit it.", "FR-39, FR-40"],
  ["Dispensing", "Dispensing more than the remaining quantity is refused; stock decreases by the dispensed quantity.", "FR-41"],
  ["Dispensing", "A cancelled or expired prescription cannot be dispensed.", "FR-41"],
  ["Appointments", "A past time or a clashing time is refused.", "FR-45"],
  ["History", "The timeline shows the source of every item and can be searched.", "FR-46"],
  ["Comparison", "Two reports of a patient show the change of each value and a trend.", "FR-47, FR-48"],
  ["Audit", "Important actions appear in the audit log, readable by the administrator only.", "FR-52"],
  ["Quality", "All 108 automated tests pass.", "All"],
  ["Key numbers", "A lab report shows the values outside the range first; a Holter or ECG report shows its numbers as tiles, with no broken sentences.", "FR-55, FR-56, FR-57"],
  ["Doctor dashboard", "Waiting reports are listed with the most important values and urgent wording first.", "FR-58"],
];

// ---------------------------------------------------------------- 12. Appendices
const sampleReports = [
  ["Report_A_July_Rahul.pdf", "Text PDF, blood and metabolic panel (earlier report)."],
  ["Report_B_October_Rahul.pdf", "Text PDF, same patient three months later (for comparison and trends)."],
  ["Report_A_scan.png", "Scanned image; needs OCR."],
  ["Report_C_other_patient.txt", "Different patient, different layout and values (proves values come from each file)."],
  ["Chest_Xray_Rahul.pdf", "Imaging report with findings and impression."],
  ["ECG_Rahul.txt", "ECG report."],
  ["Discharge_Summary_Rahul.pdf", "Discharge summary."],
  ["Prescription_Rahul.txt", "Prescription document."],
  ["Not_a_health_report.txt", "Non-medical file; must be rejected."],
];

const permissionMatrix = [
  ["Manage staff and departments", "Yes", "-", "-", "-", "-"],
  ["Read audit log", "Yes", "-", "-", "-", "-"],
  ["Register patient", "Yes", "-", "Yes", "-", "-"],
  ["Upload report", "-", "Authorised patients", "Yes", "-", "-"],
  ["See clinical values and insights for doctors", "-", "Authorised patients", "-", "-", "-"],
  ["Review a report, write notes and advice", "-", "Yes", "-", "-", "-"],
  ["See own reviewed reports and tips", "-", "-", "-", "Yes", "-"],
  ["Create a prescription", "-", "Yes", "-", "-", "-"],
  ["Dispense medicine, manage stock", "-", "-", "-", "-", "Yes"],
  ["Book appointments", "Yes", "-", "Yes", "Yes", "-"],
  ["Change appointment status", "Yes", "Yes", "Yes", "Cancel only", "-"],
];

const questionnaire = [
  "The screens were easy to understand without any training.",
  "I could find the task I wanted from the dashboard in a few clicks.",
  "The result cards and colours made the report easy to understand.",
  "The suggestions for the doctor saved time when reviewing a report.",
  "The tips for the patient were clear and did not frighten me.",
  "Error messages told me what to do next.",
  "I felt my information was kept private.",
  "Overall, I would like to use this system in a hospital.",
];

module.exports = { schema, TITLE, definitions, references, productFunctions, userClasses, techTable, modules, nfr, screens, actors, useCases, figures, tableInfo, describeCol, acceptance, sampleReports, permissionMatrix, questionnaire };
