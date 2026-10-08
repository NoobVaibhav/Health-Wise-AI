"""Optional LLM layer. It ONLY rewrites wording of results that were already classified by the rule
engine. It never decides whether a value is normal. If no API key is set, or the call fails, the app
simply keeps the template explanations (so the platform works without an LLM)."""
import json
import logging
import re

import httpx

from app.core.config import get_settings
from app.services.analysis_engine import AnalyzedParameter, STATUS_LABELS
from app.services.safety_filter import filter_text, is_safe, is_safe_for_doctor

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You write short, friendly, plain-language explanations of laboratory values for a general wellness app. "
    "STRICT RULES: use only the facts given; never diagnose; never say the person has a disease; never mention "
    "medicines, doses or supplements; never promise results; do not give emergency instructions. When a value is "
    "outside the printed range, suggest discussing it with a qualified healthcare professional. Respond with JSON only."
)


def llm_is_configured() -> bool:
    return bool(get_settings().llm_api_key)


def _call_llm(user_prompt: str, system: str = SYSTEM_PROMPT) -> str | None:
    settings = get_settings()
    try:
        response = httpx.post(
            settings.llm_api_url,
            headers={"x-api-key": settings.llm_api_key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": settings.llm_model, "max_tokens": 2000, "system": system,
                  "messages": [{"role": "user", "content": user_prompt}]},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["content"][0]["text"]
    except Exception as exc:  # network error, bad key, bad JSON ... -> fall back silently
        logger.warning("LLM unavailable, using template explanations: %s", exc)
        return None


def enhance_explanations(analyzed: list[AnalyzedParameter], summary: str) -> str:
    """Rewrite parameter 'simple' explanations and the summary using the LLM (when configured).
    Modifies `analyzed` in place and returns the final summary. Everything passes the safety filter."""
    if not llm_is_configured():
        return summary

    facts = [{"test": a.extracted.normalized_name, "value": a.extracted.value, "unit": a.extracted.unit,
              "reference": a.extracted.reference_text, "status": STATUS_LABELS[a.status]} for a in analyzed]
    prompt = ('Facts (already verified by software): ' + json.dumps(facts) +
              '\nReturn JSON: {"summary": "<3 sentence plain-language summary>", '
              '"explanations": {"<test>": "<one simple sentence about what the test is>"}}')
    raw = _call_llm(prompt)
    if not raw:
        return summary
    try:
        data = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
    except ValueError:
        return summary

    for a in analyzed:
        ai_sentence = data.get("explanations", {}).get(a.extracted.normalized_name)
        a.explanation["simple"] = filter_text(ai_sentence, a.explanation["simple"])
    return filter_text(data.get("summary"), summary)


# ------------------------------------------------------------------ insights for ANY report (optional AI)
INSIGHT_SYSTEM_PROMPT = (
    "You help a hospital team read a medical report. You receive the report text (personal details removed) and a "
    "first reading made by software. Return JSON only: "
    '{"summary": "2-3 plain sentences", "key_findings": [{"text": "...", "concern": "normal|attention|neutral"}], '
    '"doctor_suggestions": ["points for the doctor to consider"], "patient_recommendations": ["general wellness tips"]}. '
    "STRICT RULES: use only what is in the report; never diagnose; never tell the patient they have a disease; never name "
    "medicines, doses or supplements; never promise results; doctor_suggestions are considerations for the doctor's own "
    "judgement (for example follow-up tests or comparison with earlier studies), not orders; patient_recommendations must "
    "be general, simple, safe lifestyle or follow-up tips and must tell the patient to discuss the report with their doctor."
)

_PERSONAL_LINE = re.compile(
    r"^\s*(patient|name|age|sex|gender|dob|date of birth|phone|mobile|contact|address|email|uhid|mrn|patient id|"
    r"ref(?:erred)?\s*by|consultant|bill|invoice)\b.*$", re.IGNORECASE)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"(?<!\d)(?:\+?\d[\d\s-]{8,}\d)(?!\d)")


def redact_text(text: str) -> str:
    """Remove obvious personal details before any text is sent to an outside AI service."""
    kept = []
    for line in text.split("\n"):
        if _PERSONAL_LINE.match(line):
            continue
        line = _EMAIL.sub("[removed]", line)
        line = _PHONE.sub("[removed]", line)
        kept.append(line)
    return "\n".join(kept)


def _clean_list(items, limit: int, patient_facing: bool) -> list[str]:
    """Keep only short, safe strings from an AI list."""
    cleaned = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, str) or not (10 <= len(item) <= 400):
            continue
        safe = is_safe(item) if patient_facing else is_safe_for_doctor(item)
        if safe:
            cleaned.append(item.strip())
        if len(cleaned) >= limit:
            break
    return cleaned


def enhance_insights(text: str, report_type: str, insights: dict) -> dict:
    """Ask the AI for a richer reading of the report. The rule-based `insights` stay as the fallback and any
    unsafe AI sentence is dropped. Returns the (possibly improved) insights dict."""
    if not llm_is_configured():
        return insights
    prompt = ("Report type guess: " + report_type + "\nFirst reading by software: " +
              json.dumps({k: insights[k] for k in ("summary", "key_findings")}) +
              "\n\nReport text:\n" + redact_text(text)[:7000])
    raw = _call_llm(prompt, INSIGHT_SYSTEM_PROMPT)
    if not raw:
        return insights
    try:
        data = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
    except ValueError:
        return insights

    improved = dict(insights)
    doctor = _clean_list(data.get("doctor_suggestions"), 8, patient_facing=False)
    patient = _clean_list(data.get("patient_recommendations"), 8, patient_facing=True)
    findings = []
    for f in data.get("key_findings") if isinstance(data.get("key_findings"), list) else []:
        if isinstance(f, dict) and isinstance(f.get("text"), str) and is_safe_for_doctor(f["text"]):
            findings.append({"text": f["text"].strip()[:320], "concern": f.get("concern") if f.get("concern") in ("normal", "attention", "neutral") else "neutral"})
    if doctor:   # keep the rule-based checks too: they are the safety net
        improved["doctor_suggestions"] = doctor + [d for d in insights["doctor_suggestions"] if d not in doctor][:2]
    if patient:
        improved["patient_recommendations"] = patient + [p for p in insights["patient_recommendations"] if p not in patient][:2]
    if findings:
        improved["key_findings"] = findings[:14]
    improved["summary"] = filter_text(data.get("summary"), insights["summary"])
    improved["source"] = "llm"
    return improved
