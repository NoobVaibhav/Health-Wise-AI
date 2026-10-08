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
    "positive for", "worsen", "progress", "increase",
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
def looks_medical(text: str) -> bool:
    """True if the text contains enough distinct medical words to be a medical document (not an invoice)."""
    lowered = text.lower()
    return sum(1 for word in MEDICAL_WORDS if word in lowered) >= 5


def detect_report_type(text: str, has_lab_values: bool = False) -> str:
    if has_lab_values:
        return "LAB"
    lowered = text.lower()
    scores = {kind: sum(1 for word in words if word in lowered) for kind, words in TYPE_KEYWORDS.items()}
    kind, best = max(scores.items(), key=lambda item: item[1])
    return kind if best >= 2 else "OTHER"


def split_sections(text: str) -> dict[str, str]:
    """{'impression': '...', 'findings': '...'}  Lines like 'IMPRESSION: ...' start a section."""
    pattern = re.compile(rf"^\s*({'|'.join(re.escape(n) for n in SECTION_NAMES)})\s*[:\-]\s*(.*)$", re.IGNORECASE)
    sections: dict[str, str] = {}
    current = None
    for line in text.split("\n"):
        match = pattern.match(line)
        if match:
            current = match.group(1).lower()
            sections[current] = (sections.get(current, "") + " " + match.group(2)).strip()
        elif current:
            sections[current] = (sections[current] + " " + line.strip()).strip()
    return sections


def split_statements(text: str) -> list[str]:
    parts = re.split(r"(?<=[.;])\s+|\n+", text)
    return [p.strip(" -*•") for p in parts if 15 <= len(p.strip()) <= 320]


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
    outside = [i for i in items if i.status in ("ABOVE_RANGE", "BELOW_RANGE")]
    unknown = [i for i in items if i.status == "UNKNOWN"]
    categories = sorted({i.category for i in outside if i.category})

    key_findings = [
        {"text": f"{i.name}: {i.value:g}{(' ' + i.unit) if i.unit else ''} is "
                 f"{'higher' if i.status == 'ABOVE_RANGE' else 'lower'} than the normal range printed on the report",
         "concern": "attention"} for i in outside
    ] or [{"text": "Every value that has a printed range is inside it.", "concern": "normal"}]

    doctor = []
    if outside:
        doctor.append(f"{len(outside)} of {len(items)} values are outside the range printed on the report. "
                      "Compare with the patient's earlier reports (see the Compare tab) before drawing conclusions.")
        doctor += [LAB_DOCTOR_BY_CATEGORY[c] for c in categories if c in LAB_DOCTOR_BY_CATEGORY]
    else:
        doctor.append("All values that have a printed range are inside it. Routine follow-up as you judge appropriate.")
    if unknown:
        doctor.append(f"{len(unknown)} value(s) have no printed range ({', '.join(i.name for i in unknown[:5])}) "
                      "and cannot be judged here. Check them against your local reference ranges.")

    red_flags = [f"{i.name} is far from the printed range ({i.value:g}{(' ' + i.unit) if i.unit else ''} vs {i.low if i.low is not None else ''}"
                 f"{'-' if i.low is not None and i.high is not None else ''}{i.high if i.high is not None else ''}). "
                 "Check for a measurement or unit mistake, or whether it needs prompt attention."
                 for i in outside if _far_from_range(i)]

    patient = []
    for c in categories:
        patient += LAB_PATIENT_BY_CATEGORY.get(c, [])
    patient += PATIENT_GENERAL

    return {
        "report_type": "LAB", "source": "rules",
        "summary": (f"{len(items)} test results were read. "
                    + (f"{len(outside)} are outside the normal range printed on the report." if outside else "All results with a printed range are in the normal range.")),
        "key_findings": key_findings, "red_flags": red_flags,
        "doctor_suggestions": doctor, "patient_recommendations": _dedupe(patient),
    }


def build_narrative_insights(text: str, report_type: str) -> dict:
    sections = split_sections(text)
    key_text = " ".join(sections[name] for name in KEY_SECTIONS if name in sections) or text
    statements = split_statements(key_text)[:14]

    findings, red_flags = [], []
    for sentence in statements:
        concern, urgent = classify_statement(sentence)
        findings.append({"text": sentence, "concern": concern})
        if urgent:
            red_flags.append(f'The report says: "{sentence}". This wording may need prompt attention by the doctor.')

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

    patient = list(PATIENT_BY_TYPE.get(report_type, [])) + PATIENT_GENERAL

    impression = sections.get("impression") or sections.get("conclusion") or sections.get("diagnosis")
    summary = f"{label}. "
    if findings:
        summary += f"{len(findings)} key statements were found: {len(normal)} look normal and {len(attention)} are worth a look. "
    if impression:
        summary += f'The report\'s own summary says: "{impression[:240]}"'
    return {
        "report_type": report_type, "source": "rules", "summary": summary.strip(),
        "key_findings": findings, "red_flags": red_flags,
        "doctor_suggestions": _dedupe(doctor), "patient_recommendations": _dedupe(patient),
    }


def _dedupe(items: list[str]) -> list[str]:
    seen, out = set(), []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
