"""Deployment findings: the default secret of docker-compose, unpinned packages, vulnerable parsers."""
import pathlib
import re
from importlib.metadata import version

import pytest

from tests.security_and_chaos._helpers import bust

ROOT = pathlib.Path(__file__).resolve().parents[3]


@bust("O-01")
def test_the_secret_written_in_docker_compose_is_refused_on_a_real_database(monkeypatch):
    """docker-compose.yml falls back to JWT_SECRET='change-this-to-a-long-random-secret-before-deploying' when none is given. check_secret() only
    rejects the string 'change-me-in-production' or anything shorter than 32 characters, so this public 49-character default is accepted and
    anyone who has read the repository can sign a token for any user."""
    from app import main
    from app.core import config
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    default = re.search(r"JWT_SECRET:\s*\$\{JWT_SECRET:-([^}]+)\}", compose).group(1)
    monkeypatch.setattr(main, "get_settings", lambda: config.Settings(database_url="postgresql+psycopg2://u:p@h/db", jwt_secret=default))
    with pytest.raises(RuntimeError):
        main.check_secret()


@bust("O-03")
def test_the_listed_python_packages_are_pinned_to_a_known_version():
    lines = [l.strip() for l in (ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
    unpinned = [l for l in lines if "==" not in l]
    assert not unpinned, f"{len(unpinned)} packages may be any newer version, so a rebuild can silently pull a different or vulnerable release: {unpinned[:4]}"


@bust("D-02")
def test_the_installed_pillow_and_pypdf_have_no_known_vulnerabilities():
    """Both parse files uploaded by employees and doctors. pip-audit (2026-10-28) lists 39 known vulnerabilities for Pillow 12.3.0 (fixed in 13.0.0)
    and 11 for pypdf 6.19.0 (fixed in 6.21.2). This test only compares versions, so it needs no network."""
    def at_least(have, need):
        key = lambda v: [int(x) for x in re.findall(r"\d+", v)[:3]]
        return key(have) >= key(need)
    assert at_least(version("pillow"), "13.0.0") and at_least(version("pypdf"), "6.21.2"), (version("pillow"), version("pypdf"))


def test_every_voice_navigation_target_stays_inside_the_patient_area():
    """A spoken command can only open the fixed patient pages: it cannot reach another role's pages or another patient's data."""
    from app.services.assistant_talk import PAGES
    assert all(route.startswith("/patient") for _, _, route, _ in PAGES)
