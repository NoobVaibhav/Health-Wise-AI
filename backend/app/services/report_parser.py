"""Turns cleaned report text into structured parameters (name, value, unit, reference range).

How it works (good to explain in your viva):
1. Go through the text line by line.
2. A line is a candidate only if it STARTS with a known test name (see parameter_catalog.py).
3. After the name we read: value -> optional unit -> optional reference range.
4. If the value / reference is on the following lines (vertical layouts) we look ahead a few lines.
5. The reference range is read ONLY from the report itself. If it is missing, it stays missing.
"""
import re
from dataclasses import dataclass
from datetime import date

from app.services.normalization_service import match_parameter_name, skip_own_names
from app.utils.clock import hospital_today

# A number, with optional thousands separators (also Indian grouping): 4000, 4,000, 1,50,000, 11,000.5, 5.6
NUMBER = r"(?:\d{1,2}(?:,\d{2})+,\d{3}(?:\.\d+)?|\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
VALUE_RE = re.compile(rf"([<>]?)\s*({NUMBER})")
RANGE_RE = re.compile(rf"({NUMBER})\s*(?:-|to)\s*({NUMBER})", re.IGNORECASE)
LESS_RE = re.compile(rf"(<=|<|≤|upto|up to|less than|below)\s*({NUMBER})", re.IGNORECASE)
GREATER_RE = re.compile(rf"(>=|>|≥|more than|greater than|above)\s*({NUMBER})", re.IGNORECASE)
REF_LABEL_RE = re.compile(
    r"(?:biological\s+)?(?:ref(?:erence)?\.?\s*(?:range|interval|value)?s?|normal(?:\s+range)?|range)\s*[:=]?",
    re.IGNORECASE,
)
RANGE_LIKE_START = re.compile(rf"^\(?\s*(?:{NUMBER}\s*-\s*\d|[<>≤≥])")
FLAG_RE = re.compile(r"^(?:HH|LL|H|L|High|Low|Critical|\*)(?=\s+\S)", re.IGNORECASE)
UNIT_RE = re.compile(
    r"^(?:x?10\^?\d+\s*/\s*[A-Za-zµ0-9.]+|%|[A-Za-zµ/][A-Za-zµ0-9^*./]*)"
)
NOT_UNITS = {"ref", "reference", "normal", "range", "high", "low", "h", "l", "result", "to", "method", "flag",
             "up", "upto", "less", "more", "below", "above", "biological"}
SIMPLE_UNITS = {"fl", "pg", "g", "mg", "ng", "ug", "µg", "u", "iu", "mm", "mmol", "meq"}
ALLOWED_GAP_WORDS = re.compile(
    r"\b(?:result|value|levels?|count|calc(?:ulated)?|direct|method|hplc|enzymatic|serum|plasma|blood|"
    r"fasting|random|pp|ppbs|post|prandial|glycated|glycosylated|h(?:a)?emoglobin|whole|edta)\b",
    re.IGNORECASE,
)
# The "method" column of many laboratory reports sits between the test name and the value
# (e.g. "Hemoglobin Colorimetric 14.5 g/dL 13.0 - 17.0"). These words are harmless in the gap; a flag letter may also stand there.
METHOD_WORDS = re.compile(
    r"\b(?:colorimetric|photometr\w*|spectrophotometr\w*|impedance|electrical|capillary|microscopic|derived|calculated|cube|cell|analysis|sf|flow|"
    r"cytometry|uv|kinetic|turbidimetric|immunoturbidimetric|chemiluminescence|clia|ise|jaffe|god-pod|gpo|pod|nephelometr\w*|ecl|elisa|"
    r"assay|by|automated|manual|counter|laser|optical|wet|prep|visual|dip|strip|[HL])\b",
    re.IGNORECASE,
)

# the units laboratories print; used to recognise the "unit first" column layout
_UNITS = ["mg/dL", "g/dL", "µg/dL", "ug/dL", "mcg/dL", "ng/dL", "pg/dL", "mmol/L", "µmol/L", "umol/L", "micromol/L", "mol/L", "mEq/L", "g/L", "mg/L", "µg/L", "ug/L",
          "ng/mL", "pg/mL", "µg/mL", "mg/mL", "µIU/mL", "uIU/mL", "microIU/mL", "mIU/mL", "mIU/L", "IU/L", "IU/mL", "U/L", "U/mL", "KU/L", "S/Co", "/cmm", "/cumm", "/µL", "/uL",
          "/mm3", "/hpf", "/lpf", "million/cmm", "million/cumm", "million/µL", "mill/cumm", "thou/cumm", "10^3/µL", "10^6/µL", "x10^3/µL", "fL", "pg", "mm/1hr", "mm/hr", "mm/h",
          "%", "sec", "seconds", "mL/min/1.73m2", "mL/min", "kg/m2", "cells/µL", "micro g/dL", "micro g/mL"]
UNIT_KNOWN = re.compile(r"(?i:" + "|".join(re.escape(u).replace(r"\ ", r"\s*") for u in sorted(_UNITS, key=len, reverse=True)) + r")(?![a-z])")
FLAG_AT_START = re.compile(r"^\s*(?:HH|LL|H|L|\*+)(?=\s|$)")
COMPARATOR_START = re.compile(r"^\s*(?:up\s*to|upto|<=|>=|<|>|≤|≥)", re.IGNORECASE)
VALUE_END_BLOCKERS = re.compile(r"(?:[<>=:\-–−≤≥\ufffd]|\b(?:to|upto|than|below|above|under|over|up|year|since|in|on|at|of|after|before|and|the|a))\s*$", re.IGNORECASE)
RANGE_FIRST = re.compile(rf"^\s*{NUMBER}\s*[-–]\s*{NUMBER}\s*(?:[A-Za-z]|$)")     # "4.6 - 8.0 ... method ... 6.0": the range comes first, the result last
MAX_BLOCK_LINES = 10
MAX_BLOCK_LINE_LENGTH = 90
SECTION_WORDS = {
    "urine": re.compile(r"urine|urinalysis", re.IGNORECASE),
    "blood": re.compile(
        r"complete blood count|cbc|h(?:a)?ematology|biochemistry|lipid|liver|kidney|renal|thyroid|diabetes|"
        r"vitamin|serum|glycated|glycosylated",
        re.IGNORECASE,
    ),
}


@dataclass
class ParsedReference:
    text: str
    low: float | None
    high: float | None
    low_inclusive: bool = True
    high_inclusive: bool = True


@dataclass
class ExtractedParameter:
    test_name: str               # exactly as printed in the report
    normalized_name: str         # canonical name from the catalog
    value: float
    unit: str | None
    reference_text: str | None
    reference_low: float | None
    reference_high: float | None


# ---------------------------------------------------------------- reference ranges
def _to_float(text: str) -> float:
    return float(text.replace(",", ""))


# Laboratories often print several labelled ranges (Desirable / Borderline / High ...). Only a range whose label means "normal"
# can be used as the reference range: "Low: <40" or "High: >60" are not normal ranges, and guessing would flag a normal result.
LABELLED = re.compile(rf"([A-Za-z][A-Za-z/\- ]{{1,30}}?)\s*:\s*(?:(<=|>=|<|>|≤|≥|=)\s*)?({NUMBER})\s*%?(?:\s*[-–\ufffd]\s*({NUMBER}))?")
NORMAL_LABEL = re.compile(r"^(?:normal|desirable|optimal|non[- ]?diabet\w*|sufficien\w*|adequate|non[- ]?reactive|negative|healthy|acceptable)\b", re.IGNORECASE)

# The same tiers written on one line without colons: "Deficient <20 Insufficient 20-30 Sufficient 30-100", "Low <40 High >60". The tier words are matched by name so
# that a unit or a test name is never taken for a label. Longest words first ("very high" before "high", "near optimal" before "optimal").
TIER_WORDS = ["very high", "near optimal", "non-diabetic", "non diabetic", "pre-diabetes", "prediabetes", "pre-diabetic", "insufficiency", "insufficient", "deficiency", "deficient",
              "sufficient", "sufficiency", "borderline", "desirable", "optimal", "normal", "diabetes", "diabetic", "elevated", "high", "low", "moderate", "mild", "severe", "adequate",
              "toxic", "excess", "risk"]
INLINE_TIER = re.compile(rf"\b({'|'.join(re.escape(w) for w in TIER_WORDS)})\b\s*:?\s*(?:(<=|>=|<|>|≤|≥)\s*)?({NUMBER})\s*%?(?:\s*[-–]\s*({NUMBER}))?", re.IGNORECASE)

SEX_MALE = re.compile(r"\b(?:male|men|man)\b", re.IGNORECASE)
SEX_FEMALE = re.compile(r"\b(?:female|women|woman)\b", re.IGNORECASE)


def parse_reference_text(text: str) -> ParsedReference | None:
    """Read a reference range from text such as '4.0 - 5.6', '< 100', '> 40', '30 - 100 ng/mL'.
    If several patterns are present, the one that appears FIRST is used."""
    if not text:
        return None
    labelled = LABELLED.findall(text)          # looked at before a leading "Normal:" label is cut off below
    if len(labelled) < 2:
        inline = INLINE_TIER.findall(text)     # the same tiers on one line, without colons
        if len(inline) >= 2:
            labelled = inline
    label = REF_LABEL_RE.search(text)
    if label:
        text = text[label.end():]

    candidates: list[tuple[int, ParsedReference]] = []
    for m in RANGE_RE.finditer(text):
        low, high = _to_float(m.group(1)), _to_float(m.group(2))
        if low <= high:
            candidates.append((m.start(), ParsedReference(f"{m.group(1)} - {m.group(2)}", low, high)))
    for m in LESS_RE.finditer(text):
        inclusive = m.group(1).lower() in ("<=", "≤", "upto", "up to")
        candidates.append((m.start(), ParsedReference(f"< {m.group(2)}", None, _to_float(m.group(2)), True, inclusive)))
    for m in GREATER_RE.finditer(text):
        inclusive = m.group(1).lower() in (">=", "≥")
        candidates.append((m.start(), ParsedReference(f"> {m.group(2)}", _to_float(m.group(2)), None, inclusive, True)))
    if not candidates:
        return None
    if len(labelled) >= 2:
        for label, comparator, first, second in labelled:
            if NORMAL_LABEL.match(label.strip()):
                if second:
                    low, high = _to_float(first), _to_float(second)
                    if low <= high:
                        return ParsedReference(f"{first} - {second}", low, high)
                elif comparator in ("<", "<=", "≤"):
                    return ParsedReference(f"< {first}", None, _to_float(first), True, comparator != "<")
                elif comparator in (">", ">=", "≥"):
                    return ParsedReference(f"> {first}", _to_float(first), None, comparator != ">", True)
        # several labelled ranges and none of them says "normal": no range is guessed, the printed text is kept for the doctor
        shown = "; ".join(f"{lab.strip()}: {cmp or ''}{a}{('-' + b) if b else ''}" for lab, cmp, a, b in labelled)
        return ParsedReference(shown[:120], None, None)
    if len(candidates) >= 2 and SEX_MALE.search(text) and SEX_FEMALE.search(text):
        # separate ranges for men and women: the patient's sex is unknown here, so no range is guessed.
        # The printed text is kept for the doctor and the value is left "Reference range unavailable".
        return ParsedReference(re.sub(r"\s+", " ", text).strip()[:120], None, None)
    return min(candidates, key=lambda c: c[0])[1]


# ---------------------------------------------------------------- one parameter
def _gap_is_clean(gap: str) -> bool:
    """Text between the test name and the value must be harmless (spaces, ':', '(Fasting)', ...).
    This stops lines such as 'Total Cholesterol / HDL Ratio 4.1' being read as Total Cholesterol = 4.1."""
    gap = re.sub(r"\([^)]*[A-Za-z][^)]*\)", " ", gap)  # remove '(Direct)' / '(HbA1c)' notes (a range like (4-5) has no letters)
    gap = ALLOWED_GAP_WORDS.sub(" ", gap)
    gap = METHOD_WORDS.sub(" ", gap)
    return not re.search(r"[A-Za-z]", gap)


def _strip_leading_notes(text: str) -> str:
    """Drop leading '(HbA1c)' / '(Fasting)' notes so digits inside them are not mistaken for the value."""
    previous = None
    while previous != text:
        previous = text
        text = re.sub(r"^\s*\([^)]*[A-Za-z][^)]*\)", "", text)
    return text


def _ends_with_value(line: str) -> float | None:
    """The number a line ends with, if it is a measured value (not the upper end of a range or a limit such as '< 5.7')."""
    m = re.search(r"(?:(?<=\s)|^)(\d+(?:\.\d+)?)\s*$", line)
    if not m:
        return None
    before = line[: m.start()].rstrip()
    if before and VALUE_END_BLOCKERS.search(before):
        return None
    return float(m.group(1))


def _parse_unit_first(rest: str, following: list[str]) -> tuple[float, str | None, ParsedReference | None] | None:
    """Many laboratory reports print 'Test [flag] unit reference-range(s) method' and put the RESULT last, sometimes several lines down:
        Cholesterol mg/dL Desirable : <200 / Borderline High : 200-239 / High : >240 / <method> / 189.0
    The value is the number that ends the block. Returns None when the text does not have this shape."""
    rest = _strip_leading_notes(rest)
    flag = FLAG_AT_START.match(rest)
    if flag:
        rest = rest[flag.end():]
    rest = rest.lstrip()
    unit_match = UNIT_KNOWN.match(rest)
    if not unit_match and not COMPARATOR_START.match(rest) and not RANGE_FIRST.match(rest):
        return None
    unit = re.sub(r"\s+", "", unit_match.group(0)).replace("microg", "µg") if unit_match else None
    after_unit = rest[unit_match.end():] if unit_match else rest
    block = [after_unit] + [line for line in following]
    taken = []
    for line in block[: MAX_BLOCK_LINES + 1]:
        if len(line) > MAX_BLOCK_LINE_LENGTH:
            return None                                # a paragraph, not a table block
        value = _ends_with_value(line)
        if value is not None:
            taken.append(line[: re.search(r"(?:(?<=\s)|^)\d+(?:\.\d+)?\s*$", line).start()])
            reference = parse_reference_text(" ".join(taken)) if taken else None
            if reference is None and value == int(value) and 1900 <= value <= 2100:
                return None                                  # a year in a sentence, not a measured value
            return value, unit, reference
        taken.append(line)
    return None


def _parse_value_unit_reference(rest: str) -> tuple[float, str | None, ParsedReference | None] | None:
    rest = _strip_leading_notes(rest)
    m = VALUE_RE.search(rest)
    if not m or not _gap_is_clean(rest[: m.start()]):
        return None
    if m.group(1):  # '<0.5' / '>100' results are not exact numbers -> skip (documented limitation)
        return None
    value = _to_float(m.group(2))
    if re.match(r"\s*[-–]\s*\d", rest[m.end():]) and not UNIT_KNOWN.match(rest[m.end():].lstrip()):
        return None                                   # "1-2" is a count range (for example pus cells 1-2), not one measured value
    after = rest[m.end():].lstrip()

    flag = FLAG_RE.match(after)
    if flag:
        after = after[flag.end():].lstrip()

    unit = None
    unit_match = UNIT_RE.match(after)
    if unit_match and unit_match.group(0).lower() not in NOT_UNITS:
        unit = unit_match.group(0).strip()
        after = after[unit_match.end():]

    reference = parse_reference_text(after)
    return value, unit, reference


# ---------------------------------------------------------------- whole report
def _detect_context(line: str, current: str) -> str:
    """Section headings (no digits) switch between 'blood' and 'urine' parsing mode."""
    if re.search(r"\d", line) or len(line) > 70:
        return current
    if SECTION_WORDS["urine"].search(line):
        return "urine"
    if SECTION_WORDS["blood"].search(line):
        return "blood"
    return current


def _is_unit_line(line: str) -> bool:
    """A line that holds only a unit, e.g. 'g/dL' or '%' (some PDFs put every column on its own line)."""
    token = line.strip()
    if not token or len(token) > 18 or token.lower() in NOT_UNITS:
        return False
    return bool(UNIT_RE.fullmatch(token)) and (any(c in token for c in "/%") or token.lower() in SIMPLE_UNITS)


def extract_parameters(text: str) -> list[ExtractedParameter]:
    lines = text.split("\n")
    results: dict[str, ExtractedParameter] = {}
    context = "blood"

    for index, line in enumerate(lines):
        context = _detect_context(line, context)
        line = re.sub(r"^\s*(?:\d+[.)]|[*•\-])\s+", "", line)  # '1. ', '* ', '- ' list markers
        line = re.sub(r"(?<=[a-z]{4})([HL])(?=\s+\d)", r" \1", line)  # "cell analysisH 10570" -> "cell analysis H 10570"
        hit = match_parameter_name(line, context)
        if not hit:
            continue
        name_end = hit.end
        hit.end = skip_own_names(hit.info, line, hit.end)         # "Mean Corpuscular Volume, MCV": the abbreviation is part of the name, not of the result

        # Column layout with the value LAST ("Test unit range method value"): tried first, it has a very specific shape.
        following = []
        for next_line in lines[index + 1: index + 1 + MAX_BLOCK_LINES]:
            nxt = match_parameter_name(next_line, context)
            if nxt and (UNIT_KNOWN.match(_strip_leading_notes(next_line[nxt.end:]).lstrip()) or _parse_value_unit_reference(next_line[nxt.end:])):
                break                                    # the next test starts here (a method line such as "Cholesterol oxidase" is not a test)
            following.append(next_line)
        unit_first = _parse_unit_first(line[hit.end:], following)
        if unit_first:
            value, unit, reference = unit_first
            param = ExtractedParameter(
                test_name=line[: (name_end if "(" in line[name_end: hit.end] else hit.end)].strip(), normalized_name=hit.info.name, value=value, unit=unit,
                reference_text=reference.text if reference else None, reference_low=reference.low if reference else None,
                reference_high=reference.high if reference else None)
            existing = results.get(param.normalized_name)
            if existing is None or (existing.reference_text is None and param.reference_text is not None):
                results[param.normalized_name] = param
            continue

        window = _strip_leading_notes(line[hit.end:])
        # Vertical layouts: value / reference may be on the next lines.
        for next_line in lines[index + 1: index + 4]:
            if match_parameter_name(next_line, context):
                break
            has_value = VALUE_RE.search(window) is not None
            starts_reference = bool(REF_LABEL_RE.match(next_line) or RANGE_LIKE_START.match(next_line))
            if not has_value or starts_reference or _is_unit_line(next_line):
                window += " " + next_line
            else:
                break

        parsed = _parse_value_unit_reference(window)
        if not parsed:
            continue
        value, unit, reference = parsed

        param = ExtractedParameter(
            test_name=line[: (name_end if "(" in line[name_end: hit.end] else hit.end)].strip(),
            normalized_name=hit.info.name,
            value=value,
            unit=unit,
            reference_text=reference.text if reference else None,
            reference_low=reference.low if reference else None,
            reference_high=reference.high if reference else None,
        )
        existing = results.get(param.normalized_name)
        # Keep the first occurrence, unless a later one has a reference range and the first does not.
        if existing is None or (existing.reference_text is None and param.reference_text is not None):
            results[param.normalized_name] = param

    return list(results.values())


# ---------------------------------------------------------------- report date
_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
_DATE_PATTERNS = [
    (re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b"), "ymd"),
    (re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b"), "dmy"),
    (re.compile(r"\b(\d{1,2})[ /-]([A-Za-z]{3})[a-z]*[ ,/-]+(\d{4})\b"), "d_mon_y"),
    (re.compile(r"\b([A-Za-z]{3})[a-z]*\.? (\d{1,2}),? (\d{4})\b"), "mon_d_y"),
]


def _try_date(kind: str, g: tuple[str, ...]) -> date | None:
    try:
        if kind == "ymd":
            return date(int(g[0]), int(g[1]), int(g[2]))
        if kind == "dmy":
            return date(int(g[2]), int(g[1]), int(g[0]))  # day first (common for Indian labs)
        if kind == "d_mon_y":
            return date(int(g[2]), _MONTHS[g[1].lower()], int(g[0]))
        if kind == "mon_d_y":
            return date(int(g[2]), _MONTHS[g[0].lower()], int(g[1]))
    except (ValueError, KeyError):
        return None
    return None


_COLLECTED_LABEL = re.compile(r"collected(?:\s+on)?|collection\s+date|sample\s+(?:collected|date|drawn)|sampling\s+date", re.IGNORECASE)
_GENERAL_DATE_LABEL = re.compile(r"test\s+date|report(?:ed)?\s+(?:on|date)|date\s+of\s+(?:report|test)|(?<![A-Za-z])date(?!\s+of\s+birth)(?![A-Za-z])|registered|reg\.?\s+date", re.IGNORECASE)
_NOT_THE_TEST_DATE = re.compile(r"birth|dob|born|expir|valid\s+(?:till|until|upto)|due\s+date|next\s+(?:visit|review)|print", re.IGNORECASE)
LOOK_AHEAD_LINES = 2          # reports that print one cell per line put the date on the line after its label


def _first_date(text: str) -> date | None:
    """The date that appears earliest in `text` (any of the printed formats), or None."""
    found: list[tuple[int, date]] = []
    for pattern, kind in _DATE_PATTERNS:
        for m in pattern.finditer(text):
            parsed = _try_date(kind, m.groups())
            if parsed and 2000 <= parsed.year <= hospital_today().year + 1:
                found.append((m.start(), parsed))
    return min(found, key=lambda f: f[0])[1] if found else None


def _date_after_label(lines: list[str], label: re.Pattern) -> date | None:
    """The first date printed right after a label ('Collected on: 14/05/2021'), on the same line or, for one-cell-per-line readings, the next lines."""
    for index, line in enumerate(lines):
        if _NOT_THE_TEST_DATE.search(line):
            continue
        for m in label.finditer(line):
            same_line = _first_date(line[m.end():])
            if same_line:
                return same_line
            for following in lines[index + 1: index + 1 + LOOK_AHEAD_LINES]:
                if _NOT_THE_TEST_DATE.search(following):
                    break
                nxt = _first_date(following)
                if nxt:
                    return nxt
    return None


def extract_report_date(text: str) -> date | None:
    """The test date: when the sample was collected ('Collected on'), else the date printed as 'Date', 'Test date' or 'Reported on'.
    The WHOLE text is read: the page header that holds the date is often the last thing a PDF reader returns, not the first."""
    lines = text.splitlines()
    return _date_after_label(lines, _COLLECTED_LABEL) or _date_after_label(lines, _GENERAL_DATE_LABEL)


# ---------------------------------------------------------------- patient name (safety check)
_NAME_RE = re.compile(r"^\s*(?:patient(?:'s)?\s*name|name\s+of\s+patient|patient|name)\s*[:\-]\s*(.+?)\s*$",
                      re.IGNORECASE)


def extract_patient_name(text: str) -> str | None:
    """Find 'Patient Name: Rahul Patil' near the top of the report (used only to warn about a possible mix-up)."""
    for line in text.split("\n")[:150]:
        m = _NAME_RE.match(line)
        if m:
            name = re.split(r"\s{2,}|\bage\b|\bsex\b|\bgender\b|\bdate\b|\blab\b|\bclient\b|\bregistration\b|\bsample\b", m.group(1), flags=re.IGNORECASE)[0]
            name = re.sub(r"[^A-Za-z.' ]", "", name).strip()
            if len(name) >= 3:
                return name
    return None


def names_match(report_name: str, patient_name: str) -> bool:
    """Loose match: ignore titles/case; the names match if they share at least one full word of 3+ letters."""
    def words(value: str) -> set[str]:
        return {w for w in re.findall(r"[a-z]+", value.lower()) if len(w) >= 3 and w not in ("mr", "mrs", "ms", "dr")}

    return bool(words(report_name) & words(patient_name))
