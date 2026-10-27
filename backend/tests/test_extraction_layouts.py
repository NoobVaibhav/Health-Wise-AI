"""Layouts of real commercial laboratory reports: a method column, the result printed LAST after unit and range(s), labelled range tiers,
glued flags, long reports. All values here are invented."""
import io

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from app.services.report_parser import extract_parameters, parse_reference_text
from app.services.report_processor import merge_parameters, process_report
from app.utils.text_cleaning import clean_text

HEAD = "LABORATORY TEST REPORT\nPatient Name : Test Person\nCollected on : 20-Feb-2023 08:53\nTest Result Unit Biological Ref. Interval\n"


def found(text):
    return {p.normalized_name: p for p in extract_parameters(clean_text(text))}      # the same cleaning step the upload pipeline runs first


# ------------------------------------------------------------------ method column between the test name and the result
def test_a_method_column_between_name_and_value_is_read():
    got = found(HEAD + "Hemoglobin Colorimetric 14.5 g/dL 13.0 - 16.5\nRBC Count Electrical impedance 4.79 million/cmm 4.5 - 5.5\nMCV Derived 90.3 fL 83 - 101\n"
                       "ESR Capillary photometry 7 mm/1hr 0 - 14\nNeutrophils Microscopic 73 % 40 - 80\n")
    assert [(k, p.value, p.unit, p.reference_text) for k, p in got.items()] == [
        ("Hemoglobin", 14.5, "g/dL", "13.0 - 16.5"), ("RBC", 4.79, "million/cmm", "4.5 - 5.5"), ("MCV", 90.3, "fL", "83 - 101"), ("ESR", 7.0, "mm/1hr", "0 - 14"), ("Neutrophils", 73.0, "%", "40 - 80")]


def test_a_flag_letter_glued_to_the_method_or_between_method_and_value_is_not_part_of_the_value():
    got = found(HEAD + "WBC Count SF Cube cell analysisH 10570 /cmm 4000 - 10000\nMPV Calculated H 14.00 fL 7.5 - 10.3\nHb A L 84.4 % 96.8 - 97.8\n")
    assert got["WBC"].value == 10570 and got["WBC"].unit == "/cmm" and got["MPV"].value == 14.0 and got["MPV"].unit == "fL" and got["HbA"].value == 84.4


def test_units_are_never_split_by_the_flag_repair():
    got = found(HEAD + "Hemoglobin g/dL 13.0 - 16.5Colorimetric 14.5\nCreatinine mg/dL 0.66 - 1.25 0.83\n")
    assert got["Hemoglobin"].unit == "g/dL" and got["Creatinine"].unit == "mg/dL"


# ------------------------------------------------------------------ the result comes last, after unit, range(s) and method
def test_the_result_printed_last_after_unit_range_and_method_is_read_in_every_arrangement():
    one_line = found(HEAD + "VLDL mg/dL 15 - 35Calculated 33.60\nCHOL/HDL Ratio Up to 5.0Calculated 3.1\nTSH - Thyroid Stimulating Hormone microIU/mL 0.35 - 4.94Chemiluminescence 0.8199\n")
    assert one_line["VLDL"].value == 33.6 and one_line["VLDL"].reference_text == "15 - 35" and one_line["CHOL/HDL Ratio"].value == 3.1 and one_line["CHOL/HDL Ratio"].reference_text == "< 5.0"
    assert one_line["TSH"].value == 0.8199 and one_line["TSH"].unit == "microIU/mL"
    separate_lines = found(HEAD + "Total Protein g/dL 6.3 - 8.2\nCopper tartrate to colour complex\n7.00\nAlbumin g/dL 3.5 - 5.0\nBromocresol Green Method\n4.20\n")
    assert separate_lines["Total Protein"].value == 7.0 and separate_lines["Albumin"].value == 4.2 and separate_lines["Albumin"].reference_text == "3.5 - 5.0"
    flagged = found(HEAD + "Fasting Blood Sugar H mg/dL 74 - 106\nGOD-POD\n141.0\nUrea L mg/dL 19.3 - 43.0Urease, Colorimetric 18.0\n")
    assert flagged["Fasting Glucose"].value == 141.0 and flagged["Urea"].value == 18.0


def test_a_method_line_that_starts_with_a_test_word_does_not_end_the_block():
    got = found(HEAD + "Cholesterol mg/dL Desirable : <200\nBorderline High : 200-239\nHigh : >240\nCholesterol oxidase - Peroxidase method\n189.0\nCreatinine, Serum mg/dL 0.66 - 1.25Creatinine Amidohydrolase 0.83\n")
    assert got["Total Cholesterol"].value == 189.0 and got["Total Cholesterol"].reference_text == "< 200" and got["Creatinine"].value == 0.83


def test_a_range_printed_before_the_result_without_a_unit_is_read():
    got = found("Physical & Chemical examination\nurine routine\npH 4.6 - 8.0\nDouble indicator\n6.0\nSpecific Gravity 1.005 - 1.030\nPolyelectrolyte based reaction\n1.020\n")
    assert got["Urine pH"].value == 6.0 and got["Urine pH"].reference_text == "4.6 - 8.0" and got["Specific Gravity"].value == 1.02


def test_a_paragraph_or_a_year_after_a_test_name_is_not_taken_as_a_result():
    got = found(HEAD + "Calcium mg/dL is a mineral measured in many studies since\nthe year 2023\nHemoglobin 13.5 g/dL 13.0 - 17.0\n")
    assert "Calcium" not in got and got["Hemoglobin"].value == 13.5


def test_a_count_range_is_not_a_value_and_less_than_results_are_still_skipped():
    got = found("Urine routine examination\nPus Cells 1-2 Absent\nRBC Nil /hpf 0 - 2\nCreatinine 0.9 mg/dL 0.66 - 1.25\n")
    assert "Urine WBC" not in got and got["Creatinine"].value == 0.9
    assert "Vitamin B12" not in found(HEAD + "Vitamin B12 L pg/mL 187 - 833\nCLIA\n< 148\n")                       # a result "below the detection limit" is not an exact number


# ------------------------------------------------------------------ several labelled ranges
def test_only_a_range_labelled_normal_is_used_when_several_are_printed():
    assert parse_reference_text("Desirable : <200 Borderline High : 200-239 High : >240").text == "< 200"
    assert parse_reference_text("Normal : <150 Borderline : 150-199 High : 200-499 Very High : >500").text == "< 150"
    assert parse_reference_text("Optimal: <100 Near to above Optimal: 100-129 Borderline High: 130-159").text == "< 100"             # "near to above optimal" is not optimal
    assert parse_reference_text("Deficiency : <10 Insufficiency : 10 - 30 Sufficiency : 30 - 100 Toxicity : >100").text == "30 - 100"
    assert parse_reference_text("For Screening: Diabetes: >6.5% Pre-Diabetes: 5.7% - 6.4% Non-Diabetes: < 5.7% Poor Control : > 7.0 %").text == "< 5.7"
    assert parse_reference_text("Non Reactive : <1.0 Reactive : >1.0").text == "< 1.0"


def test_when_no_printed_range_says_normal_no_range_is_guessed():
    """HDL printed as 'Low: <40  High: >60': a result of 60 must NOT be flagged high because of the first number."""
    unknown = parse_reference_text("Low: <40.0 High: >60.0")
    assert unknown.low is None and unknown.high is None and "Low" in unknown.text
    got = found(HEAD + "HDL Cholesterol mg/dL Low: <40.0\nHigh: >60.0 PTA/MgCl2\n60.0\n")
    assert got["HDL"].value == 60.0
    from app.services.analysis_engine import classify_status
    assert classify_status(60.0, parse_reference_text(got["HDL"].reference_text)) == "UNKNOWN"
    assert parse_reference_text("Children : >16 Adult : 20 - 50").low is None                                                       # age groups: not guessed either


# ------------------------------------------------------------------ whole documents
BLOCK_REPORT = HEAD + """Hemoglobin g/dL 13.0 - 16.5Colorimetric 14.5
WBC Count H /cmm 4000 - 10000SF Cube cell analysis 10570
Cholesterol mg/dL Desirable : <200
Borderline High : 200-239
High : >240
Cholesterol oxidase - Peroxidase method
189.0
Triglyceride H mg/dL Normal : <150
Borderline : 150-199
High : 200-499
Enzymatic (Lipase/GK/GPO/POD)
168.0
Fasting Blood Sugar H mg/dL 74 - 106
GOD-POD
141.0
Sodium (Na+) mmol/L 136 - 145
Direct- ISE
143.00
25(OH) Vitamin D ng/mL Deficiency : <10
Insufficiency : 10 - 30
Sufficiency : 30 - 100
CLIA
8.98
"""


def pdf_of(lines_per_page: list[list[str]]) -> bytes:
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    for lines in lines_per_page:
        y = 800
        for line in lines:
            c.drawString(40, y, line)
            y -= 14
        c.showPage()
    c.save()
    return buffer.getvalue()


def test_a_pdf_in_the_value_last_layout_is_read_completely():
    result = process_report("report.pdf", pdf_of([BLOCK_REPORT.splitlines()]))
    got = {p.extracted.normalized_name: p for p in result.parameters}
    assert {"Hemoglobin", "WBC", "Total Cholesterol", "Triglycerides", "Fasting Glucose", "Sodium", "Vitamin D"} <= set(got)
    assert got["Hemoglobin"].status == "WITHIN_RANGE" and got["WBC"].status == "ABOVE_RANGE" and got["Total Cholesterol"].status == "WITHIN_RANGE"
    assert got["Triglycerides"].status == "ABOVE_RANGE" and got["Triglycerides"].extracted.reference_text == "< 150" and got["Fasting Glucose"].status == "ABOVE_RANGE"
    assert got["Vitamin D"].status == "BELOW_RANGE" and got["Vitamin D"].extracted.reference_text == "30 - 100" and got["Sodium"].extracted.value == 143.0


def test_every_page_of_a_long_report_is_read_not_only_the_first_fifteen():
    pages = [BLOCK_REPORT.splitlines()[:6]] + [[f"Filler page {i}", "Nothing to see here"] for i in range(2, 19)] + [["Hb A L 84.4 % 96.8 - 97.8", "Hb A2 2.8 % 2.2 - 3.2"]]
    assert len(pages) == 19
    got = {p.extracted.normalized_name: p.extracted.value for p in process_report("long.pdf", pdf_of(pages)).parameters}
    assert got["Hemoglobin"] == 14.5 and got["HbA"] == 84.4 and got["HbA2"] == 2.8                  # tests printed on page 19 are found


def test_two_readings_of_a_pdf_are_merged_without_replacing_a_found_value():
    first = extract_parameters(HEAD + "Hemoglobin Colorimetric 14.5 g/dL 13.0 - 16.5\n")
    second = extract_parameters(HEAD + "Hemoglobin Colorimetric 9.9 g/dL 13.0 - 16.5\nMCV Derived 90.3 fL 83 - 101\n")
    merged = {p.normalized_name: p.value for p in merge_parameters(first, second)}
    assert merged == {"Hemoglobin": 14.5, "MCV": 90.3}                                             # the new test is added; the value already found is kept


def test_the_patient_name_stops_at_the_next_label_of_the_report_header():
    from app.services.report_parser import extract_patient_name
    assert extract_patient_name("Name : Lyu Bochka Lab Id Client Name : City Lab\n") == "Lyu Bochka"
    assert extract_patient_name("Patient Name: Rahul Patil   Age: 28\n") == "Rahul Patil"
