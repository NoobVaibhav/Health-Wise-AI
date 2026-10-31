"""Deployment and operations checks: the PostgreSQL schema file, secrets in the repository, personal data and tokens in log files."""
import pathlib
import re
import subprocess

from tests.security_and_chaos._helpers import bust

ROOT = pathlib.Path(__file__).resolve().parents[3]


def schema_tables():
    sql = (ROOT / "backend" / "schema.sql").read_text(encoding="utf-8")
    tables = {}
    for m in re.finditer(r"CREATE TABLE(?: IF NOT EXISTS)?\s+(\w+)\s*\((.*?)\n\);", sql, re.S | re.I):
        cols = set()
        for line in m.group(2).split("\n"):
            line = line.strip().rstrip(",")
            if line and not line.upper().startswith(("PRIMARY", "FOREIGN", "UNIQUE", "CONSTRAINT", "CHECK", "--")):
                cols.add(line.split()[0].strip('"'))
        tables[m.group(1)] = cols
    return tables


def test_schema_sql_for_postgresql_has_every_table_and_column_of_the_models():
    """schema.sql is what a PostgreSQL deployment is told to load. It lacks 19 of the 37 tables and about 20 columns (insights, lab, past history,
    clinical intelligence, assistant, billing sales ...), so an application started on it fails on the first request that needs one."""
    from app.database.connection import Base
    import app.database.models  # noqa: F401
    tables = schema_tables()
    missing_tables = sorted(set(Base.metadata.tables) - set(tables))
    missing_columns = {n: sorted({c.name for c in t.columns} - tables[n]) for n, t in Base.metadata.tables.items() if n in tables and {c.name for c in t.columns} - tables[n]}
    assert not missing_tables and not missing_columns, f"missing tables {missing_tables}; missing columns {missing_columns}"


def test_no_secret_key_or_environment_file_is_tracked_by_git():
    files = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.splitlines()
    bad = [f for f in files if re.search(r"(^|/)\.env$|\.db$|\.sqlite3?$|\.pem$|\.key$|\.log$|(^|/)uploads/", f)]
    assert not bad, bad
    hits = subprocess.run(["git", "grep", "-nIE", r"sk-ant-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}|-----BEGIN (RSA |EC )?PRIVATE KEY-----|jwt_secret\s*=\s*['\"][^'\"]{12,}['\"]"], cwd=ROOT, capture_output=True, text=True).stdout
    assert not hits.strip(), hits[:300]


def test_log_files_in_the_project_folder_hold_no_tokens_or_passwords():
    for name in ("backend.log", "backend.err.log", "frontend.log", "frontend.err.log"):
        path = ROOT / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        assert not re.search(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}", text), f"a JWT is in {name}"
        assert not re.search(r"(?i)password[\"']?\s*[:=]\s*[\"'][^\"']{4,}", text), f"a password is in {name}"


@bust("O-01")
def test_the_secret_written_in_docker_compose_is_refused_on_a_real_database(monkeypatch):
    """docker-compose.yml falls back to JWT_SECRET='change-this-to-a-long-random-secret-before-deploying' when none is given. check_secret() only
    rejects the one string 'change-me-in-production' or anything shorter than 32 characters, so this public 49-character default is accepted and
    anyone who has read the repository can sign a token for any user."""
    from app.core import config
    from app import main
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    default = re.search(r"JWT_SECRET:\s*\$\{JWT_SECRET:-([^}]+)\}", compose).group(1)
    monkeypatch.setattr(main, "get_settings", lambda: config.Settings(database_url="postgresql+psycopg2://u:p@h/db", jwt_secret=default))
    import pytest
    with pytest.raises(RuntimeError):
        main.check_secret()


@bust("O-03")
def test_the_listed_python_packages_are_pinned_to_a_known_version():
    lines = [l.strip() for l in (ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8").splitlines() if l.strip() and not l.startswith("#")]
    unpinned = [l for l in lines if "==" not in l]
    assert not unpinned, f"{len(unpinned)} packages are allowed to be any newer version: a rebuild can silently pull a different (or vulnerable) release: {unpinned[:4]}"


@bust("D-02")
def test_the_installed_pillow_and_pypdf_have_no_known_vulnerabilities():
    """Both parse files uploaded by employees and doctors. pip-audit (run 2026-10-28) lists 39 known vulnerabilities for Pillow 12.3.0 (fixed in 13.0.0)
    and 11 for pypdf 6.19.0 (fixed in 6.21.2). This test only compares versions, so it needs no network."""
    from importlib.metadata import version
    def at_least(have, need):
        key = lambda v: [int(x) for x in re.findall(r"\d+", v)[:3]]
        return key(have) >= key(need)
    assert at_least(version("pillow"), "13.0.0") and at_least(version("pypdf"), "6.21.2"), (version("pillow"), version("pypdf"))
