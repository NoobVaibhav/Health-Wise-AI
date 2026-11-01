# Doctor grades

Interns, PG residents, senior residents and consultants are one role (**Doctor**) with a **grade**. The separate Trainee role is retired.

| Grade | Prescribe | Diagnosis | Sign consultation | Orders | Discharge summary / discharge |
|---|---|---|---|---|---|
| Intern | Never (403, even with the admin flag) | Draft only | No | Draft + countersign request | Cannot prepare; admits only under a consultant |
| PG resident / Senior resident | Waits for countersign (`PENDING_COUNTERSIGN`), unless the admin set `can_prescribe_independently` | Provisional; final only by a consultant | Yes | Placed | Can write; creates a countersign request; only the treating consultant approves |
| Consultant (and old rows with no grade) | Yes | Final | Yes | Placed | Approves and discharges |

A prescription waiting for countersign is hidden from the patient, the pharmacy and the lab sync, and cannot be dispensed or billed.

## Data
- `doctors.grade`, `pg_year`, `pg_branch`, `supervisor_id` (consultant of the same department), `can_prescribe_independently` (admin only, default false).
- `countersign_requests` (kind PRESCRIPTION / ORDER / DISCHARGE_SUMMARY; status PENDING / APPROVED / EDITED / RETURNED; the junior doctor's original version is kept when a consultant edits).
- API: `/api/countersign/awaiting`, `/mine`, `/{id}`, `/{id}/approve` (optional edited items), `/{id}/return` (comment required).

## Migration (idempotent, runs at start-up)
1. Doctors with no grade become CONSULTANT.
2. Old trainee accounts become Doctor rows (intern or PG resident), their user role becomes DOCTOR, and their histories and referrals are repointed. The old `trainees` table is left untouched.

## Assumptions
- Juniors need a supervising consultant of their department.
- Juniors reach patients through a visit, assignment or consulting staff, as other doctors do; a consultant also sees the patients of juniors they supervise.
- `can_prescribe_independently` has no effect on interns.
- Complaint-to-department suggestion rules are unchanged.
- This is decision support: a clinician must review everything.
