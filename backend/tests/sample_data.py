"""Synthetic lab reports used ONLY for tests / demo uploads. The application never reads these
values directly; it must extract them from the uploaded file like any other report."""
import io

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

REPORT_A_LINES = [
    "SYNTHETIC DEMO LABORATORY",
    "Patient Name: Rahul Patil",
    "Report Date: 03/07/2026",
    "",
    "BIOCHEMISTRY",
    "Test Name Result Unit Reference Range",
    "Glycosylated Hemoglobin (HbA1c) 7.2 % 4.0 - 5.6",
    "Total Cholesterol 215 mg/dL < 200",
    "LDL Cholesterol 148 mg/dL < 100",
    "HDL Cholesterol 38 mg/dL > 40",
    "Vitamin D 17 ng/mL 30 - 100",
    "Hemoglobin 13.9 g/dL 13.0 - 17.0",
]

REPORT_B_LINES = [
    "SYNTHETIC DEMO LABORATORY",
    "Patient Name: Rahul Patil",
    "Report Date: 06/10/2026",
    "",
    "BIOCHEMISTRY",
    "Test Name Result Unit Reference Range",
    "Glycosylated Hemoglobin (HbA1c) 6.8 % 4.0 - 5.6",
    "Total Cholesterol 186 mg/dL < 200",
    "LDL Cholesterol 118 mg/dL < 100",
    "HDL Cholesterol 44 mg/dL > 40",
    "Vitamin D 27 ng/mL 30 - 100",
    "Hemoglobin 14.2 g/dL 13.0 - 17.0",
]

# A different layout (no reference range for Vitamin D, vertical layout for TSH): proves the parser is not tied
# to one format. It is for ANOTHER patient name, to test the name-mismatch warning.
REPORT_C_LINES = [
    "Sample Diagnostics",
    "Patient Name: Sunita Kulkarni",
    "Collected On: 12 Jan 2026",
    "Fasting Blood Sugar: 92 mg/dL (70 - 99)",
    "Vitamin D",
    "27 ng/mL",
    "TSH",
    "2.1 uIU/mL",
    "Reference: 0.4 - 4.0",
    "Platelet Count 250000 /cumm 150000 - 410000",
]

# ---- reports that are NOT lab tables. The insight engine reads the wording itself.
CHEST_XRAY_LINES = [
    "SYNTHETIC RADIOLOGY CENTRE",
    "CHEST X-RAY PA VIEW",
    "Patient Name: Rahul Patil",
    "Report Date: 05/10/2026",
    "Clinical history: Cough for three weeks.",
    "Findings: Both lung fields are clear. No evidence of consolidation or pleural effusion.",
    "Cardiac silhouette is within normal limits. A 1.5 cm nodule is seen in the left lower zone.",
    "Impression: Left lower zone nodule. Further evaluation with CT chest is suggested.",
]

ECG_LINES = [
    "SYNTHETIC CARDIAC CARE",
    "12 LEAD ECG REPORT",
    "Patient Name: Rahul Patil",
    "Report Date: 04/10/2026",
    "Heart rate: 72 bpm. Rhythm: normal sinus rhythm. PR interval 160 ms, QRS 90 ms, QT interval normal.",
    "ST segment and T wave are unremarkable. Axis is normal.",
    "Impression: Normal ECG. No acute ischemic changes.",
]

DISCHARGE_LINES = [
    "SYNTHETIC GENERAL HOSPITAL",
    "DISCHARGE SUMMARY",
    "Patient Name: Rahul Patil",
    "Date of admission: 01/10/2026   Date of discharge: 03/10/2026",
    "Diagnosis: Acute gastroenteritis, treated and recovered.",
    "Hospital course: Admitted with vomiting and loose stools. Managed with fluids. Condition at discharge: stable.",
    "Advice on discharge: Take plenty of fluids and a light diet. Follow up in the outpatient clinic after one week.",
]

PRESCRIPTION_LINES = [
    "SYNTHETIC CLINIC",
    "Patient Name: Rahul Patil",
    "Rx",
    "Tab. Medicine A 500 mg twice daily after food for 5 days",
    "Cap. Medicine B 10 mg once daily before food for 7 days",
    "Dosage and duration as written. Review after one week.",
]

NOT_A_REPORT_LINES = [
    "Invoice #4521",
    "Thank you for shopping with us.",
    "Total amount due: 1500 rupees",
    "Please pay within 30 days.",
]


def lines_to_text(lines: list[str]) -> bytes:
    return "\n".join(lines).encode("utf-8")


def lines_to_pdf(lines: list[str]) -> bytes:
    """Create a text-based PDF (one text line per row)."""
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    y = 800
    for line in lines:
        pdf.drawString(50, y, line)
        y -= 18
    pdf.save()
    return buffer.getvalue()


def blank_scanned_pdf() -> bytes:
    """A PDF that contains only a drawn rectangle (no text layer) -> forces the OCR pathway."""
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.rect(100, 100, 300, 300)
    pdf.save()
    return buffer.getvalue()


def lines_to_png(lines: list[str]) -> bytes:
    """Render text onto an image (like a photographed/scanned report). Needs OCR to read."""
    from PIL import Image, ImageDraw, ImageFont

    image = Image.new("RGB", (1400, 60 + 40 * len(lines)), "white")
    draw = ImageDraw.Draw(image)
    try:
        font = ImageFont.truetype("arial.ttf", 28)
    except OSError:
        font = ImageFont.load_default()
    for i, line in enumerate(lines):
        draw.text((40, 30 + 40 * i), line, fill="black", font=font)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


if __name__ == "__main__":
    # python -m tests.sample_data  -> writes demo files to ../sample_reports
    from pathlib import Path

    out = Path(__file__).resolve().parents[2] / "sample_reports"
    out.mkdir(exist_ok=True)
    (out / "Report_A_July_Rahul.pdf").write_bytes(lines_to_pdf(REPORT_A_LINES))
    (out / "Report_B_October_Rahul.pdf").write_bytes(lines_to_pdf(REPORT_B_LINES))
    (out / "Report_C_other_patient.txt").write_bytes(lines_to_text(REPORT_C_LINES))
    (out / "Report_A_scan.png").write_bytes(lines_to_png(REPORT_A_LINES))
    (out / "Chest_Xray_Rahul.pdf").write_bytes(lines_to_pdf(CHEST_XRAY_LINES))
    (out / "ECG_Rahul.txt").write_bytes(lines_to_text(ECG_LINES))
    (out / "Discharge_Summary_Rahul.pdf").write_bytes(lines_to_pdf(DISCHARGE_LINES))
    (out / "Prescription_Rahul.txt").write_bytes(lines_to_text(PRESCRIPTION_LINES))
    (out / "Not_a_health_report.txt").write_bytes(lines_to_text(NOT_A_REPORT_LINES))
    print("Sample reports written to", out)
