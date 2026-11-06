"""What the patient assistant does with the words of a SPOKEN question before it works out what was asked.

A speech recogniser hands back words, not meaning, and it is least reliable exactly where a health question is most specific: medicine names, test names, letters
and numbers. Three small, fixed-rule steps (no model, no outside service) make the same question work whether it was typed or spoken:

1. `strip_fillers`: "umm, can you tell me ... please" is the question with its padding taken off.
2. `repair`: a medical word split in pieces ("met for min", "h b a 1 c"), spelled in Devanagari ("मेटफॉर्मिन") or slightly misheard ("kreatinin") is put back to
   the name used in the records. Only names from a fixed list of tests and medicines, and from THIS patient's own prescriptions and reports, are ever used.
   A number in the sentence is never changed, added or dropped.
3. nothing else: what the question means is decided afterwards, by the same rules as for typed text.

The original message is what is stored and shown; only the copy used for matching is repaired."""
import difflib
import re

from app.services.parameter_catalog import PARAMETERS

# ------------------------------------------------------------------ filler words
_PREFIX = re.compile(
    r"^(?:(?:umm+|uhh*|err+|hmm+|um|uh|ah|okay|ok|so|well|hey|hi|please|pls|sir|madam|mam|yaar|bhai|dear|zara|assistant|healthwise|health wise|"
    r"(?:can|could|would|will) you (?:please )?(?:just )?(?:tell|show|give|explain|say|let)?\s?me|"
    r"i (?:want|would like|wanna|need) to know|let me know|tell me|show me|give me|please tell me|"
    r"अं+|उम्म?|ओके|कृपया|प्लीज़?|जी|सुनो|सुनिए|ज़रा|जरा|हे|अहो)[,.\s]+)+", re.IGNORECASE)
_SUFFIX = re.compile(
    r"(?:[,.\s]+(?:please|pls|sir|madam|mam|thanks|thank you|yaar|bhai|na|once|once again|once more|bata do|batao|bataiye|bata dijiye|bataiyega|kripya|dijiye|"
    r"कृपया|सांगा ना|सांगा|बताइए|बताओ|बता दो|बताइये|प्लीज़|जी|ना))+$", re.IGNORECASE)


def strip_fillers(text: str) -> str:
    """The question without "umm", "can you tell me", "please", "sir", "bata do" and the like around it. A message that is ONLY fillers is returned as it was."""
    t = text.strip()
    cleaned = _SUFFIX.sub("", _PREFIX.sub("", t)).strip(" ,.")
    return cleaned if cleaned else t


# ------------------------------------------------------------------ sound skeletons (so a Devanagari spelling and a Latin spelling of one word can be compared)
_DEVANAGARI = {
    "क": "k", "ख": "k", "ग": "g", "घ": "g", "ङ": "n", "च": "k", "छ": "k", "ज": "j", "झ": "j", "ञ": "n", "ट": "t", "ठ": "t", "ड": "d", "ढ": "d", "ण": "n", "त": "t", "थ": "t",
    "द": "d", "ध": "d", "न": "n", "प": "p", "फ": "p", "ब": "b", "भ": "b", "म": "m", "र": "r", "ल": "l", "व": "v", "श": "s", "ष": "s", "स": "s", "ळ": "l", "ं": "n", "ँ": "",
    "क़": "k", "ख़": "k", "ग़": "g", "ज़": "j", "ड़": "d", "ढ़": "d", "फ़": "p", "य": "", "ह": "",
}
# the names of letters as people say them in Hindi and Marathi: "एच बी ए वन सी" is "h b a 1 c"
_LETTER_NAMES = {"ए": "a", "बी": "b", "सी": "c", "डी": "d", "ई": "e", "एफ": "f", "जी": "g", "एच": "h", "आई": "i", "जे": "j", "के": "k", "एल": "l", "एम": "m", "एन": "n", "ओ": "o", "पी": "p",
                 "आर": "r", "एस": "s", "टी": "t", "यू": "u", "वी": "v", "एक्स": "x", "वाई": "y", "वन": "1", "टू": "2", "थ्री": "3", "फोर": "4", "फाइव": "5", "सिक्स": "6", "सेवन": "7", "एट": "8", "नाइन": "9"}
_NUMBER_WORDS = {"one": "1", "won": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9"}


def skeleton(word: str) -> str:
    """The consonant sound of a word, with Devanagari and Latin spellings mapped to the same letters: "मेटफॉर्मिन" and "metformin" both give "mtprmn"."""
    w = word.lower()
    if re.search(r"[ऀ-ॿ]", w):
        out = []
        i = 0
        w = w.replace("क्ष", "ks").replace("ज्ञ", "gn")
        while i < len(w):
            ch = w[i]
            if i + 1 < len(w) and w[i + 1] == "़":                      # a dot under a letter (ज़, फ़): the plain sound is enough
                out.append(_DEVANAGARI.get(ch, ""))
                i += 2
                continue
            out.append(_DEVANAGARI.get(ch, ch if ch in "ks" else ""))
            i += 1
        s = "".join(out)
    else:
        s = re.sub(r"[^a-z]", "", w)
        s = re.sub(r"c(?=[eiy])", "s", s)
        for a, b in (("ph", "p"), ("ck", "k"), ("ch", "k"), ("sh", "s"), ("th", "t"), ("kh", "k"), ("gh", "g"), ("dh", "d"), ("bh", "b")):
            s = s.replace(a, b)
        s = s.replace("c", "k").replace("q", "k").replace("f", "p").replace("w", "v").replace("x", "ks")
        s = re.sub(r"[aeiouyh]", "", s)
    return re.sub(r"(.)\1+", r"\1", s)


def _score(candidate: str, name: str) -> float:
    """How close the heard word is to a known name: the letters themselves (exact spelling counts most), or only the consonant sounds (slightly less)."""
    plain = difflib.SequenceMatcher(None, candidate, name).ratio() if candidate.isascii() else 0.0
    a, b = skeleton(candidate), skeleton(name)
    sound = difflib.SequenceMatcher(None, a, b).ratio() * 0.99 if len(a) >= 4 and len(b) >= 4 else 0.0
    return max(plain if plain >= 0.88 else 0.0, sound if sound >= 0.89 else 0.0)


# ------------------------------------------------------------------ the fixed vocabulary
GENERAL_TERMS = (
    "metformin", "atorvastatin", "paracetamol", "amlodipine", "telmisartan", "losartan", "aspirin", "clopidogrel", "pantoprazole", "omeprazole", "levothyroxine", "glimepiride",
    "rosuvastatin", "azithromycin", "amoxicillin", "cetirizine", "ibuprofen", "diclofenac", "montelukast", "insulin", "ramipril", "metoprolol", "furosemide", "ondansetron",
    "hemoglobin", "haemoglobin", "creatinine", "cholesterol", "triglycerides", "bilirubin", "platelet", "platelets", "glucose", "thyroid", "hba1c", "calcium", "potassium", "sodium",
    # plain words the question rules look for, so that "a point ment" or "ab normal" still finds its meaning
    "appointment", "appointments", "abnormal", "latest", "checkup", "prescription", "prescriptions", "medicine", "medicines", "medication", "allergies", "allergy", "instructions",
    "consultation", "follow-up",
)


def vocabulary(extra: list[str] | tuple[str, ...] = ()) -> list[str]:
    words = set(GENERAL_TERMS)
    for p in PARAMETERS:
        for n in (p.name, *p.aliases):
            n = n.lower()
            if n.isascii() and " " not in n and len(n) >= 5 and re.fullmatch(r"[a-z0-9]+", n):
                words.add(n)
    for n in extra:
        n = (n or "").lower().strip()
        if n and " " not in n and len(n) >= 4:
            words.add(n)
    return sorted(words)


_TOKEN = re.compile(r"[A-Za-z0-9]+|[ऀ-ॿ]+")
_ACCENTS = ((re.compile(r"\bvitamin\s+(?:dee|di|the|d3|d 3)\b"), "vitamin d"), (re.compile(r"\bcheck\s+up\b"), "checkup"))
_HBA1C = re.compile(r"\bh\s*b\s*a\s*(?:1|one|won)\s*c\b|\ba\s*(?:1|one|won)\s*c\b", re.IGNORECASE)


def _join_spelled_letters(text: str) -> str:
    """"h b a 1 c" -> "hba1c", "l d l" -> "ldl", "एल डी एल" -> "ldl". Only runs of three or more single letters/digits are joined, so a number in a sentence stays apart."""
    text = _HBA1C.sub(lambda m: "hba1c" if "h" in m.group(0).lower()[:2] else "a1c", text)
    tokens = list(_TOKEN.finditer(text))
    out, i, last = [], 0, 0
    while i < len(tokens):
        j = i
        letters = []
        while j < len(tokens):
            tok = tokens[j].group(0).lower()
            letter = _LETTER_NAMES.get(tok) or (tok if len(tok) == 1 and tok.isalnum() and tok.isascii() else None)
            if letter is None:
                break
            letters.append(letter)
            j += 1
        if len(letters) >= 3 and any(c.isalpha() for c in letters):
            out.append(text[last:tokens[i].start()])
            out.append("".join(letters))
            last = tokens[j - 1].end()
            i = j
        else:
            i += 1
    out.append(text[last:])
    return "".join(out)


def repair(text: str, extra_vocabulary: list[str] | tuple[str, ...] = ()) -> str:
    """The text with medical words put back together and spelled the way the records spell them. Digits are never touched except in "h b a 1 c" style spelling.
    A Latin word that was split ("met for min") is replaced by the name. A Devanagari word is kept and the Latin name is added after it, so the Hindi and Marathi
    keyword rules that already work on the Devanagari spelling keep working."""
    text = _join_spelled_letters(text)
    for pattern, replacement in _ACCENTS:
        text = pattern.sub(replacement, text)
    vocab = vocabulary(extra_vocabulary)
    known = set(vocab)
    tokens = list(_TOKEN.finditer(text))
    candidates = []                                                       # (score, letters, size, start, name): every group of 1 to 6 words that could be a medical word
    for i in range(len(tokens)):
        for size in range(1, min(6, len(tokens) - i) + 1):
            window = tokens[i:i + size]
            words = [m.group(0).lower() for m in window]
            if any(w.isdigit() for w in words):
                continue                                                  # a number is never part of a medical word
            joined = "".join(words)
            if size == 1 and (len(joined) < 6 or joined in known):
                continue
            if size > 1 and (any(len(w) > 8 for w in words) or not 6 <= len(joined) <= 18 or any(w in known for w in words)):
                continue
            score, name = max(((_score(joined, n), n) for n in vocab if abs(len(n) - len(joined)) <= 4 or not joined.isascii()), default=(0.0, ""))
            if score >= 0.88 and (name != joined or size > 1):
                candidates.append((score, len(joined), size, i, name))
    chosen, taken = [], set()
    for score, _, size, i, name in sorted(candidates, key=lambda c: (-c[0], -c[1], c[3])):      # the best fit first, and on a tie the group that covers more of the word
        span = set(range(i, i + size))
        if not span & taken:
            chosen.append((i, size, name))
            taken |= span
    pieces, last = [], 0
    for i, size, name in sorted(chosen):
        first, final = tokens[i], tokens[i + size - 1]
        original = text[first.start():final.end()]
        pieces.append(text[last:first.start()])
        pieces.append(f"{original} {name}" if re.search(r"[ऀ-ॿ]", original) else name)
        last = final.end()
    pieces.append(text[last:])
    return "".join(pieces)
