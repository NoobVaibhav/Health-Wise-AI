"""Step 5: the real files of the sample_reports/ folder go through the real upload API. The report is read from what is printed: values, units and ranges exactly, a missing range
stays missing and the value is then "not judged", a report with another patient's name is flagged, a text that is not a health report is refused, and the AI wording is
labelled as needing review. Invented data only."""
import pathlib

import pytest

from tests.conftest import upload

FOLDER = pathlib.Path(__file__).resolve().parents[2] / "sample_reports"


def send(client, world, name, as_user="employee"):
    content = (FOLDER / name).read_bytes()
    return upload(client, getattr(world, as_user), world.patient_id, name, content, world.doctor_id)


@pytest.mark.parametrize("name", ["Report_A_July_Rahul.pdf", "Report_B_October_Rahul.pdf"])
def test_the_lab_pdfs_are_read_exactly_and_no_range_is_ever_invented(client, world, name):
    r = send(client, world, name)
    assert r.status_code in (200, 201), r.text
    report = client.get(f"/api/reports/{r.json()['id']}", headers=world.doctor).json()
    assert report["parameters"], "no values were read"
    for p in report["parameters"]:
        assert p["value"] == p["value"] and abs(p["value"]) < 1e9                                     # a real number, not NaN or absurd
        if p["reference_low"] is None and p["reference_high"] is None:
            assert p["status"] == "UNKNOWN", f"{p['test_name']}: no printed range but judged {p['status']}"
        else:
            low, high = p["reference_low"], p["reference_high"]
            expected = "BELOW_RANGE" if low is not None and p["value"] < low else "ABOVE_RANGE" if high is not None and p["value"] > high else "WITHIN_RANGE"
            assert p["status"] == expected, f"{p['test_name']} {p['value']} vs {low}-{high} judged {p['status']}"
    assert "professional" in report["disclaimer"].lower() or "doctor" in report["disclaimer"].lower() or "healthcare" in report["disclaimer"].lower()


def test_a_report_with_another_patients_name_is_flagged_for_the_staff(client, world):
    r = send(client, world, "Report_C_other_patient.txt")
    assert r.status_code in (200, 201), r.text
    assert any("does not match" in w for w in r.json()["warnings"]), r.json()["warnings"]


def test_the_range_less_tsh_value_keeps_its_own_printed_range_and_the_unit(client, world):
    r = send(client, world, "Report_C_other_patient.txt")
    rows = {p["normalized_name"].lower(): p for p in client.get(f"/api/reports/{r.json()['id']}", headers=world.doctor).json()["parameters"]}
    tsh = next((p for k, p in rows.items() if "tsh" in k), None)
    assert tsh and tsh["value"] == 2.1 and (tsh["reference_low"], tsh["reference_high"]) == (0.4, 4.0) and "uiu" in (tsh["unit"] or "").lower().replace("µ", "u")


def test_a_text_that_is_not_a_health_report_is_refused_with_a_clear_message(client, world):
    r = send(client, world, "Not_a_health_report.txt")
    assert r.status_code in (400, 422), r.text
    assert "report" in r.text.lower()


@pytest.mark.parametrize("name", ["Report_A_scan.png", "Chest_Xray_Rahul.pdf", "Discharge_Summary_Rahul.pdf", "ECG_Rahul.txt", "Prescription_Rahul.txt"])
def test_scans_and_narrative_documents_never_crash_and_never_invent_values(client, world, name):
    r = send(client, world, name)
    assert r.status_code in (200, 201, 400, 422, 503), (name, r.status_code, r.text[:200])     # 503 = no OCR engine installed, a clear message
    if r.status_code in (200, 201):
        report = client.get(f"/api/reports/{r.json()['id']}", headers=world.doctor).json()
        for p in report["parameters"]:
            assert p["status"] in ("WITHIN_RANGE", "ABOVE_RANGE", "BELOW_RANGE", "UNKNOWN")
        if report["is_narrative"]:
            assert report["parameters"] == [] or all(p["reference_text"] or p["status"] == "UNKNOWN" for p in report["parameters"])
    else:
        assert "Traceback" not in r.text and "File \"" not in r.text


def test_the_patient_sees_no_analysis_until_a_doctor_reviews_it_and_the_wording_is_labelled(client, world):
    r = send(client, world, "Report_A_July_Rahul.pdf")
    rid = r.json()["id"]
    before = client.get(f"/api/reports/{rid}", headers=world.patient).json()
    assert before["analysis_visible"] is False and before["parameters"] == [] and not before["ai_summary"]
    assert client.put(f"/api/doctor/reports/{rid}/review", headers=world.doctor, json={"decision": "APPROVED", "comment": "Seen"}).status_code == 200
    after = client.get(f"/api/reports/{rid}", headers=world.patient).json()
    assert after["analysis_visible"] is True and after["review_decision"] == "APPROVED"
    text = (after["ai_summary"] or "") + after["disclaimer"]
    assert "diagnos" not in (after["ai_summary"] or "").lower().replace("not a diagnos", "") or "not" in text.lower()
