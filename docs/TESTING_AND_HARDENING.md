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
