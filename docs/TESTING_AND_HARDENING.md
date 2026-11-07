# Testing and hardening log (23 Oct 2026)

A full pass to find bugs and loopholes. Everything below was reproduced first, fixed, and then covered by an automated test.

## How it was tested
| Method | What it covers |
|---|---|
| Existing + new pytest suites | Workflows, RBAC, extraction, clinical intelligence, patient assistant |
| `tests/test_idor_sweep.py` | Another patient and a doctor who is not authorised try ~35 id-based endpoints (read and change); staff roles try clinical data |
| `tests/test_fuzz_no_500.py` | Every write endpoint x every role x malformed/extreme/hostile bodies; every read endpoint with odd query values; huge ids in paths; hostile upload files |
| Browser smoke run | Every menu page of all five roles, plus doctor/patient detail pages: console errors, failed API calls |
| Static checks | `ruff` (unused/undefined names), `bandit` (no medium or high findings) |
| Question sweep | 25 differently worded questions to the assistant, checking the routing |

## Bugs and loopholes found and fixed
| # | Problem | Fix |
|---|---|---|
| 1 | **No brute-force protection**: unlimited password guesses | After 5 failed logins for an email (or 30 from one address) in 15 minutes, login answers 429; counted from the audit log so it survives restarts |
| 2 | **Temporary password only enforced in the browser**: a user with a temporary password could call the whole API | The server now refuses everything except `/auth/me` and `/auth/change-password` until the password is changed |
| 3 | **Stolen/old tokens kept working for 24 h after a password change** | Tokens carry a fingerprint of the password hash; changing the password ends all older tokens (the changing device receives a new one) |
| 4 | **Weak passwords accepted** (`aaaaaaaa`, `password`) | At least one letter and one number, not a common password; the new password must differ from the old one |
| 5 | **Default JWT secret could run in production** | Start-up refuses a missing/short secret on a non-SQLite database and warns on SQLite |
| 6 | No security headers; patient data could be cached | `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`; API answers are `Cache-Control: no-store` |
| 7 | **Server crash (500)** on a very large number in an id or query (`patient_id=99999999999999999999`) in several list endpoints (notes, recommendations, reports, prescriptions ...) | Global handler turns it into a 422 |
| 8 | Two people saving at the same moment (for example the same bill number) crashed with 500 | Database conflicts now return 409 "please try again"; stock rows are locked during a sale on PostgreSQL so the last units cannot be sold twice |
| 9 | **Lab values read wrongly**: a report printing `5,6 mmol/L` was stored as 5 with no unit and no range | Decimal commas are converted (thousands separators such as `1,200` stay) |
| 10 | Indian digit grouping `1,50,000` (platelets, WBC) was not read at all | The number pattern accepts lakh grouping |
| 11 | Assistant misrouted natural wording: "cholestrol" (typo), "what did the doctor tell me", Hinglish "dawai", "can I take paracetamol" (answered with the help text) | Spelling repair for test names, more keywords, medicine-advice questions are refused safely, a prescribed medicine's name shows the prescription |
| 12 | Unused imports/variables in new code | Removed |

## Checked and found sound
* Every `/api` route needs a login except `/api/health`, the setup check, login and the one-time first-admin registration.
* No cross-patient or cross-role access found on any id-based endpoint (reads or changes).
* Uploads: extension allow-list, real file signature check, random stored names, size limit, downloads as attachments; avatars are re-encoded and protected against decompression bombs.
* No raw HTML injection in the frontend; the database layer is parameterised (SQL text in inputs is stored as plain text).

## Known remaining limitations
* The login lockout can be used to lock a known email for 15 minutes (an accepted trade-off against password guessing).
* Rate limits other than login are kept in memory per server process.
* Tokens live in the browser's local storage (a cross-site scripting bug would expose them); a hardened deployment should move to HTTP-only cookies and add a Content-Security-Policy.
* No two-factor login, no password reset by e-mail (an administrator cannot yet reset a password either).
* A one-line lab file without any header is reported as "not a recognisable report".
* Result values written with a `<` prefix (for example `<100`) are not stored.
* Row locking during a sale only takes effect on PostgreSQL; SQLite serialises writes anyway.


---

# Model cross-check (23 Oct 2026, second pass)

Each main module was checked against answers worked out independently of the code (labelled test sets), not only "does it run".

| Module | Test set | Result |
|---|---|---|
| Report extraction + range classification | 402 lab values: 24 tests x 6 print layouts (plain, with H/L flag, colon, brackets, "Ref:", pipe tables) x low/normal/high values, as text files **and** as real PDFs | **402/402 correct** in both (value, unit, status) |
| Tricky layouts (checked one by one) | tiered ranges, units inside the range, `*` flags, "High/Low" words, values on separate lines, DOB next to the report date, boundary values (value = limit) | correct; boundary rules (`<150` with 150 is above) confirmed |
| Unit conversion | 9 conversions against textbook values (glucose, creatinine, haemoglobin, cholesterol, triglycerides) and 5 conversions that must be refused | all correct, refused ones return "not comparable" |
| Trend verdicts | 8 cases (back in range, newly out of range, closer/further from range, stable, no range) + percent and unit arithmetic | all correct |
| Patient assistant question routing | 59 golden questions in English, Hindi, Marathi and Hinglish | 95% at first, **100% after fixes** |
| Emergency detection | 23 dangerous messages (3 languages) and 11 ordinary record questions | 23/23 caught, 0 false alarms after one fix |
| Medicine-change and diagnosis requests | 6 + 7 messages | 13/13 caught |
| Safety filter | 7 forbidden and 6 allowed sentences | correct |
| Billing and stock | 25 random sales (random prices, GST, discounts): totals recomputed independently, stock reconciled | exact; overselling, expired stock, negative quantity, over-discount refused |
| Medicine matching and allergy flag | strengths/forms stripped; allergy matched by name only | correct |
| Clinical summary urgent notice | mild vs severe value | correct |

## Found and fixed in this pass
1. **Reference ranges printed separately for men and women** (`Male: 13.0 - 17.0 Female: 12.0 - 15.5`): the first range (men's) was used silently, so a woman with 12.5 g/dL would be flagged low. Now the value is shown as "reference range unavailable" with the printed text kept, and no range is guessed.
2. Assistant: "compare ... jaanch" (Hindi) was read as a checkup question, "which test did the doctor mark abnormal" was read as a checkup question, "explain what haemoglobin means" was read as a personal result, "what is the weather" got a medical-sounding reply, and "what is the meaning of stroke" triggered the emergency message. All fixed; a real emergency phrased as a question ("my father seems to be having a stroke, what is happening") is still caught.

## Known limits found
* **Scanned images and photos cannot be read on this computer**: Tesseract OCR is not installed (the app answers "OCR is not configured" instead of failing). Install Tesseract (or set `TESSERACT_CMD`) for scans; text-based PDFs, text and CSV files work now.
* Qualitative results (`Negative`, `Trace`, `Positive`) are not stored, and values written with `<` (for example `<100`) are skipped.
* A single sex-specific range cannot be applied because the sex is not passed to the extractor; the doctor sees the printed text instead.

---

# Real commercial laboratory report (27 Oct 2026)

A real 19-page report (Sterling Accuris style, with its own patient name) was uploaded and **only one test was read, and the value was wrong**
(Hematocrit shown as 40, the lower end of its range, instead of 43.3). After the fixes the same file reads **58 tests with the right values,
the lab's own H/L flags agree with the computed status, and the patient name is detected.**

| Problem | Fix |
|---|---|
| The app's PDF reader (pypdf) prints this layout as `Hemoglobin g/dL 13.0 - 16.5Colorimetric 14.5` (value last), and the first number after the unit was taken as the value | New "value-last" layout: `Test [flag] unit range(s) [method] value`, also when the result is on a line of its own several lines below a block of range tiers |
| A **method column** between the name and the value (`Hemoglobin Colorimetric 14.5 g/dL ...`), flags such as `analysisH 10570` or `MPV Calculated H 14.00` | Method words and flag letters are accepted in the gap |
| Several labelled ranges (`Desirable <200 / Borderline 200-239 / High >240`, HDL `Low <40 / High >60`) | Only a range labelled normal/desirable/optimal/sufficiency/non-diabetes/non-reactive is used. If none says normal (HDL, age groups), **no range is guessed** and the printed text is kept, so HDL 60 is never wrongly flagged |
| Only 15 pages were read, the report has 19 | All pages (up to 60) are read for text; OCR still renders at most 15 |
| Each PDF reader garbles different rows | A text PDF is read two ways (column order and visual order) and the results are merged: a test found by one is added, a value found by the first is never replaced |
| 30 tests of the report were not in the catalog | Added RDW, MPV, ESR, the five differential counts, mean blood glucose, CHOL/HDL and LDL/HDL ratios, globulin, A/G ratio, indirect and delta bilirubin, calcium, sodium, potassium, chloride, iron, TIBC, transferrin saturation, homocysteine, PSA, microalbumin, total IgE, HbA / HbA2 / HbF, and the long printed forms of T3, T4 and TSH |
| A count range `Pus Cells 1-2` was read as the value 1; a sentence ending "year 2023" under a test name was read as 2023 | Both are refused |
| Patient name not found (header printed below the table) | The first 150 lines are searched and the name stops at the next label |

Checked: the 402-value accuracy set is still 402/402 for text and PDF; new tests in `tests/test_extraction_layouts.py` use invented values only.
Not read yet: qualitative results (Reactive / Non reactive, Present (+)), results printed as `< 148`, and nameless absolute-count lines.
**A report uploaded before this fix stays as it was analysed: delete it and upload it again.**

## Report analysis: what matters first, and no unwanted text

Complaint: the analysis listed every out-of-range value as equally important, repeated explanation text, and for ECG / Holter reports quoted page headers and footers and showed 16 identical daily numbers as 16 problems.

**Laboratory reports** (`services/result_priority.py`). Each out-of-range value is ordered by two things visible on the report: how far it is from the printed range, and how important the test usually is (key markers such as glucose, HbA1c, vitamin D count more than MPV or a ratio). Calculated values (VLDL, BUN, ratios) are never listed on their own. The screen shows four tiles (tests read, normal, look at first, slightly outside), the "look at first" cards with how far outside the range, and the rest in one collapsed list. Doctor suggestions and patient tips come only from the categories that matter. It only orders results; it does not diagnose. Lab comment sections are used as findings; educational text such as "Increased in..." is not.

**Narrative reports (ECG, Holter, scans)**. Headers, footers, copyright and signature lines are removed, empty sections are dropped, repeated daily numbers become one card ("N readings, from a to b"), and Holter key numbers are read as labelled values (heart rate, longest gap, pauses, ectopic beats). The summary quotes the report's own findings. Only a ventricular ectopic count or pauses/AF are flagged; supraventricular counts stay neutral.

**Old reports** are rebuilt on display from the stored data (`INSIGHTS_ENGINE = 2`); insights written by an AI model are kept. No re-upload needed for the analysis view.

Tests: `tests/test_result_priority.py` (ranking, derived values excluded, Holter facts, header cleaning, old report upgrade). Invented data only.

## Running the tests

| Command (in `backend`) | What it runs | Time |
|---|---|---|
| `python -m pytest -q -m "not slow"` | everything except the two exhaustive hostile-input sweeps | about 6 minutes |
| `python -m pytest -q` | all tests including the sweeps | about 10 minutes |

Most of the time is the test hospital being built again for each test (about 1.3 s); the application itself answers a login in about 15 ms.
Frontend: `npx vitest run` (about 10 seconds).

## First-login password pop-up
A person who logs in with the starting password sees a pop-up on top of the app (`ChangePasswordDialog`): it cannot be closed by Esc or by clicking outside, shows the three password rules as they are met, and the only other choice is "Log out instead". The server also blocks every other request until the password is changed. The "Change password" page (`/change-password`) is for people who already chose their own password. Both use `ChangePasswordForm`.

## Download the analysis of a report (PDF)
The report page has a **Download analysis (PDF)** button (doctor and patient, once the analysis is visible). It prints an A4 sheet named after the patient, for example `Hari_Lad_Laboratory_Test_Report_Analysis`: summary, doctor's review, the results to look at first, key numbers, all test results and the doctor's points or the patient's tips. It uses only what the screen already received, so a patient never gets anything before the doctor has checked the report. Sheet: `ReportPrintSheet.jsx`.

## Reports that are not lab tables (echo, angiography, scans ...)
`services/report_measures.py` recognises the kind of report from its title and reads its key numbers and graded findings:

| Kind | What is read |
|---|---|
| 2D echo | LVEF (pumping strength), chamber and wall sizes, lung-artery pressure, leaking or narrowed valves with their grade, wall motion, fluid round the heart, diastolic grade |
| Coronary angiography | % narrowing of each artery (LAD, LCx, RCA, left main ...), completely blocked arteries, TIMI flow, dominance, LV ejection fraction; a severe narrowing is raised as a red flag for the doctor |
| Treadmill (stress) test | METs, % of the target heart rate, ST depression, positive / negative result |
| Lung function | FEV1/FVC, FEV1 and FVC as % of predicted |
| Bone density | T-score and Z-score for each site |
| X-ray, CT, MRI, ultrasound | the conclusion first, the size of each nodule, node, stone or cyst, organ sizes, the cardiothoracic ratio |

Numbers are judged only against standard adult reference values shown on the card (or the grade the report itself uses). The summary starts with the report's own conclusion; headers, patient banners and titles are removed. Each kind has its own points for the doctor and tips for the patient.
**Limits:** only the written report is analysed, never the picture itself (the computer does not read an X-ray or CT image). A scanned report or a photo needs OCR (Tesseract), which is not installed on this computer, so such files are refused with a clear message until it is installed. Tests: `tests/test_report_kinds.py` (invented reports in `tests/sample_reports.py`).


---

# Validation and testing pass (4 Nov 2026)

A full pass over input validation, roles and data isolation, end-to-end and concurrent workflows, clinical safety, mobile and accessibility, and security and performance. Every gap below was reproduced with a test that failed first, then fixed with the smallest change.

## Input validation: gaps found and fixed
| Area | Gap | Fix |
|---|---|---|
| Dates a doctor sets ahead (follow-up, due date, expected discharge) | Year 1, year 9999 or dates years ahead were accepted | `PlannedDate`: not before 1900, at most 2 years ahead |
| Timeline entries (emergency) | Could be dated in the future | `RecordedTime`: not in the future (1 hour of grace for clock differences) |
| Recommendation priority | Free text (HTML, 5,000 characters) | Only `NORMAL`, `IMPORTANT`, `FOLLOW_UP_REQUIRED` |
| Blood pressure | Upper below lower accepted on the health-history and past-history forms | One shared `check_blood_pressure` rule on all vitals forms |
| Prescription duration | `-3 days` accepted as free text | A leading minus on a number is refused |
| Stock expiry | Year 1 and year 9999 accepted | Between 2000 and 20 years ahead |
| Filters that use `one_of` (admin role, finance status) | A value that was only markup (`<script>`) cleaned to nothing and was ignored, so the list came back unfiltered | A markup-only value is now refused with 422 |
| Finance invoices | Any word accepted as `status_filter`; unbounded `patient_id` | `DRAFT`/`FINAL`/`CANCELLED` only; bounded `QueryId` |
| One-time code | Arabic-Indic and other non-ASCII digits matched `\d` | `[0-9]{6}` |
| Follow-up form (browser) | A double click added the task twice | Busy guard; the date box stops at 2 years like the server |

Checked and sound: password strength and length, e-mail normalisation, generic login error, lockout (429), names, phone, address, gender, blood group, DOB, appointment times, diagnosis and operation years, admission order, vitals/dose/price/GST/quantity/barcode/discount bounds (NaN, Infinity, negatives, absurd sizes), file checks (renamed executables, a PDF named .png, empty, double extension, path traversal, over-long name, oversize), ids and `limit`, search length, HTML/SQL/null-byte text, malformed JSON, wrong content type, extra fields.
Tests: `test_validation_audit.py`, `test_validation_audit_api.py`, `test_validation_audit_values.py`.

## Roles and isolation
* `security_and_chaos/test_route_drift.py` compares every route with the reviewed list `routes.snapshot.txt` (258 operations). The matrix test rewrites its own output each run, so it could never notice a new route; this one fails and names it.
* The matrix test now also fails when a role the code lets in is told it is not logged in (401), or when a route is unreachable by every role (two are listed with their reason: `PUT /api/health-history/me` refuses everyone by design; `POST /api/lab/tests/{id}/approve` needs a pathologist, covered by the acceptance workflow).
* `test_idor_hms.py`: another patient, the patient using staff actions, and staff outside the workflow try ids of patient 1 in the lab, radiology, IPD, OPD and finance modules. Nothing is reachable. A billing executive may see the stay itself (bed, dates) but never the clinical part.

## Workflows with two actors
`test_concurrency_flows.py` releases its threads together:
* **Bug found and fixed:** two users booking the same doctor and time both succeeded (the check and the insert were not one step). The doctor's row is now locked first (`ensure_free` in `routers/appointments.py`), so one booking wins and the other gets 409.
* **Bug found and fixed:** moving an appointment onto a time the doctor already has was never checked, and neither was bringing a cancelled appointment back onto a taken slot.
* Eight identical submissions create one appointment; the same e-mail registered six times creates one account; two admins editing one person, and two doctors saving one consultation, never crash.

## Clinical safety
(The former `test_sample_report_folder.py` and the generated text sample files were removed: demo and test reports are real-format files, not generated text.)

## Mobile and accessibility
* Patient pages (dashboard, reports, medicines, appointments, bills, timeline, notes, advice, health history, profile, emergency card, assistant) measured at 360 and 412 px (the assistant also at tablet width): no horizontal overflow. Fixed: section links on three dashboards and the emergency card's back link were 20 px tall (now 44 px); the voice settings controls were 37 px / 16 px (now 44 px / 20 px); the assistant page now fits a tablet screen exactly.
* `__tests__/a11y.axe.test.jsx` runs axe-core on the login page (both tabs), the assistant (empty, microphone sheet open, clear-chat question open) and the disclaimer banner: no violations. A control case proves the audit really finds a nameless button and an unlabelled input. Colour contrast needs a real browser and was not machine-checked.

## Security and performance
* `pip-audit` on `requirements.txt`: no known vulnerabilities. `bandit`: three findings, all false positives (the sanitiser's own list of direction-override characters; two SQL strings built from database identifiers and integer ids the code produced).
* `npm audit`: `follow-redirects` (high, via axios) patched to 1.16.2. Left alone because the fix is a major upgrade: `react-router-dom` (moderate, an open-redirect advisory) and the dev-only `vitest`/`vite`/`esbuild`/`tinypool` chain (not shipped).
* Secrets: no key, token or private key in the working tree or in any commit; `.env` and the database are ignored and untracked. The only placeholder (`change-me-in-production`) is refused at start-up on a non-SQLite database.
* Performance on a temporary database of 5,000 patients, 10,000 reports and 51,000 report values: almost every endpoint answers in under 130 ms. Four lists send everything with no paging: patients 2.0 s / 1.5 MB, reports 2.4 s / 1.2 MB, a doctor's patients 0.5 s / 0.5 MB, admin people 0.4 s / 1.5 MB. Added the missing index on `patients.assigned_doctor_id` (also in `schema.sql` and applied to old databases at start-up).

## Not verified
Real phone hardware, a real on-screen keyboard, a real microphone, real SMS, real iOS, OCR quality on poor scans, and colour contrast by tool. There is no PWA yet, so installability and offline behaviour were not tested.

# Appointment rules and clock re-audit (5-6 Nov 2026)

## The appointment-date bug
**Before.** The server compared an appointment with its own clock (`datetime.now()` of the machine) and the page had a plain date-time box with no limits. On a server running in UTC (the Docker default; nothing in the repo set a time zone) a time up to 5 h 30 min in the past was accepted, because the hospital's wall-clock time was compared with the UTC clock. Also accepted: 03:00 at night, 10:07, a time 360 days ahead, two bookings 5 minutes apart, one patient with two doctors at the same time, a future appointment marked COMPLETED, COMPLETED turned into CANCELLED or SCHEDULED, and a completed appointment moved to another day. Yesterday and obvious past times were already refused (422).

**After** (`app/utils/clock.py`, `app/utils/appointment_time.py`, `app/services/appointment_rules.py`, `routers/appointments.py`, `services/trainee_service.py`):
* Every time is the hospital's wall-clock time (`HOSPITAL_TIMEZONE`, default `Asia/Kolkata`). A time with an offset (`Z`, `+05:30`) is converted; a time without one means hospital time. The stored value is the hospital wall-clock time, as it was before, so existing rows stay valid. (The brief asked for UTC storage; that needs a data migration and a change of every reader, so it is listed as a decision.)
* Past times are refused, today's earlier times too, with a grace of `APPOINTMENT_GRACE_MINUTES` (5) for walk-ins; at most `APPOINTMENT_MAX_ADVANCE_DAYS` (30) ahead; only 15-minute slots (`APPOINTMENT_SLOT_MINUTES`) between 09:00 and 17:00 (`APPOINTMENT_DAY_START`, `APPOINTMENT_DAY_END`); the last slot ends at closing time.
* One open appointment per doctor and slot is a database rule (partial unique index `uq_appointment_doctor_slot_open`, also added to old databases at start-up) and a locked check; a patient cannot hold two open appointments at the same time with different doctors (409).
* Status moves forward only: SCHEDULED to CONFIRMED to COMPLETED, or CANCELLED while open (409 otherwise); a future appointment cannot be completed (422); a completed or cancelled appointment cannot be moved (409). Patients may only cancel their own; doctors change the status of their own; reception and admin do both.
* `GET /api/appointments/slots?doctor_id=&day=` lists the day's slots as free, taken or unavailable.
* Pages: the booking form's date box runs from today (hospital date) to 30 days ahead, the times are a grid with taken and passed slots disabled, the server's message appears under the Time field, what was typed is kept, and a double click sends one request. The trainee referral time box has the same limits. "Mark done" appears only on a confirmed appointment.
* Tests (clock frozen, nothing depends on today): `test_appointment_rules.py` (28), `test_hospital_clock.py` (7), `Appointments.test.jsx` (4), `validators.test.js`. Against the old code 22 of the 28 and 6 of the 7 fail. `test_validation.py::test_appointment_time_rules` was rewritten for the new rules (30 days, slots); `future()` in `tests/conftest.py` now returns a real slot.

## Same root cause everywhere
About 75 places used the server's `date.today()` / `datetime.now()`: date of birth, "not in the future" checks, expired stock, dashboards, queue tokens, follow-ups, medication and nursing schedules. They now use `hospital_today()` / `hospital_now()`. Effect on a UTC server: for the first 5 h 30 min of every Indian day a baby born that morning was refused, and stock that expires today was treated as expired.

## Other findings
* Date of birth: the floor was 1930, which refused real patients born 1900-1929; it is now 1900 with the 120-year age limit (backend and page).
* `bandit` HIGH (trojan source): the sanitiser's regex held invisible direction-override characters literally; written as `\u` escapes now (same set), backend and page. The other `bandit` findings (3 medium, 5 low) are false positives: SQL built from the code's own identifiers and integers, and the configurable starting password.
* `pip-audit`: nothing. `npm audit`: two moderate `react-router` advisories (the fix is a major upgrade; not applied). No secrets in the tree or the history.

## Paging of the long lists
The four lists that grew with the hospital are paged: patients (`GET /api/patients`), reports (`GET /api/reports`), a doctor's patients (`GET /api/doctor/patients`) and admin people (`GET /api/admin/people`). The answer is still a plain list, so older clients keep working; `limit` (1-500, default 100) and `offset` choose the slice and the size of the whole list is in the `X-Total-Count` header (exposed to the phone app by CORS). Reports also take `needs_review` and `q`, so the doctor's "Reports to review" page and the filter box are applied before paging and a waiting report is never hidden behind the first page. Screens show "Showing 100 of N" with a "Show more" button. Bad values are a 422.
Measured on 5,000 patients, 10,000 reports and 51,000 values: patients 2.0 s and 1.5 MB became 0.18 s and 30 KB; reports 2.4 s and 1.2 MB became 0.27 s and 48 KB; a doctor's patients 0.5 s became 0.22 s; admin people 0.4 s became 0.24 s. Tests: `tests/test_pagination.py` (backend), `hooks/usePagedFetch.test.jsx` (page). Pickers that search as you type (`PatientPicker`, the registry panel) still take the first 100 matches, which is what a search box needs.

## File actions on phones (open, download, print, share)
**What was broken.** "View the original report" fetched the file and then called `window.open(blob)` after an `await`: on a phone, in an installed PWA and in a WebView a window may open only inside the tap, so the call returned `null`, no tab opened, and the error was ignored (reproduced: `navigator.userActivation.isActive` was false and `window.open` returned `null`). "Download PDF" was `window.print()` on a hidden sheet: no PDF is made, a print dialog appears (or nothing, in a WebView), and there was no feedback. Bill and receipt printing used `window.open(..., "noopener,...")`, which by specification never returns a window, so it never printed; the radiology file link had the same bug as the report. **Not the cause:** the backend (200, `application/pdf`, `no-store`, 403/401/404 as designed), authentication, the manifest scope, the service worker (none is registered unless a user turns push on, and it has no fetch handler).
**The fix, once, in a shared layer** (`utils/fileActions.js`, `hooks/useFileAction.js`, `components/FileViewer.jsx`, `components/PdfPages.jsx`, `context/FileViewerContext.jsx`):
* The file is fetched with the signed-in client as a Blob. A short-lived signed URL was considered and rejected: the header already authenticates, and a blob puts nothing in a URL (the long-lived token is never in one).
* The in-app viewer opens on the tap itself (no popup), shows loading with progress, then the file: the browser's own PDF viewer where `navigator.pdfViewerEnabled`, otherwise PDF.js (lazy-loaded, pinned `pdfjs-dist@4.10.38` legacy build, with page and zoom controls and a redraw when the screen turns); images in a zoom view; text; anything else says so. Download, Share, Print and Close are in the viewer; errors show one sentence (the server's own for 403/404) and Try again only where a retry can help.
* Saving is chosen by capability, never by browser name: a touch device that can share files gets the share sheet; if the browser refuses because the tap is over, the viewer opens with its own buttons (a fresh tap); a computer downloads with `<a download>` (the object URL is released after a minute, never at once). Printing uses a hidden frame (never a popup), and says so plainly where there is no print dialog.
* The summary is a real A4 PDF made on the server (`GET /api/reports/{id}/summary.pdf?mode=short|full`, `reportlab`, streamed, never stored) from the same report detail as the screen, so it shows exactly what that user may see (a patient only after the doctor's review); audited as `REPORT_SUMMARY_DOWNLOADED`.
* File responses now carry the right content type, `nosniff`, `no-store` and an encoded filename; CORS exposes `Content-Disposition`, `Content-Length`, `X-Total-Count` and `X-Unread-Count` (the phone app is a different origin).
* **Native app later:** `npm i @capacitor/filesystem @capacitor/share @capacitor-community/file-opener`, then call `setNativeFileAdapter({ save, share, open })` once at start-up (save = write to the Documents folder and tell the person where it went; share = `Share.share({ files: [uri] })`; open = `FileOpener.open(...)`). No screen changes: the viewer, the menu and the buttons already call the adapter first.
**Found on the way (test infrastructure):** the access matrix and the route guard read a hard-coded router list that left out ten routers (finance, stock, theatre, blood bank, claims, integrations, countersign, radiology, diagnostics, procurement: 129 routes). They now read the application's own routers (409 routes), the matrix has a radiology actor, and it passes for every role.
Tests: `tests/test_file_actions.py` (headers and encoding, owner, other patient, no token, admin, missing file, large and empty files, PDF text, access rules, audit, nothing written to disk), `utils/fileActions.test.js`, `__tests__/fileViewer.test.jsx`, `components/PdfPages.test.jsx`, `utils/printDocument.test.js`.

## Existing data
In a copy of the development database: 19 appointments, 5 CONFIRMED in the past, no duplicate slots. Proposed, not applied: mark past SCHEDULED/CONFIRMED appointments CANCELLED or a new MISSED status.

## Not verified here
A clean-HEAD baseline of the whole backend suite did not finish (the machine was saturated by the emulator; the part that ran, about 28 %, had no failures). The final full run was done in six parallel shards: 1,203 passed, 24 expected failures, 2 failed (both were tests that checked the old rules and are fixed above). Doctor off-days and hospital holidays: no such data exists, so they are not enforced. Real devices, SMS, microphone and OCR quality are as in the earlier section.
