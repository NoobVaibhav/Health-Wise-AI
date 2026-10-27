"""Which out-of-range results matter most?

A report can have a dozen values slightly outside their printed range. Listing them all as equally important hides the few that matter.
Each out-of-range value is scored from two things only, both visible in the report:
  1. HOW FAR it is from the printed range (a value 70% below the lower limit is very different from one 2% above the upper limit);
  2. HOW IMPORTANT the test usually is (blood sugar, haemoglobin, kidney and liver markers, vitamin D ... against minor or calculated values such as MPV, VLDL or a ratio).
It never decides what a result means for the patient and never uses anything but the range printed on the report: it only orders the list."""
from app.services.parameter_catalog import get_parameter_info

# 3 = key marker doctors look at first, 2 = ordinary (the default), 1 = minor
KEY = {"HbA1c", "Fasting Glucose", "Random Glucose", "Glucose", "Hemoglobin", "WBC", "Platelets", "Creatinine", "eGFR", "Potassium", "Sodium", "Calcium", "ALT", "AST", "ALP",
       "Bilirubin", "Direct Bilirubin", "TSH", "Free T3", "Free T4", "T3", "T4", "Vitamin D", "Vitamin B12", "Total Cholesterol", "LDL", "Triglycerides", "Uric Acid",
       "Homocysteine", "PSA", "Iron"}
MINOR = {"MCV", "MCH", "MCHC", "RDW", "MPV", "Basophils", "Monocytes", "Eosinophils", "HbF", "Chloride"}
# worked out from other values on the report: they repeat what the measured values already say
DERIVED = {"Mean Blood Glucose", "VLDL", "BUN", "CHOL/HDL Ratio", "LDL/HDL Ratio", "A/G Ratio", "Indirect Bilirubin", "Delta Bilirubin", "Globulin", "Transferrin Saturation",
           "MCH", "MCHC"}

MARKED, MODERATE, MILD = 0.5, 0.15, 0.0            # how far outside the range (as a fraction of the nearest limit)
IMPORTANT_MILD_KEY = 0.08                          # a key marker only slightly outside the range still counts when it is at least this far out
DEGREE = {"MARKED": "much", "MODERATE": "clearly", "MILD": "slightly"}


def weight(name: str) -> int:
    return 3 if name in KEY else 1 if name in MINOR or name in DERIVED else 2


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
            "score": round(weight(item.name) * (1 + 3 * min(dev, 1.5)), 2)}


def prioritise(items: list) -> dict:
    """Splits the results into: important (look at first, most important first), slight (outside the range by a little or minor tests),
    derived (calculated from others, not listed on their own), no_range, and counts."""
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
            w = weight(item.name)
            if item.name in DERIVED:
                derived.append(entry)
            elif sev == "MARKED" or (sev == "MODERATE" and w >= 2) or (sev == "MILD" and w == 3 and dev >= IMPORTANT_MILD_KEY):
                important.append(entry)
            else:
                slight.append(entry)
    important.sort(key=lambda e: -e["score"])
    slight.sort(key=lambda e: -e["score"])
    return {"important": important, "slight": slight, "derived": derived, "no_range": [n for n in no_range if n not in DERIVED],
            "counts": {"normal": normal, "important": len(important), "slight": len(slight) + len(derived), "no_range": len(no_range)}}


def summary_text(items: list) -> str:
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
    text += " This is not a diagnosis; a doctor must review these results."
    if p["no_range"]:
        text += f" No normal range is printed for: {', '.join(p['no_range'][:6])}; the doctor should check these against the lab's own comments."
    return text
