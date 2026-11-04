"""Regression test on a real 8-page multi-panel laboratory report (invented patient "Mr. Dummy"): blood count, liver, kidney, lipid and thyroid panels,
plus Widal, semen examination, an unfilled FNAC template and a Mantoux test.

It protects the fixes that were made after the first run read only 28 of 39 ranged results: names with a trailing abbreviation or a slash, bilirubin kept
as three results, tests without a printed range, results of non-blood sections shown as printed, the coverage check, the test date, the ranking, the
report's own interpretation table as a separate note, and the doctor notes. The same numbers must appear on every screen, so the API output is checked too."""
import pathlib

import pytest

from app.services.report_processor import process_report
from tests.conftest import upload

SAMPLE = pathlib.Path(__file__).parent / "fixtures" / "kamal_diagnostic_sample_report.pdf"


@pytest.fixture(scope="module")
def processed():
    return process_report(SAMPLE.name, SAMPLE.read_bytes())


def by_name(processed):
    return {a.extracted.normalized_name: a for a in processed.parameters}


# ------------------------------------------------------------------ what is read
def test_every_result_row_is_read_39_with_a_printed_range_and_5_without(processed):
    ranged = [a for a in processed.parameters if a.extracted.reference_low is not None or a.extracted.reference_high is not None]
    unranged = [a for a in processed.parameters if a not in ranged]
    assert len(ranged) == 39 and len(unranged) == 5 and len(processed.parameters) == 44
    assert {a.extracted.normalized_name for a in unranged} == {"ALP", "Urea/Creatinine Ratio", "BUN/Creatinine Ratio", "TG/HDL Ratio", "Non-HDL Cholesterol"}
    assert all(a.status == "UNKNOWN" for a in unranged)                       # never Normal, High or Low without a printed range


def test_29_are_normal_and_10_are_outside_the_printed_range(processed):
    named = lambda status: {a.extracted.normalized_name for a in processed.parameters if a.status == status}
    assert len(named("WITHIN_RANGE")) == 29
    assert named("ABOVE_RANGE") == {"WBC", "Lymphocytes", "Hematocrit", "MCV"}
    assert named("BELOW_RANGE") == {"MCHC", "Total Protein", "Creatinine", "LDL", "LDL/HDL Ratio", "CHOL/HDL Ratio"}


def test_the_names_with_an_abbreviation_a_slash_or_a_comma_are_all_found(processed):
    found = by_name(processed)
    for name in ("Hematocrit", "MCV", "MCH", "MCHC", "T3", "T4", "TSH", "LDL/HDL Ratio", "CHOL/HDL Ratio"):
        assert name in found, f"{name} was not extracted"
    assert found["Hematocrit"].extracted.value == 56 and found["MCHC"].extracted.value == 25.0 and found["TSH"].extracted.value == 3.0
    assert found["LDL/HDL Ratio"].extracted.value == 0.64 and found["CHOL/HDL Ratio"].extracted.value == 2.32


def test_total_direct_and_indirect_bilirubin_stay_separate(processed):
    found = by_name(processed)
    assert (found["Bilirubin"].extracted.value, found["Direct Bilirubin"].extracted.value, found["Indirect Bilirubin"].extracted.value) == (1.0, 0.2, 0.8)


def test_the_test_date_is_the_collection_date(processed):
    assert processed.report_date.isoformat() == "2021-05-14"


# ------------------------------------------------------------------ what is shown as printed, and what is not analysed
def test_widal_semen_and_mantoux_are_shown_as_printed_without_a_verdict(processed):
    other = processed.insights["other_results"]
    titles = {r["title"] for r in other}
    assert {"Widal Test (Slide Method)", "Semen Examination", "Mantoux test"} <= titles
    assert len(other) == 22
    by_test = {r["name"]: r for r in other}
    assert by_test["Salmonella Typhi 'O'"]["value"] == "1:20" and by_test["RESULTS"]["value"] == "Negative" and by_test["Colour"]["value"] == "Whitish"
    assert by_test["Total Sperm Count"]["reference"] == "60 - 200" and by_test["Total Sperm Count"]["value"] == "155"
    assert all("status" not in r for r in other)                                    # no Normal / High / Low on these rows
    assert not any(a.extracted.normalized_name in ("RBC", "Urine RBC") and a.extracted.value == 1 for a in processed.parameters)   # the semen "R.B.C. 01 /HPF" is not a blood count


def test_the_unfilled_fnac_template_is_not_a_result_and_is_reported_as_not_analysed(processed):
    everything = " ".join(a.extracted.test_name for a in processed.parameters) + " ".join(r["name"] for r in processed.insights["other_results"])
    assert "SPECIMEN" not in everything.upper() and "IMPRESSION" not in everything.upper() and "<" not in everything
    skipped = processed.insights["coverage"]["skipped_sections"]
    assert len(skipped) == 1 and "FNAC" in skipped[0]["section"] and "template" in skipped[0]["reason"]


def test_the_coverage_never_claims_the_whole_report_was_analysed(processed):
    c = processed.insights["coverage"]
    assert c["detected_rows"] == 66 and c["analysed_rows"] == 44 and c["printed_only_rows"] == 22 and c["unread_rows"] == [] and c["complete"] is False
    assert "44 of 66" in c["message"] and "Semen Examination" in c["message"] and "FNAC" in c["message"]
    assert "Not the whole report was analysed" in processed.summary                    # the short summary says it too
    assert any(p["text"].startswith("Not the whole report was analysed") for p in processed.insights["summary_points"])


# ------------------------------------------------------------------ ranking and notes
def test_ranking_is_by_distance_from_the_printed_range_with_calculated_values_last(processed):
    ranked = [e["name"] for e in processed.insights["ranked"]]
    assert ranked.index("MCHC") < ranked.index("Creatinine") < ranked.index("WBC") and ranked.index("MCHC") < ranked.index("WBC")
    assert ranked[0] == "MCHC" and ranked[0] != "LDL"                               # the low LDL (58% out) is not put first only because of its percentage
    assert ranked[-2:] == ["LDL/HDL Ratio", "CHOL/HDL Ratio"]                      # calculated ratios come after every measured result
    top = [e["name"] for e in processed.insights["priority"]]
    assert top == ["MCHC", "Creatinine", "LDL"]


def test_the_reports_own_interpretation_table_is_a_note_and_never_changes_the_status(processed):
    found = by_name(processed)
    ldl, tg = found["LDL"], found["Triglycerides"]
    assert ldl.status == "BELOW_RANGE" and "lists LDL below 100 mg/dl as Optimal" in ldl.explanation["table_note"]
    assert tg.status == "WITHIN_RANGE" and "lists Triglycerides 150-199 mg/dl as Borderline High" in tg.explanation["table_note"]
    assert {n["name"] for n in processed.insights["interpretation_notes"]} == {"Total Cholesterol", "Triglycerides", "LDL"}


def test_doctor_notes_have_no_cardiovascular_risk_note_for_a_low_ldl_and_a_blood_count_note_without_a_diagnosis(processed):
    notes = " ".join(processed.insights["doctor_suggestions"])
    assert "cardiovascular" not in notes.lower()
    blood = next(n for n in processed.insights["doctor_suggestions"] if n.startswith("Red blood cell values"))
    assert "Hematocrit (high)" in blood and "MCV (high)" in blood and "MCHC (low)" in blood and "does not suggest a diagnosis" in blood
    tips = " ".join(processed.insights["patient_recommendations"]).lower()
    assert "heart" not in tips and "cholesterol" not in tips                           # no lipid advice for a low LDL alone


# ------------------------------------------------------------------ one set of numbers everywhere
def test_the_api_shows_the_same_results_counts_summary_and_date_on_every_screen(client, world):
    r = upload(client, world.employee, world.patient_id, SAMPLE.name, SAMPLE.read_bytes(), world.doctor_id)
    assert r.status_code == 201, r.text
    report = client.get(f"/api/reports/{r.json()['id']}", headers=world.doctor).json()
    assert report["report_date"] == "2021-05-14" and len(report["parameters"]) == 44
    assert report["counts"] == {"WITHIN_RANGE": 29, "ABOVE_RANGE": 4, "BELOW_RANGE": 6, "UNKNOWN": 5}
    insights = report["insights"]
    assert insights["counts"]["normal"] == 29 and insights["counts"]["no_range"] == 5 and insights["counts"]["important"] + insights["counts"]["slight"] == 10
    assert "44 test results" in report["ai_summary"] and report["ai_summary"] == insights["summary"]
    assert insights["coverage"]["analysed_rows"] == len(report["parameters"])
    assert next(p for p in report["parameters"] if p["normalized_name"] == "ALP")["status_label"] == "No normal range"
    assert "not a diagnosis" in report["ai_summary"].lower() and report["disclaimer"]
    # the date drives the comparison and trend views
    patient_reports = client.get(f"/api/reports?patient_id={world.patient_id}", headers=world.doctor).json()
    assert patient_reports[0]["report_date"] == "2021-05-14"
