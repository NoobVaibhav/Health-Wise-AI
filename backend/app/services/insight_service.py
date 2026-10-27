"""Insights for ANY medical report: suggestions for the doctor and general tips for the patient.

How it works (explainable in the viva):
1. Decide the report TYPE (lab table, X-ray/scan, ECG, biopsy, discharge summary, prescription, clinical note ...)
   by counting characteristic words.
2. For lab tables the values were already classified by the rule engine; we group the out-of-range ones by body
   system (sugar, cholesterol, liver, kidney ...) and attach considerations.
3. For free-text reports we split the text into sections (Findings, Impression, Conclusion ...), cut it into
   statements, and mark each as "looks normal" or "worth a look" using two word lists plus a NEGATION check
   ("no evidence of mass" is normal, "mass seen" is not). Wording that suggests urgency is flagged for the doctor.
4. Everything here is rule-based and works without any AI. An optional LLM (llm_service) can improve the wording,
   but its answers go through the safety filter and the rule-based result is the fallback.

Nothing here diagnoses or prescribes. Doctor suggestions are "points to consider"; patient tips are general
wellness advice that is shown only after a doctor has reviewed the report.
"""
import re
from dataclasses import dataclass

# ------------------------------------------------------------------ report types
from app.services.result_priority import DERIVED, prioritise, summary_text

REPORT_TYPE_LABELS = {
    "LAB": "Laboratory test report",
    "IMAGING": "Imaging report (X-ray, CT, MRI, ultrasound)",
    "ECG": "ECG / heart tracing",
    "PATHOLOGY": "Pathology / biopsy report",
    "DISCHARGE": "Discharge or hospital summary",
    "PRESCRIPTION": "Prescription / medicine list",
    "CLINICAL": "Clinical note / consultation",
    "OTHER": "Other medical report",
}

TYPE_KEYWORDS = {
    "IMAGING": ["x-ray", "xray", "radiograph", "ct scan", "computed tomography", "mri", "magnetic resonance", "ultrasound",
                "sonography", "usg", "doppler", "mammogra", "radiolog", "impression", "opacity", "lesion", "echogenic"],
    "ECG": ["ecg", "ekg", "electrocardiogram", "sinus rhythm", "qrs", "st segment", "pr interval", "qt interval",
            "t wave", "heart rate", "bpm", "p wave", "axis"],
    "PATHOLOGY": ["histopatholog", "biopsy", "cytology", "specimen", "microscopic", "carcinoma", "margins", "grossly",
                  "immunohistochem", "pap smear"],
    "DISCHARGE": ["discharge summary", "date of admission", "date of discharge", "hospital course", "admitted",
                  "discharged", "advice on discharge", "condition at discharge", "follow up", "follow-up"],
    "PRESCRIPTION": ["rx", "tab.", "tab ", "cap.", "syrup", "twice daily", "once daily", "thrice daily", "bd", "tds",
                     "after food", "before food", "dosage", "sig:"],
    "CLINICAL": ["chief complaint", "complaints", "history of present illness", "examination", "vitals", "assessment",
                 "plan", "blood pressure", "pulse", "temperature", "spo2", "diagnosis"],
}

# Words that make a document look medical at all (used to reject invoices, letters, random PDFs).
MEDICAL_WORDS = [
    "patient", "doctor", "dr.", "hospital", "clinic", "diagnosis", "findings", "impression", "examination", "clinical",
    "medication", "medicine", "symptom", "treatment", "scan", "x-ray", "ecg", "mri", "ct ", "ultrasound", "biopsy",
    "pathology", "radiolog", "blood pressure", "pulse", "heart", "lung", "liver", "kidney", "abdomen", "chest", "brain",
    "bone", "fracture", "lesion", "tumour", "tumor", "infection", "history", "admission", "discharge", "prescription",
    "dosage", "mg", "tablet", "specimen", "report", "normal", "abnormal", "study", "advice", "follow up", "follow-up",
]

SECTION_NAMES = [
    "comment", "comments", "remark", "remarks", "note", "notes",
    "findings", "finding", "impression", "conclusion", "diagnosis", "assessment", "plan", "advice", "recommendation",
    "recommendations", "summary", "clinical history", "history", "indication", "technique", "comparison", "medications",
    "treatment", "discharge advice", "interpretation", "opinion", "result", "results", "microscopy", "gross description",
]
KEY_SECTIONS = ("impression", "conclusion", "findings", "finding", "diagnosis", "assessment", "interpretation", "opinion",
                "summary", "microscopy", "result", "results")

# ------------------------------------------------------------------ wording lists
ATTENTION_TERMS = [
    "mass", "lesion", "nodule", "tumour", "tumor", "malignan", "carcinoma", "metasta", "fracture", "effusion", "enlarg",
    "dilat", "cardiomegaly", "hepatomegaly", "splenomegaly", "organomegaly", "stenosis", "occlusion", "thromb", "embol", "infarct", "ischemi", "ischaemi", "arrhythmi", "fibrillation",
    "tachycardia", "bradycardia", "st elevation", "st depression", "consolidation", "opacity", "opacities", "pneumonia",
    "infection", "abscess", "hemorrhage", "haemorrhage", "bleed", "edema", "oedema", "hypertrophy", "calcification",
    "stone", "calculus", "cyst", "polyp", "ulcer", "inflammation", "abnormal", "elevated", "raised", "decreased",
    "reduced", "impaired", "suspicious", "atelectasis", "pneumothorax", "deviat", "thicken", "irregular", "dysplasia",
    "positive for", "worsen", "progress", "increase", "ectopic", "extrasystol", "pause",
]
URGENT_TERMS = [
    "urgent", "immediate", "critical", "life-threatening", "malignan", "carcinoma", "pulmonary embol", "st elevation",
    "pneumothorax", "hemorrhage", "haemorrhage", "dissection", "infarct", "rupture", "perforation", "acute abdomen",
    "stat ", "emergent",
]
# A negation word cancels every finding named after it in the same clause ("no evidence of A or B"),
# until a full stop, semicolon, colon, or a turning word such as "but" / "however".
NEGATION_RE = re.compile(
    r"\b(no|without|negative for|absence of|absent|not seen|not identified|not demonstrated|free of|"
    r"rules? out|ruled out|nil|unremarkable|within normal)\b")
CLAUSE_BREAK_RE = re.compile(r"[.;:]|\b(but|however|except|although|whereas)\b")
NORMAL_PHRASES = ["no acute", "within normal limits", "unremarkable", "normal study", "normal sinus rhythm",
                  "no abnormality", "no significant", "grossly normal", "normal in", "are normal", "is normal",
                  "appears normal", "no focal", "clear lung", "preserved", "benign"]


# ------------------------------------------------------------------ helpers
STRONG_MEDICAL = [
    "patient", "doctor", "physician", "hospital", "clinic", "diagnosis", "impression", "findings", "radiolog", "x-ray", "xray",
    "ecg", "ekg", "mri", "ct scan", "ultrasound", "sonograph", "biopsy", "patholog", "specimen", "haemoglobin", "hemoglobin",
    "glucose", "cholesterol", "creatinine", "blood pressure", "pulse", "symptom", "prescription", "tablet", "dosage",
    "medication", "discharge summary", "admission", "lung", "liver", "kidney", "abdomen", "chest", "fracture", "lesion",
    "tumour", "tumor", "infection", "reference range", "serum", "plasma", "urine", "haematology", "hematology", "biochemistry",
    "cardiac", "heart rate", "sinus rhythm", "bpm", "mg/dl", "g/dl", "clinical", "ectopic", "rhythm", "ventricular",
]
# Words that only real reports contain (who the patient is, who reported it, what sample it is).
REPORT_MARKERS = [
    "patient name", "name of patient", "patient id", "uhid", "mrn", "referred by", "ref. by", "referring doctor", "consultant",
    "specimen", "sample collected", "collected on", "reported on", "reported by", "pathologist", "radiologist", "cardiologist",
    "impression:", "findings:", "reference range", "reg no", "lab no", "ipd no", "opd no", "bio. ref", "ref. range", "holter",
    "date of admission", "chief complaint", "rx",
]
# Words that show the file is some other kind of document (a project report, an assignment, an invoice, a CV).
NOT_MEDICAL_MARKERS = [
    "software requirements", "table of contents", "chapter 1", "abstract", "bibliography", "invoice", "gst", "total amount",
    "curriculum vitae", "resume", "assignment", "semester", "question paper", "syllabus", "acknowledgement", "declaration",
    "project report", "literature review", "methodology", "unit price", "bill to", "terms and conditions",
]


def _distinct_hits(lowered: str, words: list[str]) -> int:
    """How many different words appear, each matched from the start of a word ('mg' does not match 'management')."""
    return sum(1 for word in words if re.search(r"(?<![a-z0-9])" + re.escape(word), lowered))


def looks_like_other_document(text: str) -> bool:
    """Two or more signs of a project report, assignment, invoice or CV (see NOT_MEDICAL_MARKERS)."""
    return _distinct_hits(text.lower(), NOT_MEDICAL_MARKERS) >= 2


def has_report_signs(text: str) -> bool:
    """Weaker check for a file that already has a test result: one report marker (e.g. 'Patient Name') or three
    medical words is enough to believe that the single number really is a lab result."""
    lowered = text.lower()
    return _distinct_hits(lowered, REPORT_MARKERS) >= 1 or _distinct_hits(lowered, STRONG_MEDICAL) >= 3


def looks_medical(text: str) -> bool:
    """True only if the file reads like a real medical report: enough medical vocabulary, at least one marker that
    only reports have (patient name, specimen, impression ...) and no sign of being a different kind of document.
    A project report or an invoice that mentions patients and doctors is therefore not accepted."""
    lowered = text.lower()
    if _distinct_hits(lowered, NOT_MEDICAL_MARKERS) >= 2:
        return False
    vocabulary = _distinct_hits(lowered, STRONG_MEDICAL)
    markers = _distinct_hits(lowered, REPORT_MARKERS)
    if _distinct_hits(lowered, NOT_MEDICAL_MARKERS) == 1:
        return vocabulary >= 8 and markers >= 2
    return (vocabulary >= 5 and markers >= 1) or (vocabulary >= 3 and markers >= 2)


def detect_report_type(text: str, has_lab_values: bool = False) -> str:
    if has_lab_values:
        return "LAB"
    lowered = text.lower()
    scores = {kind: sum(1 for word in words if word in lowered) for kind, words in TYPE_KEYWORDS.items()}
    kind, best = max(scores.items(), key=lambda item: item[1])
    return kind if best >= 2 else "OTHER"


def split_sections(text: str) -> dict[str, str]:
    """{'impression': '...', 'findings': '...'}  Lines like 'IMPRESSION: ...' start a section. A heading with nothing after it (a blank
    impression to be filled in by hand) ends at the next short heading-like line instead of taking everything that follows."""
    pattern = re.compile(rf"^\s*({'|'.join(re.escape(n) for n in SECTION_NAMES)})\s*[:\-]\s*(.*)$", re.IGNORECASE)
    sections: dict[str, str] = {}
    current, since_heading = None, 0
    for line in text.split("\n"):
        match = pattern.match(line)
        if match:
            current, since_heading = match.group(1).lower(), 0
            sections[current] = (sections.get(current, "") + " " + match.group(2)).strip()
        elif current:
            since_heading += 1
            if line.strip().startswith("*"):
                continue                                 # a footnote such as "*Findings to be clinically correlated"
            words = line.split()
            heading_like = 0 < len(words) <= 4 and not re.search(r"[.;]$", line.strip())
            if not sections[current] and heading_like:
                current = None                           # the section was empty and a new heading starts
                continue
            sections[current] = (sections[current] + " " + line.strip()).strip()
    return {k: v for k, v in sections.items() if v}


BOILERPLATE = [
    r"page\s+\d+\s*(?:of|/)\s*\d+", r"©|\(c\)\s*\d{4}|copyright|all rights reserved", r"\bbiosensor\s+id\b", r"https?://|www\.", r"[\w.+-]+@[\w-]+\.[\w.]+",
    r"^\s*(?:signature(?:\s+and\s+date)?|interpreting physician|reporting physician|name|date|sign|stamp|doctor'?s? (?:name|signature))\s*:?\s*$",
    r"^\s*(?:patient|patient name|holter report of|report of)\b.{0,60}\[", r"^\s*(?:tel|phone|mobile|fax)\b", r"\bmrd#", r"printed on|approved on|registration on",
]
BOILERPLATE_RE = re.compile("|".join(BOILERPLATE), re.IGNORECASE)


def clean_report_text(text: str) -> str:
    """The report without its page headers and footers (page numbers, copyright and device lines, signature blocks, the patient banner)
    and without lines that repeat on every page. Used for the summary and the key statements, so they are made of the report's content."""
    lines = text.split("\n")
    norm = lambda l: re.sub(r"\s+", " ", l.strip().lower())
    counts: dict[str, int] = {}
    for l in lines:
        if len(l.strip()) >= 18 and len(l.split()) >= 2 and not re.search(r"\d", l):
            counts[norm(l)] = counts.get(norm(l), 0) + 1
    keep = []
    for l in lines:
        if BOILERPLATE_RE.search(l):
            continue
        if len(l.strip()) >= 18 and len(l.split()) >= 2 and not re.search(r"\d", l) and counts.get(norm(l), 0) >= 3:
            continue                                    # a title or navigation line repeated on every page
        keep.append(l)
    return "\n".join(keep)


ABBREVIATIONS = re.compile(r"\b(no|nos|dr|mr|mrs|ms|vs|approx|fig|st|ref|avg|max|min)\.", re.IGNORECASE)
PAIR_RE = re.compile(r"[^:\n]{1,45}:\s*-?\d[\d,.]*\s*[A-Za-z%/]{0,6}")


def _is_data_line(sentence: str) -> bool:
    """A table row such as 'VPB Isolated Ectopics: 0 Pairs: 0 Run Beats: 0'. Rows like this are shown as numbers
    (see extract_metrics), not as sentences."""
    return len(PAIR_RE.sub("", sentence).strip(" .,;-")) < 15 and bool(PAIR_RE.search(sentence))


def split_statements(text: str) -> list[str]:
    """Plain sentences of the report. Abbreviations such as 'No.' do not end a sentence, table rows are left out,
    and a sentence that appears twice (reports repeat headers on every page) is kept once."""
    protected = ABBREVIATIONS.sub(lambda m: m.group(1) + "․", text)        # one-dot leader: not a sentence end
    parts = re.split(r"(?<=[.;])\s+|\n+", protected)
    seen, out = set(), []
    for part in parts:
        sentence = part.replace("․", ".").strip(" -*•")
        key = re.sub(r"\W+", " ", sentence.lower()).strip()
        if not 15 <= len(sentence) <= 320 or key in seen or _is_data_line(sentence):
            continue
        seen.add(key)
        out.append(sentence)
    return out


# ------------------------------------------------------------------ numbers in a narrative report (KPI tiles)
UNITS = r"(?:bpm|ms|msec|sec|s|mm|cm|mmhg|mm/s|mv|%|beats|/min|min|hrs|hr|hours|kg|mg|g|ml|cc)"
METRIC_RE = re.compile(
    r"(?P<label>[A-Za-z][A-Za-z0-9 /()%\-]{1,60}?)\s*[:=]\s*(?P<value>-?\d[\d,]*(?:\.\d+)?)(?:\s*(?P<unit>" + UNITS + r")(?![A-Za-z]))?"
    r"(?:\s*\(\s*(?P<low>-?\d+(?:\.\d+)?)\s*(?:-|–|to)\s*(?P<high>-?\d+(?:\.\d+)?)\s*\))?", re.IGNORECASE)
SKIP_LABELS = ("age", "date", "phone", "mobile", "tel", "id", "uhid", "mrn", "pin", "page", "ref", "dob", "time", "bed", "room",
               "sex", "gender", "year", "no", "number", "sr", "serial", "visit", "opd", "ipd", "contact", "zip")
EVENT_WORDS = ("episode", "ectopic", "pause", "run", "couplet", "pair", "vtac", "svt", "vpb", "event", "arrhythm", "block")


SIGNIFICANT_EVENTS = ("pause", "vtac", "ventricular", "svt", "atrial fib", "asystole", "episode", "block")      # a count above zero is worth a look
# (counts of single or paired ectopic beats are reported as numbers but are not marked on their own)


def _tidy_label(label: str) -> str:
    label = re.sub(r"\s+", " ", label).strip(" -:/()")
    label = re.sub(r"^(?:MRD#?\S*|NA|N/A)\s+", "", label, flags=re.IGNORECASE)          # "MRD#NA Height" -> "Height"
    label = re.sub(r"\bNo of\b", "No. of", label)
    return label[:1].upper() + label[1:] if label else label


STAT_RE = re.compile(r"\b(?P<stat>max(?:imum)?|min(?:imum)?|avg|average|mean)\b\s*[:=]?\s*(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>" + UNITS + r")(?![A-Za-z])", re.IGNORECASE)


def _stat_metrics(line: str) -> list[dict]:
    """'Heart rate: Max 142 bpm  Min 48 bpm  Avg 72 bpm' gives three numbers: Heart rate (max), (min), (average)."""
    first = STAT_RE.search(line)
    if not first:
        return []
    before = line[:first.start()].rstrip(" :=")                     # '... Total beats: 98562  Heart rate'
    tail = re.search(r"([A-Za-z][A-Za-z ]*)$", before)              # the words just before 'Max', after the last number
    prefix = " ".join(tail.group(1).split()[-3:]) if tail else "Value"
    names = {"max": "highest", "min": "lowest", "avg": "average", "mea": "average"}
    out = []
    for m in STAT_RE.finditer(line):
        value = float(m.group("value"))
        out.append({"label": f"{prefix[:1].upper() + prefix[1:]} ({names[m.group('stat').lower()[:3]]})", "value": int(value) if value == int(value) else value,
                    "unit": m.group("unit"), "range": None, "concern": "neutral"})
    return out


def extract_metrics(text: str, limit: int = 16) -> list[dict]:
    """Label: number pairs found in the text, for a doctor's 'key numbers' view. Each is
    {label, value, unit, range, concern}. A number is judged only if the report prints a range next to it, or if it counts
    events (episodes, ectopics, pauses ...) and the count is above zero."""
    found, seen = [], set()
    cleaned = ABBREVIATIONS.sub(lambda m: m.group(1), text)
    for line in cleaned.split("\n"):
        for extra in _stat_metrics(line):
            if (extra["label"].lower(), extra["value"]) not in seen:
                seen.add((extra["label"].lower(), extra["value"]))
                found.append(extra)
        for m in METRIC_RE.finditer(STAT_RE.sub(" ", line)):
            label = _tidy_label(m.group("label"))
            words = label.lower().split()
            if not words or len(label) < 2 or words[-1] in SKIP_LABELS or label.lower() in SKIP_LABELS:
                continue
            if sum(c.isalpha() for c in label) < 2:
                continue
            try:
                value = float(m.group("value").replace(",", ""))
            except ValueError:
                continue
            low = float(m.group("low")) if m.group("low") else None
            high = float(m.group("high")) if m.group("high") else None
            concern = "neutral"
            if low is not None and high is not None:
                concern = "attention" if (value < low or value > high) else "normal"
            elif any(w in label.lower() for w in EVENT_WORDS):
                if any(w in label.lower() for w in SIGNIFICANT_EVENTS) or re.search(r"\b(?:vpb|pvc|vt)\b", label, re.IGNORECASE):     # VPB = ventricular; SVPB (supraventricular) is not matched
                    concern = "attention" if value > 0 else "normal"
            key = (label.lower(), value)
            if key in seen:
                continue
            seen.add(key)
            unit = (m.group("unit") or "").replace("MMHG", "mmHg").replace("mmhg", "mmHg")
            found.append({"label": label, "value": int(value) if value == int(value) else value, "unit": unit or None,
                          "range": f"{m.group('low')} - {m.group('high')}" if low is not None else None, "concern": concern})
    found = _group_repeated(found)
    order = {"attention": 0, "neutral": 1, "normal": 2}
    found.sort(key=lambda f: order[f["concern"]])
    return found[:limit]


def _group_repeated(found: list[dict]) -> list[dict]:
    """The same measurement printed on every day of a long report (for example a daily summary) becomes ONE card: its highest
    reading, with the number of readings and their range as a note."""
    groups: dict[str, list[dict]] = {}
    for m in found:
        groups.setdefault(m["label"].lower(), []).append(m)
    out = []
    for items in groups.values():
        if len(items) == 1:
            out.append(items[0])
            continue
        values = [i["value"] for i in items if isinstance(i["value"], (int, float))]
        top = dict(max(items, key=lambda i: i["value"] if isinstance(i["value"], (int, float)) else -1))
        if values:
            top["detail"] = f"{len(items)} readings in the report, from {min(values):,.4g} to {max(values):,.4g}"
        out.append(top)
    return out


def _after(lines: list[str], label: str, start: int = 0) -> tuple[int, str | None]:
    for i in range(start, len(lines)):
        if lines[i].strip().lower() == label.lower():
            return i, (lines[i + 1].strip() if i + 1 < len(lines) else None)
    return -1, None


def extract_holter_facts(text: str) -> dict | None:
    """The key values of a Holter / long-term ECG report, whose summary page prints a label on one line and its value on the next
    (Min / 39 bpm Oct-05 02:30, Total beats ..., Supraventricular ectopics: Total / Isolated / Couplet ... then the values in the same order).
    Returns {"facts": [metric tiles], "findings": text} or None when this is not such a report."""
    if not re.search(r"\bholter\b", text, re.IGNORECASE):
        return None
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    facts: list[dict] = []

    def add(label, value, unit=None, detail=None, concern="neutral"):
        facts.append({"label": label, "value": value, "unit": unit, "range": None, "concern": concern, "detail": detail})

    hr_at, _ = _after(lines, "Heart Rate")
    if hr_at >= 0:
        for label, key, low_bad, high_bad in (("Lowest heart rate", "Min", 40, None), ("Highest heart rate", "Max", None, 130), ("Average heart rate", "Avg", None, None)):
            at, value = _after(lines, key, hr_at)
            m = re.match(r"(\d+)\s*bpm\s*(.*)", value or "", re.IGNORECASE)
            if m:
                n = int(m.group(1))
                add(label, n, "bpm", m.group(2) or None, "attention" if (low_bad and n < low_bad) or (high_bad and n > high_bad) else "neutral")
    _, rr = _after(lines, "Longest RR")
    m = re.match(r"([\d.]+)\s*s\s*(.*)", rr or "", re.IGNORECASE)
    if m:
        add("Longest gap between beats (RR)", float(m.group(1)), "sec", m.group(2) or None, "attention" if float(m.group(1)) >= 2.0 else "neutral")
    joined = " ".join(lines)
    m = re.search(r"Total Beats\s+(\d+)\s+Brady Beats\s+(\d+)\s*\(([\d.]+)%\)\s+Tachy Beats\s+(\d+)\s*\(([\d.]+)%\)\s+Pauses\s*\(\s*>?\s*([\d.]+)\s*Sec\)\s+(\d+)", joined, re.IGNORECASE)
    if m:
        add("Total heartbeats recorded", int(m.group(1)))
        add("Slow beats (bradycardia)", int(m.group(2)), None, f"{m.group(3)}% of all beats")
        add("Fast beats (tachycardia)", int(m.group(4)), None, f"{m.group(5)}% of all beats")
        add(f"Pauses longer than {m.group(6)} seconds", int(m.group(7)), None, None, "attention" if int(m.group(7)) > 0 else "normal")
    ve_at, ve = _after(lines, "Ventricular Ectopics")
    if ve and ve.lower() == "not present":
        add("Ventricular ectopic beats", "None", None, "reported as not present", "normal")
    sv_at, _ = _after(lines, "Supraventricular Ectopics")
    if sv_at >= 0:
        labels = []
        for l in lines[sv_at + 1: sv_at + 9]:
            if l.lower() in ("total", "isolated", "couplet", "run count", "beats in run", "fastest run", "longest run"):
                labels.append(l.lower())
            else:
                break
        values = lines[sv_at + 1 + len(labels): sv_at + 1 + 2 * len(labels)]
        nice = {"total": "Supraventricular ectopic beats (total)", "isolated": "Single supraventricular ectopic beats", "couplet": "Pairs of supraventricular beats",
                "run count": "Runs of supraventricular beats", "beats in run": "Beats inside runs", "fastest run": "Fastest run", "longest run": "Longest run"}
        for label, value in zip(labels, values):
            m = re.match(r"(\d[\d,]*)\s*(\([^)]*\)|bpm|beats)?\s*(.*)", value)
            if m:
                note = " ".join(x for x in (m.group(2), m.group(3)) if x and x not in ("bpm", "beats")) or None
                add(nice[label], int(m.group(1).replace(",", "")), m.group(2) if m.group(2) in ("bpm", "beats") else None, note)
    _, af = _after(lines, "Atrial Fibrillation")
    if af:
        add("Atrial fibrillation", "None" if af.lower() == "not present" else af, None, "reported as not present" if af.lower() == "not present" else None, "normal" if af.lower() == "not present" else "attention")
    _, duration = _after(lines, "Analysis Duration")
    if duration:
        add("Recording analysed", duration)
    findings = ""
    start = next((i for i, l in enumerate(lines) if re.match(r"findings\s*:", l, re.IGNORECASE)), None)
    if start is not None:
        end = next((i for i in range(start + 1, len(lines)) if re.match(r"impression\s*:", lines[i], re.IGNORECASE)), min(len(lines), start + 12))
        findings = " ".join(l for l in lines[start + 1: end] if not l.startswith("*"))
    return {"facts": facts, "findings": findings} if facts or findings else None


def _is_negated(sentence: str, start: int) -> bool:
    """Is the attention word that starts at `start` preceded by a negation within a few words?"""
    before = sentence[:start].lower()
    breaks = list(CLAUSE_BREAK_RE.finditer(before))
    clause = before[breaks[-1].end():] if breaks else before        # only the text of the same clause counts
    return bool(NEGATION_RE.search(clause[-120:]))


def classify_statement(sentence: str) -> tuple[str, bool]:
    """Return (concern, urgent). concern is 'normal', 'attention' or 'neutral'."""
    lowered = sentence.lower().replace("body mass index", "bmi")   # "mass" in BMI is not a finding
    attention_hit = False
    negated_hit = False
    urgent_hit = False
    for term in ATTENTION_TERMS:
        # \b = the word must START here, so "mass" matches "masses" but not "gymnasium"
        for match in re.finditer(r"\b" + re.escape(term), lowered):
            if _is_negated(lowered, match.start()):
                negated_hit = True       # e.g. "no masses seen": the finding is explicitly absent
            else:
                attention_hit = True
    for term in URGENT_TERMS:
        for match in re.finditer(r"\b" + re.escape(term), lowered):
            if not _is_negated(lowered, match.start()):
                urgent_hit = True
    if attention_hit:
        return "attention", urgent_hit
    if negated_hit or any(phrase in lowered for phrase in NORMAL_PHRASES) or any(n in lowered for n in ("no evidence of", "negative for")):
        return "normal", False
    return "neutral", False


# ------------------------------------------------------------------ doctor suggestions and patient tips (templates)
DOCTOR_BY_TYPE = {
    "IMAGING": [
        "Review the original images or the radiologist's full report and correlate the impression with the patient's symptoms and examination.",
        "Compare with any earlier imaging of the same area, which this system does not hold, to see whether a finding is new or changed.",
    ],
    "ECG": [
        "Correlate the tracing with symptoms, blood pressure, electrolytes and the medicines the patient takes.",
        "Compare with a previous ECG if one exists, because a change from the patient's baseline matters more than a single tracing.",
    ],
    "PATHOLOGY": [
        "Make sure the responsible clinician has read the full pathology report, including margins, grade and any special tests.",
        "Consider whether the result should be discussed in a multidisciplinary meeting and how it will be explained to the patient.",
    ],
    "DISCHARGE": [
        "Reconcile the discharge medicines with what the patient already takes, and check allergies.",
        "Confirm that follow-up visits and any pending tests mentioned in the summary have been arranged.",
    ],
    "PRESCRIPTION": [
        "Check dose, frequency and duration against the patient's age, allergies, kidney and liver function and other medicines.",
        "Look for duplicate medicines or known interactions before the prescription is accepted.",
    ],
    "CLINICAL": [
        "Check that the assessment and plan match the findings written in the note.",
        "Confirm that any tests or referrals mentioned in the plan have been ordered.",
    ],
    "OTHER": [
        "The computer cannot be sure of the type of this document. Please read the original before relying on this summary.",
    ],
}
PATIENT_BY_TYPE = {
    "IMAGING": ["Bring any earlier scans or X-rays to your appointment so your doctor can compare them."],
    "ECG": ["Tell your doctor about chest discomfort, dizziness, fainting or a racing heartbeat if you notice them."],
    "PATHOLOGY": ["Ask your doctor to explain this result in person. Waiting for results can be stressful, so talking to someone you trust can help."],
    "DISCHARGE": ["Follow the instructions in your discharge papers and keep every follow-up visit."],
    "PRESCRIPTION": ["Take medicines exactly as written, tell your doctor about any allergies, and ask the pharmacist if anything is unclear."],
    "CLINICAL": ["Keep a short list of your symptoms and questions for your next visit."],
    "OTHER": [],
    "LAB": [],
}
PATIENT_GENERAL = [
    "Take this report to your next appointment and ask your doctor what it means for you.",
    "Do not start, stop or change any medicine on your own. Your doctor decides about medicines.",
    "If you feel worse or notice new symptoms, contact your doctor or hospital.",
]

LAB_DOCTOR_BY_CATEGORY = {
    "glucose": "Glucose-related values are outside the printed range: consider reviewing symptoms, diet and family history, and repeating or confirming the test as you judge appropriate.",
    "lipid": "Lipid values are outside the printed range: consider overall cardiovascular risk factors, family history and whether a repeat fasting profile is needed.",
    "liver": "Liver-related values are outside the printed range: consider medicines, alcohol and infection history, and compare with earlier values.",
    "kidney": "Kidney-related values are outside the printed range: consider hydration, medicines that affect the kidney, blood pressure and a repeat test.",
    "vitamin": "Vitamin levels are outside the printed range: consider diet, sun exposure and whether supplementation is needed (your decision).",
    "thyroid": "Thyroid values are outside the printed range: consider a full thyroid panel and a review of symptoms.",
    "cbc": "Blood count values are outside the printed range: consider symptoms, recent illness or bleeding, and whether a repeat or further tests are needed.",
    "urine": "Urine results are outside the printed range: consider repeating with a clean sample and correlating with symptoms.",
}
LAB_PATIENT_BY_CATEGORY = {
    "glucose": ["Choose whole grains, vegetables and fibre-rich foods, and limit sugary drinks and sweets.",
                "A daily walk of around 30 minutes is a gentle habit, if your doctor says activity is fine for you.",
                "Try to eat at regular times."],
    "lipid": ["Eat more vegetables, fruit, nuts, oats and fish, and eat less fried and processed food.",
              "Regular activity and not smoking are good for your heart."],
    "liver": ["Limit or avoid alcohol.", "Ask your doctor before using herbal products or supplements."],
    "kidney": ["Drink enough water through the day unless your doctor has told you otherwise.", "Eat less extra salt."],
    "vitamin": ["Spend a little time outdoors in daylight and eat a varied diet.",
                "Ask your doctor before taking strong supplements."],
    "thyroid": ["Keep a regular sleep routine and find ways to relax.",
                "Tell your doctor about tiredness, weight changes or a racing heartbeat."],
    "cbc": ["Eat a varied diet with leafy greens, pulses and fruit.", "Rest well and drink water."],
    "urine": ["Drink water regularly through the day."],
}


@dataclass
class LabItem:
    """The few facts about one lab value that the insight engine needs (works for fresh and stored results)."""
    name: str
    category: str | None
    status: str          # WITHIN_RANGE / ABOVE_RANGE / BELOW_RANGE / UNKNOWN
    value: float
    unit: str | None
    low: float | None
    high: float | None


def _far_from_range(item: LabItem) -> bool:
    """A value 3 times above the upper limit or below a third of the lower limit: worth a second look
    (could be a real finding or a unit/typing mistake). Only uses the range printed on the report."""
    if item.status == "ABOVE_RANGE" and item.high and item.high > 0:
        return item.value >= 3 * item.high
    if item.status == "BELOW_RANGE" and item.low and item.low > 0:
        return item.value <= item.low / 3
    return False


# ------------------------------------------------------------------ builders
def build_lab_insights(items: list[LabItem]) -> dict:
    """Insights for a laboratory report. The out-of-range values are ranked (see result_priority): a few "look at first" results, the rest
    listed once as "slightly outside", calculated values not repeated, and only a handful of suggestions and tips."""
    pri = prioritise(items)
    important, slight, derived = pri["important"], pri["slight"], pri["derived"]
    categories = []
    for e in important:                                                  # the categories of the most important results first
        if e["category"] and e["category"] not in categories:
            categories.append(e["category"])

    key_findings = [{"text": e["text"], "concern": "attention"} for e in important[:8]]
    minor = slight + derived
    if minor:
        names = ", ".join(e["name"] for e in minor[:10]) + (f" and {len(minor) - 10} more" if len(minor) > 10 else "")
        key_findings.append({"text": f"{len(minor)} other result{'s are' if len(minor) != 1 else ' is'} only slightly outside the printed range, or {'are minor tests' if len(minor) != 1 else 'is a minor test'}: {names}.",
                             "concern": "neutral"})
    if not key_findings:
        key_findings = [{"text": "Every value that has a printed range is inside it.", "concern": "normal"}]

    doctor = []
    if important:
        doctor.append(f"{len(important)} result{'s need' if len(important) != 1 else ' needs'} attention first: {', '.join(e['name'] for e in important[:6])}. "
                      f"{len(minor)} other{'s are' if len(minor) != 1 else ' is'} only slightly outside the printed range. Compare with the patient's earlier reports (Compare tab) before drawing conclusions."
                      if minor else f"{len(important)} result{'s need' if len(important) != 1 else ' needs'} attention first: {', '.join(e['name'] for e in important[:6])}. "
                                    "Compare with the patient's earlier reports (Compare tab) before drawing conclusions.")
    elif minor:
        doctor.append(f"No result is far outside its printed range. {len(minor)} {'are' if len(minor) != 1 else 'is'} slightly outside ({', '.join(e['name'] for e in minor[:6])}): "
                      "consider whether this matters for this patient before repeating tests.")
    else:
        doctor.append("All values that have a printed range are inside it. Routine follow-up as you judge appropriate.")
    if pri["no_range"]:
        doctor.append(f"{len(pri['no_range'])} value(s) have no printed range ({', '.join(pri['no_range'][:5])}) and cannot be judged here. Check them against your local reference ranges.")
    doctor += [LAB_DOCTOR_BY_CATEGORY[c] for c in categories[:3] if c in LAB_DOCTOR_BY_CATEGORY]

    red_flags = [f"{i.name} is far from the printed range ({i.value:g}{(' ' + i.unit) if i.unit else ''} vs {i.low if i.low is not None else ''}"
                 f"{'-' if i.low is not None and i.high is not None else ''}{i.high if i.high is not None else ''}). "
                 "Check for a measurement or unit mistake, or whether it needs prompt attention."
                 for i in items if i.status in ("ABOVE_RANGE", "BELOW_RANGE") and _far_from_range(i) and i.name not in DERIVED]

    patient = []
    for n, c in enumerate(categories[:3]):                               # tips only for the categories that matter most: two lines each, one for the third
        patient += LAB_PATIENT_BY_CATEGORY.get(c, [])[:2 if n < 2 else 1]
    patient += PATIENT_GENERAL

    return {
        "report_type": "LAB", "source": "rules", "summary": summary_text(items),
        "key_findings": key_findings, "red_flags": red_flags, "doctor_suggestions": _dedupe(doctor)[:6], "patient_recommendations": _dedupe(patient)[:8],
        "engine": 2, "priority": important, "slightly_outside": [{k: e[k] for k in ("name", "value", "unit", "range", "direction", "how_far")} for e in minor],
        "counts": pri["counts"],
    }


def build_narrative_insights(text: str, report_type: str) -> dict:
    cleaned = clean_report_text(text)
    sections = split_sections(cleaned)
    holter = extract_holter_facts(text)
    key_text = " ".join(sections[name] for name in KEY_SECTIONS if name in sections) or (holter["findings"] if holter and holter["findings"] else cleaned)
    statements = split_statements(key_text)[:14]
    metrics = holter["facts"] if holter and holter["facts"] else extract_metrics(text)

    findings, red_flags = [], []
    for sentence in statements:
        concern, urgent = classify_statement(sentence)
        findings.append({"text": sentence, "concern": concern})
        if urgent:
            red_flags.append(f'The report says: "{sentence}". This wording may need prompt attention by the doctor.')
    for m in metrics:                                           # a pause, atrial fibrillation or a dangerously slow rate is raised even when the sentences do not say it
        if holter and m["concern"] == "attention" and m["label"].startswith(("Pauses", "Atrial fib")):
            red_flags.append(f"{m['label']}: {m['value']}{(' ' + m['unit']) if m['unit'] else ''}. Please check this against the original report.")

    attention = [f for f in findings if f["concern"] == "attention"]
    normal = [f for f in findings if f["concern"] == "normal"]
    label = REPORT_TYPE_LABELS.get(report_type, "Medical report")

    doctor = list(DOCTOR_BY_TYPE.get(report_type, DOCTOR_BY_TYPE["OTHER"]))
    if attention:
        doctor.append(f"{len(attention)} statement(s) mention something that may need follow-up (marked 'worth a look'). "
                      "Decide whether further tests, a repeat study or a specialist opinion is needed.")
    elif findings:
        doctor.append("No statement in the key sections mentions an abnormal finding. Confirm this by reading the original report.")
    doctor.append("This is an automatic reading of the text and can miss or misread details. It supports, and does not replace, your own review.")

    if metrics:
        flagged = [m for m in metrics if m["concern"] == "attention"]
        doctor.append(f"{len(metrics)} measured values were read from the report (see 'Key numbers'). "
                      + (f"{len(flagged)} of them need a look: {', '.join(m['label'] for m in flagged[:4])}." if flagged else "None of them is outside a printed range or a finding that needs a look."))

    patient = list(PATIENT_BY_TYPE.get(report_type, [])) + PATIENT_GENERAL

    impression = sections.get("impression") or sections.get("conclusion") or sections.get("diagnosis")
    summary = f"{label}. "
    if findings:
        summary += f"{len(findings)} key statements were found: {len(normal)} look normal and {len(attention)} are worth a look. "
    if metrics:
        summary += f"{len(metrics)} key numbers were read. "
    if impression:
        summary += f'The report\'s impression: "{impression[:240]}"'
    elif findings:
        summary += f'The report\'s findings: "{" ".join(f["text"] for f in findings[:2])[:260]}"'
    return {
        "report_type": report_type, "source": "rules", "engine": 2, "summary": summary.strip(),
        "key_findings": findings, "metrics": metrics, "red_flags": red_flags,
        "doctor_suggestions": _dedupe(doctor), "patient_recommendations": _dedupe(patient),
        **({"holter": {"recording": next((m["value"] for m in metrics if m["label"] == "Recording analysed"), None)}} if holter else {}),
    }


def _dedupe(items: list[str]) -> list[str]:
    seen, out = set(), []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


LAB_COMMENT_SECTIONS = ("impression", "conclusion", "comment", "comments", "remark", "remarks", "advice", "note", "notes")
EDUCATIONAL_START = re.compile(r"^\W*(?:increased|decreased|raised|reduced|elevated|interpretation|limitations?|summary and uses|reference|explanation|causes?|clinical significance|"
                               r"note that|please note|in random|due to|because)\b", re.IGNORECASE)


def lab_comment_findings(text: str) -> tuple[list[dict], list[str]]:
    """Sentences the laboratory itself wrote about THIS patient (an impression, comment or remark under the table). Explanation pages
    such as "Increased in: ..." or "Limitations" describe the test in general and are never findings."""
    sections = split_sections(clean_report_text(text))
    body = " ".join(sections[n] for n in LAB_COMMENT_SECTIONS if n in sections)
    findings, red = [], []
    for sentence in split_statements(body)[:8]:
        if EDUCATIONAL_START.match(sentence):
            continue
        concern, urgent = classify_statement(sentence)
        findings.append({"text": sentence, "concern": concern})                  # the lab's own words about this patient are shown, whatever their tone
        if urgent:
            red.append(f'The report says: "{sentence}". This wording may need prompt attention by the doctor.')
    return findings[:4], red
