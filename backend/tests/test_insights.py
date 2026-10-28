"""Insights for ANY report: type detection, wording analysis, doctor suggestions, patient tips, safety, privacy."""
import json

import pytest

from app.core.errors import InvalidHealthReportError
from app.services import llm_service, report_processor
from app.services.insight_service import (
    DOCTOR_BY_TYPE, LAB_DOCTOR_BY_CATEGORY, LAB_PATIENT_BY_CATEGORY, PATIENT_BY_TYPE, PATIENT_GENERAL,
    build_narrative_insights, classify_statement, detect_report_type, looks_medical,
)
from app.services.safety_filter import is_safe, is_safe_for_doctor
from tests import sample_data as sd
from tests.conftest import upload


def process(name: str, lines: list[str]):
    return report_processor.process_report(name, sd.lines_to_text(lines))


# ---------- recognising what kind of report it is
@pytest.mark.parametrize("lines,expected", [
    (sd.CHEST_XRAY_LINES, "XRAY"), (sd.ECG_LINES, "ECG"), (sd.DISCHARGE_LINES, "DISCHARGE"),
    (sd.PRESCRIPTION_LINES, "PRESCRIPTION"),
])
def test_report_type_is_detected(lines, expected):
    text = "\n".join(lines)
    assert looks_medical(text)
    assert detect_report_type(text) == expected
    assert process("r.txt", lines).report_type == expected


def test_lab_report_is_still_a_lab_report():
    result = report_processor.process_report("a.pdf", sd.lines_to_pdf(sd.REPORT_A_LINES))
    assert result.report_type == "LAB" and len(result.parameters) == 6


def test_non_medical_documents_are_still_rejected():
    assert not looks_medical("\n".join(sd.NOT_A_REPORT_LINES))
    with pytest.raises(InvalidHealthReportError):
        process("invoice.txt", sd.NOT_A_REPORT_LINES)
    with pytest.raises(InvalidHealthReportError):
        process("letter.txt", ["Dear customer, your subscription renews next month.", "Please contact support if you have questions."])


# ---------- reading the wording
@pytest.mark.parametrize("sentence,concern", [
    ("No evidence of mass or consolidation in either lung.", "normal"),     # negation
    ("There are no masses seen.", "normal"),
    ("A 2 cm nodule is seen in the right upper lobe.", "attention"),
    ("Heart size is within normal limits.", "normal"),
    ("Body mass index is 24.", "neutral"),                                   # 'mass' inside BMI is not a finding
    ("Mild cardiomegaly is present.", "attention"),
])
def test_statement_classification(sentence, concern):
    assert classify_statement(sentence)[0] == concern


def test_urgent_wording_is_flagged_for_the_doctor():
    result = process("scan.txt", [
        "CT SCAN CHEST REPORT", "Findings: Filling defect in the right pulmonary artery.",
        "Impression: Findings suggestive of pulmonary embolism, urgent review advised.",
        "Patient history: shortness of breath. Clinical examination advised. Radiology report."])
    assert result.insights["red_flags"] and "prompt attention" in result.insights["red_flags"][0]
    normal = process("scan2.txt", sd.ECG_LINES)
    assert normal.insights["red_flags"] == []


def test_xray_gives_findings_and_suggestions_for_doctor_and_patient():
    insights = process("xray.txt", sd.CHEST_XRAY_LINES).insights
    concerns = {f["text"]: f["concern"] for f in insights["key_findings"]}
    assert any("nodule" in text.lower() and c == "attention" for text, c in concerns.items())
    assert any("No evidence of consolidation" in text and c == "normal" for text, c in concerns.items())
    assert any("follow-up" in d or "follow up" in d or "repeat study" in d for d in insights["doctor_suggestions"])
    assert any("earlier scans" in p for p in insights["patient_recommendations"])
    assert insights["source"] == "rules" and "worth a look" in insights["summary"]


def test_normal_ecg_has_no_attention_items():
    insights = process("ecg.txt", sd.ECG_LINES).insights
    assert not [f for f in insights["key_findings"] if f["concern"] == "attention"]
    assert any("Compare with a previous ECG" in d for d in insights["doctor_suggestions"])


def test_lab_insights_group_by_body_system_and_use_only_printed_ranges():
    result = report_processor.process_report("a.pdf", sd.lines_to_pdf(sd.REPORT_A_LINES))
    insights = result.insights
    joined = " ".join(insights["doctor_suggestions"])
    assert "Glucose" in joined and "Lipid" in joined and "vitamin" in joined.lower()
    assert any("fibre" in p for p in insights["patient_recommendations"])
    assert "earlier reports" in joined and not insights["red_flags"]
    far = process("cbc.txt", ["Patient Name: Test Person", "Total Leucocyte Count 40,000 /cumm 4,000 - 11,000"])
    assert far.insights["red_flags"] and "far from the printed range" in far.insights["red_flags"][0]


def test_value_without_printed_range_is_not_judged():
    insights = process("t.txt", ["Patient Name: Test Person", "Vitamin D 17 ng/mL"]).insights
    assert any("no printed range" in d for d in insights["doctor_suggestions"])
    assert not insights["red_flags"]


# ---------- safety of the built-in wording
def test_built_in_texts_never_diagnose_or_prescribe():
    patient_texts = [t for v in PATIENT_BY_TYPE.values() for t in v] + PATIENT_GENERAL + \
        [t for v in LAB_PATIENT_BY_CATEGORY.values() for t in v]
    doctor_texts = [t for v in DOCTOR_BY_TYPE.values() for t in v] + list(LAB_DOCTOR_BY_CATEGORY.values())
    for text in patient_texts:
        assert is_safe(text), text
        assert "you have" not in text.lower()
    for text in doctor_texts:
        assert is_safe_for_doctor(text), text


def test_doctor_filter_blocks_doses_and_patient_filter_blocks_diagnosis():
    assert not is_safe_for_doctor("Give 500 mg twice daily")
    assert not is_safe_for_doctor("You have diabetes")
    assert is_safe_for_doctor("Consider repeating the test and reviewing the diagnosis with a specialist.")
    assert not is_safe("You have a tumour, start taking tablets")


# ---------- optional AI: redaction + filtering + fallback
def test_redaction_removes_personal_details():
    text = "Patient Name: Rahul Patil\nPhone: 9999999999\nEmail: rahul@example.com\nFindings: nodule seen. Call 98765 43210 now.\nAddress: 5 Main Road"
    cleaned = llm_service.redact_text(text)
    assert "Rahul" not in cleaned and "9999999999" not in cleaned and "@" not in cleaned and "Main Road" not in cleaned
    assert "nodule seen" in cleaned and "98765" not in cleaned


def test_ai_output_is_filtered_and_personal_data_is_not_sent(monkeypatch):
    sent = []
    reply = json.dumps({
        "summary": "A small nodule is mentioned; please discuss it with your doctor.",
        "key_findings": [{"text": "A 1.5 cm nodule in the left lower zone", "concern": "attention"}],
        "doctor_suggestions": ["Consider comparing with earlier chest imaging and deciding on a CT.", "Give 500 mg amoxicillin daily"],
        "patient_recommendations": ["Keep your follow-up appointment and bring earlier scans.", "You have cancer, start taking tablets now"],
    })
    monkeypatch.setattr(llm_service, "llm_is_configured", lambda: True)
    monkeypatch.setattr(llm_service, "_call_llm", lambda prompt, system=None: sent.append(prompt) or reply)
    insights = report_processor.process_report("x.txt", sd.lines_to_text(sd.CHEST_XRAY_LINES)).insights
    assert insights["source"] == "llm"
    assert "Consider comparing with earlier chest imaging and deciding on a CT." in insights["doctor_suggestions"]
    assert not any("500 mg" in d for d in insights["doctor_suggestions"])           # unsafe doctor text dropped
    assert "Keep your follow-up appointment and bring earlier scans." in insights["patient_recommendations"]
    assert not any("cancer" in p for p in insights["patient_recommendations"])      # unsafe patient text dropped
    assert sent and "Rahul" not in sent[0] and "Patient Name" not in sent[0]        # personal details never left the server


def test_bad_ai_reply_falls_back_to_rules(monkeypatch):
    monkeypatch.setattr(llm_service, "llm_is_configured", lambda: True)
    monkeypatch.setattr(llm_service, "_call_llm", lambda prompt, system=None: "this is not json")
    insights = report_processor.process_report("x.txt", sd.lines_to_text(sd.CHEST_XRAY_LINES)).insights
    assert insights["source"] == "rules" and insights["doctor_suggestions"]


# ---------- through the API, with role visibility
def test_any_report_workflow_and_role_visibility(client, world):
    response = upload(client, world.employee, world.patient_id, "xray.pdf", sd.lines_to_pdf(sd.CHEST_XRAY_LINES))
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["report_type"] == "XRAY" and body["is_narrative"] is True and body["parameter_count"] == 0
    assert body["report_type_label"].startswith("X-ray report") and body["insights"] is None      # employee: none
    report_id = body["id"]

    doctor_view = client.get(f"/api/reports/{report_id}", headers=world.doctor).json()
    assert doctor_view["insights"]["doctor_suggestions"] and doctor_view["insights"]["key_findings"]
    assert "nodule" in doctor_view["ai_summary"].lower() or "nodule" in str(doctor_view["insights"]).lower()

    before = client.get(f"/api/reports/{report_id}", headers=world.patient).json()
    assert before["insights"] is None and before["ai_summary"] is None                              # not reviewed yet
    client.put(f"/api/doctor/reports/{report_id}/review", headers=world.doctor, json={"decision": "APPROVED"})
    after = client.get(f"/api/reports/{report_id}", headers=world.patient).json()["insights"]
    assert after["patient_recommendations"] and after["key_findings"]
    assert "doctor_suggestions" not in after and "red_flags" not in after                           # patient never sees these

    listing = client.get("/api/reports", headers=world.employee).json()
    assert listing[0]["report_type"] == "XRAY"
    assert client.get(f"/api/reports/{report_id}", headers=world.admin).json()["insights"] is None


def test_all_kinds_of_files_are_accepted_and_invoice_is_not(client, world):
    for name, lines in (("ecg.txt", sd.ECG_LINES), ("discharge.pdf", sd.DISCHARGE_LINES), ("rx.txt", sd.PRESCRIPTION_LINES)):
        content = sd.lines_to_pdf(lines) if name.endswith(".pdf") else sd.lines_to_text(lines)
        assert upload(client, world.employee, world.patient_id, name, content).status_code == 201, name
    bad = upload(client, world.employee, world.patient_id, "invoice.txt", sd.lines_to_text(sd.NOT_A_REPORT_LINES))
    assert bad.status_code == 422 and "recognizable laboratory" in bad.json()["detail"]
    types = {r["filename"]: r["report_type"] for r in client.get("/api/reports", headers=world.doctor).json()}
    assert types == {"ecg.txt": "ECG", "discharge.pdf": "DISCHARGE", "rx.txt": "PRESCRIPTION"}


def test_lab_report_insights_visible_to_doctor_and_patient_tips_after_review(client, world):
    report_id = upload(client, world.employee, world.patient_id, "a.pdf", sd.lines_to_pdf(sd.REPORT_A_LINES)).json()["id"]
    doctor = client.get(f"/api/reports/{report_id}", headers=world.doctor).json()
    assert doctor["report_type"] == "LAB" and doctor["is_narrative"] is False
    assert any("Lipid" in d for d in doctor["insights"]["doctor_suggestions"])
    assert client.get(f"/api/reports/{report_id}", headers=world.patient).json()["insights"] is None
    client.put(f"/api/doctor/reports/{report_id}/review", headers=world.doctor, json={"decision": "APPROVED"})
    assert client.get(f"/api/reports/{report_id}", headers=world.patient).json()["insights"]["patient_recommendations"]


def test_old_lab_reports_without_saved_insights_still_get_them(client, world):
    from app.database.connection import SessionLocal
    from app.database.models import HealthReport
    report_id = upload(client, world.employee, world.patient_id, "a.pdf", sd.lines_to_pdf(sd.REPORT_A_LINES)).json()["id"]
    with SessionLocal() as db:               # simulate a report saved before this feature existed
        row = db.get(HealthReport, report_id)
        row.report_type, row.insights_json = None, None
        db.commit()
    detail = client.get(f"/api/reports/{report_id}", headers=world.doctor).json()
    assert detail["report_type"] == "LAB" and detail["insights"]["doctor_suggestions"]


def test_refresh_insights_is_doctor_only(client, world):
    report_id = upload(client, world.employee, world.patient_id, "xray.txt", sd.lines_to_text(sd.CHEST_XRAY_LINES)).json()["id"]
    url = f"/api/reports/{report_id}/insights/refresh"
    assert client.post(url, headers=world.doctor).status_code == 200
    for who in (world.patient, world.employee, world.pharmacy, world.admin, world.other_doctor):
        assert client.post(url, headers=who).status_code == 403
    logs = client.get("/api/admin/audit-logs?limit=500", headers=world.admin).json()
    assert "INSIGHTS_REFRESHED" in {l["action"] for l in logs}


# ---------- database upgrade
def test_new_columns_are_added_to_an_existing_database(tmp_path):
    from sqlalchemy import create_engine, inspect, text
    from app.database.connection import add_missing_columns
    old = create_engine(f"sqlite:///{tmp_path}/old.db")
    with old.begin() as c:                   # a health_reports table from before the feature (missing the new columns)
        c.execute(text("CREATE TABLE health_reports (id INTEGER PRIMARY KEY, filename VARCHAR(255))"))
        c.execute(text("INSERT INTO health_reports (id, filename) VALUES (1, 'old.pdf')"))
    add_missing_columns(old)
    columns = {c["name"] for c in inspect(old).get_columns("health_reports")}
    assert {"report_type", "insights_json", "ai_summary"} <= columns
    with old.connect() as c:
        assert c.execute(text("SELECT filename FROM health_reports")).scalar() == "old.pdf"   # existing row survived
    add_missing_columns(old)                 # running it twice is harmless


HOLTER_TEXT = """HOLTER ECG REPORT
Patient Name: Rahul Patil   Age: 45   Date: 12/10/2026
Total beats: 98562  Heart rate: Max 142 bpm  Min 48 bpm  Avg 72 bpm
Total No. of episodes: 0 VTAC No. of episodes: 0
VPB Isolated Ectopics: 3 Pairs: 0 Run Beats: 0 SVT No. of episodes: 2
Total No. of episodes: 0 VTAC No. of episodes: 0
QT interval: 410 ms (350 - 440)
Impression: Predominant sinus rhythm. No evidence of sustained ventricular tachycardia. Occasional isolated ventricular ectopics seen.
"""


def test_table_rows_become_numbers_not_broken_sentences():
    from app.services.insight_service import build_narrative_insights, split_statements
    statements = split_statements(HOLTER_TEXT)
    assert all(": 0 VTAC" not in s and not s.lower().startswith("of episodes") for s in statements)
    insights = build_narrative_insights(HOLTER_TEXT, "ECG")
    texts = [f["text"] for f in insights["key_findings"]]
    assert "No evidence of sustained ventricular tachycardia." in texts       # "No." inside a sentence is not a break
    by_label = {m["label"]: m for m in insights["metrics"]}
    assert by_label["VPB Isolated Ectopics"]["value"] == 3 and by_label["VPB Isolated Ectopics"]["concern"] == "attention"
    assert by_label["SVT No. of episodes"]["value"] == 2
    assert by_label["VTAC No. of episodes"]["concern"] == "normal"                # a zero count is not a finding
    assert by_label["Heart rate (highest)"]["value"] == 142 and by_label["Heart rate (highest)"]["unit"] == "bpm"
    assert by_label["QT interval"]["concern"] == "normal"                            # inside the range printed next to it
    assert "Age" not in by_label and "Patient Name" not in by_label                  # personal / admin fields are not KPIs


def test_extract_metrics_ignores_ids_and_repeats():
    from app.services.insight_service import extract_metrics
    metrics = extract_metrics("Age: 45\nMRN: 12345\nPhone: 9999999999\nPauses No. of episodes: 0\nPauses No. of episodes: 0\n")
    assert [m["label"] for m in metrics] == ["Pauses No. of episodes"]


WRONG_FILES = {
    "project_report": "Software Requirements Specification\nTable of Contents\nChapter 1 Introduction\nThe hospital management system lets a doctor review a patient report, "
                      "prescription and diagnosis. Abstract: this project report describes the methodology.\n",
    "assignment": "Assignment 3 Semester V\nName: Vaibhav Lad Roll No: 57\nUnderstand the architecture of a pre-trained model in deep learning. "
                  "Explain the patient data, hospital records and clinical use of such a model.\n",
    "invoice": "INVOICE\nBill to: City Hospital\nGST No 27ABCDE1234F1Z5\nTotal amount: 4,500\nUnit price 450 x 10 tablets of paracetamol for the clinic and doctor.\n",
    "cv": "Curriculum Vitae\nObjective: seeking a position as a hospital administrator. Worked with doctor teams, patient records and clinic software.\n",
}


@pytest.mark.parametrize("kind", list(WRONG_FILES))
def test_wrong_files_are_rejected_with_a_clear_message(kind):
    from app.core.errors import InvalidHealthReportError
    with pytest.raises(InvalidHealthReportError) as caught:
        process(kind + ".txt", WRONG_FILES[kind].split("\n"))
    assert "Wrong file uploaded" in str(caught.value)
