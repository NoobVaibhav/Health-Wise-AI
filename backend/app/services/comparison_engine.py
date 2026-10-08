"""Compare two reports parameter by parameter.

The trend is parameter-aware but never diagnostic:
1. If the report gives a reference range, we look at how far each value is from that range.
2. If there is no range but a general direction rule exists for the parameter (e.g. HbA1c/LDL: lower
   is generally preferred) we mention it as 'appears favorable', with a note.
3. Otherwise we only say the value 'changed' (we do NOT assume increase = bad or decrease = good).
"""
from app.database.models import HealthParameter
from app.services.analysis_engine import ABOVE, BELOW, UNKNOWN
from app.services.parameter_catalog import get_parameter_info
from app.services.report_parser import ParsedReference, parse_reference_text

IMPROVED = "IMPROVED"
STABLE = "STABLE"
INCREASED = "INCREASED"
DECREASED = "DECREASED"
STILL_OUTSIDE = "STILL_OUTSIDE_RANGE"
FOLLOW_UP = "REQUIRES_PROFESSIONAL_FOLLOW_UP"
UNDETERMINED = "UNABLE_TO_DETERMINE"

STABLE_THRESHOLD_PCT = 2.0     # smaller change than this is called stable when no range is known
IN_RANGE_STABLE_PCT = 5.0      # same, when both values are inside the range


def _distance_outside(value: float, ref: ParsedReference | None) -> float | None:
    """0 if inside the range, otherwise how far outside. None if there is no range."""
    if ref is None or (ref.low is None and ref.high is None):
        return None
    if ref.low is not None and value < ref.low:
        return ref.low - value
    if ref.high is not None and value > ref.high:
        return value - ref.high
    return 0.0


def compare_parameter(prev: HealthParameter, latest: HealthParameter) -> dict:
    change = round(latest.value - prev.value, 4)
    pct = round(change / prev.value * 100, 1) if prev.value else None
    direction = "up" if change > 0 else "down" if change < 0 else "same"

    base = {
        "parameter": latest.normalized_name,
        "unit": latest.unit,
        "previous": prev.value,
        "latest": latest.value,
        "change": change,
        "change_percent": pct,
        "reference_text": latest.reference_text,
        "latest_status": latest.status,
        "previous_status": prev.status,
    }

    if prev.unit and latest.unit and prev.unit.lower() != latest.unit.lower():
        return {**base, "trend": UNDETERMINED,
                "note": "The units differ between the two reports, so the values cannot be compared directly."}

    ref = parse_reference_text(latest.reference_text) if latest.reference_text else None
    prev_ref = parse_reference_text(prev.reference_text) if prev.reference_text else None
    ref = ref or prev_ref
    prev_dist = _distance_outside(prev.value, ref)
    latest_dist = _distance_outside(latest.value, ref)

    # --- 1. reference range available
    if prev_dist is not None and latest_dist is not None:
        if latest_dist == 0 and prev_dist > 0:
            return {**base, "trend": IMPROVED,
                    "note": "The value moved into the normal range printed on the lab report."}
        if latest_dist == 0 and prev_dist == 0:
            if pct is not None and abs(pct) <= IN_RANGE_STABLE_PCT:
                return {**base, "trend": STABLE, "note": "The value stayed inside the normal range."}
            trend = INCREASED if direction == "up" else DECREASED
            return {**base, "trend": trend, "note": "The value changed but stayed inside the normal range."}
        if latest_dist > 0 and prev_dist == 0:
            return {**base, "trend": FOLLOW_UP,
                    "note": "The value moved outside the normal range. Please talk to your "
                            "doctor about it."}
        # both outside the range
        if latest_dist < prev_dist:
            return {**base, "trend": STILL_OUTSIDE,
                    "note": "The value moved closer to the normal range but is still outside it."}
        if latest_dist > prev_dist:
            return {**base, "trend": FOLLOW_UP,
                    "note": "The value moved further from the normal range. Please talk to your "
                            "doctor about it."}
        return {**base, "trend": STILL_OUTSIDE, "note": "The value is still outside the normal range."}

    # --- 2. no range, but a general direction rule exists
    info = get_parameter_info(latest.normalized_name)
    if change == 0 or (pct is not None and abs(pct) < STABLE_THRESHOLD_PCT):
        return {**base, "trend": STABLE, "note": "The value is about the same as in the previous report."}
    if info and info.favorable_direction in ("up", "down"):
        if info.favorable_direction == direction:
            return {**base, "trend": IMPROVED,
                    "note": "Value changed compared with the previous report; the direction generally appears "
                            "favorable. This is a general rule, not a diagnosis."}
        return {**base, "trend": INCREASED if direction == "up" else DECREASED,
                "note": "Value changed compared with the previous report. Consider discussing the trend with a "
                        "healthcare professional."}

    # --- 3. unknown clinical direction
    trend = INCREASED if direction == "up" else DECREASED
    return {**base, "trend": trend, "note": "Changed compared with the previous result."}


def compare_reports(previous_params: list[HealthParameter], latest_params: list[HealthParameter]) -> list[dict]:
    """Match parameters by canonical name and compare them."""
    prev_by_name = {p.normalized_name: p for p in previous_params}
    rows = []
    for latest in latest_params:
        prev = prev_by_name.get(latest.normalized_name)
        if prev is not None:
            rows.append(compare_parameter(prev, latest))
    return rows
