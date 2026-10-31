# Input validation rules

One set of rules, written once and used everywhere.

* **Backend (the real check):** `backend/app/utils/validators.py` holds the reusable types (`Email`, `PersonName`, `Phone`, `DateOfBirth`, `Password`, `Money`, `PositiveId` ...). Every request schema in `backend/app/schemas/` uses them, and the routers use `PathId`, `QueryId`, `SearchText`, `Limit` and `one_of(...)` for ids, search, limits and filters.
* **Frontend (instant feedback only):** `frontend/src/utils/validators.js` repeats the same rules. Each function returns an error sentence or `""`. The hook `useValidation` and the component `FormField` show the message under the field.
* **Answer of the server:** invalid input is a **422** (never a 500) with `{"detail": "<one readable sentence>", "errors": [{"field", "label", "message"}]}`. `getErrorMessage` shows `detail`; `getFieldErrors` puts each message under its field.
* All text is **trimmed**, **HTML tags and control characters are removed**, repeated spaces inside names are collapsed, and a text of only spaces counts as empty.

## Accounts and passwords

| Field | Rule | Message (shortened) | Enforced in |
|---|---|---|---|
| E-mail | required, trimmed, lower-cased, valid form, no spaces, at most 254 characters | "Please enter a valid e-mail address, for example name@example.com." | `Email` (all account schemas, login); `email()` |
| Login password | not empty, at most 128 characters (the strength rules apply when a password is chosen) | "Please enter your password." | `LoginRequest`; login form |
| Login answer | one message for a wrong e-mail and a wrong password | "Incorrect email or password." | `routers/auth.py` |
| Lockout | 5 failed logins per e-mail **and** address in 15 minutes (30 per e-mail overall, 30 per address) | "Too many failed attempts. Please try again in N minutes." (429, `Retry-After`) | `minutes_until_unlocked` in `routers/auth.py` |
| New password | 8 to 128 characters, a letter and a number, not a common password (about 50 listed), not containing the e-mail's name part (4+ letters) | "The password must have at least 8 characters." ... "This password is too common." ... "The password must not contain your e-mail name." | `Password`, `check_password`, `password_has_email_name`; password forms |
| Change password | the new one differs from the current one; the confirmation matches | "The new password must be different from the current one." / "The two passwords are not the same." | `ChangePasswordRequest`; `ChangePasswordForm` |
| Password storage | the whole password counts (SHA-256, then bcrypt); older records still work and are re-saved at the next login | | `core/security.py` |
| Strength hint, show/hide | weak / okay / strong; eye button | | `PasswordInput` |

## Names, contact details, dates

| Field | Rule | Enforced in |
|---|---|---|
| Full name | 2 to 150 characters; letters (any language), spaces, apostrophes, hyphens and dots only; no digits, emoji, tags or control characters; inner spaces collapsed | `PersonName`; `personName()` |
| Phone | digits with spaces, dashes, brackets; `+91 98765 43210`, `098765-43210` become `9876543210`; a 10-digit Indian mobile starts with 6 to 9; any other country needs `+`, code and 8 to 15 digits in all (stored `+...`) | `Phone`, `OptionalPhone`; `phone()`, `normalisePhone()` |
| Emergency contact | at most 150 characters; must not hold the patient's own number (checked also when only one of them changes) | `PatientFields`, `routers/patients.py`, profile service; `emergencyContact()` |
| Address | at most 300 characters, HTML removed (character counter on screen) | `Address`; `address()` |
| Pincode (when present) | 6 digits | `Pincode` |
| Gender | `male`, `female` or `other` (any case; stored lower case) | `Gender`; `gender()` |
| Blood group | A+, A-, B+, B-, AB+, AB-, O+, O- | `BloodGroup`; `bloodGroup()` |
| Date of birth | a real calendar date, not in the future, not before 1930-01-01, age at most 120; the date box has `min` and `max`; **a warning only** (not an error) under 1 year or over 110 | `DateOfBirth`; `dateOfBirth()`, `ageWarning()` |
| Appointment time | not in the past (5 minutes of grace), not more than 1 year ahead; a time with a time zone is converted first; no double booking of a doctor at the same time (409, existing check) | `check_appointment_time`; `routers/appointments.py` |
| Appointment status | `SCHEDULED`, `CONFIRMED`, `COMPLETED`, `CANCELLED` | `AppointmentUpdate` |
| Dates of entries (history entry date) | not in the future | `PastOrTodayRequired` |

## Clinical values

| Field | Rule | Enforced in |
|---|---|---|
| Vital signs | height 30 to 260 cm; weight 1 to 500 kg; pulse 20 to 250; upper blood pressure 50 to 300; lower 30 to 200; oxygen 50 to 100 %; temperature 30 to 45 °C (86 to 113 °F); breathing rate 4 to 80; no NaN or Infinity | one table in `validators.py`, used by the health-history, past-history and emergency schemas; `vital()` |
| Lab value | a number, not negative, at most 1,000,000,000, never NaN or Infinity; unit from the known list | `check_lab_value`, `check_lab_unit` (and the report reader) |
| Prescription item | medicine name 2 to 200 characters; dose and frequency not zero or negative; duration 1 to 365 days (also `2 weeks`, `1 month`, or words such as `as needed`); quantity a positive whole number; the same medicine twice is a **warning** in the answer (`warnings`), not an error | `PrescriptionItemCreate`, `routers/prescriptions.py` |
| Free text (allergies, history, notes, advice ...) | maximum lengths per field (counter shown where the form has one); HTML and control characters removed | `text()`, `opt_text()` |

## Pharmacy and billing

| Field | Rule | Enforced in |
|---|---|---|
| Price, GST, discount, quantity | not negative, at most 10,000,000; money rounded to 2 decimals (half up); GST 0 to 100; quantity a positive whole number; the discount is an amount in rupees (see "not done") | `Money`, `OptionalMoney`, `Percent`, `Quantity`; `nonNegativeNumber()`, `percent()` |
| Barcode | 4 to 64 letters, digits or hyphens | `Barcode`; `barcode()` |
| Manufacturing and expiry date | the manufacturing date is not in the future; the expiry is after it; expired stock cannot be sold (existing check); new column `manufacture_date` | `InventoryCreate`, `ReceiveStock`, `check_stock_dates` |
| Stock | cannot go below zero (existing checks in the sale and dispense services) | `billing_service`, `dispensing_service` |
| Customer on a bill | optional name (same rule as names) and phone (same rule as phones) | `SaleCreate`, `PrescriptionBillRequest` |

## Files

| Rule | Enforced in |
|---|---|
| Reports: PDF, PNG, JPG (a plain-text or CSV export is also accepted), up to 10 MB, not empty; the type comes from the **content** (magic bytes), and the name must fit the content (a JPG named .png is refused) | `utils/file_validation.py`; `UploadBox` (tells the allowed types and size before choosing) |
| Profile photo: JPG or PNG, up to 2 MB, really opened as an image | `profile_service.set_avatar`; `Profile.jsx` |
| File names shown to people: no folder part, no control characters, markup or `<>:"|?*`, at most 150 characters; the file is stored under a random name | `safe_filename` |
| A request body above 1 MB (12 MB for an upload form) is refused with 413 from its announced size, before it is read | `limit_body_size` in `main.py` |

## Ids, search, limits, filters

| Parameter | Rule | Enforced in |
|---|---|---|
| Id in the URL | a positive whole number below 2,000,000,000, else 422 | `PathId` |
| Id in the query or body | positive whole number | `QueryId`, `PositiveId` |
| `q` (search) | trimmed, at most 100 characters | `SearchText` |
| `limit` | 1 to 200 | `Limit` (audit log) |
| `status_filter`, `role` | one of the allowed words (any case), else 422 | `one_of(...)` |
| Bodies that cannot be read, or are nested too deeply | 422 or 400, never 500 | handlers in `main.py` |

## Behaviour of the forms

* Checked **when the person leaves a field** and **when sending**, not at every key (except the password strength hint and the character counters).
* The message is red, under the field, linked with `aria-describedby`; the field has `aria-invalid`; sending moves the cursor to the first wrong field.
* Typed values are **never cleared** by a validation error (also not by an error from the server).
* The send button is disabled while the request runs, so a double click sends once.
* Input attributes: `type="email"` with `autocomplete="email"`, `type="tel"` with `inputmode="tel"`, `type="date"` with `min` and `max`, `autocomplete="new-password"` on set-password fields, `maxLength` on every text field.
* Forms with the full set: Login, first-administrator Register, Change password, Register patient, Add staff, My profile, report upload. The other forms (health history, prescriptions, pharmacy, lab) have the **server rules** and `maxLength`, and show the server's message.

## Tests

`backend/tests/test_validation.py` (good and bad cases for every rule), `backend/tests/test_fuzz_no_500.py` (hostile values on every endpoint: never a 500), `frontend/src/utils/validators.test.js`, and the form tests `pages/auth/forms.validation.test.jsx` and `pages/employee/RegisterPatient.validation.test.jsx`.
