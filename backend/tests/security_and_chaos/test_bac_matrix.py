"""Broken access control sweep: every endpoint x every role and no token. The intended roles are read from the code (require_roles) itself."""
import json
import pathlib

from fastapi.testclient import TestClient

from app.main import app
from tests.security_and_chaos._helpers import all_actors, fill, intended_roles, operations

OUT = pathlib.Path(__file__).with_name("endpoint_matrix.json")


def test_every_endpoint_denies_the_roles_it_is_not_meant_for_and_never_crashes(client, world):
    actors = all_actors(client, world)
    quiet = TestClient(app, raise_server_exceptions=False)
    matrix, violations = [], []
    for route, method in operations():
        public, roles = intended_roles(route)
        row = {"method": method, "path": route.path, "public": public, "roles": sorted(roles) if roles else ("ANY LOGGED-IN" if not public else "PUBLIC"), "results": {}}
        for name in ["none", "PATIENT", "PHARMACY", "LAB", "EMPLOYEE", "ADMIN", "DOCTOR"]:           # the broadest roles last: they may change the data
            kw = {"json": {}} if method in ("POST", "PUT", "PATCH") else {}
            r = quiet.request(method, fill(route.path), headers=actors[name], **kw)
            row["results"][name] = r.status_code
            allowed = public or (roles is None and name != "none") or (roles is not None and name in roles)
            if r.status_code >= 500 and r.status_code != 503:      # 503 = a clearly worded "no AI model connected", by design
                violations.append(f"CRASH {r.status_code} {method} {route.path} as {name}")
            elif not public and name == "none" and r.status_code != 401:
                violations.append(f"NO-TOKEN {r.status_code} {method} {route.path}")
            elif not allowed and name != "none" and r.status_code not in (401, 403):
                violations.append(f"NOT-DENIED {r.status_code} {method} {route.path} as {name} (intended: {row['roles']})")
        matrix.append(row)
    OUT.write_text(json.dumps(matrix, indent=1), encoding="utf-8")
    assert not violations, "\n".join(violations)
    assert len(matrix) >= 120
