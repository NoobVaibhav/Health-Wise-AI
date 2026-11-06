"""The spoken version of an answer: shorter than the written one, with no list marks or symbols, the source named, and the reminder to talk to the doctor kept.

It is cut from the WRITTEN answer, line by line. It never writes a value of its own, so a medicine, a dose, a test value or a date that is read aloud is exactly the
one on the screen (and in the record). A test checks that every number in the spoken text is in the written text or in the source record's date.
What is left out is not lost: `more` is true and the person can say "tell me more" to hear the whole written answer."""
import re
from datetime import date

from app.services.assistant_text import fdate, t

SOURCE_WORD = {"report": "src_report", "prescription": "src_prescription", "appointment": "src_appointment", "note": "src_note", "recommendation": "src_recommendation", "history": "src_history"}
# the closing reminders that every written answer carries: the spoken answer gets its own short one (below), so these lines are not read twice
FOOTNOTE = re.compile(r"^(?:This is what your records say|Only what is written|Please talk to your doctor|यह आपके रिकॉर्ड|कृपया अपने डॉक्टर|हे तुमच्या नोंदी|कृपया तुमच्या डॉक्टर|"
                      r"This does not|इसका मतलब|याचा अर्थ)", re.IGNORECASE)
MAX_WORDS = {"BRIEFING": 80}
DEFAULT_WORDS = 45
NO_REMINDER = {"GREETING", "THANKS", "BYE", "WHO", "TIME", "NAVIGATE", "EMERGENCY", "REFUSED", "HELP", "TERM_UNKNOWN"}


def _plain(line: str) -> str:
    line = re.sub(r"^[\s\-•*·>#]+", "", line)
    line = re.sub(r"[*_`|]+", " ", line)
    return re.sub(r"\s+", " ", line).strip()


def _words(line: str) -> int:
    return len(line.split())


def _first_sentences(line: str, limit: int) -> str:
    """A line that is longer than the limit, cut at the end of a sentence (never in the middle of one)."""
    if _words(line) <= limit:
        return line
    out, count = [], 0
    for sentence in re.findall(r"[^.!?।]+[.!?।]*\s*", line):
        n = _words(sentence)
        if out and count + n > limit:
            break
        out.append(sentence.strip())
        count += n
    return " ".join(out) if out else " ".join(line.split()[:limit])


def _from(sources: list[dict], lang: str) -> str:
    """"From your report of 12 Sep 2026." taken from the first source of the answer, when the written answer does not already say the date."""
    if not sources:
        return ""
    first = sources[0]
    word = t(SOURCE_WORD.get(first.get("type"), "src_record"), lang)
    when = first.get("date")
    if when:
        try:
            return t("spoken_from", lang, x=word, d=fdate(date.fromisoformat(str(when)[:10]), lang))
        except ValueError:
            pass
    return t("spoken_from_nodate", lang, x=word)


def spoken_version(text: str, lang: str, intent: str | None, sources: list[dict] | None) -> dict:
    """{"text": the short spoken answer, "more": whether the written answer has more, "private": what to say instead when other people may hear}."""
    sources = sources or []
    lines = [p for p in (_plain(x) for x in text.split("\n")) if p]
    body = [x for x in lines if not FOOTNOTE.match(x)]
    private = t("private_summary", lang, x=t(SOURCE_WORD.get(sources[0].get("type"), "src_record"), lang)) if sources else t("private_generic", lang)
    if intent in ("EMERGENCY", "REFUSED", "HELP", "TERM_UNKNOWN"):
        return {"text": " ".join(lines), "more": False, "private": " ".join(lines)}                 # short already, and never to be left out
    if intent == "WHO":
        body = body[:1]
    limit = MAX_WORDS.get(intent or "", DEFAULT_WORDS)
    chosen, count = [], 0
    for line in body:
        n = _words(line)
        if chosen and count + n > limit:
            break
        chosen.append(_first_sentences(line, limit) if not chosen else line)
        count += min(n, limit)
    more = len(chosen) < len(body) or any(_words(c) < _words(b) for c, b in zip(chosen, body))
    spoken = [c if c.endswith((".", "!", "?", "।", ":")) else c + "." for c in chosen]
    if intent not in NO_REMINDER and sources and not re.search(r"\d{1,2} [A-Z][a-z]{2} \d{4}|\d\d/\d\d/\d{4}", " ".join(spoken)):
        spoken.append(_from(sources, lang))
    if intent not in NO_REMINDER:
        spoken.append(t("discuss", lang))                                                           # "Please talk to your doctor ...": the professional-review wording is always spoken
    return {"text": " ".join(s for s in spoken if s), "more": more, "private": private}
