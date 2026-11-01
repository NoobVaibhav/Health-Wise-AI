"""Roles and permissions of the hospital system.

Every user keeps the one role they log in with (users.role: ADMIN, DOCTOR, EMPLOYEE, ...). That role is mapped to a default hospital role here, and the administrator
can give a person more roles (for example an employee who is also the billing executive). A permission is a plain name such as "patient.merge". The old
`require_roles(...)` checks still protect the older endpoints; the new endpoints use `require_permission(...)`."""
from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import ADMIN, DOCTOR, EMPLOYEE, LAB, NURSE, PATIENT, PHARMACY, RADIOLOGY, forbidden, get_current_user
from app.database.connection import get_db
from app.database.models import Permission, Role, RolePermission, User, UserRole

# Phase 2 permissions. Later phases add theirs here (a code change, then the start-up seeding adds them).
PERMISSIONS: dict[str, str] = {
    "hospital.view": "See the hospital profile, branches and settings",
    "hospital.manage": "Change the hospital profile and settings",
    "branch.manage": "Add and change branches",
    "service.view": "See the price list",
    "service.manage": "Change the price list",
    "role.manage": "Give roles to people and change what a role may do",
    "patient.register": "Register patients",
    "patient.search": "Search patients by name, phone or UHID",
    "patient.merge": "Merge two records of the same patient",
    "consent.manage": "Record and withdraw patient consents",
    "insurance.manage": "Record patient insurance",
    "abha.manage": "Record a patient's ABHA number (needs consent)",
    "breakglass.use": "Open a patient's record in an emergency with a written reason",
    "breakglass.review": "Review emergency (break-glass) access",
    "audit.view": "Read the audit log",
    # Phase 3: clinical workflows
    "opd.checkin": "Check in appointments and walk-in patients and give tokens",
    "opd.queue": "See the OPD queue",
    "consult.write": "Write and sign consultations",
    "orders.write": "Order tests, scans, procedures, diets and nursing tasks",
    "vitals.record": "Record vital signs",
    "nursing.chart": "Write nursing notes, give medicines (MAR), record intake and output, handover",
    "alert.ack": "Acknowledge clinical alerts",
    "ed.register": "Register an emergency patient (also an unknown one)",
    "ed.triage": "Triage emergency patients",
    "ed.treat": "Assess, treat and decide the outcome of emergency patients",
    "ipd.admit": "Admit a patient and assign doctors",
    "ipd.bed": "Assign, transfer and release beds; see the bed board",
    "ipd.notes": "Write progress notes and medication orders for inpatients",
    "discharge.write": "Prepare a discharge summary",
    "discharge.approve": "Approve a discharge summary and discharge the patient",
    "referral.request": "Refer a patient to another department",
    "referral.respond": "Accept or decline a referral and write the consult note",
    "ward.manage": "Add wards and beds",
    "template.manage": "Change consultation templates",
    "escalation.manage": "Change the alert thresholds",
    # Phase 5: pharmacy stock, procurement, operation theatre, blood bank
    "stock.view": "See medicine stock history, alerts and the ward medicine requests",
    "stock.manage": "Add suppliers, recall and write off batches, count stock, issue medicines to wards",
    "inventory.manage": "Manage the hospital store (consumables, equipment, supplies)",
    "procure.request": "Raise a requisition for items or medicines",
    "procure.order": "Make purchase orders and receive goods",
    "procure.approve": "Approve requisitions and purchase orders",
    "ot.view": "See the operation theatre schedule",
    "ot.schedule": "Book surgeries in the operation theatre",
    "ot.record": "Fill the theatre records: pre-op, consent, checklist, notes, consumables",
    "bloodbank.manage": "Run the blood bank: donors, units, cross-match, issue",
    "bloodbank.request": "Ask the blood bank for blood for a patient",
    "transfusion.give": "Give a transfusion and record it",
}
ALL = list(PERMISSIONS)
DOCTOR_PERMISSIONS = ["hospital.view", "service.view", "breakglass.use", "opd.queue", "consult.write", "orders.write", "vitals.record", "alert.ack", "ed.register", "ed.triage", "ed.treat",
                      "ipd.admit", "ipd.bed", "ipd.notes", "discharge.write", "discharge.approve", "referral.request", "referral.respond"]

# code -> (name, description, permissions)
ROLES: dict[str, tuple[str, str, list[str]]] = {
    "SUPER_ADMIN": ("Super Admin", "The first administrator: everything, including roles", ALL),
    "HOSPITAL_ADMIN": ("Hospital Admin", "Runs the hospital system", ALL),
    "BRANCH_ADMIN": ("Branch Admin", "Runs one branch", ["ipd.bed", "opd.queue", "hospital.view", "service.view", "patient.register", "patient.search", "consent.manage", "insurance.manage", "abha.manage", "audit.view"]),
    "RECEPTIONIST": ("Receptionist", "Registers patients and books appointments", ["opd.checkin", "opd.queue", "ed.register", "ipd.bed", "hospital.view", "service.view", "patient.register", "patient.search", "consent.manage", "insurance.manage", "abha.manage"]),
    "DOCTOR": ("Doctor", "Treats patients; interns and residents are doctors of a lower grade (see docs/DOCTOR_GRADES.md)", DOCTOR_PERMISSIONS),
    "SPECIALIST_DOCTOR": ("Specialist Doctor", "A doctor with a specialization", DOCTOR_PERMISSIONS),
    "NURSE": ("Nurse", "Nursing care", ["hospital.view", "service.view", "breakglass.use", "opd.queue", "ed.register", "ed.triage", "vitals.record", "nursing.chart", "alert.ack", "ipd.bed"]),
    "LAB_TECHNICIAN": ("Lab Technician", "Laboratory work", ["hospital.view"]),
    "PATHOLOGIST": ("Pathologist", "Approves laboratory results", ["hospital.view"]),
    "RADIOLOGY_TECHNICIAN": ("Radiology Technician", "Takes the scans", ["hospital.view"]),
    "RADIOLOGIST": ("Radiologist", "Reports the scans", ["hospital.view"]),
    "PHARMACIST": ("Pharmacist", "Pharmacy", ["hospital.view", "service.view"]),
    "PHARMACY_ASSISTANT": ("Pharmacy Assistant", "Pharmacy counter", ["hospital.view"]),
    "BILLING_EXECUTIVE": ("Billing Executive", "Bills and payments", ["hospital.view", "service.view", "patient.search"]),
    "ACCOUNTANT": ("Accountant", "Accounts and reports", ["hospital.view", "service.view"]),
    "INSURANCE_EXECUTIVE": ("Insurance/TPA Executive", "Insurance and claims", ["hospital.view", "patient.search", "insurance.manage"]),
    "OT_STAFF": ("OT Staff", "Operation theatre", ["hospital.view"]),
    "ICU_STAFF": ("ICU Staff", "Intensive care", ["hospital.view", "breakglass.use", "vitals.record", "nursing.chart", "alert.ack", "ipd.bed"]),
    "WARD_STAFF": ("Ward Staff", "Wards", ["hospital.view", "vitals.record", "nursing.chart", "alert.ack", "ipd.bed"]),
    "BLOOD_BANK_STAFF": ("Blood Bank Staff", "Blood bank", ["hospital.view"]),
    "INVENTORY_MANAGER": ("Inventory Manager", "Stores and purchases", ["hospital.view", "service.view"]),
    "HR_MANAGER": ("HR Manager", "Staff, rosters, attendance", ["hospital.view"]),
    "PATIENT": ("Patient", "A patient sees only their own data", []),
    "AUDITOR": ("Hospital Auditor", "Reads audit trails and reviews emergency access", ["hospital.view", "audit.view", "breakglass.review"]),
}

_EXTRA = {
    "PHARMACIST": ["stock.view", "stock.manage", "procure.request", "procure.order"],
    "PHARMACY_ASSISTANT": ["stock.view"],
    "INVENTORY_MANAGER": ["stock.view", "stock.manage", "inventory.manage", "procure.request", "procure.order", "procure.approve"],
    "DOCTOR": ["ot.view", "ot.schedule", "bloodbank.request"],
    "SPECIALIST_DOCTOR": ["ot.view", "ot.schedule", "bloodbank.request"],
    "NURSE": ["ot.view", "procure.request", "transfusion.give"],
    "ICU_STAFF": ["transfusion.give", "procure.request"],
    "WARD_STAFF": ["transfusion.give", "procure.request"],
    "OT_STAFF": ["ot.view", "ot.schedule", "ot.record", "procure.request", "stock.view"],
    "BLOOD_BANK_STAFF": ["bloodbank.manage", "procure.request"],
    "AUDITOR": ["stock.view"],
}
for _code, _perms in _EXTRA.items():
    _name, _description, _have = ROLES[_code]
    ROLES[_code] = (_name, _description, _have + [p for p in _perms if p not in _have])

# the login role -> the hospital role it means
BASE_ROLE = {ADMIN: "HOSPITAL_ADMIN", DOCTOR: "DOCTOR", EMPLOYEE: "RECEPTIONIST", PATIENT: "PATIENT", PHARMACY: "PHARMACIST", LAB: "LAB_TECHNICIAN", NURSE: "NURSE", RADIOLOGY: "RADIOLOGY_TECHNICIAN"}


def seed_access(db: Session) -> None:
    """Start-up, safe to repeat: adds the permissions and roles that are missing and, for a role created now, its default permissions.
    A role that exists is never changed (the administrator may have edited it)."""
    have = {p.code: p for p in db.scalars(select(Permission))}
    created = []
    for code, description in PERMISSIONS.items():
        if code not in have:
            have[code] = Permission(code=code, description=description)
            db.add(have[code])
            created.append(code)
    db.flush()
    roles = {r.code: r for r in db.scalars(select(Role))}
    for code in created:                  # a permission added by a newer version goes (once) to the roles that are meant to have it, also roles that already exist
        for role_code, (_, _, permissions) in ROLES.items():
            if code in permissions and role_code in roles:
                db.add(RolePermission(role_id=roles[role_code].id, permission_id=have[code].id))
    for code, (name, description, permissions) in ROLES.items():
        if code in roles:
            continue
        role = Role(code=code, name=name, description=description, is_system=True)
        db.add(role)
        db.flush()
        for permission in permissions:
            db.add(RolePermission(role_id=role.id, permission_id=have[permission].id))
    # the permissions added by a later version go to the roles that are meant to have them, once
    db.commit()


def first_admin_id(db: Session) -> int | None:
    return db.scalar(select(User.id).where(User.role == ADMIN).order_by(User.id).limit(1))


def role_codes(db: Session, user: User) -> list[str]:
    codes = [BASE_ROLE[user.role]] if user.role in BASE_ROLE else []
    if user.role == ADMIN and first_admin_id(db) == user.id:
        codes.append("SUPER_ADMIN")
    codes += list(db.scalars(select(Role.code).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user.id)))
    return list(dict.fromkeys(codes))


def permissions_of(db: Session, user: User) -> set[str]:
    codes = role_codes(db, user)
    if not codes:
        return set()
    rows = db.scalars(select(Permission.code).join(RolePermission, RolePermission.permission_id == Permission.id)
                      .join(Role, Role.id == RolePermission.role_id).where(Role.code.in_(codes)))
    return set(rows)


def require_permission(*needed: str):
    """Dependency: the user needs at least one of the permissions (the same idea as require_roles, but by what a person may do)."""
    def checker(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        if not permissions_of(db, user) & set(needed):
            raise forbidden()
        return user
    return checker


def role_out(db: Session, role: Role) -> dict:
    perms = list(db.scalars(select(Permission.code).join(RolePermission, RolePermission.permission_id == Permission.id).where(RolePermission.role_id == role.id).order_by(Permission.code)))
    return {"id": role.id, "code": role.code, "name": role.name, "description": role.description, "permissions": perms}


def set_role_permissions(db: Session, role: Role, codes: list[str]) -> None:
    unknown = [c for c in codes if c not in PERMISSIONS]
    if unknown:
        raise HTTPException(422, f"Unknown permission: {unknown[0]}.")
    if role.code in ("SUPER_ADMIN", "HOSPITAL_ADMIN") and "role.manage" not in codes:
        raise HTTPException(422, "The administrator roles must keep the permission to manage roles, or nobody could change roles any more.")
    perms = {p.code: p for p in db.scalars(select(Permission))}
    for rp in db.scalars(select(RolePermission).where(RolePermission.role_id == role.id)):
        db.delete(rp)
    db.flush()
    for code in dict.fromkeys(codes):
        db.add(RolePermission(role_id=role.id, permission_id=perms[code].id))
    db.commit()
