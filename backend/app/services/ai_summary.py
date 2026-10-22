"""Optional AI narrative of the verified clinical summary. It is kept apart from every clinician's own text.

The model gets only the statements that ordinary code already verified (key, label, text), with personal details removed, and no
access to the database. It must cite the statement keys it uses. What it returns is checked: a paragraph is kept only if every key
it cites exists, it passes the doctor-facing safety filter (no doses, no prescribing) and it does not claim a cause. If the model
is not configured, fails, or returns nothing usable, there is simply no AI narrative: the rule-based summary stands on its own."""
import json
import re

from app.core.config import get_settings
from app.services import llm_service
from app.services.llm_service import redact_text
from app.services.safety_filter import is_safe_for_doctor

SYSTEM_PROMPT = (
    "You help a doctor read a patient's DOCUMENTED history. You receive numbered statements that software has already verified against "
    "the hospital's records. RULES: use only these statements; never add a value, date, diagnosis, medicine or cause that is not in them; "
    "never say a medicine, disease, food or test result caused an event; never say the patient is healthy; do not prescribe or suggest doses; "
    "do not call a change good or bad unless a statement says so. Write 2 to 5 short paragraphs in clinical language. Every paragraph must list "
    "the keys of the statements it is based on. Also give up to 4 questions the doctor may want to consider, each tied to a missing or unresolved "
    "item. Reply with JSON only: {\"paragraphs\": [{\"text\": \"...\", \"cites\": [\"key\", ...]}], \"questions\": [\"...\"]}"
)
CAUSAL = re.compile(r"\b(caused|causing|due to|because of|resulted from|result of|led to|responsible for)\b", re.IGNORECASE)
SECTIONS = ("what_happened", "current_status", "important_changes", "red_flags", "missing")


def available() -> bool:
    return llm_service.llm_is_configured()


def payload(summary: dict) -> dict:
    """What the model may see: statements only, no names, phone numbers, addresses, report file names or record ids."""
    statements = []
    for section in SECTIONS:
        for s in summary[section]:
            statements.append({"key": s["key"], "section": section, "label": s["label"], "text": redact_text(s["text"])})
    o = summary["overview"]
    return {"patient": {"age": o["age"], "gender": o["gender"]}, "statements": statements}


def generate(summary: dict) -> dict | None:
    if not available():
        return None
    data = payload(summary)
    raw = llm_service._call_llm("Verified statements (JSON):\n" + json.dumps(data), SYSTEM_PROMPT)
    if not raw:
        return None
    try:
        parsed = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
    except ValueError:
        return None
    valid_keys = {s["key"] for s in data["statements"]}
    paragraphs = []
    for p in parsed.get("paragraphs") if isinstance(parsed.get("paragraphs"), list) else []:
        text, cites = p.get("text") if isinstance(p, dict) else None, p.get("cites") if isinstance(p, dict) else None
        if not isinstance(text, str) or not isinstance(cites, list) or not cites or not all(isinstance(c, str) and c in valid_keys for c in cites):
            continue                                           # no evidence, or evidence that does not exist: dropped
        if len(text) > 700 or not is_safe_for_doctor(text) or CAUSAL.search(text):
            continue
        paragraphs.append({"text": text.strip(), "cites": cites})
    questions = [q.strip() for q in (parsed.get("questions") if isinstance(parsed.get("questions"), list) else []) if isinstance(q, str) and 8 <= len(q) <= 220 and is_safe_for_doctor(q) and not CAUSAL.search(q)][:4]
    if not paragraphs:
        return None
    return {"label": "AI_GENERATED", "paragraphs": paragraphs, "questions": questions, "model": get_settings().llm_model}
