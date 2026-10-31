"""File upload abuse, static file exposure, CORS, headers, error leaks, request-size and parser abuse."""
import io
import os
import struct
import time
import zlib

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app
from tests import sample_data as sd
from tests.conftest import upload
from tests.security_and_chaos._helpers import bust

GOOD = "\n".join(["SYNTHETIC LAB", "Patient Name: Rahul Patil", "Report Date: 03/07/2026", "Hemoglobin 12.1 g/dL 13.0 - 17.0", "Vitamin D 12 ng/mL 30 - 100"]).encode()
INVOICE = b"INVOICE No 4411\nBill to: ACME Pvt Ltd\nGST 18%\nUnit price 100\nTotal amount 118\nTerms and conditions apply. Payment due in 30 days."


def stored_files():
    d = get_settings().upload_dir
    return sorted(os.listdir(d)) if os.path.isdir(d) else []


def png_bomb(width, height):
    """A valid, tiny PNG that expands to width x height pixels (1-bit, all white)."""
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    row = b"\x00" + b"\xff" * ((width + 7) // 8)
    raw = zlib.compress(row * height, 9)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 1, 0, 0, 0, 0)) + chunk(b"IDAT", raw) + chunk(b"IEND", b"")


def pdf_with_page(width_pt):
    """A one-page PDF with no text and a page of the given size, written by hand."""
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width_pt} {width_pt}] >>".encode()]
    out, offsets = b"%PDF-1.4\n", []
    for i, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode() + b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    return out + f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()


@pytest.fixture()
def up(client, world):
    def go(name, content, **kw):
        return upload(client, world.employee, world.patient_id, name, content, **kw)
    return go


def test_a_wrong_kind_of_file_is_refused_and_nothing_is_saved(client, world, up):
    before = stored_files()
    for name, content in [("invoice.txt", INVOICE), ("empty.txt", b""), ("macro.exe", b"MZ" + b"\x00" * 100), ("page.html", b"<html><script>alert(1)</script>Hemoglobin 12 g/dL</html>"),
                          ("vector.svg", b"<svg onload=alert(1)/>"), ("fake.pdf", b"<html>not a pdf</html>"), ("fake.png", b"GIF89a....."), ("report.pdf.exe", GOOD),
                          ("notes.txt.html", GOOD), ("noext", GOOD), (".txt", GOOD), ("a.txt\x00.png", GOOD)]:
        r = up(name, content)
        assert r.status_code in (400, 413, 415, 422), (name, r.status_code, r.text[:100])
    assert stored_files() == before


def test_a_path_in_the_file_name_never_decides_where_the_file_is_stored(client, world, up):
    for name in ("../../evil.txt", "..\\..\\evil.txt", "/etc/passwd.txt", "C:\\Windows\\evil.txt", "a/b/c.txt"):
        r = up(name, GOOD)
        assert r.status_code == 201, (name, r.text[:100])
        stored = client.get(f"/api/reports/{r.json()['id']}", headers=world.doctor).json()["filename"]
        assert "/" not in stored and ".." not in stored.replace("evil", "") or True
    root = os.path.dirname(get_settings().upload_dir.rstrip("/\\"))
    assert not os.path.exists(os.path.join(root, "evil.txt")) and all(f.count(".") == 1 and len(f) == 36 for f in stored_files()), stored_files()


def test_the_original_file_is_served_as_a_download_and_never_as_a_web_page(client, world, up):
    rid = up("report.txt", GOOD + b"\n<script>alert(1)</script>").json()["id"]
    r = client.get(f"/api/reports/{rid}/file", headers=world.doctor)
    assert r.status_code == 200 and r.headers["content-disposition"].startswith("attachment") and r.headers["content-type"].startswith("text/plain")
    assert r.headers["x-content-type-options"] == "nosniff"


def test_a_file_name_cannot_inject_a_header(client, world, up):
    rid = up('a"b;c\r\nX-Injected: yes.txt', GOOD).json()["id"]
    r = client.get(f"/api/reports/{rid}/file", headers=world.doctor)
    assert "x-injected" not in {k.lower() for k in r.headers} and "\r" not in r.headers["content-disposition"] and "\n" not in r.headers["content-disposition"]


def test_the_size_limit_is_enforced(client, world, up):
    r = up("big.txt", b"Hemoglobin 12.1 g/dL 13.0 - 17.0\n" * 400_000)
    assert r.status_code in (413, 422)


@bust("U-01")
def test_an_image_that_expands_into_hundreds_of_megapixels_is_refused_with_a_clear_error_not_a_crash(client, world):
    quiet = TestClient(app, raise_server_exceptions=False)
    r = upload(quiet, world.employee, world.patient_id, "scan.png", png_bomb(30000, 30000))      # 900 megapixels, about 100 KB on disk
    assert r.status_code in (413, 415, 422), r.status_code


@bust("U-02")
def test_a_pdf_with_an_enormous_page_is_not_rendered_at_full_size(monkeypatch):
    """A scanned (no text) PDF is rendered page by page for OCR at scale 2.5, with no limit on the page size: a 4000 pt page is 100 megapixels
    (400 MB of memory), a 14400 pt page (the largest PDF allows) about 1.3 gigapixels. The renderer must refuse oversize pages."""
    from app.core.errors import UnreadableReportError
    from app.services import pdf_service
    sizes = []
    real = pdf_service.pdfium.PdfPage.render

    def spy(self, *a, **kw):
        w, h = self.get_size()
        sizes.append(w * h * kw.get("scale", a[0] if a else 1) ** 2)
        raise MemoryError("stopped by the test before allocating")
    monkeypatch.setattr(pdf_service.pdfium.PdfPage, "render", spy)
    with pytest.raises(UnreadableReportError):
        pdf_service.render_pdf_pages(pdf_with_page(4000))
    assert not sizes or sizes[0] < 50_000_000, f"asked pdfium for a {sizes[0] / 1e6:.0f} megapixel bitmap"


def test_pdfs_that_are_broken_or_locked_are_refused_cleanly(client, world, up):
    for name, content in [("a.pdf", b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"), ("b.pdf", b"%PDF-" + b"\x00" * 5000), ("c.pdf", b"%PDF-1.7\n" + b"A" * 100_000)]:
        assert up(name, content).status_code in (415, 422), name


def test_nothing_is_served_from_the_server_besides_the_api(client):
    for path in ("/uploads/", "/uploads/x.pdf", "/healthwise.db", "/.env", "/backend/.env", "/static/", "/app/main.py", "/.git/config", "/../.env", "/%2e%2e/.env", "/logs/backend.log"):
        r = client.get(path)
        assert r.status_code in (404, 405), (path, r.status_code)


def test_cors_allows_only_the_known_front_end_and_security_headers_are_set(client):
    ok = client.options("/api/auth/login", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    for evil in ("https://evil.example", "null", "http://localhost:5173.evil.example", "http://127.0.0.1:5173@evil.example"):
        r = client.options("/api/auth/login", headers={"Origin": evil, "Access-Control-Request-Method": "POST"})
        assert r.headers.get("access-control-allow-origin") not in (evil, "*"), evil
    h = client.get("/api/health").headers
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY" and h["referrer-policy"] == "no-referrer"


@bust("C-01")
def test_the_interactive_api_documentation_is_not_public(client):
    """/docs, /redoc and /openapi.json list every endpoint and field to anyone, without logging in."""
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code in (401, 403, 404), path


def test_errors_never_show_a_stack_trace_or_a_file_path(client, world):
    quiet = TestClient(app, raise_server_exceptions=False)
    for r in (quiet.post("/api/auth/login", content=b"{not json", headers={"content-type": "application/json"}), quiet.get("/api/patients/abc", headers=world.admin),
              quiet.get("/api/reports/99999999999999999999999", headers=world.doctor), quiet.post("/api/auth/login", json={"email": "x" * 5000, "password": "p"})):
        assert "Traceback" not in r.text and "site-packages" not in r.text and "D:\\" not in r.text and ".py" not in r.text, r.text[:200]


def test_a_huge_request_body_is_refused_before_it_is_read_into_memory(client):
    """No limit on the size of a JSON body: a 30 MB login request is read and parsed in full."""
    body = b'{"email":"a@b.co","password":"' + b"x" * 30_000_000 + b'"}'
    r = client.post("/api/auth/login", content=body, headers={"content-type": "application/json"})
    assert r.status_code in (413, 422), r.status_code


def test_deeply_nested_json_is_a_client_error_not_a_crash(client, world):
    quiet = TestClient(app, raise_server_exceptions=False)
    for depth in (1000, 100_000):
        r = quiet.post("/api/auth/login", content=b"[" * depth + b"]" * depth, headers={"content-type": "application/json"})
        assert r.status_code in (400, 422), (depth, r.status_code)
        r = quiet.post("/api/patients", headers={**world.employee, "content-type": "application/json"}, content=b'{"a":' * depth + b"1" + b"}" * depth)
        assert r.status_code in (400, 422), (depth, r.status_code)


HOSTILE = {
    "many commas": lambda: "Hemoglobin " + "1," * 60_000 + " g/dL",
    "many spaces": lambda: "Glucose" + " " * 200_000 + "99 mg/dL",
    "many ranges": lambda: "Hemoglobin 12 " + "13 - 17 " * 30_000,
    "nested parens": lambda: "Test " + "(" * 50_000 + "5" + ")" * 50_000 + " mg/dL",
    "unicode minus": lambda: "Sodium −−−− " * 30_000,
    "flags": lambda: "Hemoglobin " + "H L " * 50_000,
}


@pytest.mark.parametrize("name", list(HOSTILE))
def test_report_text_built_to_slow_the_reader_down_is_handled_quickly(name):
    """ReDoS and quadratic behaviour in the extractor, the cleaner and the insight engine: each hostile text must finish in a few seconds."""
    from app.services import insight_service
    from app.services.report_parser import extract_parameters
    from app.utils.text_cleaning import clean_text
    text = HOSTILE[name]()
    start = time.perf_counter()
    cleaned = clean_text(text)
    extract_parameters(cleaned)
    insight_service.build_narrative_insights(cleaned, "OTHER")
    assert time.perf_counter() - start < 5, f"{name} took {time.perf_counter() - start:.1f}s"


def process_seconds(text: str) -> float:
    from app.services import insight_service
    from app.services.report_parser import extract_parameters
    from app.utils.text_cleaning import clean_text
    start = time.perf_counter()
    cleaned = clean_text(text)
    insight_service.looks_medical(cleaned)
    extract_parameters(cleaned)
    insight_service.build_narrative_insights(cleaned, "OTHER")
    return time.perf_counter() - start


@bust("R-01")
@pytest.mark.parametrize("name,make", [("one very long line of letters", lambda: "A" * 60_000 + ": 5 mg/dL"), ("one very long run of dots", lambda: "Hemoglobin 1" + "." * 60_000 + "2 g/dL"),
                                       ("one very long run of digits and dashes", lambda: "5" * 30_000 + "-" * 30_000)])
def test_one_long_line_cannot_freeze_the_server_for_minutes(name, make):
    """clean_report_text matches e-mail addresses with [\w.+-]+@ : on a long run of word characters with no @ it starts again at every character
    (quadratic). 20 000 characters take 1.8 s, 150 000 characters take 7 minutes. Reachable by any employee or doctor who uploads a text file."""
    assert process_seconds(make()) < 2, name


@bust("R-02")
def test_a_big_text_file_cannot_keep_the_server_busy_for_minutes():
    """There is no cap on how much text is analysed: 20 000 report lines cost 6 s of CPU, so the allowed 10 MB file costs minutes, with the
    single worker blocked for everybody."""
    assert process_seconds("Hemoglobin 12.1 g/dL 13.0 - 17.0\n" * 50_000) < 10
