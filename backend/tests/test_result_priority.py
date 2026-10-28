"""Which results matter first, and a summary made of the report's own content (not its page headers). All values are invented."""
import json

from app.services import insight_service as ins
from app.services.result_priority import prioritise, summary_text
from tests import sample_data as sd
from tests.conftest import upload


def item(name, value, low=None, high=None, unit="x", category=None):
    status = "UNKNOWN" if low is None and high is None else "BELOW_RANGE" if low is not None and value < low else "ABOVE_RANGE" if high is not None and value > high else "WITHIN_RANGE"
    return ins.LabItem(name, category, status, value, unit, low, high)


# ------------------------------------------------------------------ ranking of out-of-range values
def test_the_values_that_matter_come_first_and_small_ones_are_not_listed_as_equals():
    items = [item("Vitamin D", 8.98, 30, 100, "ng/mL", "vitamin"), item("Urea", 18.0, 19.3, 43, "mg/dL", "kidney"), item("WBC", 10570, 4000, 10000, "/cmm", "cbc"),
             item("HbA1c", 7.1, None, 5.7, "%", "glucose"), item("MPV", 14.0, 7.5, 10.3, "fL", "cbc"), item("Hemoglobin", 14.5, 13, 16.5, "g/dL", "cbc"),
             item("Triglycerides", 168, None, 150, "mg/dL", "lipid"), item("BUN", 8.41, 9.0, 20.0, "mg/dL", "kidney"), item("LDL", 100.39, None, 100, "mg/dL", "lipid")]
    p = prioritise(items)
    assert [e["name"] for e in p["important"]] == ["Vitamin D", "HbA1c", "Triglycerides"]                  # far or clearly outside, and key markers
    assert {e["name"] for e in p["slight"]} == {"Urea", "WBC", "MPV", "LDL"}                                  # a few percent out, or a minor test
    assert [e["name"] for e in p["derived"]] == ["BUN"]                                                       # calculated from urea: not listed on its own
    assert p["counts"] == {"normal": 1, "important": 3, "slight": 5, "no_range": 0}
    assert p["important"][0]["severity"] == "MARKED" and p["important"][0]["how_far"] == "about 70% below the lower limit" and p["important"][0]["direction"] == "LOW"
    assert p["important"][1]["severity"] == "MODERATE" and p["important"][2]["severity"] == "MILD"


def test_how_far_is_measured_from_the_printed_range_only():
    far = prioritise([item("Total IgE", 492.3, 0, 87, "IU/mL")])["important"][0]
    assert far["how_far"] == "about 5.7 times the upper limit" and far["range"] == "0 - 87"
    assert prioritise([item("Creatinine", 1.3, 0.66, 1.25, "mg/dL", "kidney")])["important"] == []           # 4% above the limit: only slightly outside
    assert prioritise([item("Sodium", 150, 136, 145, "mmol/L", "electrolyte")])["important"] == []           # 3% out: slight
    only_upper_bound = prioritise([item("Fasting Glucose", 141, 74, 106, "mg/dL", "glucose")])["important"][0]
    assert only_upper_bound["severity"] == "MODERATE" and only_upper_bound["range"] == "74 - 106"


def test_a_value_without_a_printed_range_is_never_ranked_or_guessed():
    p = prioritise([item("HDL", 60.0), item("Mean Blood Glucose", 157.0)])
    assert p["important"] == [] and p["slight"] == [] and p["no_range"] == ["HDL"] and p["counts"]["no_range"] == 2


# ------------------------------------------------------------------ the insights built from the ranking
def test_lab_insights_are_short_ranked_and_free_of_unrelated_text():
    items = [item("Vitamin D", 8.98, 30, 100, "ng/mL", "vitamin"), item("HbA1c", 7.1, None, 5.7, "%", "glucose"), item("Urea", 18.0, 19.3, 43, "mg/dL", "kidney"),
             item("WBC", 10570, 4000, 10000, "/cmm", "cbc"), item("MPV", 14.0, 7.5, 10.3, "fL", "cbc")]
    out = ins.build_lab_insights(items)
    texts = [f["text"] for f in out["key_findings"]]
    assert texts[0].startswith("Vitamin D") and texts[1].startswith("HbA1c") and len(texts) == 3                    # two important results, one line for the rest
    assert "Urea" in texts[2] and "WBC" in texts[2] and "MPV" in texts[2] and out["counts"] == {"normal": 0, "important": 2, "slight": 3, "no_range": 0}
    assert "2 results need attention first: Vitamin D, HbA1c" in out["doctor_suggestions"][0]
    assert all("blood count" not in s.lower() for s in out["doctor_suggestions"])                                   # minor blood-count deviations do not trigger a suggestion
    assert len(out["patient_recommendations"]) <= 8 and len(out["doctor_suggestions"]) <= 6 and out["engine"] >= 2
    assert "Look at these first: Vitamin D (much lower); HbA1c (clearly higher)" in out["summary"] and "2 results" not in out["summary"].split("Look at these first")[0]
    calm = ins.build_lab_insights([item("Hemoglobin", 14.5, 13, 16.5, "g/dL", "cbc")])
    assert calm["key_findings"] == [{"text": "Every value that has a printed range is inside it.", "concern": "normal"}] and calm["priority"] == []


def test_explanation_pages_of_a_lab_report_are_not_findings():
    text = ("Hemoglobin 14.5 g/dL 13.0 - 16.5\nWBC Count 10570 /cmm 4000 - 10000\n"
            "Interpretation:\nIncreased In : Chronic granulocytic leukemia , COPD and Chronic renal failure , Liver cell damage\n"
            "Limitations:\nHigh dose biotin can interfere with the assay.\nComments:\nMild leukocytosis is noted. Clinical correlation is advised.\n")
    findings, flags = ins.lab_comment_findings(text)
    joined = " ".join(f["text"] for f in findings)
    assert "leukemia" not in joined and "biotin" not in joined                                                      # what the test means in general is not about this patient
    assert "leukocytosis" in joined.lower()                                                                          # the lab's own comment is kept


# ------------------------------------------------------------------ a long ECG / Holter report
HOLTER = """Holter Report Of: Test Person [M, 70 Y]
MRD#NA Height: 158 cm Weight: 73 kg
Indications
Palpitations
Analysis Duration
48 hrs 10 mins
Heart Rate
Min
45 bpm Oct-05, 02:30
Max
118 bpm Oct-07, 00:57
Avg
66 bpm
Longest RR
1.40s Oct-04, 21:38
Total Beats 150000 Brady Beats 1000 (0.7%) Tachy Beats 20 (0.0%) Pauses(>2.5 Sec) 2
Ventricular Ectopics
Not Present
Supraventricular Ectopics
Total
Isolated
Couplet
Run Count
Beats in Run
Fastest Run
Longest Run
500 (0.3%)
400
50
3
12 (5.0s)
130 bpm Oct-07, 14:21
7 beats Oct-07, 14:15
Atrial Fibrillation
Not Present
Findings:
*Findings to be clinically correlated
The predominant rhythm was sinus rhythm. Supraventricular ectopic beats were noted in single and run forms.
Impression:
Interpreting Physician
Name
Signature and Date
Biosensor Id : XYZ Oct-08-2025, 07:51 Page 1 of 3
Test Device Copyright 2024 Example Medical Systems
Summary Daily Summary Strips Additional Information
Arrhythmia Summary
Patient: Test Person [M, 70 Y] , MRD#NA
SVPB Isolated Ectopics 1,178 Pairs 121 Run Beats 5
Biosensor Id : XYZ Oct-08-2025, 07:51 Page 2 of 3
Test Device Copyright 2024 Example Medical Systems
Summary Daily Summary Strips Additional Information
SVPB Isolated Ectopics 4,243 Pairs 256 Run Beats 3
Biosensor Id : XYZ Oct-08-2025, 07:51 Page 3 of 3
Test Device Copyright 2024 Example Medical Systems
Summary Daily Summary Strips Additional Information
SVPB Isolated Ectopics 2,670 Pairs 266 Run Beats 22
"""


def test_a_holter_report_gets_a_summary_made_of_its_content_not_its_page_footers():
    out = ins.build_narrative_insights(HOLTER, "ECG")
    summary = out["summary"]
    assert "Biosensor" not in summary and "Copyright" not in summary and "Signature" not in summary and "Page 1" not in summary
    assert "predominant rhythm was sinus rhythm" in summary                                                         # the real findings are used because the impression is empty


def test_the_holter_key_values_are_read_with_clear_labels_and_flagged_only_when_they_matter():
    facts = {m["label"]: m for m in ins.build_narrative_insights(HOLTER, "ECG")["metrics"]}
    assert facts["Lowest heart rate"]["value"] == 45 and facts["Lowest heart rate"]["concern"] == "neutral" and facts["Highest heart rate"]["value"] == 118
    assert facts["Average heart rate"]["value"] == 66 and facts["Longest gap between beats (RR)"]["value"] == 1.4 and facts["Total heartbeats recorded"]["value"] == 150000
    assert facts["Pauses longer than 2.5 seconds"]["value"] == 2 and facts["Pauses longer than 2.5 seconds"]["concern"] == "attention"
    assert facts["Ventricular ectopic beats"]["value"] == "None" and facts["Atrial fibrillation"]["value"] == "None" and facts["Atrial fibrillation"]["concern"] == "normal"
    assert facts["Runs of supraventricular beats"]["value"] == 3 and facts["Longest run"]["value"] == 7 and facts["Recording analysed"]["value"] == "48 hrs 10 mins"
    assert not any("Height" in label or "MRD" in label for label in facts)                                         # no junk labels
    flags = ins.build_narrative_insights(HOLTER, "ECG")["red_flags"]
    assert any("Pauses longer than 2.5 seconds: 2" in f for f in flags)


def test_a_measurement_repeated_every_day_is_one_card_and_event_counts_are_not_all_flagged():
    metrics = ins.extract_metrics("Daily summary\n" + "\n".join(f"SVPB Isolated Ectopics: {n}  Pairs: {p}  Run Beats: {r}" for n, p, r in ((1178, 121, 5), (4243, 256, 3), (2670, 266, 22))) + "\nSVT No. of episodes: 2\nMRD#NA Height: 158 cm\n")
    by_label = {m["label"]: m for m in metrics}
    assert len([m for m in metrics if m["label"] == "SVPB Isolated Ectopics"]) == 1 and by_label["SVPB Isolated Ectopics"]["value"] == 4243
    assert "3 readings in the report, from 1,178 to 4,243" in by_label["SVPB Isolated Ectopics"]["detail"]
    assert by_label["SVPB Isolated Ectopics"]["concern"] == "neutral" and by_label["Pairs"]["concern"] == "neutral"       # counts of single or paired beats are numbers, not alarms
    assert by_label["SVT No. of episodes"]["concern"] == "attention" and "Height" in by_label and "MRD#NA Height" not in by_label


def test_an_empty_impression_does_not_swallow_the_footer_and_header_lines_are_removed():
    sections = ins.split_sections(ins.clean_report_text(HOLTER))
    assert "impression" not in sections and "predominant rhythm" in sections["findings"] and "clinically correlated" not in sections["findings"]
    cleaned = ins.clean_report_text(HOLTER)
    assert "Biosensor" not in cleaned and "Copyright" not in cleaned and "Test Person" not in cleaned and "Palpitations" in cleaned


# ------------------------------------------------------------------ stored reports are upgraded when shown
def test_a_report_analysed_by_an_older_version_is_shown_with_the_new_ranking(client, world):
    from app.database.connection import SessionLocal
    from app.database.models import HealthReport
    text = sd.lines_to_text(["SYNTHETIC LAB", "Patient Name: Rahul Patil", "Report Date: 22/10/2026", "", "Test Name Result Unit Reference Range",
                             "Vitamin D 8.98 ng/mL 30 - 100", "Hemoglobin 14.5 g/dL 13.0 - 16.5", "MPV 14.0 fL 7.5 - 10.3", "Urea 18 mg/dL 19.3 - 43.0"])
    r = upload(client, world.employee, world.patient_id, "old.txt", text)
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    with SessionLocal() as db:                                                                                       # simulate a report saved before the ranking existed
        row = db.get(HealthReport, rid)
        old = json.loads(row.insights_json)
        for key in ("priority", "slightly_outside", "counts", "engine"):
            old.pop(key, None)
        row.insights_json = json.dumps(old)
        db.commit()
    shown = client.get(f"/api/reports/{rid}", headers=world.doctor).json()["insights"]
    assert shown["engine"] >= 2 and [e["name"] for e in shown["priority"]] == ["Vitamin D"] and shown["counts"]["slight"] == 2
    client.put(f"/api/doctor/reports/{rid}/review", headers=world.doctor, json={"decision": "APPROVED"})
    patient_view = client.get(f"/api/reports/{rid}", headers=world.patient).json()["insights"]
    assert [e["name"] for e in patient_view["priority"]] == ["Vitamin D"] and "doctor_suggestions" not in patient_view and "red_flags" not in patient_view     # patients see the ranking, not the doctor-only notes


def test_the_summary_on_screen_is_the_rebuilt_one_not_the_text_saved_by_an_older_version(client, world):
    from app.database.connection import SessionLocal
    from app.database.models import HealthReport
    r = upload(client, world.employee, world.patient_id, "ecg.txt", sd.lines_to_text(["Holter Report Of: Test Person [M, 70 Y]", "Findings:", "The predominant rhythm was sinus rhythm.", "Impression:", "Signature and Date",
                                                                                      "Biosensor Id : XYZ Oct-08-2025, 07:51 Page 1 of 3", "Heart Rate", "Min", "45 bpm Oct-05, 02:30", "Max", "118 bpm Oct-07, 00:57", "Avg", "66 bpm"]))
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    with SessionLocal() as db:
        row = db.get(HealthReport, rid)
        row.ai_summary = 'ECG. The report\'s own summary says: "Signature and Date Biosensor Id : XYZ Page 1 of 3"'
        old = json.loads(row.insights_json)
        old.pop("engine", None)
        row.insights_json = json.dumps(old)
        db.commit()
    shown = client.get(f"/api/reports/{rid}", headers=world.doctor).json()
    assert "Biosensor" not in shown["ai_summary"] and "predominant rhythm was sinus rhythm" in shown["ai_summary"]


def test_the_summary_is_also_given_as_short_points_for_lab_and_narrative_reports():
    from app.services.insight_service import build_lab_insights, build_narrative_insights
    out = build_lab_insights([item("Vitamin D", 8.98, 30, 100, "ng/mL", "vitamin"), item("HbA1c", 7.1, None, 5.7, "%", "glucose"), item("Urea", 18.0, 19.3, 43, "mg/dL", "kidney")])
    pts = out["summary_points"]
    assert 3 <= len(pts) <= 6 and all(p["text"] for p in pts)
    assert any(p.get("items") for p in pts) and "not a diagnosis" in pts[-1]["text"].lower()
    holter = build_narrative_insights("Holter report\nImpression: Sinus rhythm with first degree AV block.\nMax heart rate: 103 bpm", "ECG")
    assert len(holter["summary_points"]) >= 3 and "not a diagnosis" in holter["summary_points"][-1]["text"].lower()
