"""The report-processing pipeline. It takes the bytes of an uploaded file and returns an analysis, or raises a typed
ReportError. It never returns demo/placeholder data and never touches the database (saving is done by the router
only after this succeeds).

Two kinds of reports are accepted:
1. LAB reports: values, units and printed reference ranges are extracted and classified by rules.
2. Any other MEDICAL report (X-ray, ECG, biopsy, discharge summary, prescription, clinical note ...): the text is
   read and summarised by the insight engine. Documents that are not medical at all (invoices, letters) are rejected.
Both kinds get "insights": suggestions for the doctor and general tips for the patient.
"""
from dataclasses import dataclass, field
from datetime import date

from app.core.errors import InvalidHealthReportError, UnreadableReportError
from app.services import insight_service, llm_service, ocr_service, pdf_service
from app.services.analysis_engine import AnalyzedParameter, analyze_parameters, build_summary
from app.services.report_parser import extract_parameters, extract_patient_name, extract_report_date
from app.utils.file_validation import detect_file_type, get_extension
from app.utils.text_cleaning import clean_text

MIN_CLEAN_TEXT_CHARS = 20


@dataclass
class ProcessedReport:
    text: str
    method: str                      # 'pdf_text' | 'ocr' | 'text'
    report_date: date | None
    parameters: list[AnalyzedParameter]
    summary: str
    patient_name: str | None = None   # name printed on the report (if found)
    report_type: str = "LAB"
    insights: dict = field(default_factory=dict)


def extract_text(filename: str, content: bytes) -> tuple[str, str]:
    """Step 1: get raw text out of the file. Returns (text, method)."""
    file_type = detect_file_type(filename, content)

    if file_type == "pdf":
        text = pdf_service.extract_pdf_text(content)
        if pdf_service.has_enough_text(text):
            return text, "pdf_text"
        # No text layer -> scanned PDF -> render pages and OCR them.
        images = pdf_service.render_pdf_pages(content)
        return ocr_service.run_ocr(images), "ocr"

    if file_type == "image":
        image = ocr_service.load_image(content)
        return ocr_service.run_ocr([image]), "ocr"

    # plain text / csv
    try:
        return content.decode("utf-8"), "text"
    except UnicodeDecodeError:
        return content.decode("latin-1"), "text"


def lab_items(analyzed: list[AnalyzedParameter]) -> list[insight_service.LabItem]:
    """Adapter: fresh analysis results -> the small records the insight engine works with."""
    from app.services.parameter_catalog import get_parameter_info
    items = []
    for a in analyzed:
        p = a.extracted
        info = get_parameter_info(p.normalized_name)
        items.append(insight_service.LabItem(p.normalized_name, info.category if info else None, a.status, p.value,
                                             p.unit, p.reference_low, p.reference_high))
    return items


def process_report(filename: str, content: bytes) -> ProcessedReport:
    raw_text, method = extract_text(filename, content)

    cleaned = clean_text(raw_text, is_csv=get_extension(filename) == "csv")
    if len(cleaned) < MIN_CLEAN_TEXT_CHARS:
        raise UnreadableReportError()

    if insight_service.looks_like_other_document(cleaned):
        raise InvalidHealthReportError()       # a project report, assignment, invoice or CV: wrong file

    parameters = extract_parameters(cleaned)
    # a single stray number is not enough: with fewer than two test results the file must still show signs of a report
    if parameters and (len(parameters) >= 2 or insight_service.has_report_signs(cleaned)):
        analyzed = analyze_parameters(parameters)
        summary = build_summary(analyzed)
        summary = llm_service.enhance_explanations(analyzed, summary)  # no-op when no LLM key
        report_type = "LAB"
        insights = insight_service.build_lab_insights(lab_items(analyzed))
        narrative = insight_service.build_narrative_insights(cleaned, "LAB")   # e.g. an impression written under the table
        if insight_service.split_sections(cleaned).keys() & set(insight_service.KEY_SECTIONS):
            insights["key_findings"] = insights["key_findings"] + [
                f for f in narrative["key_findings"] if f["concern"] != "neutral"][:6]
            insights["red_flags"] = insights["red_flags"] + narrative["red_flags"]
        insights["summary"] = summary
    else:
        # Not a lab table. Accept it only if it really looks like a medical document.
        if not insight_service.looks_medical(cleaned):
            raise InvalidHealthReportError()
        analyzed = []
        report_type = insight_service.detect_report_type(cleaned)
        insights = insight_service.build_narrative_insights(cleaned, report_type)
        summary = insights["summary"]

    insights = llm_service.enhance_insights(cleaned, report_type, insights)   # no-op when no LLM key
    if report_type != "LAB":
        summary = insights["summary"]

    return ProcessedReport(
        text=cleaned, method=method, report_date=extract_report_date(cleaned), parameters=analyzed, summary=summary,
        patient_name=extract_patient_name(cleaned), report_type=report_type, insights=insights,
    )
