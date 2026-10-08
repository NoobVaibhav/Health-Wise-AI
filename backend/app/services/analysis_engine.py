"""Deterministic analysis: decides WITHIN / ABOVE / BELOW / UNKNOWN by comparing the value with the
reference range printed in the report. No AI is involved in this decision."""
from dataclasses import dataclass

from app.services.parameter_catalog import get_parameter_info
from app.services.report_parser import ExtractedParameter, ParsedReference, parse_reference_text

WITHIN = "WITHIN_RANGE"
ABOVE = "ABOVE_RANGE"
BELOW = "BELOW_RANGE"
UNKNOWN = "UNKNOWN"

STATUS_LABELS = {
    WITHIN: "Within provided range",
    ABOVE: "Above provided range",
    BELOW: "Below provided range",
    UNKNOWN: "Reference range unavailable",
}


def classify_status(value: float, reference: ParsedReference | None) -> str:
    """Core rule engine.
    - range  'a - b'  : below a -> BELOW, above b -> ABOVE, otherwise WITHIN
    - '< b'           : value >= b -> ABOVE (value == b is ABOVE for '<', WITHIN for '<=')
    - '> a'           : value <= a -> BELOW (value == a is BELOW for '>', WITHIN for '>=')
    - no range        : UNKNOWN (we never invent a range)."""
    if reference is None or (reference.low is None and reference.high is None):
        return UNKNOWN
    if reference.low is not None:
        too_low = value < reference.low or (value == reference.low and not reference.low_inclusive)
        if too_low:
            return BELOW
    if reference.high is not None:
        too_high = value > reference.high or (value == reference.high and not reference.high_inclusive)
        if too_high:
            return ABOVE
    return WITHIN


@dataclass
class AnalyzedParameter:
    extracted: ExtractedParameter
    status: str
    explanation: dict


def build_explanation(param: ExtractedParameter, status: str) -> dict:
    """Template (non-AI) explanation. Never diagnoses; only describes the value vs the printed range."""
    info = get_parameter_info(param.normalized_name)
    meaning = info.meaning if info else "This is a laboratory measurement listed in your report."
    why = info.why_it_matters if info else "Doctors review it together with your other results."

    unit = f" {param.unit}" if param.unit else ""
    ref = param.reference_text or "not provided"
    if status == WITHIN:
        interpretation = (f"The result ({param.value:g}{unit}) is inside the normal range printed on the lab report "
                          f"({ref}).")
        follow_up = "Your doctor will review this result with the rest of your report."
    elif status == ABOVE:
        interpretation = (f"The result ({param.value:g}{unit}) is higher than the normal range printed on the lab report "
                          f"({ref}). A result outside the normal range does not by itself mean there is a health problem.")
        follow_up = "Please discuss this result with your doctor."
    elif status == BELOW:
        interpretation = (f"The result ({param.value:g}{unit}) is lower than the normal range printed on the lab report "
                          f"({ref}). A result outside the normal range does not by itself mean there is a health problem.")
        follow_up = "Please discuss this result with your doctor."
    else:
        interpretation = (f"The result is {param.value:g}{unit}. The lab report does not print a normal range for this test, "
                          "so we cannot say whether it is normal.")
        follow_up = "Please ask your doctor how to interpret this value."

    return {
        "simple": meaning,
        "what_this_means": interpretation,
        "why_it_matters": why,
        "follow_up": follow_up,
    }


def analyze_parameters(params: list[ExtractedParameter]) -> list[AnalyzedParameter]:
    analyzed = []
    for param in params:
        reference = parse_reference_text(param.reference_text) if param.reference_text else None
        status = classify_status(param.value, reference)
        analyzed.append(AnalyzedParameter(param, status, build_explanation(param, status)))
    return analyzed


def build_summary(analyzed: list[AnalyzedParameter]) -> str:
    """Deterministic one-paragraph summary of the report, in plain language."""
    counts = {s: sum(1 for a in analyzed if a.status == s) for s in (WITHIN, ABOVE, BELOW, UNKNOWN)}
    outside = [a.extracted.normalized_name for a in analyzed if a.status in (ABOVE, BELOW)]

    def count(n: int, singular: str, plural: str) -> str:
        return f"{n} {singular if n == 1 else plural}"

    total = len(analyzed)
    text = (f"The computer found {count(total, 'test result', 'test results')} in this report. "
            f"{count(counts[WITHIN], 'is', 'are')} in the normal range, "
            f"{count(counts[ABOVE], 'is', 'are')} higher than normal, "
            f"{count(counts[BELOW], 'is', 'are')} lower than normal and "
            f"{count(counts[UNKNOWN], 'has', 'have')} no normal range printed on the report.")
    if outside:
        text += (" Results outside the normal range: " + ", ".join(outside) +
                 ". This is not a diagnosis; a doctor must review these results.")
    return text
