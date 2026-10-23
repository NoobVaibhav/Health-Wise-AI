"""Compare a patient's laboratory results over time, parameter by parameter, using only what the reports say.

Rules (see the clinical-intelligence brief):
- the SAME parameter is compared, units are checked, and values are converted only with the few validated factors below;
- different units without a validated conversion = "Not comparable" (the original values are always kept);
- the reference range is the one printed on the laboratory report; if none was printed we say so and never guess one;
- "Improved" / "Worsened" are used only when the printed range supports it (back inside, newly outside, moving toward or away from
  the range). A change of direction alone is shown as Increased / Decreased with "needs clinical interpretation";
- a missing value is never treated as zero; duplicates are merged and conflicting values on one date are flagged."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models import HealthReport, Patient

# value in the FIRST unit x factor = value in the SECOND unit. Only widely accepted factors are listed.
CONVERSIONS = {
    ("glucose", "mg/dl", "mmol/l"): 1 / 18.016, ("glucose", "mmol/l", "mg/dl"): 18.016,
    ("creatinine", "mg/dl", "umol/l"): 88.4, ("creatinine", "umol/l", "mg/dl"): 1 / 88.4,
    ("hemoglobin", "g/dl", "g/l"): 10.0, ("hemoglobin", "g/l", "g/dl"): 0.1,
    ("cholesterol", "mg/dl", "mmol/l"): 1 / 38.67, ("cholesterol", "mmol/l", "mg/dl"): 38.67,
    ("triglycerides", "mg/dl", "mmol/l"): 1 / 88.57, ("triglycerides", "mmol/l", "mg/dl"): 88.57,
}
FAMILY = [("glucose", "glucose"), ("creatinine", "creatinine"), ("hemoglobin", "hemoglobin"), ("haemoglobin", "hemoglobin"),
          ("cholesterol", "cholesterol"), ("ldl", "cholesterol"), ("hdl", "cholesterol"), ("triglyceride", "triglycerides")]
OUTSIDE = ("ABOVE_RANGE", "BELOW_RANGE")


def unit_key(unit: str | None) -> str:
    return (unit or "").strip().lower().replace("µ", "u").replace("μ", "u").replace(" ", "")


def _family(name: str) -> str | None:
    lowered = name.lower()
    return next((fam for word, fam in FAMILY if word in lowered), None)


def convert(name: str, value: float, from_unit: str | None, to_unit: str | None) -> float | None:
    """The value in the other unit, or None when the two units cannot be compared with a validated factor."""
    a, b = unit_key(from_unit), unit_key(to_unit)
    if a == b:
        return value
    fam = _family(name)
    factor = CONVERSIONS.get((fam, a, b)) if fam else None
    return round(value * factor, 4) if factor else None


def _day(report: HealthReport):
    """(date, known): the printed report date, or the upload date flagged as 'not the test date'."""
    if report.report_date:
        return report.report_date, True
    return report.uploaded_at.date(), False


def _distance_outside(value: float, low: float | None, high: float | None) -> float | None:
    if low is None and high is None:
        return None
    if low is not None and value < low:
        return low - value
    if high is not None and value > high:
        return value - high
    return 0.0


def collect(db: Session, patient: Patient) -> list[dict]:
    """Every measurement of every parameter, oldest first. Duplicates (same day, value and unit) are merged."""
    reports = db.scalars(select(HealthReport).where(HealthReport.patient_id == patient.id)).all()
    reports.sort(key=lambda r: (_day(r)[0], r.id))
    by_name: dict[str, dict] = {}
    for r in reports:
        when, known = _day(r)
        for p in r.parameters:
            entry = by_name.setdefault(p.normalized_name, {"name": p.normalized_name, "points": [], "duplicates_removed": 0, "conflicts": []})
            point = {"report_id": r.id, "report_name": r.filename, "date": when.isoformat(), "date_known": known, "value": p.value, "unit": p.unit,
                     "status": p.status, "reference_text": p.reference_text, "reference_low": p.reference_low, "reference_high": p.reference_high,
                     "review_status": "REVIEWED" if r.doctor_review_status == "REVIEWED" else "WAITING_FOR_DOCTOR"}
            same_day = [q for q in entry["points"] if q["date"] == point["date"]]
            if any(q["value"] == point["value"] and unit_key(q["unit"]) == unit_key(point["unit"]) for q in same_day):
                entry["duplicates_removed"] += 1
                continue
            if same_day:
                entry["conflicts"].append(f"{point['date']}: {same_day[0]['value']} {same_day[0]['unit'] or ''} ({same_day[0]['report_name']}) and "
                                          f"{point['value']} {point['unit'] or ''} ({point['report_name']}) were both recorded.")
            entry["points"].append(point)
    return sorted(by_name.values(), key=lambda e: e["name"].lower())


def compare_points(name: str, prev: dict, latest: dict) -> dict:
    """The comparison row for the two newest measurements of one parameter."""
    base = {"parameter": name, "previous": prev, "latest": latest, "warnings": [], "converted": False}
    shown_prev = prev["value"]
    if unit_key(prev["unit"]) != unit_key(latest["unit"]):
        converted = convert(name, prev["value"], prev["unit"], latest["unit"])
        if converted is None:
            return {**base, "status": "NOT_COMPARABLE", "trend": None, "assessment": "NOT_COMPARABLE", "change": None, "change_percent": None,
                    "reference_range": latest["reference_text"] or "reference range not provided",
                    "interpretation": f"The units differ ({prev['unit'] or 'no unit'} and {latest['unit'] or 'no unit'}) and there is no validated conversion, so the two results are shown but not compared."}
        shown_prev = converted
        base["converted"] = True
        base["warnings"].append(f"The earlier value ({prev['value']} {prev['unit']}) was converted to {latest['unit']} with a standard factor to compare it.")
    if not prev["date_known"] or not latest["date_known"]:
        base["warnings"].append("At least one report has no printed test date. The upload date is used only for ordering; it is not the date of the test.")
    if unit_key(prev["unit"]) == unit_key(latest["unit"]) and (prev["reference_text"] or "") != (latest["reference_text"] or "") and prev["reference_text"] and latest["reference_text"]:
        base["warnings"].append(f"The two laboratories printed different reference ranges ({prev['reference_text']} and {latest['reference_text']}). The latest range is used.")

    change = round(latest["value"] - shown_prev, 4)
    pct = round(change / shown_prev * 100, 1) if shown_prev else None
    trend = "UNCHANGED" if change == 0 else "INCREASED" if change > 0 else "DECREASED"
    low, high = latest["reference_low"], latest["reference_high"]
    has_range = latest["status"] != "UNKNOWN" and (low is not None or high is not None)
    rng = latest["reference_text"] or "reference range not provided"
    row = {**base, "trend": trend, "change": change, "change_percent": pct, "reference_range": rng}
    unit = latest["unit"] or ""

    if not has_range:
        return {**row, "status": "NO_REFERENCE_RANGE", "assessment": "NEUTRAL",
                "interpretation": f"{trend.title()} from {shown_prev:g} to {latest['value']:g} {unit}. The report prints no reference range, so the direction alone does not show whether the change is favourable: clinical interpretation is needed."}
    prev_outside = prev["status"] in OUTSIDE if not base["converted"] else (_distance_outside(shown_prev, low, high) or 0) > 0
    now_outside = latest["status"] in OUTSIDE
    if prev_outside and not now_outside:
        return {**row, "status": "RETURNED_WITHIN_RANGE", "assessment": "IMPROVED",
                "interpretation": f"{shown_prev:g} was outside the printed range; {latest['value']:g} {unit} is now inside {rng}."}
    if not prev_outside and now_outside:
        return {**row, "status": "NEWLY_OUTSIDE_RANGE", "assessment": "WORSENED",
                "interpretation": f"{shown_prev:g} was inside the printed range; {latest['value']:g} {unit} is now outside {rng}."}
    if prev_outside and now_outside:
        d_prev, d_now = _distance_outside(shown_prev, low, high) or 0, _distance_outside(latest["value"], low, high) or 0
        if d_now < d_prev:
            return {**row, "status": "STILL_OUTSIDE_RANGE", "assessment": "IMPROVED", "moving": "toward",
                    "interpretation": f"Still outside {rng}, but closer to it: {shown_prev:g} to {latest['value']:g} {unit}."}
        if d_now > d_prev:
            return {**row, "status": "STILL_OUTSIDE_RANGE", "assessment": "WORSENED", "moving": "away",
                    "interpretation": f"Still outside {rng} and further from it: {shown_prev:g} to {latest['value']:g} {unit}."}
        return {**row, "status": "STILL_OUTSIDE_RANGE", "assessment": "STABLE", "moving": "same",
                "interpretation": f"Still outside {rng} by the same amount ({latest['value']:g} {unit})."}
    small = pct is not None and abs(pct) <= 5
    return {**row, "status": "WITHIN_RANGE", "assessment": "STABLE" if small else "NEUTRAL",
            "interpretation": f"Inside {rng} both times ({shown_prev:g} to {latest['value']:g} {unit})." + ("" if small else " The change stayed inside the range.")}


def analyse(db: Session, patient: Patient) -> dict:
    parameters, rows = [], []
    for entry in collect(db, patient):
        pts = entry["points"]
        units = {unit_key(p["unit"]) for p in pts}
        item = {"name": entry["name"], "unit": pts[-1]["unit"], "points": pts, "mixed_units": len(units) > 1,
                "duplicates_removed": entry["duplicates_removed"], "conflicts": entry["conflicts"], "comparison": None}
        if len(pts) >= 2:
            item["comparison"] = compare_points(entry["name"], pts[-2], pts[-1])
            rows.append(item["comparison"])
        else:
            only = pts[0]
            item["comparison"] = {"parameter": entry["name"], "previous": None, "latest": only, "status": "INSUFFICIENT_DATA", "trend": None, "assessment": "INSUFFICIENT_DATA",
                                  "change": None, "change_percent": None, "reference_range": only["reference_text"] or "reference range not provided", "warnings": [],
                                  "converted": False, "interpretation": "Only one result is available, so there is nothing to compare it with."}
        parameters.append(item)
    verdicts = {k: [r["parameter"] for r in rows if r["assessment"] == k] for k in ("IMPROVED", "WORSENED", "STABLE", "NEUTRAL", "NOT_COMPARABLE")}
    return {"parameters": parameters, "compared_count": len(rows), "groups": verdicts,
            "reports_considered": len(db.scalars(select(HealthReport.id).where(HealthReport.patient_id == patient.id)).all())}
