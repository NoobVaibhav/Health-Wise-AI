# HealthWise AI: bust report (red-team of the local copy)

Date of the run: 28 Oct 2026. Scope: backend, frontend, voice assistant, deployment files, dependencies, all against **local copies**: the automated tests use a temporary database, the browser sweep used a copy of the dev database on port 8001, and the live `healthwise.db` and `uploads/` were backed up first (`C:\hw_backup`) and **never attacked**. Only synthetic data. **Nothing was fixed**: phase 1 finds and proves, the fixes wait for approval.

## 1. Executive summary

The access-control design held up well: **all 128 operations were called by all six roles and with no token and no role got in where it should not** (`docs/ENDPOINT_MATRIX.md`). Forged, tampered and expired tokens, role-claim edits, IDOR on every id-based endpoint, mass assignment, upload type and path tricks, static-file exposure, CORS and header injection all failed for the attacker.

The problems are in four other places:

1. **The analysis can read a result the wrong way, and some of those errors are in the dangerous direction**: "Cannot rule out pulmonary embolism" is classified as *normal*; a deficient Vitamin D of 15 or a "Low" HDL of 35 is read as *within range*; serious findings such as aortic dissection, ST-segment elevation, STEMI, cardiac arrest, free air and testicular torsion are not flagged at all.
2. **Denial of service by a single employee or doctor**: one 150 KB line in a report takes 7 minutes (quadratic regex), an image or PDF can make the server crash or allocate gigabytes, there is no request-size limit, and the dispense step can be raced to hand out 5x the prescribed quantity.
3. **Accountability and privacy**: stock changes, denied access attempts and (after deletion) the actor behind every audit row are not recorded; with an AI key set, names, address and phone numbers are sent to the outside service; patient history drafts stay in the browser after logout.
4. **Deployment**: the default secret in `docker-compose.yml` is accepted by the app's own weak-secret check, `schema.sql` lacks 19 of 37 tables, packages are unpinned, and the installed Pillow (39 known vulnerabilities) and pypdf (11) parse untrusted uploads.

Counts: **8 High, 18 Medium, 12 Low/Info** (38 findings). 50 expected-failing backend tests and 5 frontend tests reproduce them (marked with the finding ID); 103 backend and 10 frontend chaos tests passed.

## 2. How to reproduce

| What | Command |
|---|---|
| All backend chaos tests | `cd backend && pytest tests/security_and_chaos -q` (about 4 minutes) |
| One finding | `pytest tests/security_and_chaos -q --runxfail -k <test name>` |
| Frontend chaos tests | `cd frontend && npx vitest run src/__tests__/chaos` |
| Browser sweep (white screens, phone width) | see the header of `backend/tests/security_and_chaos/ui_chaos_playwright.py` (isolated stack only) |

A test marked `@bust("ID")` (backend) asserts the SECURE behaviour and is an expected failure while the bug exists; the strict mark turns it into a loud failure the day the bug is fixed (remove the mark then). Frontend: `it.fails(...)`. Baseline before the attack: backend 334 passed, frontend 48 passed, `npm run build` OK.

## 3. Findings, most severe first

| ID | Severity | Finding | Test |
|---|---|---|---|
| T-02 | High | "Cannot rule out X" is read as a negation: the finding is treated as absent | `test_ai_integrity.py::test_phrases_where_the_reading_is_wrong_or_dangerous` |
| T-06 | High | Rows with interpretive tiers on one line use the first tier as the normal range | `test_ai_integrity.py::test_a_row_that_prints_interpretive_tiers...` |
| T-03 | High | Serious findings not recognised, and "urgent" words are ignored unless a second word also matches | same file, `[T-03-*]` |
| R-01 | High | Quadratic regex: one long line freezes the server for minutes | `test_uploads_static_config.py::test_one_long_line...` |
| B-01 | High | Race in dispensing: 8 parallel calls gave out up to 5x the prescribed quantity | `test_business_logic.py::test_two_pharmacists...` |
| P-01 | High (when an AI key is set) | Names, address and phone numbers are sent to the AI service | `test_ai_integrity.py::test_personal_details...` |
| D-02 | High | Pillow 12.3.0 (39 known vulnerabilities) and pypdf 6.19.0 (11) parse uploaded files | `test_ops_findings.py::test_the_installed_pillow...` |
| O-01 | High (deployment) | The secret in `docker-compose.yml` passes the weak-secret check | `test_ops_findings.py::test_the_secret_written_in_docker_compose...` |
| S-02 | Medium | The AI model can turn a rule-flagged finding into "looks normal" | `test_ai_integrity.py::test_the_ai_model_cannot_turn...` |
| U-01 | Medium | An image that expands to 900 megapixels gives HTTP 500 | `test_uploads_static_config.py::test_an_image_that_expands...` |
| U-02 | Medium | A PDF with a huge page is rendered at full size for OCR | `...::test_a_pdf_with_an_enormous_page...` |
| D-01 | Medium | No request-size limit: a 30 MB JSON login body is read and parsed | `...::test_a_huge_request_body...` |
| J-01 | Medium | 1,000-level nested JSON to the login (no token needed) gives HTTP 500 | `...::test_deeply_nested_json...` |
| R-02 | Medium | No cap on analysed text: a legal 10 MB text file costs minutes of CPU | `...::test_a_big_text_file...` |
| L-01 | Medium | A non-text `summary` in the AI reply crashes the upload (HTTP 500) | `test_ai_integrity.py::test_the_app_works_when_the_ai_model_fails...` |
| S-01 | Medium | AI wording shown to the patient only passes the weaker doctor filter | `test_ai_integrity.py::test_wording_from_the_ai...` |
| A-04 | Medium | Two simultaneous first-admin registrations both succeed | `test_auth_attacks.py::test_two_people_registering...` |
| A-01 | Medium | Anyone can lock any known user out (lockout per email) | `test_auth_attacks.py::test_the_lockout_cannot_be_used...` |
| B-02 | Medium | A reviewed report is silently re-reviewed with another decision, no history | `test_business_logic.py::test_a_report_that_was_reviewed...` |
| B-03 | Medium | Stock and price changes and stock receipts are not audited | `...::test_changes_to_the_medicine_stock...` |
| B-04 | Medium | Refused (403) access attempts leave no trace | `...::test_attempts_to_reach_someone_elses_data...` |
| B-05 | Medium | Deleting a user makes their whole audit trail anonymous | `...::test_deleting_a_user_does_not_make...` |
| F-02 | Medium | Patient history drafts stay in `localStorage` after logout | `session.chaos.test.jsx` |
| F-05 | Medium | No error boundary: 68 page/answer combinations end in a white screen | `errorboundary.chaos.test.js` + browser sweep |
| S-03 | Medium | `schema.sql` lacks 19 of 37 tables and about 20 columns | `test_schema_and_ops.py::test_schema_sql...` |
| X-01 | Medium | Birth dates in year 0001, 1800, 9999 and 2999 are accepted | `test_business_logic.py::...[dob-*]` |
| T-04 | Low | "Not suspicious for malignancy" is flagged as suspicious and urgent | `[T-04-*]` |
| O-03 | Low | Python packages are not pinned (`>=`) and pytest is a runtime requirement | `test_ops_findings.py::test_the_listed_python_packages...` |
| A-02 | Low | Passwords sharing their first 72 bytes are the same password | `test_auth_attacks.py::test_two_passwords...` |
| A-03 | Low | No maximum password length (2 MB accepted) | `test_auth_attacks.py::test_an_absurdly_long...` |
| C-01 | Low | `/docs`, `/redoc`, `/openapi.json` are public | `...::test_the_interactive_api_documentation...` |
| X-02 | Low | NUL bytes accepted in names (PostgreSQL would answer 500) | `[name-nul-byte]` |
| F-03 | Low | Logging out in one tab does not end the session on screen in other tabs | `session.chaos.test.jsx` |
| F-04 | Low | The words "health wise" in normal speech switch the wake-phrase microphone on | `voice.chaos.test.js` |
| V-01 | Low | The spoken words "start over" delete the chat on the server without asking | `assistant.chaos.test.jsx` |
| F-06 | Low | 7 pages scroll sideways at phone width (375 px) | browser sweep only |
| I-01 | Info | JWT in `localStorage` (readable by any script injected into the page; none found); 24 h token, no server-side logout | design |
| I-02 | Info | Pharmacy sees `clinical_indication`; employees see the report type label; a doctor gets access to a patient's whole record through any appointment or report assignment made by staff, and report reads are not audited (B-04 family) | design |

### High

**T-02, "cannot rule out" is read as normal.** `classify_statement("Cannot rule out pulmonary embolism.")` returns `('normal', False)`. The negation list contains "rule out", so the finding after it counts as absent. Expected `('attention', True)`. Impact: a radiology sentence that means "possible PE" is shown as "looks normal" to doctor and patient. Fix: treat "cannot / unable to / not possible to rule out / exclude", "not excluded", "cannot be excluded" as uncertainty (attention) and handle them before the negation check.

**T-03, serious findings missed.** Returned `('neutral', False)` for: "Aortic dissection.", "ST-segment elevation in the anterior leads.", "ST segment elevation in leads II, III and aVF.", "Features of STEMI.", "Cardiac arrest.", "Free air under the diaphragm.", "Pneumoperitoneum.", "Testicular torsion."; "Ventricular tachycardia sustained." is attention but not urgent. Cause: `URGENT_TERMS` is only consulted when an `ATTENTION_TERMS` word also matched ("dissection", "rupture", "perforation", "critical", "life-threatening" are urgent-only terms and so never fire alone), and the lists lack "st-segment", "stemi", "arrest", "free air", "pneumoperitoneum", "torsion". Fix: any urgent term implies attention and urgent; extend the lists; add a regression table of urgent phrases.

**T-06, interpretive tiers read from the wrong tier.** Single-line rows: `Vitamin D 15 ng/mL Deficient <20 Insufficient 20-30 Sufficient 30-100` gives WITHIN_RANGE (high=20 taken as the upper normal limit); value 25 gives ABOVE_RANGE; `HDL Cholesterol 35 mg/dL Low <40 High >60` gives WITHIN_RANGE; value 70 gives ABOVE_RANGE. Rows whose first tier is the normal one (Cholesterol, Glucose, HbA1c, LDL, Triglycerides) came out right, by luck. The multi-line layout was fixed earlier; the one-line layout was not. Impact: a deficient or low value is reported as normal. Fix: reuse the labelled-tier logic (only a tier labelled normal/desirable/optimal/sufficient is the normal range; otherwise UNKNOWN) for the inline layout.

**R-01, quadratic regex.** `clean_report_text` (BOILERPLATE_RE) and `llm_service.redact_text` (`_EMAIL`) use `[\w.+-]+@...`: on a long run of word characters without `@` the match restarts at every position. Measured: 20,000 characters 1.8 s; 60,000 about 16 s; 150,000 characters **431 s**; 100,000 dots 88 s. One uploaded text file (or a PDF with such a line) blocks the single worker for everyone. Fix: bound the quantifier (`[\w.+-]{1,64}@`), cap line length (for example 2,000 characters) before any regex, cap the text analysed (R-02).

**B-01, dispensing race.** Read-then-write without a lock. Eight simultaneous 5-unit dispenses on a 5-unit prescription: 5 returned 200 (25 units dispensed). Fix: lock the prescription item (`SELECT ... FOR UPDATE` on PostgreSQL, a `BEGIN IMMEDIATE` transaction on SQLite) or an atomic `UPDATE ... WHERE remaining >= :q` and check the row count.

**P-01, personal details go to the AI service.** With a key set, `enhance_insights` sends `redact_text(text)` plus the software's first reading as JSON. Reproduced leaks: the name in a sentence ("Mr. Rahul Patil ...", "Rahul reports"), a relative's name, the street address, a phone number inside a sentence, a PAN number; the first-reading JSON (summary and key findings) is **not redacted at all**. Only lines that *start* with Patient/Name/DOB/UHID/... and e-mails are removed. This breaks the project promise "the AI never receives identifiable data". Fix: redact the first-reading JSON too; remove the patient's own name parts and phone/e-mail/address from the text by value (the server knows them), add pattern redaction for ids; or send only structured values.

**D-02, vulnerable parsers.** `pip-audit` on the project environment: Pillow 12.3.0 has 39 known vulnerabilities (fixed in 13.0.0), pypdf 6.19.0 has 11 (fixed in 6.21.2), dnspython 1. Both libraries open files uploaded by employees and doctors. Fix: upgrade and pin; re-run the suites.

**O-01, default secret in compose.** `JWT_SECRET: ${JWT_SECRET:-change-this-to-a-long-random-secret-before-deploying}`. `check_secret()` rejects only `change-me-in-production` or fewer than 32 characters, so on PostgreSQL this public 49-character string is accepted and anyone who read the repository can sign a token for any user id. Fix: refuse any value that starts with `change` or equals the compose default, remove the fallback from compose (`${JWT_SECRET:?set JWT_SECRET}`).

### Medium (short form: expected / actual / fix)

* **S-02**: `enhance_insights` replaces the rule-based `key_findings`, including `concern`. With a model reply (or text hidden in the report) marking "Right lower zone consolidation..." as `normal`, the output shows `normal`. The README says the AI never decides. Fix: keep the rule-based `concern`; let the model change wording only.
* **S-01**: `key_findings` are in the patient's view but are checked with `is_safe_for_doctor`. "This is a clear diagnosis of lung cancer and a medical emergency." passes. Fix: use `is_safe` for anything the patient can see.
* **L-01**: reply `{"summary": 5}` or `"explanations": "x"` makes `safety_filter.is_safe` raise `TypeError`; the upload answers 500. Fix: type-check the model's reply and wrap the whole enhancement in a try/except that falls back to the rules.
* **U-01**: a 100 KB PNG of 30000x30000 pixels: `Image.DecompressionBombError` is not caught (`load_image` catches `UnidentifiedImageError`, `OSError`) so the upload is HTTP 500. Fix: catch it, and set `Image.MAX_IMAGE_PIXELS` to a sane limit (for example 50 megapixels).
* **U-02**: `render_pdf_pages` renders each page at scale 2.5 with no size check: a 4,000 pt page asks pdfium for 100 megapixels (400 MB); the PDF maximum, 14,400 pt, is about 1.3 gigapixels. Fix: read `page.get_size()` first and refuse or lower the scale above about 30 megapixels.
* **D-01**: a 30 MB JSON body to `/api/auth/login` is read and parsed (answer 401). No limit in uvicorn or the app. Fix: reject by `Content-Length` and while streaming in a small middleware (for example 1 MB for JSON, 11 MB for uploads), and set the limit at the reverse proxy.
* **J-01**: `[`x1000 as a login body gives HTTP 500 (`RecursionError` in the JSON parser), unauthenticated. Fix: catch `RecursionError`/`ValueError` in a handler and answer 400.
* **R-02**: 20,000 report lines cost 6 s; the allowed 10 MB text is about 300,000 lines, minutes. Fix: cap text length and line count, and run analysis in a worker with a timeout.
* **A-04**: six threads registering at once: two got 201 (two first administrators). Fix: do the "no user exists yet" check and insert in one transaction with a unique marker, or lock.
* **A-01**: 12 wrong passwords for `anjali@...` then the correct one: 429. An attacker can lock out any known user, including the admin, indefinitely. Fix: lock per (email, source address) with a growing delay, never hard-block the correct owner from a different address, and alert the admin.
* **B-02**: review twice with a different decision: both accepted; the first decision, comment and time are overwritten. Fix: refuse or version the review; audit the old value.
* **B-03**: `POST/PUT /api/pharmacy/inventory`, `POST /inventory/receive` have no `audit_service` call (sales and dispensing do). A rogue pharmacist can zero a quantity or price unseen. Fix: audit with before/after values.
* **B-04**: 28 refused reads by a patient left no audit row; only `LOGIN_FAILED` exists. Fix: log 403s on patient data (`ACCESS_DENIED` with route and target id), rate-alert on repeated ones.
* **B-05**: `USER_DELETED` sets `audit_logs.user_id` to NULL; every `LOGIN`, upload and review of that person becomes anonymous. Fix: store an actor snapshot (id, name, role, e-mail) in the audit row, or soft-delete users.
* **F-02**: the doctor's history form saves drafts in `localStorage` (`hw_history_draft_<patientId>`); `logout()` removes only the token. On a shared computer the next person can read the previous patient's history. Fix: clear drafts (and any `hw_*` PHI) on logout and on the 401 path; or keep drafts on the server.
* **F-05**: the browser sweep answered every API call with `{}`, `null` or `[]`: **68 page/answer combinations** (ADMIN 12, DOCTOR 12, EMPLOYEE 10, PHARMACY 11, LAB 3, PATIENT 20, for example `/patient/reports` with `{}`) end in a blank page, because there is no error boundary and pages assume the data shape. Server errors (500/403) and a dead network were handled with sane messages. Fix: a top-level and per-route error boundary with a "Something went wrong, go back / log out" screen, and defensive defaults (`?? []`).
* **S-03**: `schema.sql` vs the models: 19 tables missing (`sales`, `sale_items`, `lab_staff`, `lab_test_orders`, `patient_history`, `patient_medications`, `chronic_conditions`, `surgery_records`, `hospital_admissions`, `clinical_assessments`, `clinical_summary_snapshots`, `summary_reviews`, `follow_up_tasks`, `emergency_events`, `emergency_timeline_entries`, `history_revisions`, `patient_assistant_*` x3) and columns missing in 8 tables (for example `health_reports.insights_json`, `report_type`; `users.avatar_path`; `medicine_inventory.barcode`). Fix: generate the file from the models (`CREATE TABLE` via SQLAlchemy `CreateTable`, or Alembic) and test it in CI.
* **X-01**: `date_of_birth` 0001-01-01, 1800-01-01, 9999-12-31, 2999-01-01 accepted (negative or 800-year ages). Fix: validate 1900-01-01 to today.

### Low and informational

T-04 (`classify_statement("Not suspicious for malignancy.")` gives attention and urgent, an alarm in the safe direction), A-02 (`bcrypt` cut at 72 bytes: `"A1"+"x"*70+"-original"` and `+"-SOMETHING-ELSE"` are the same password; pre-hash with SHA-256 before bcrypt, or refuse longer), A-03 (cap at 128), C-01 (disable docs in production or put behind login), X-02 (strip or refuse `\x00`), F-03 (listen to the `storage` event), F-04 (`afterWakePhrase("being health wise is important")` is not null: require "hey/ok/hi" before the name), V-01 (ask before the spoken "clear chat"/"start over" deletes server data), F-06 (horizontal scroll at 375 px on `/admin/reports`, `/doctor/reports/:id`, `/employee`, `/employee/reports`, `/patient`, `/patient/reports`, `/patient/profile`), O-03 (pin with a lock file; move pytest to a dev requirements file; the Dockerfile also runs as root and has no healthcheck).

## 4. What I tried that held up

* **Access control**: 128 operations x (no token + 6 roles): every refusal correct, no 500 except a clearly worded 503 "no AI model connected". Admin and employee receive no clinical content in any response (insights, summary and parameters are null); the patient gets nothing before the review and never `red_flags`, `doctor_suggestions`, extracted text or file paths.
* **IDOR**: another patient and an unrelated doctor tried about 35 id-based calls on a patient's reports, prescriptions, history, conversations, follow-ups and emergency events: all 403/404, nothing changed. The assistant ignores a patient id in the request.
* **Tokens**: wrong secret, the documented default secret, no `exp`, expired, no or wrong `pv`, `alg: none` (with and without junk signature), HS384/HS512, edited subject, garbage, a role claim: all 401/403. A deactivated user loses access at once; changing the password kills older tokens and requires the old password. Brute force is stopped with 429 and unknown and known e-mails get the identical answer.
* **Mass assignment**: `role`, `is_active`, `must_change_password`, `user_id`, `id` in patient creation and profile update changed nothing. A temporary-password account reaches only `/me` and change-password.
* **Uploads**: invoice, empty file, `.exe`, `.html`, `.svg`, fake PDF/PNG, `report.pdf.exe`, `notes.txt.html`, no extension, NUL in the name: refused and **nothing left in the upload folder**. Path traversal names store under a random name; the file is served as an attachment with `nosniff`; a CR/LF in the file name cannot inject a header; broken, locked and junk PDFs are refused; a file over the limit is refused.
* **Exposure**: `/uploads`, `/healthwise.db`, `/.env`, `/.git/config`, `/app/main.py`, logs: all 404. CORS answers only the known front end (also for `null`, look-alike hosts). Security headers present; `Cache-Control: no-store` on the API; no stack trace or path in any error. No `dangerouslySetInnerHTML`, `innerHTML` or `eval` in the frontend; no raw SQL with user data.
* **Parser inputs**: nine hostile texts (commas, spaces, ranges, dots, nested brackets, 20,000 lines, Unicode minus, flags) all under 5 s except the cases in R-01/R-02.
* **Range logic**: reversed ranges, half ranges, `<`, `>`, "Up to", "Less than", European decimals, en dash, "to", boundary values, other units (g/L), contradictory printed flags, "0 - 0", sex-specific ranges (UNKNOWN or within): statuses correct or unknown. Dates: DOB ignored, future, impossible, two-digit-year and 1899/9999 dates give "unknown", never a guess.
* **AI promises**: the app works with no key and with 12 kinds of model failure at the HTTP level (timeouts, 401/500, bad JSON); unsafe model wording ("You have diabetes. Take 500 mg...") is dropped from summary and tips; hidden instructions in a report change nothing in the rule-based result.
* **Workflow**: a second doctor cannot review someone else's report; a patient cannot review, upload or delete; dispensing refuses too much, zero, negative, cancelled and expired prescriptions; negative or oversize sales and a second bill for the same prescription are refused; absurd lab values (1e308, NaN, Infinity, -0) never crash; deleting or deactivating staff with records never crashes; the audit API has no write or delete route.
* **Voice**: a spoken command can only control the voice; noise and gibberish give no command; navigation targets are fixed `/patient/...` pages; denied microphone, unsupported browser and no voice installed all fall back to typing.
* **Frontend**: all 6 roles typing each other's URLs go home; no token goes to login; expired token clears the session; 500, 403 and a dead network show readable messages.

## 5. Not covered (be aware)

Docker is not installed here, so `docker compose up` was reviewed by reading only (O-01, root user, no healthchecks). PostgreSQL was not run. Tesseract is not installed, so OCR was exercised only for its error path (a clear 503). I did not kill the database mid-request, load-test, measure colour contrast, or do a full keyboard-only walk; the accessibility scan flagged five voice-setting controls that turned out to be a false positive (closed menu). Timing-based user enumeration (unknown e-mail skips bcrypt) was not measured.

## 6. Suggested order of fixes

1. T-02, T-03, T-06 (wrong clinical reading), then R-01/R-02/U-01/U-02/D-01/J-01 together (one "input limits" change), B-01.
2. D-02 + O-03 (upgrade and pin), O-01 + S-03 (deployment).
3. P-01, S-01, S-02, L-01 (the AI layer), then B-02..B-05 (audit), F-02, F-05.
4. The Low items.

## 7. Fixed so far (the browser findings)

| ID | Fix | Proof |
|---|---|---|
| F-05 | `ErrorBoundary` around the whole app and around every page inside the frame (resets when you move to another page): a plain message with Try again, Home page and Log out | the browser sweep now shows **all 68 former white screens as the friendly screen**; `errorboundary.chaos.test.jsx` |
| F-06 | long file names and e-mail addresses now wrap (`min-w-0`, `break-words`); the two "older/newer report" selects fit | no page scrolls sideways at 375 px (7 of 7 checked) |
| F-02 | logging out removes the saved patient history drafts (`clearSavedPatientData`) | `session.chaos.test.jsx` |
| F-03 | the session ends in every tab when the token is removed or changed in another tab (`storage` event) | `session.chaos.test.jsx` |
| F-04 | the wake phrase needs a greeting before the name ("hey / hi / hello / ok healthwise"); "health wise" in normal speech no longer switches the microphone on | `voice.chaos.test.js` |
| V-01 | the spoken "clear the chat" / "start over" asks "Do you want to clear this chat? Say yes or no." and deletes only after a yes | `assistant.chaos.test.jsx` |

The `it.fails` marks of these six tests were removed (they are normal tests now). Still open: everything in sections 3 that is not in this table; waiting for your decision.
