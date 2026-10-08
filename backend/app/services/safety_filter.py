"""Safety filter applied to every AI-written text before it reaches the user.
If the text contains diagnosis / prescription style language, it is rejected and the
deterministic template text is used instead."""
import re

DISCLAIMER = (
    "HealthWise AI provides AI-assisted educational analysis of uploaded health reports. It is not a diagnostic "
    "system. AI analysis must be reviewed by a qualified healthcare professional. Prescriptions are created only "
    "by authorized doctors."
)

_FORBIDDEN = [
    r"\byou (?:have|suffer from|are suffering|are diabetic|are anemic|are anaemic)\b",
    r"\bdiagnos(?:is|ed|e|es)\b",
    r"\byou(?:'re| are) (?:sick|ill|diseased)\b",
    r"\b(?:prescrib\w+|dosage|dose of)\b",
    r"\b(?:stop|skip|reduce|increase|change|double) (?:taking )?(?:your )?(?:medication|medicine|tablets?|insulin|pills?)\b",
    r"\bstart (?:taking )?\w*\s?(?:medication|medicine|tablets?|insulin|supplements?)\b",
    r"\b\d+\s?(?:mg|mcg|iu|ml)\s+(?:daily|per day|a day|twice)\b",
    r"\b(?:cure|cures|cured|guarantee\w*|will (?:become|return to) normal)\b",
    r"\b\d{1,3}\s?%\s+healthy\b",
    r"\bemergency\b",
]
_FORBIDDEN_RE = re.compile("|".join(_FORBIDDEN), re.IGNORECASE)


# Text written for DOCTORS may use clinical words (diagnosis, differential ...), but it must still never contain
# doses or instructions to prescribe, cures/guarantees, or tell anyone "you have <disease>".
_DOCTOR_FORBIDDEN = [
    r"\b\d+(?:\.\d+)?\s?(?:mg|mcg|ug|ml|iu|units?)\b",
    r"\b(?:prescribe|administer|start|give)\s+(?:him|her|them|the patient)?\s*\w*\s?(?:tablets?|capsules?|injection|insulin|antibiotics?)\b",
    r"\byou (?:have|suffer from|are suffering)\b",
    r"\b(?:cure|cures|cured|guarantee\w*|will (?:become|return to) normal)\b",
    r"\b\d{1,3}\s?%\s+healthy\b",
]
_DOCTOR_FORBIDDEN_RE = re.compile("|".join(_DOCTOR_FORBIDDEN), re.IGNORECASE)


def is_safe_for_doctor(text: str) -> bool:
    return bool(text) and not _DOCTOR_FORBIDDEN_RE.search(text)


def is_safe(text: str) -> bool:
    return bool(text) and not _FORBIDDEN_RE.search(text)


def filter_text(ai_text: str | None, fallback: str) -> str:
    """Return the AI text if it is safe, otherwise the deterministic fallback."""
    if ai_text and is_safe(ai_text):
        return ai_text.strip()
    return fallback
