"""Small, focused tests for the pieces behind the multi-panel report fixes: names with commas and slashes, results without a printed range, the report date,
the ranking adjustments and the coverage warning for a section that cannot be parsed. All values are invented."""
from datetime import date

from app.services import insight_service as ins
from app.services.analysis_engine import STATUS_LABELS, analyze_parameters
from app.services.normalization_service import match_parameter_name
from app.services.report_parser import extract_parameters, extract_report_date
from app.services.report_processor import process_report
from app.services.result_priority import prioritise
from app.utils.text_cleaning import clean_text


def read(text: str):
    return {p.normalized_name: p for p in extract_parameters(clean_text(text))}


# ------------------------------------------------------------------ names with a comma or a slash
def test_a_test_name_with_a_comma_and_an_abbreviation_is_read():
    found = read("Hematocrit Value, Hct  H  56  %  40 - 50\nMean Corpuscular Volume, MCV  H  109.8  fL  83 - 101\nSerum Triiodothyronine, T3  2.10  ng/mL  0.69 - 2.15")
    assert (found["Hematocrit"].value, found["Hematocrit"].reference_text) == (56, "40 - 50")
    assert found["MCV"].value == 109.8 and found["T3"].value == 2.1
    assert match_parameter_name("Hematocrit Value, Hct 56 %").info.name == "Hematocrit"          # also when the comma is not removed by the text cleaning


def test_a_test_name_with_a_slash_is_read_as_the_ratio_not_as_its_first_word():
    found = read("LDL / HDL  L  0.64  1.5 - 3.5\nTotal Cholesterol/HDL  4.1  0 - 5\nLDL Cholesterol  80  mg/dl  0 - 100")
    assert found["LDL/HDL Ratio"].value == 0.64 and found["CHOL/HDL Ratio"].value == 4.1 and found["LDL"].value == 80
    assert "LDL" in found and found["LDL"].value != 0.64                                           # the ratio did not become the LDL value


def test_bilirubin_total_direct_and_indirect_are_never_merged():
    found = read("Serum Bilirubin (Total) 1.0 mg/dl 0.2 - 1.2\nSerum Bilirubin (Direct) 0.2 mg/dl 0 - 0.3\nSerum Bilirubin (Indirect) 0.80 mg/dl 0.2 - 1")
    assert {n: found[n].value for n in ("Bilirubin", "Direct Bilirubin", "Indirect Bilirubin")} == {"Bilirubin": 1.0, "Direct Bilirubin": 0.2, "Indirect Bilirubin": 0.8}
    assert match_parameter_name("Bilirubin - Direct 0.2").info.name == "Direct Bilirubin" and match_parameter_name("Serum Bilirubin Direct 0.2").info.name == "Direct Bilirubin"


def test_british_and_american_spellings_and_a_leading_specimen_word_match():
    assert match_parameter_name("Mean Cell Haemoglobin 27.5").info.name == "MCH"
    assert match_parameter_name("Mean Cell Haemoglobin CON, MCHC 25").info.name == "MCHC"
    assert match_parameter_name("Serum thyroxine T4 59").info.name == "T4" and match_parameter_name("Plasma Glucose 90").info.name == "Glucose"


# ------------------------------------------------------------------ no printed range
def test_a_numeric_result_with_no_printed_range_is_kept_and_never_judged():
    found = read("Serum Alkaline Phosphatase 67 U/L\nHemoglobin 14 g/dl 13 - 17")
    alp = found["ALP"]
    assert alp.value == 67 and alp.reference_text is None and alp.reference_low is None and alp.reference_high is None
    analysed = {a.extracted.normalized_name: a for a in analyze_parameters(list(found.values()))}
    assert analysed["ALP"].status == "UNKNOWN" and STATUS_LABELS["UNKNOWN"] == "No normal range"
    assert "does not print a normal range" in analysed["ALP"].explanation["what_this_means"]


# ------------------------------------------------------------------ the date
def test_the_collection_date_is_preferred_and_found_anywhere_in_the_text():
    far_down = "\n".join(["Hemoglobin 14 g/dl 13 - 17"] * 120 + ["Date: 20/05/2021", "Collected on: 14/05/2021  Reported on: 15/05/2021"])
    assert extract_report_date(far_down) == date(2021, 5, 14)                                      # after more than 80 lines, and "Collected on" wins over "Date"
    assert extract_report_date("Collected on:\n14/05/2021\nReported on:\n16/05/2021") == date(2021, 5, 14)       # one cell per line
    assert extract_report_date("Date of Birth: 01/01/1990\nDate: 03/02/2022") == date(2022, 2, 3)  # a birth date is never the test date
    assert extract_report_date("Hemoglobin 14 g/dl 13 - 17") is None


# ------------------------------------------------------------------ ranking
def item(name, value, low, high, category, unit="x"):
    status = "BELOW_RANGE" if low is not None and value < low else "ABOVE_RANGE" if high is not None and value > high else "WITHIN_RANGE"
    return ins.LabItem(name, category, status, value, unit, low, high)


def test_a_low_ldl_is_not_ranked_first_only_because_the_percentage_is_large():
    p = prioritise([item("LDL", 36, 85, 130, "lipid"), item("MCHC", 25, 31.5, 34.5, "cbc"), item("Creatinine", 0.5, 0.6, 1.1, "kidney")])
    assert [e["name"] for e in p["ranked"]] == ["MCHC", "Creatinine", "LDL"]
    assert p["ranked"][2]["percent_outside"] > 50 and p["ranked"][2]["adjusted"] is True
    high_ldl = prioritise([item("LDL", 190, 85, 130, "lipid"), item("MCHC", 25, 31.5, 34.5, "cbc")])
    assert high_ldl["ranked"][0]["name"] == "LDL"                                                  # a HIGH ldl keeps its full weight


def test_calculated_ratios_are_listed_after_the_measured_results_whatever_their_distance():
    p = prioritise([item("LDL/HDL Ratio", 0.2, 1.5, 3.5, "lipid"), item("WBC", 11000, 4000, 10000, "cbc"), item("TG/HDL Ratio", 9, None, 3, "lipid")])
    assert [e["name"] for e in p["ranked"]] == ["WBC", "TG/HDL Ratio", "LDL/HDL Ratio"] and [e["calculated"] for e in p["ranked"]] == [False, True, True]


# ------------------------------------------------------------------ doctor notes
def test_the_cardiovascular_note_needs_a_real_cardiovascular_finding():
    low_only = ins.build_lab_insights([item("LDL", 36, 85, 130, "lipid"), item("Total Cholesterol", 100, 125, 200, "lipid")])
    assert not any("cardiovascular" in s.lower() for s in low_only["doctor_suggestions"])
    high = ins.build_lab_insights([item("LDL", 190, 85, 130, "lipid")])
    assert any("cardiovascular" in s.lower() for s in high["doctor_suggestions"])
    low_hdl = ins.build_lab_insights([item("HDL", 20, 35, 80, "lipid")])
    assert any("cardiovascular" in s.lower() for s in low_hdl["doctor_suggestions"])


# ------------------------------------------------------------------ the coverage warning
MIXED = (
    "HAEMATOLOGY\nCOMPLETE BLOOD COUNT (CBC)\n"
    "TEST                         VALUE        UNIT        REFERENCE\n"
    "Hemoglobin                   14           g/dl        13 - 17\n"
    "Total Leukocyte Count        9,000        cumm        4,000 - 11,000\n"
    "Platelet Count               4.0          lakhs/cumm  1.5 - 4.5\n"
    "Serum Zorblax Factor         12.5         mg/dl       1 - 5\n"
    "\nCYTOLOGY\nFNAC (Fine Needle Aspiration)\nIMPRESSION : <IMPRESSION>\n")


def test_a_row_of_a_blood_panel_that_cannot_be_read_appears_in_the_coverage_warning():
    done = process_report("mixed.txt", MIXED.encode())
    coverage = done.insights["coverage"]
    assert coverage["complete"] is False and coverage["detected_rows"] == 4 and coverage["analysed_rows"] == 3
    assert [r["text"] for r in coverage["unread_rows"]] == ["Serum Zorblax Factor 12.5 mg/dl 1 - 5"]
    assert "could not be read" in coverage["message"] and "Zorblax" in coverage["message"]
    assert any("Zorblax" in p["text"] for p in done.insights["summary_points"]) and "Not the whole report was analysed" in done.summary
    assert [s["section"] for s in coverage["skipped_sections"]] == ["CYTOLOGY"]
    assert "Zorblax" not in " ".join(p.extracted.test_name for p in done.parameters)               # an unreadable row is never turned into a made-up result


def test_a_report_with_every_row_read_says_so():
    text = MIXED.split("Serum Zorblax")[0] + "\n"
    coverage = process_report("full.txt", text.encode()).insights["coverage"]
    assert coverage["complete"] is True and coverage["message"] == "All 3 printed result rows were analysed against the printed range."
