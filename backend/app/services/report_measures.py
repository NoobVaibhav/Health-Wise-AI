"""What matters in a report that is not a lab table: 2D echo, coronary angiography, treadmill test, lung function, bone density, and the
written reports of X-ray, CT, MRI and ultrasound.

  * detect_kind(text)  says which of these a report is (from its title first, then from its wording);
  * measures(kind, text) reads the key numbers and graded findings (heart pumping strength, how narrow each artery is, valve leaks,
    size of a nodule or stone ...) as {label, value, unit, range, concern, detail, urgent} for the "key numbers" cards.

A number is judged only against standard adult reference values written below (shown on the card), or against the grade the report itself
uses (mild / moderate / severe). Nothing here says what a result means for the patient: it orders what a doctor should look at first."""
import re

# ------------------------------------------------------------------ which kind of report
KINDS = [
    ("TMT", [r"treadmill", r"\btmt\b", r"stress test", r"bruce protocol", r"stress ecg"]),
    ("ECHO", [r"echocardiogra", r"\b2\s*-?\s*d\s+echo", r"\blvef\b", r"ejection fraction", r"\blvidd\b", r"\bdoppler echo"]),
    ("ANGIO", [r"coronary angiogra", r"\bcag\b", r"\bptca\b", r"cath(?:eterization)? lab", r"\bangiogram\b", r"\bangioplasty\b"]),
    ("PFT", [r"spirometry", r"pulmonary function", r"\bfev1\b", r"\bpft\b"]),
    ("DEXA", [r"\bdexa\b", r"\bdxa\b", r"bone mineral density", r"\bt-?\s?score\b"]),
    ("CT", [r"\bct\s+(?:scan|chest|abdomen|brain|head|thorax|pelvis|angiogra|kub|spine|neck)", r"computed tomograph", r"\bhrct\b", r"\bncct\b", r"\bcect\b", r"\bct\s*-\s*scan"]),
    ("MRI", [r"\bmri\b", r"magnetic resonance"]),
    ("XRAY", [r"x\s*-?\s*ray", r"radiograph"]),
    ("ULTRASOUND", [r"ultrasound", r"sonograph", r"\busg\b", r"\bsonogram"]),
]
NOT_THESE = re.compile(r"discharge summary|chief complaint|date of admission", re.IGNORECASE)             # a discharge summary or a clinical note only mentions a test
NOT_THESE_WEAK = re.compile(r"\brx\b|tab\.|prescription", re.IGNORECASE)


def detect_kind(text: str) -> str | None:
    """The specific kind of report, or None. The title (the first lines) decides; otherwise a kind needs at least three of its words
    and the file must not be a discharge summary, note or prescription that merely mentions a test."""
    lowered = text.lower()
    head = lowered[:350]
    if NOT_THESE.search(lowered[:3000]):
        return None
    for kind, patterns in KINDS:
        if any(re.search(p, head) for p in patterns):
            return kind
    if NOT_THESE_WEAK.search(lowered[:3000]):
        return None
    best, best_hits = None, 0
    for kind, patterns in KINDS:
        hits = sum(1 for p in patterns if re.search(p, lowered))
        if hits > best_hits:
            best, best_hits = kind, hits
    return best if best_hits >= 3 else None


# ------------------------------------------------------------------ helpers
def _num(s: str) -> float:
    return float(s.replace(",", "").replace("−", "-").replace("–", "-"))


def _clean(v: float):
    return int(v) if v == int(v) else round(v, 2)


def _metric(label, value, unit=None, range_=None, concern="neutral", detail=None, urgent=False) -> dict:
    return {"label": label, "value": value, "unit": unit, "range": range_, "concern": concern, "detail": detail, "urgent": urgent}


def _band(value: float, bands: list[tuple[float, str, str, bool]]):
    """bands from the highest limit down: (at least, concern, words, urgent). The first band the value reaches is used."""
    for limit, concern, words, urgent in bands:
        if value >= limit:
            return concern, words, urgent
    return bands[-1][1:]


def _ranged(label, value, unit, low, high, note=None) -> dict:
    out = value < low or value > high
    rng = f"{low:g} - {high:g}"
    detail = ("Below the usual range" if value < low else "Above the usual range") if out else None
    return _metric(label, _clean(value), unit, rng, "attention" if out else "normal", detail or note)


def _first(pattern: str, text: str, flags=re.IGNORECASE):
    m = re.search(pattern, text, flags)
    return m


NEGATED = re.compile(r"\b(no|without|nil|absent|absence of|not seen|not identified|free of|negative for)\b[^.;\n]{0,40}$", re.IGNORECASE)


def _clauses(text: str):
    for sentence in re.split(r"(?<=[.;])\s+|\n+", text):
        for clause in re.split(r",|\band\b(?=\s+(?:no|mild|moderate|severe|trivial)\b)", sentence):
            if clause.strip():
                yield clause.strip()


# ------------------------------------------------------------------ ECHO
EF_BANDS = [(55, "normal", "Normal pumping strength", False), (41, "attention", "Mildly reduced", False),
            (31, "attention", "Reduced", False), (0, "attention", "Severely reduced", True)]


def _ef(text: str) -> list[dict]:
    out = []
    m = re.search(r"(?:lvef|ejection fraction|\bEF\b)[^0-9\n.]{0,15}(\d{1,2}(?:\.\d+)?)\s*%", text, re.IGNORECASE)
    if m:
        v = _num(m.group(1))
        concern, words, urgent = _band(v, EF_BANDS)
        out.append(_metric("LVEF (how strongly the heart pumps)", _clean(v), "%", "55 - 70", concern, words, urgent))
    return out


DIMENSIONS = [   # label, regex (value then unit), usual adult range in cm
    ("Left ventricle size, end of filling (LVIDd)", r"lvidd\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(cm|mm)", 3.9, 5.9),
    ("Left ventricle size, end of beat (LVIDs)", r"lvids\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(cm|mm)", 2.2, 4.0),
    ("Septum thickness (IVSd)", r"ivsd\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(cm|mm)", 0.6, 1.1),
    ("Back wall thickness (LVPWd)", r"lvpwd\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(cm|mm)", 0.6, 1.1),
    ("Left atrium size (LA)", r"\bLA\b(?:\s+(?:size|diameter|dimension))?\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(cm|mm)", 1.9, 4.0),
    ("Aortic root", r"aortic root(?:\s+diameter)?\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(cm|mm)", 2.0, 3.7),
]
VALVES = r"(mitral|aortic|tricuspid|pulmonary|pulmonic)"
LEAK = r"(regurgitation|stenosis|insufficiency)"
GRADES = [("trivial", "Trivial"), ("trace", "Trace"), ("mild to moderate", "Mild to moderate"), ("moderate to severe", "Moderate to severe"),
          ("mild", "Mild"), ("moderate", "Moderate"), ("severe", "Severe")]
GRADE_CONCERN = {"Trivial": "neutral", "Trace": "neutral", "Mild": "neutral", "Mild to moderate": "attention", "Moderate": "attention",
                 "Moderate to severe": "attention", "Severe": "attention"}


def _valves(text: str) -> list[dict]:
    out, seen = [], set()
    for clause in _clauses(text):
        for m in re.finditer(VALVES + r"\s+" + LEAK, clause, re.IGNORECASE):
            valve, kind = m.group(1).capitalize(), m.group(2).lower().replace("insufficiency", "regurgitation")
            valve = "Pulmonary" if valve == "Pulmonic" else valve
            label = f"{valve} {kind}"
            before = clause[:m.start()].lower()
            if label in seen:
                continue
            if re.search(r"\b(no|without|nil|absent)\b", before[-40:]):
                out.append(_metric(label, "None", None, None, "normal", "Reported as not present"))
                seen.add(label)
                continue
            grade = next((name for word, name in GRADES if re.search(r"\b" + word + r"\b", before[-40:])), None)
            if grade:
                seen.add(label)
                concern = GRADE_CONCERN[grade]
                out.append(_metric(label, grade, None, None, concern, None, urgent=grade == "Severe"))
    return out


PHRASES = [   # label, regex, value when present, value when reported absent, concern when present
    ("Wall motion of the heart", r"(?:regional\s+)?wall motion abnormalit(?:y|ies)|\bRWMA\b|hypokinesia|akinesia|dyskinesia", "Abnormal", "Normal", "attention"),
    ("Fluid around the heart (pericardial effusion)", r"pericardial effusion", "Present", "None", "attention"),
    ("Clot or growth in the heart", r"\b(?:clot|thrombus|vegetation|mass)\b", "Reported", "None seen", "attention"),
]


def _phrases(text: str, kind: str) -> list[dict]:
    if kind != "ECHO":
        return []
    out = []
    for label, pattern, present, absent, concern in PHRASES:
        found = None
        for clause in _clauses(text):
            m = re.search(pattern, clause, re.IGNORECASE)
            if m:
                found = "absent" if NEGATED.search(clause[:m.start()] + " ") or re.search(r"\bno\b\s+\w*\s*" + pattern, clause, re.IGNORECASE) else "present"
                if found == "present":
                    break
        if found:
            out.append(_metric(label, present if found == "present" else absent, None, None, concern if found == "present" else "normal"))
    g = re.search(r"(?:grade\s*(I{1,3}V?|[1-4])\s*diastolic dysfunction|diastolic dysfunction\s*(?:of\s*)?(?:-|:)?\s*grade\s*(I{1,3}V?|[1-4]))", text, re.IGNORECASE)
    if g:
        out.append(_metric("Heart relaxation (diastolic function)", "Grade " + (g.group(1) or g.group(2)).upper(), None, None, "attention", "Diastolic dysfunction"))
    return out


def _echo(text: str) -> list[dict]:
    out = _ef(text)
    for label, pattern, low, high in DIMENSIONS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            v = _num(m.group(1))
            out.append(_ranged(label, v / 10 if m.group(2).lower() == "mm" else v, "cm", low, high))
    m = re.search(r"(?:rvsp|pasp|pa systolic pressure|pulmonary artery systolic pressure)\s*[:=]?\s*(\d{2,3})\s*mm\s*hg", text, re.IGNORECASE)
    if m:
        v = _num(m.group(1))
        out.append(_metric("Lung artery pressure (RVSP)", _clean(v), "mmHg", "up to 35", "attention" if v > 35 else "normal",
                           "Raised" if v > 35 else None, urgent=v >= 60))
    m = re.search(r"tapse\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(cm|mm)", text, re.IGNORECASE)
    if m:
        v = _num(m.group(1)) / (10 if m.group(2).lower() == "mm" else 1)
        out.append(_metric("Right heart movement (TAPSE)", _clean(v), "cm", "1.7 or more", "normal" if v >= 1.7 else "attention", None if v >= 1.7 else "Reduced"))
    return out + _valves(text) + _phrases(text, "ECHO")


# ------------------------------------------------------------------ ANGIO
VESSEL = re.compile(r"(?:(proximal|mid|distal|ostial|osteal)\s+)?(left main(?: coronary artery)?|\bLMCA\b|\bLM\b|\bLAD\b|\bLCX\b|\bLCx\b|\bRCA\b|\bRI\b|ramus(?: intermedius)?|"
                    r"\bOM\s?\d?\b|obtuse marginal|\bD\s?\d\b|diagonal(?:\s*\d)?|\bPDA\b|\bPLV\b|\bPLB\b|SVG|LIMA)", re.IGNORECASE)
CANON = {"left main coronary artery": "Left main", "left main": "Left main", "lmca": "Left main", "lm": "Left main", "lad": "LAD", "lcx": "LCx", "rca": "RCA", "ri": "Ramus"}


def _vessel_name(match) -> str:
    base = match.group(2)
    key = re.sub(r"\s+", " ", base.lower()).strip()
    name = CANON.get(key, base.upper() if len(base) <= 4 else base.capitalize())
    pos = match.group(1)
    return (pos.capitalize() + " " if pos else "") + name


def _angio(text: str) -> list[dict]:
    out, vessels_with_stenosis = [], set()
    for m in re.finditer(r"(\d{1,3})\s*%\s*(?:chronic total occlusion|total occlusion|stenosis|block(?:age)?|narrowing|lesion|occlusion|disease)", text, re.IGNORECASE):
        before = text[max(0, m.start() - 50):m.start()]
        found = list(VESSEL.finditer(before))
        if not found:
            continue
        name = _vessel_name(found[-1])
        pct = min(100, int(m.group(1)))
        main = "Left main" in name
        severe = pct >= (50 if main else 70)
        words = "Completely blocked" if pct >= 100 else "Severe narrowing" if severe else "Moderate narrowing" if pct >= 50 else "Mild narrowing"
        vessels_with_stenosis.add(name.split()[-1].lower())
        out.append(_metric(f"{name} narrowing", pct, "%", "under 50", "attention" if pct >= 50 else "neutral", words, urgent=severe))
    for m in re.finditer(r"(left main(?: coronary artery)?|\bLAD\b|\bLCX\b|\bLCx\b|\bRCA\b)\s*[:\-]?\s*(?:is |are |appears? |shows? )?(?:normal|free of disease|no (?:significant )?(?:stenosis|disease))", text, re.IGNORECASE):
        name = CANON.get(re.sub(r"\s+", " ", m.group(1).lower()), m.group(1).upper())
        if name.split()[-1].lower() not in vessels_with_stenosis:
            out.append(_metric(f"{name} artery", "Normal", None, None, "normal"))
    m = re.search(r"TIMI\s*(?:grade\s*)?(?:flow\s*)?[:\-]?\s*(0|III|II|I|[0-3])\b", text)
    if m:
        grade = {"0": 0, "I": 1, "II": 2, "III": 3}.get(m.group(1), None)
        grade = int(m.group(1)) if grade is None else grade
        out.append(_metric("Blood flow in the artery (TIMI)", f"TIMI {grade}", None, "TIMI 3 is normal", "normal" if grade == 3 else "attention", None if grade == 3 else "Flow is slowed or absent", urgent=grade <= 1))
    m = re.search(r"\b(right|left)[- ]dominan", text, re.IGNORECASE)
    if m:
        out.append(_metric("Dominant artery system", m.group(1).capitalize(), None, None, "neutral"))
    return out + _ef(text)


# ------------------------------------------------------------------ TMT
def _tmt(text: str) -> list[dict]:
    out = []
    m = re.search(r"(?:achieved\s+)?mets?\s*[:=]?\s*(\d+(?:\.\d+)?)", text, re.IGNORECASE)
    if m:
        v = _num(m.group(1))
        out.append(_metric("Exercise capacity (METs)", _clean(v), "METs", "7 or more is good", "normal" if v >= 7 else "attention", None if v >= 7 else "Lower than expected"))
    m = re.search(r"(\d{2,3})\s*%\s*of\s*(?:the\s*)?(?:maximum\s+|max\.?\s+)?(?:age[- ]predicted|predicted)", text, re.IGNORECASE)
    if m:
        v = _num(m.group(1))
        out.append(_metric("Heart rate reached (of the target)", _clean(v), "%", "85 or more", "normal" if v >= 85 else "attention", None if v >= 85 else "The target heart rate was not reached, so the test may be less reliable"))
    m = re.search(r"peak (?:hr|heart rate)\s*[:=]?\s*(\d{2,3})\s*(?:bpm)?", text, re.IGNORECASE)
    if m:
        out.append(_metric("Peak heart rate", int(m.group(1)), "bpm"))
    m = re.search(r"exercise time\s*[:=]?\s*(\d+)\s*min(?:utes?)?(?:\s*(\d+)\s*sec)?", text, re.IGNORECASE)
    if m:
        out.append(_metric("Exercise time", f"{m.group(1)} min" + (f" {m.group(2)} sec" if m.group(2) else "")))
    m = re.search(r"st[- ]?(?:segment\s+)?depression\s*(?:of\s*)?(\d+(?:\.\d+)?)\s*mm", text, re.IGNORECASE)
    if m:
        v = _num(m.group(1))
        out.append(_metric("ST depression on exercise", _clean(v), "mm", "under 1", "attention" if v >= 1 else "normal", "Changes of this size can mean the heart muscle gets too little blood during effort" if v >= 1 else None, urgent=v >= 2))
    m = re.search(r"\b(?:tmt|test|stress test)\s+(?:is|was)\s+(positive|negative|inconclusive|equivocal)", text, re.IGNORECASE)
    if m:
        res = m.group(1).capitalize()
        out.append(_metric("Result of the test", res, None, None, "normal" if res == "Negative" else "attention", urgent=res == "Positive"))
    return out


# ------------------------------------------------------------------ PFT, DEXA
def _pft(text: str) -> list[dict]:
    out = []
    m = re.search(r"fev1\s*/\s*fvc\s*(?:ratio)?\s*[:=]?\s*(\d+(?:\.\d+)?)\s*%?", text, re.IGNORECASE)
    if m:
        v = _num(m.group(1))
        v = v * 100 if v <= 1 else v
        out.append(_metric("FEV1 / FVC ratio", _clean(v), "%", "70 or more", "normal" if v >= 70 else "attention", None if v >= 70 else "Below 70 % points to narrowed airways"))
    for name, label in (("fev1", "FEV1 (air blown out in 1 second)"), ("fvc", "FVC (total air blown out)")):
        m = re.search(name + r"\s*[:=]?\s*[\d.]+\s*l?\s*\(\s*(\d+)\s*%\s*(?:of\s*)?pred", text, re.IGNORECASE)
        if m:
            v = _num(m.group(1))
            concern, words, urgent = _band(v, [(80, "normal", "Normal", False), (50, "attention", "Reduced", False), (0, "attention", "Much reduced", False)])
            out.append(_metric(label + ", % of predicted", _clean(v), "%", "80 or more", concern, None if concern == "normal" else words))
    return out


def _dexa(text: str) -> list[dict]:
    out = []
    for m in re.finditer(r"(?P<site>[A-Za-z][A-Za-z0-9 \-]{2,32}?)\s+(?P<kind>T|Z)-?\s?score\s*[:=]?\s*(?P<v>[-−–]?\s?\d+(?:\.\d+)?)", text, re.IGNORECASE):
        v = _num(m.group("v").replace(" ", ""))
        site = re.sub(r"\s+", " ", m.group("site")).strip()
        site = site[:1].upper() + site[1:]
        kind = m.group("kind").upper()
        if kind == "T":
            words = "Osteoporosis range" if v <= -2.5 else "Low bone density, osteopenia range" if v < -1 else "Normal"
            out.append(_metric(f"{site}, T-score", _clean(v), None, "-1 or higher", "normal" if v >= -1 else "attention", None if v >= -1 else words))
        else:
            out.append(_metric(f"{site}, Z-score", _clean(v), None, "-2 or higher", "normal" if v >= -2 else "attention", None if v >= -2 else "Lower than expected for the age"))
    return out


# ------------------------------------------------------------------ X-ray, CT, MRI, ultrasound
LESION = r"(?:nodules?|masses|mass|lesions?|cysts?|calculus|calculi|stones?|lymph nodes?|nodes?|polyps?|collections?|thrombus|aneurysm|tumou?rs?|fibroids?|effusion|abscess)"
SIZE = r"(?P<a>\d+(?:\.\d+)?)(?:\s*[x×]\s*(?P<b>\d+(?:\.\d+)?))?(?:\s*[x×]\s*(?P<c>\d+(?:\.\d+)?))?\s*(?P<u>mm|cm)"


def _size_text(m) -> str:
    return " x ".join(g for g in (m.group("a"), m.group("b"), m.group("c")) if g) + " " + m.group("u")


def _singular(word: str) -> str:
    word = word.lower()
    if word == "calculi":
        return "calculus"
    if word.endswith("sses"):
        return word[:-2]
    if word.endswith("ies"):
        return word[:-3] + "y"
    return word[:-1] if word.endswith("s") and not word.endswith(("ss", "us")) else word


def _imaging(text: str) -> list[dict]:
    out, seen = [], set()
    for sentence in re.split(r"(?<=[.;])\s+|\n+", text):
        for m in re.finditer(r"(?P<w>" + LESION + r")\b[^.;\n]{0,70}?" + SIZE, sentence, re.IGNORECASE):
            word = m.group("w").lower()
            if NEGATED.search(sentence[:m.start()] + " "):
                continue
            label = "Lymph node size" if "node" in word and "lymph" in sentence.lower()[max(0, m.start() - 12):m.end()] else _singular(word).capitalize() + " size"
            key = (label, _size_text(m))
            if key not in seen:
                seen.add(key)
                out.append(_metric(label, _size_text(m), None, None, "attention", None))
        for m in re.finditer(SIZE + r"\s+(?:sized\s+|size\s+)?(?:\w+\s+)?(?P<w>" + LESION + r")\b", sentence, re.IGNORECASE):
            word = m.group("w").lower()
            label = _singular(word).capitalize() + " size"
            key = (label, _size_text(m))
            if key not in seen and not NEGATED.search(sentence[:m.start()] + " "):
                seen.add(key)
                out.append(_metric(label, _size_text(m), None, None, "attention", None))
    for m in re.finditer(r"\b(liver|spleen|right kidney|left kidney|kidneys?|prostate|uterus|thyroid)\b[^.;\n]{0,40}?\(\s*(\d+(?:\.\d+)?)\s*(cm|mm)\s*\)", text, re.IGNORECASE):
        sentence = text[max(0, text.rfind(".", 0, m.start()) + 1): m.end() + 80]
        big = re.search(r"enlarg|increased|bulky|hepatomegaly|splenomegaly", sentence, re.IGNORECASE)
        out.append(_metric(f"{m.group(1).capitalize()} size", _clean(_num(m.group(2))), m.group(3), None, "attention" if big else "normal", "Described as enlarged" if big else None))
    m = re.search(r"cardiothoracic ratio\s*(?:\(ctr\))?\s*(?:is|of|[:=])?\s*(0?\.\d+|\d{2}\s*%)", text, re.IGNORECASE)
    if m:
        raw = m.group(1)
        v = _num(raw.replace("%", "")) / (100 if "%" in raw else 1)
        out.append(_metric("Heart size on the X-ray (cardiothoracic ratio)", _clean(v), None, "up to 0.50", "attention" if v > 0.5 else "normal", "A ratio above 0.50 can mean an enlarged heart" if v > 0.5 else None))
    return out


def measures(kind: str | None, text: str) -> list[dict]:
    """The key numbers and graded findings for this kind of report (empty for a kind that has none)."""
    if kind == "ECHO":
        return _echo(text)
    if kind == "ANGIO":
        return _angio(text)
    if kind == "TMT":
        return _tmt(text)
    if kind == "PFT":
        return _pft(text)
    if kind == "DEXA":
        return _dexa(text)
    if kind in ("XRAY", "CT", "MRI", "ULTRASOUND", "IMAGING"):
        return _imaging(text)
    return []
