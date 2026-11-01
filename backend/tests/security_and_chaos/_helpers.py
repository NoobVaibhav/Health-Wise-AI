"""Shared helpers for the security and chaos tests. `bust(ID)` marks a test that proves a confirmed finding of docs/BUST_REPORT.md: it asserts the
SECURE behaviour, so it fails while the bug exists (expected failure) and the strict mark turns it into a loud failure the day the bug is fixed
(remove the mark then). Synthetic data only."""
import re

import pytest
from fastapi.routing import APIRoute

from app.core.permissions import get_current_user
from app.main import app
from tests.conftest import PASSWORD, login


def bust(finding_id: str):
    return pytest.mark.xfail(strict=True, reason=f"{finding_id}: confirmed finding, see docs/BUST_REPORT.md")


def intended_roles(route: APIRoute):
    """(public, roles): roles is None when any logged-in role may call it, else the set named by require_roles(...)."""
    state = {"public": True, "roles": None}

    def walk(dep):
        call = dep.call
        if call is get_current_user:
            state["public"] = False
        if getattr(call, "__qualname__", "").startswith("require_roles.<locals>.checker"):
            state["public"] = False
            for cell in call.__closure__ or []:
                if isinstance(cell.cell_contents, tuple):
                    state["roles"] = set(cell.cell_contents)
        if getattr(call, "__qualname__", "").startswith("require_permission.<locals>.checker"):
            # an endpoint guarded by permissions: the login roles whose default hospital role holds one of them are the intended callers
            from app.services.access_service import BASE_ROLE, ROLES
            state["public"] = False
            for cell in call.__closure__ or []:
                if isinstance(cell.cell_contents, tuple):
                    needed = set(cell.cell_contents)
                    state["roles"] = (state["roles"] or set()) | {login for login, base in BASE_ROLE.items() if needed & set(ROLES[base][2])}
        for sub in dep.dependencies:
            walk(sub)

    walk(route.dependant)
    return state["public"], state["roles"]


def operations():
    """Every (route, method) of the application: the routers are read directly because newer FastAPI wraps included routers."""
    from app.routers import (admin, appointments, auth, billing, catalog, clinical_intel, dashboard, doctors, employees, health_history, lab, patient_assistant, patient_portal,
                             patients, pharmacy, prescriptions, profile, reports, trainee, referrals, hospital, access, patient_registry, opd, nursing, emergency, ipd, referral_requests)
    from app.main import health_check
    routers = [m.router for m in (auth, admin, patients, doctors, employees, reports, appointments, prescriptions, pharmacy, patient_portal, dashboard, catalog, lab,
                                  billing, profile, health_history, clinical_intel, patient_assistant, trainee, referrals, hospital, access, patient_registry, opd, nursing, emergency, ipd, referral_requests)] + [doctors.directory]
    for router in routers:
        for route in router.routes:
            if isinstance(route, APIRoute):
                for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
                    yield route, method
    for route in app.routes:
        if isinstance(route, APIRoute) and route.endpoint is health_check:
            yield route, "GET"


def fill(path: str, value: str = "1") -> str:
    return re.sub(r"\{[^}]+\}", value, path)


def all_actors(client, world):
    """Headers for every role, plus none."""
    client.post("/api/admin/lab-staff", headers=world.admin, json={"email": "lab@hospital.example.com", "full_name": "Lab Person", "password": PASSWORD})
    client.post("/api/admin/doctors", headers=world.admin, json={"email": "intern@hospital.example.com", "full_name": "Intern Person", "password": PASSWORD,
                                                                "department_id": world.department_id, "grade": "INTERN", "supervisor_id": world.doctor_id})
    client.post("/api/admin/nurses", headers=world.admin, json={"email": "nurse@hospital.example.com", "full_name": "Nurse Person", "password": PASSWORD})
    return {"none": {}, "ADMIN": world.admin, "DOCTOR": world.doctor, "EMPLOYEE": world.employee, "PATIENT": world.patient, "PHARMACY": world.pharmacy,
            "LAB": login(client, "lab@hospital.example.com"), "INTERN": login(client, "intern@hospital.example.com"), "NURSE": login(client, "nurse@hospital.example.com")}
