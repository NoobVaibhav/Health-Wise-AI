"""Which out-of-range results matter most?

A report can have a dozen values slightly outside their printed range. Listing them all as equally important hides the few that matter.
The order is worked out from the report alone:
  1. HOW FAR each value is from the printed range, as a percentage of the nearest limit (a value 70% below the lower limit is very different from one 2% above the upper limit);
  2. two plain adjustments, both explained on the screen:
       - a value that is outside the range in the direction that is usually reassuring (a LOW LDL, LOW triglycerides, a HIGH HDL) counts for a quarter,
         so that it is not put first only because the percentage is large;
       - values CALCULATED from other results (ratios, VLDL, Non-HDL, BUN) are listed after the directly measured ones, because they repeat what the measured values already say.
It never decides what a result means for the patient and never uses anything but the range printed on the report: it only orders the list."""
from app.services.parameter_catalog import get_parameter_info

# worked out from other values on the report: they repeat what the measured values already say
DERIVED = {"Mean Blood Glucose", "VLDL", "BUN", "CHOL/HDL Ratio", "LDL/HDL Ratio", "TG/HDL Ratio", "Non-HDL Cholesterol", "Urea/Creatinine Ratio", "BUN/Creatinine Ratio",
           "A/G Ratio", "Indirect Bilirubin", "Delta Bilirubin", "Globulin", "Transferrin Saturation"}

MARKED, MODERATE, MILD = 0.5, 0.15, 0.0            # how far outside the range (as a fraction of the nearest limit)
REASSURING_FACTOR = 0.25                           # weight of a deviation in the direction that is usually reassuring
REASSURING_CATEGORIES = {"lipid"}                  # only here: a low blood sugar, for example, is never treated as reassuring
DEGREE = {"MARKED": "much", "MODERATE": "clearly", "MILD": "slightly"}


def is_reassuring_direction(item) -> bool:
    """True for a result that is outside the range in the direction that is generally favourable (low LDL / triglycerides, high HDL, high eGFR)."""
    info = get_parameter_info(item.name)
    if info is None or info.favorable_direction is None:
        return False
    if item.category not in REASSURING_CATEGORIES and item.name != "eGFR":
        return False
    return (item.status == "BELOW_RANGE" and info.favorable_direction == "down") or (item.status == "ABOVE_RANGE" and info.favorable_direction == "up")


def rank_score(item, dev: float) -> float:
    """Percent distance from the printed range, with the reassuring-direction adjustment."""
    return round(dev * 100 * (REASSURING_FACTOR if is_reassuring_direction(item) else 1.0), 2)


def deviation(item) -> float:
    """How far outside the printed range, as a fraction of the nearest limit (0.7 = 70% beyond it)."""
    if item.status == "ABOVE_RANGE" and item.high is not None:
        base = abs(item.high) or ((item.high - item.low) if item.low is not None else 1.0) or 1.0
        return max(0.0, (item.value - item.high) / base)
    if item.status == "BELOW_RANGE" and item.low is not None:
        base = abs(item.low) or ((item.high - item.low) if item.high is not None else 1.0) or 1.0
        return max(0.0, (item.low - item.value) / base)
    return 0.0


def severity(dev: float) -> str:
    return "MARKED" if dev >= MARKED else "MODERATE" if dev >= MODERATE else "MILD"


def range_text(item) -> str:
    if item.low is not None and item.high is not None:
        return f"{item.low:g} - {item.high:g}"
    if item.high is not None:
        return f"below {item.high:g}"
    if item.low is not None:
        return f"above {item.low:g}"
    return "not printed"


def how_far(item, dev: float) -> str:
    if item.status == "ABOVE_RANGE":
        return f"about {item.value / item.high:.1f} times the upper limit" if item.high and item.value >= 2 * item.high else f"about {dev * 100:.0f}% above the upper limit"
    return f"about {dev * 100:.0f}% below the lower limit"


def _entry(item, dev: float, sev: str) -> dict:
    info = get_parameter_info(item.name)
    unit = f" {item.unit}" if item.unit else ""
    direction = "HIGH" if item.status == "ABOVE_RANGE" else "LOW"
    degree = DEGREE[sev]
    return {"name": item.name, "value": item.value, "unit": item.unit, "range": range_text(item), "direction": direction, "severity": sev, "how_far": how_far(item, dev),
            "category": item.category, "meaning": info.meaning if info else None,
            "text": f"{item.name}: {item.value:g}{unit} is {degree} {'higher' if direction == 'HIGH' else 'lower'} than the normal range ({range_text(item)})",
            "percent_outside": round(dev * 100, 1), "score": rank_score(item, dev), "calculated": item.name in DERIVED,
            "adjusted": is_reassuring_direction(item)}


def prioritise(items: list) -> dict:
    """Splits the results into: important (look at first), slight (outside the range by a little), derived (calculated from other results),
    no_range, and counts. `ranked` is every outside result in one order: measured results by score, then calculated ones by score."""
    important, slight, derived, no_range, normal = [], [], [], [], 0
    for item in items:
        if item.status == "WITHIN_RANGE":
            normal += 1
        elif item.status == "UNKNOWN":
            no_range.append(item.name)
        elif item.status in ("ABOVE_RANGE", "BELOW_RANGE"):
            dev = deviation(item)
            sev = severity(dev)
            entry = _entry(item, dev, sev)
            if item.name in DERIVED:
                derived.append(entry)
            elif sev in ("MARKED", "MODERATE"):
                important.append(entry)
            else:
                slight.append(entry)
    for group in (important, slight, derived):
        group.sort(key=lambda e: -e["score"])
    ranked = sorted(important + slight, key=lambda e: -e["score"]) + derived
    for number, entry in enumerate(ranked, start=1):
        entry["rank"] = number
    return {"important": important, "slight": slight, "derived": derived, "ranked": ranked, "no_range": no_range,
            "counts": {"normal": normal, "important": len(important), "slight": len(slight) + len(derived), "no_range": len(no_range)}}


def coverage_sentence(coverage: dict | None) -> str | None:
    """One sentence saying what was NOT analysed; None when the whole report was (or when nothing is known about it)."""
    if not coverage or coverage.get("complete", True):
        return None
    return f"{coverage.get('headline', 'Not the whole report was analysed')}: " + coverage.get("message", "")


def summary_points(items: list, coverage: dict | None = None) -> list[dict]:
    """The same summary as a few short points for the screen and the PDF: [{"text": ..., "items": [...optional sub-points]}]."""
    p = prioritise(items)
    total, c = len(items), p["counts"]
    out = c["important"] + c["slight"]
    first = f"{total} test result{'s' if total != 1 else ''} read: {c['normal']} normal, {out} outside the printed range"
    first += f", {c['no_range']} with no printed range." if c["no_range"] else "."
    points = [{"text": first}]
    if p["important"]:
        points.append({"text": "Look at these first (most important first):",
                       "items": [f"{e['name']}: {e['value']:g}{(' ' + e['unit']) if e['unit'] else ''}, {DEGREE[e['severity']]} {'higher' if e['direction'] == 'HIGH' else 'lower'} than normal ({e['range']})"
                                 for e in p["important"][:6]]})
    else:
        points.append({"text": "No result is far outside its printed range."})
    minor = p["slight"] + p["derived"]
    if minor:
        names = ", ".join(e["name"] for e in minor[:8]) + (f" and {len(minor) - 8} more" if len(minor) > 8 else "")
        points.append({"text": f"{len(minor)} other{'s are' if len(minor) != 1 else ' is'} only slightly outside the range, or minor: {names}."})
    if p["no_range"]:
        points.append({"text": f"No normal range is printed for {', '.join(p['no_range'][:6])}{' and more' if len(p['no_range']) > 6 else ''}. Ask the doctor, who can check it against the lab's own comments."})
    note = coverage_sentence(coverage)
    if note:
        points.append({"text": note})
    points.append({"text": "This is not a diagnosis. A doctor must review these results."})
    return points


def summary_text(items: list, coverage: dict | None = None) -> str:
    """One plain paragraph: what was read, what to look at first, what is only slightly outside."""
    p = prioritise(items)
    total, c = len(items), p["counts"]
    out = c["important"] + c["slight"]
    text = f"The computer read {total} test result{'s' if total != 1 else ''}. {c['normal']} {'is' if c['normal'] == 1 else 'are'} inside the printed range"
    text += f" and {out} {'is' if out == 1 else 'are'} outside it" if out else ", and none is outside it"
    text += f"; {c['no_range']} {'has' if c['no_range'] == 1 else 'have'} no printed range." if c["no_range"] else "."
    if p["important"]:
        top = p["important"][:6]
        text += " Look at these first: " + "; ".join(f"{e['name']} ({DEGREE[e['severity']]} {'higher' if e['direction'] == 'HIGH' else 'lower'})" for e in top) + "."
    if p["slight"] or p["derived"]:
        names = [e["name"] for e in (p["slight"] + p["derived"])][:8]
        text += f" {len(p['slight']) + len(p['derived'])} other{'s are' if len(p['slight']) + len(p['derived']) != 1 else ' is'} only slightly outside the range or minor ({', '.join(names)})."
    note = coverage_sentence(coverage)
    if note:
        text += " " + note
    text += " This is not a diagnosis; a doctor must review these results."
    if p["no_range"]:
        text += f" No normal range is printed for: {', '.join(p['no_range'][:6])}; the doctor should check these against the lab's own comments."
    return text
