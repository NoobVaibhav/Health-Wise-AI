"""Unit tests: text extraction, parameter parsing, reference ranges, status rules, invalid files."""
import pytest

from app.core.errors import InvalidHealthReportError, OCRUnavailableError, UnsupportedFileError
from app.services import report_processor
from app.services.analysis_engine import ABOVE, BELOW, UNKNOWN, WITHIN, classify_status
from app.services.report_parser import (
    extract_parameters, extract_patient_name, extract_report_date, names_match, parse_reference_text,
)
from app.utils.text_cleaning import clean_text
from tests import sample_data as sd


def parse(lines):
    return {p.normalized_name: p for p in extract_parameters(clean_text("\n".join(lines)))}


# ---------- reference range parsing
@pytest.mark.parametrize("text,low,high", [
    ("4.0 - 5.6", 4.0, 5.6), ("4.0–5.6", 4.0, 5.6), ("30 - 100 ng/mL", 30, 100),
    ("< 100", None, 100), ("> 40", 40, None), ("Ref: 0.4 - 4.0", 0.4, 4.0),
])
def test_reference_parsing(text, low, high):
    ref = parse_reference_text(clean_text(text))
    assert (ref.low, ref.high) == (low, high)


def test_reference_none_when_absent():
    assert parse_reference_text("") is None
    assert parse_reference_text("ng/mL") is None


# ---------- status rules
def test_range_classification():
    ref = parse_reference_text("10 - 20")
    assert classify_status(15, ref) == WITHIN
    assert classify_status(25, ref) == ABOVE
    assert classify_status(5, ref) == BELOW
    assert classify_status(10, ref) == WITHIN and classify_status(20, ref) == WITHIN


def test_less_than_classification():
    ref = parse_reference_text("< 100")
    assert classify_status(80, ref) == WITHIN
    assert classify_status(120, ref) == ABOVE
    assert classify_status(100, ref) == ABOVE  # '<' is strict


def test_greater_than_classification():
    ref = parse_reference_text("> 40")
    assert classify_status(50, ref) == WITHIN
    assert classify_status(30, ref) == BELOW


def test_unknown_when_no_reference():
    assert classify_status(27, None) == UNKNOWN


# ---------- parameter extraction
def test_extracts_value_unit_reference():
    params = parse(sd.REPORT_A_LINES)
    hba1c = params["HbA1c"]
    assert (hba1c.value, hba1c.unit, hba1c.reference_low, hba1c.reference_high) == (7.2, "%", 4.0, 5.6)
    assert hba1c.test_name == "Glycosylated Hemoglobin"  # original text preserved
    assert params["LDL"].value == 148 and params["LDL"].reference_high == 100
    assert params["HDL"].reference_low == 40


def test_different_layout_and_missing_reference():
    params = parse(sd.REPORT_C_LINES)
    assert params["Fasting Glucose"].value == 92 and params["Fasting Glucose"].reference_high == 99
    assert params["Vitamin D"].value == 27 and params["Vitamin D"].reference_text is None  # never invented
    assert params["TSH"].value == 2.1 and params["TSH"].reference_high == 4.0  # vertical layout
    assert params["Platelets"].value == 250000


def test_ratio_line_is_not_misread():
    assert "Total Cholesterol" not in parse(["Total Cholesterol / HDL Cholesterol Ratio 4.1"])


def test_urine_section_context():
    params = parse(["URINE ROUTINE EXAMINATION", "Protein 1.0 mg/dL", "pH 6.0 4.6 - 8.0"])
    assert "Urine Protein" in params and "Urine pH" in params


def test_report_date_and_patient_name():
    assert str(extract_report_date("Report Date: 06/10/2026")) == "2026-10-06"
    assert extract_report_date("no date here") is None
    assert extract_patient_name(clean_text("\n".join(sd.REPORT_A_LINES))) == "Rahul Patil"
    assert names_match("RAHUL PATIL", "Rahul Patil") and names_match("Mr. Rahul Patil", "Rahul S. Patil")
    assert not names_match("Sunita Kulkarni", "Rahul Patil")


# ---------- pipeline
def test_text_pdf_is_read_without_ocr():
    result = report_processor.process_report("a.pdf", sd.lines_to_pdf(sd.REPORT_A_LINES))
    assert result.method == "pdf_text" and result.patient_name == "Rahul Patil"
    names = {p.extracted.normalized_name: p for p in result.parameters}
    assert names["HbA1c"].status == ABOVE and names["HDL"].status == BELOW


def test_scanned_pdf_uses_ocr_pathway(monkeypatch):
    called = {}

    def fake_ocr(images):
        called["pages"] = len(images)
        return "\n".join(sd.REPORT_B_LINES)

    monkeypatch.setattr(report_processor.ocr_service, "run_ocr", fake_ocr)
    result = report_processor.process_report("scan.pdf", sd.blank_scanned_pdf())
    assert result.method == "ocr" and called["pages"] == 1
    assert {p.extracted.normalized_name for p in result.parameters} >= {"HbA1c", "LDL"}


def test_image_uses_ocr_pathway(monkeypatch):
    monkeypatch.setattr(report_processor.ocr_service, "run_ocr", lambda imgs: "\n".join(sd.REPORT_A_LINES))
    assert report_processor.process_report("photo.png", sd.lines_to_png(["x"])).method == "ocr"


def test_ocr_unavailable_error(monkeypatch):
    from app.services import ocr_service
    monkeypatch.setattr(ocr_service, "ocr_is_available", lambda: False)
    with pytest.raises(OCRUnavailableError):
        report_processor.process_report("scan.pdf", sd.blank_scanned_pdf())


def test_invalid_document_rejected():
    with pytest.raises(InvalidHealthReportError):
        report_processor.process_report("invoice.txt", sd.lines_to_text(sd.NOT_A_REPORT_LINES))


def test_unsupported_and_fake_files_rejected():
    with pytest.raises(UnsupportedFileError):
        report_processor.process_report("virus.exe", b"MZ....")
    with pytest.raises(UnsupportedFileError):
        report_processor.process_report("fake.pdf", b"this is not a pdf")
    with pytest.raises(UnsupportedFileError):
        report_processor.process_report("fake.png", b"not an image")


def test_different_files_give_different_results():  # the most important rule: no demo data
    a = report_processor.process_report("a.pdf", sd.lines_to_pdf(sd.REPORT_A_LINES))
    b = report_processor.process_report("b.pdf", sd.lines_to_pdf(sd.REPORT_B_LINES))
    value = lambda r, n: next(p.extracted.value for p in r.parameters if p.extracted.normalized_name == n)
    assert value(a, "HbA1c") == 7.2 and value(b, "HbA1c") == 6.8


# ---------- real-world layouts (regression tests for bugs found in manual testing)
@pytest.mark.parametrize("line,name,value,low,high", [
    ("Total Leucocyte Count (TLC) 6,500 cells/cu.mm 4,000 - 11,000", "WBC", 6500, 4000, 11000),  # thousands separator
    ("Platelet Count 250,000 /cumm 150,000 - 410,000", "Platelets", 250000, 150000, 410000),
    ("Haemoglobin (Hb) 13.5 g/dL 13.0 - 17.0", "Hemoglobin", 13.5, 13.0, 17.0),
    ("Hemoglobin : 13.5 g/dL (13.0-17.0)", "Hemoglobin", 13.5, 13.0, 17.0),
    ("TOTAL CHOLESTEROL, SERUM 190 mg/dL Desirable: <200", "Total Cholesterol", 190, None, 200),
    ("Triglycerides 210 H mg/dL < 150", "Triglycerides", 210, None, 150),            # flag between value and unit
    ("LDL CHOLESTEROL - DIRECT 110 mg/dL Optimal: <100", "LDL", 110, None, 100),
    ("25-OH VITAMIN D (TOTAL) 18.2 ng/mL 30 - 100", "Vitamin D", 18.2, 30, 100),
    ("S. Creatinine 0.9 mg/dL 0.7 - 1.3", "Creatinine", 0.9, 0.7, 1.3),
    ("SGPT (ALT) 32 U/L 7 - 56", "ALT", 32, 7, 56),
    ("Fasting Plasma Glucose (FPG) 98 mg/dL 70 - 100", "Fasting Glucose", 98, 70, 100),
    ("BILIRUBIN, TOTAL 0.8 mg/dL 0.3 - 1.2", "Bilirubin", 0.8, 0.3, 1.2),
    ("eGFR (CKD-EPI) 92 mL/min/1.73m2 > 90", "eGFR", 92, 90, None),
    ("HbA1c 6.8 % HPLC 4.0 - 5.6", "HbA1c", 6.8, 4.0, 5.6),                        # method column
    ("Hemoglobin\n13.5\ng/dL\n13.0 - 17.0", "Hemoglobin", 13.5, 13.0, 17.0),         # one column per line
])
def test_real_world_layouts(line, name, value, low, high):
    p = parse([line])[name]
    assert (p.value, p.reference_low, p.reference_high) == (value, low, high)


def test_normal_white_cell_count_is_not_flagged():
    """Before the fix a normal WBC count was read against the range '0 - 11' and shown as HIGH."""
    result = report_processor.process_report("cbc.txt", sd.lines_to_text(
        ["Patient Name: Test Person", "Total Leucocyte Count 6,500 /cumm 4,000 - 11,000"]))
    assert result.parameters[0].status == WITHIN


def test_hba1c_without_printed_range_is_extracted_as_unknown():
    text = ("HBA1C (GLYCATED HEMOGLOBIN) , WHOLE BLOOD EDTA\n"
            "HBA1C, GLYCATED HEMOGLOBIN 7.2 % HPLC\n"
            "ESTIMATED AVERAGE GLUCOSE (eAG) 160 mg/dL Calculated\n")
    params = {p.normalized_name: p for p in extract_parameters(text)}
    assert params["HbA1c"].value == 7.2
    assert params["HbA1c"].unit == "%"
    assert params["HbA1c"].reference_text is None


def test_report_date_prefers_collected_date_with_slash_month():
    from datetime import date
    text = ("Collected : 04/Jun/2026 09:22AM\nReceived : 05/Jun/2026 12:36PM\n"
            "Reported : 06/Jun/2026 02:54PM\n")
    assert extract_report_date(text) == date(2026, 6, 4)


def test_decimal_commas_are_read_as_decimals_not_cut_off():
    """A laboratory that prints 5,6 for 5.6 must not become 5 with no unit (a silently wrong value)."""
    from app.services.report_processor import process_report
    text = "Report Date: 05/10/2026\nTest Result Unit Reference\nGlucose Fasting 5,6 mmol/L 3,9 - 5,6\nCreatinine 1,1 mg/dL 0,7 - 1,3\nTotal Cholesterol 1,200 mg/dL < 200\n"
    found = {p.extracted.normalized_name: p.extracted for p in process_report("eu.txt", text.encode()).parameters}
    assert found["Fasting Glucose"].value == 5.6 and found["Fasting Glucose"].unit == "mmol/L" and found["Fasting Glucose"].reference_text == "3.9 - 5.6"
    assert found["Creatinine"].value == 1.1 and found["Creatinine"].reference_text == "0.7 - 1.3"
    assert found["Total Cholesterol"].value == 1200            # a thousands separator is not a decimal comma
    indian = "Report Date: 05/10/2026\nTest Result Unit Reference\nPlatelets 1,50,000 /cumm 150000 - 410000\nHemoglobin 13.1 g/dL 13.0 - 17.0\n"
    assert {p.extracted.normalized_name: p.extracted.value for p in process_report("in.txt", indian.encode()).parameters}["Platelets"] == 150000     # Indian grouping 1,50,000


def test_separate_male_and_female_ranges_are_never_guessed():
    """With two printed ranges and an unknown sex, the value is left 'reference range unavailable' and the printed text is kept."""
    from app.services.report_processor import process_report
    text = "Report Date: 05/10/2026" + chr(10) + "Test Result Unit Reference" + chr(10) + "Hemoglobin 12.5 g/dL Male: 13.0 - 17.0 Female: 12.0 - 15.5" + chr(10) + "Vitamin D 25 ng/mL 30 - 100" + chr(10)
    found = {p.extracted.normalized_name: p for p in process_report("sex.txt", text.encode()).parameters}
    hb = found["Hemoglobin"]
    assert hb.status == "UNKNOWN" and "Male" in hb.extracted.reference_text and "Female" in hb.extracted.reference_text
    assert found["Vitamin D"].status == "BELOW_RANGE"           # an ordinary single range still works
