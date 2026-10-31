# Departments and specializations

A doctor has a **department** and, inside it, a **specialization**, both chosen from lists (no free text any more).

## Data
* `departments` (id, name, `is_active`) and `specializations` (id, name, `name_key` = lower-cased name, `department_id`, `is_active`). A name is unique inside its department, ignoring case; a department name is unique ignoring case.
* `doctors.specialization_id` is new (nullable). `doctors.specialization` (the old text) stays for old rows.
* Nothing is hard-deleted. A department or specialization that is no longer used is switched off (`is_active = false`): it disappears from the dropdowns, and the doctors who have it keep it.

## Start-up migration (`init_db`, safe to run every time)
1. `create_all` makes the `specializations` table; `add_missing_columns` adds `departments.is_active`, `specializations.is_active` and `doctors.specialization_id` only when missing. No data is lost.
2. `catalog_service.ensure_catalog`: rows without `is_active` become active; **only if there are no specializations at all** the default list is added (existing departments are reused, none is duplicated).
3. Old doctors: the old text is matched with a specialization **by name, ignoring case** (inside the doctor's department when it has one). One match: the doctor gets `specialization_id` (and the department, when it had none). No match: the old text is kept and shown as an old entry ("Other (legacy)"); the admin can choose a real one in **Doctors → Edit**.

## API
| Endpoint | Who | Notes |
|---|---|---|
| `GET /api/catalog/departments` | every signed-in role | active ones: `id`, `name`. The admin may add `?include_inactive=true` (adds `is_active`, `doctor_count`) |
| `GET /api/catalog/specializations?department_id=` | every signed-in role | same |
| `POST /api/catalog/departments`, `PUT/PATCH /api/catalog/departments/{id}` | admin | add, rename, switch on/off |
| `POST /api/catalog/specializations`, `PUT/PATCH /api/catalog/specializations/{id}` | admin | add (with `department_id`), rename, switch on/off |
| `POST /api/admin/doctors` | admin | `department_id`, `specialization_id` (old `specialization` text is still accepted when no id is sent) |
| `PUT /api/admin/users/{id}` | admin | for a doctor also `department_id`, `specialization_id` |

Names: 2 to 100 characters, trimmed, HTML removed, no duplicate (409). A bad id is a **422 with a sentence**, never a 500: "The selected department does not exist.", "The selected department is no longer in use.", "Please choose a department before choosing a specialization.", "The selected specialization does not belong to the selected department.". A doctor may keep a department or specialization that was switched off after the choice was made.

Responses with doctors (`/api/doctors`, `/api/admin/people`, the profile, the prescription sheet) carry `department_name` and `specialization_name` (the old text when there is no id).

## Screens
* `DepartmentSpecializationSelect` (two `<select>` boxes: keyboard and phone friendly): department list loaded once and cached; specializations reloaded for each department; cleared when the department changes; disabled until a department is chosen; "No specializations for this department yet"; error and **Try again** button without losing the choice.
* Admin: **Doctors → Add doctor** (department required) and **Edit** on a doctor card; **Settings** manages the lists (add, rename, switch on/off).
* `DoctorSelect` (new appointment, register patient): a department filter above the doctor list.
* The doctor's own profile shows both read-only, as before (the hospital assigns them).

Tests: `backend/tests/test_catalog_specializations.py`, `frontend/src/components/DepartmentSpecializationSelect.test.jsx`, `EditDoctorDialog.test.jsx`, `pages/admin/StaffManager.test.jsx`. `backend/schema.sql` was regenerated from the models (it also had tables missing before).
