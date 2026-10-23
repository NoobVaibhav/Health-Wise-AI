"""Safety checks that run BEFORE any record is looked up or any model is called.

An emergency message gets the emergency guidance straight away. The checks are keyword rules (English, Hindi, Marathi) because
they must be fast, predictable and work without any AI service. They err on the side of showing the guidance."""
import re

EMERGENCY_PATTERNS = [
    # English
    r"\bchest (?:pain|tightness|pressure)\b", r"\bpain in (?:my )?chest\b", r"\bheart attack\b",
    r"\b(?:can ?not|can't|unable to|cannot|difficult(?:y)? to|trouble|difficulty) (?:to )?breath", r"\bshort(?:ness)? of breath\b", r"\bstruggling to breathe\b", r"\bgasping\b",
    r"\bface (?:is )?droop", r"\bslurred speech\b", r"\b(?:one[- ]sided|one side) (?:weakness|numbness)\b", r"\bweakness (?:on|in) one side\b", r"\bsudden(?:ly)? (?:numb|weak|confus|blind|vision loss)", r"\bstroke\b",
    r"\b(?:unconscious|passed out|fainted|collapsed|not responding|unresponsive)\b", r"\b(?:seizure|convulsion|having a fit)\b",
    r"\b(?:severe|heavy|uncontrolled) bleeding\b", r"\bbleeding (?:that )?(?:will not|won't|does not|doesn't) stop\b", r"\bcoughing (?:up )?blood\b", r"\bvomiting blood\b",
    r"\b(?:throat|face|tongue|lips) (?:is )?(?:swelling|swollen)\b", r"\bswelling of (?:the |my )?(?:throat|face|tongue|lips)\b", r"\banaphyla",
    r"\b(?:suicid|kill myself|end my life|want to die|take my own life)", r"\boverdose\b", r"\bswallowed (?:poison|too many)",
    # Hindi
    r"सीने में (?:तेज़ |तेज |बहुत )?दर्द", r"छाती में (?:तेज़ |तेज |बहुत )?दर्द", r"दिल का दौरा", r"सा[ंँ]स (?:लेने )?में (?:बहुत )?(?:तकलीफ|दिक्कत|परेशानी)", r"सा[ंँ]स नहीं (?:ले|आ)",
    r"बेहोश", r"दौरा पड़", r"लकवा", r"चेहरा टेढ़ा", r"बोलने में (?:दिक्कत|तकलीफ)", r"जुबान लड़खड़ा", r"खून (?:बंद|रुक) नहीं", r"खून की उल्टी", r"गला (?:या चेहरा )?सूज", r"आत्महत्या", r"मरना चाहता", r"जान देना",
    # Marathi
    r"छातीत (?:खूप |जोरात )?(?:दुखत|दुखणे|दुखतंय|वेदना)", r"हृदयविकाराचा झटका", r"श्वास घेता येत नाही", r"श्वास घेण्यास (?:खूप )?त्रास", r"दम लागत", r"बेशुद्ध", r"झटके येत", r"पक्षाघात", r"चेहरा वाकडा",
    r"बोलता येत नाही", r"रक्तस्राव थांबत नाही", r"रक्त थांबत नाही", r"रक्ताची उलटी", r"घसा सुजला", r"चेहरा सुजला", r"जीव द्यावा", r"स्वतःला संपवा",
]
EMERGENCY_RE = re.compile("|".join(EMERGENCY_PATTERNS), re.IGNORECASE)

# "What did the doctor say about my chest pain last time?" is a question about records, not an emergency, unless it also says it is happening now.
RECORD_QUESTION = re.compile(r"\b(?:last|previous|earlier|report|history|notes?|prescri\w*|result|did my|was my|were my)\b|पिछल|पहले|रिपोर्ट|मागील|आधी|शेवटच्या", re.IGNORECASE)
HAPPENING_NOW = re.compile(r"\b(?:now|right now|currently|at the moment|i am having|i'm having|i have|i feel|suddenly|since (?:morning|today|last night)|help)\b|अभी|इस समय|आत्ता|सध्या|होत आहे|हो रहा|हो रही", re.IGNORECASE)

# "What is the meaning of stroke?" is a vocabulary question, not a person having one.
EDUCATIONAL = re.compile(r"\b(?:what (?:is|are|does)|meaning of|define|explain|definition of)\b.{0,25}\b(?:stroke|seizure|heart attack|chest pain|anaphyla\w*|overdose)\b", re.IGNORECASE)

MED_CHANGE_RE = re.compile("|".join([
    r"\b(?:can|should|may|could|shall) i (?:take|have|use|try|start|eat|drink)\b|\bis it (?:safe|okay|ok) to (?:take|use|have)\b",
    r"\b(?:should|can|may|could|shall|do) i (?:just )?(?:stop|skip|quit|reduce|increase|double|halve|change|start|miss|take more|take less|take extra)\b.{0,40}\b(?:medicine|medicines|medication|tablet|tablets|pill|pills|dose|dosage|insulin|capsule|syrup)\b",
    r"\b(?:stop|stopping|skip|skipping|quit|double|increase|reduce)\b.{0,15}\b(?:my )?(?:medicine|medicines|medication|tablets?|pills?|insulin|dose)\b",
    r"दवा(?:ई|इयाँ|इयां)? (?:बंद|छोड़|बढ़ा|कम|रोक)", r"(?:दवा|गोली).{0,15}(?:बंद|छोड़|रोक|बढ़ा|कम) (?:कर|दूँ|दूं|सकता|दे)",
    r"औषध(?:े)? (?:बंद|थांबव|वाढव|कमी)", r"गोळी(?:ळ्या)? (?:बंद|थांबव|वाढव|कमी)",
]), re.IGNORECASE)

DIAGNOSIS_RE = re.compile("|".join([
    r"\bdo i have\b(?! (?:any |an? |the |my |some )?(?:allerg|appointment|report|medic|prescri|test|record|follow|pending|upcoming|instruction|advice))", r"\bam i (?:diabetic|anemic|anaemic|sick|ill|healthy|dying|in danger)\b", r"\bwhat (?:disease|illness|condition|sickness) do i have\b", r"\bdiagnose me\b", r"\bwhat(?:'s| is) wrong with me\b", r"\bis (?:it|this) (?:cancer|serious|dangerous)\b",
    r"क्या मुझे .{0,25}(?:बीमारी|रोग|डायबिटीज़|डायबिटीज)", r"मुझे कौन सी बीमारी", r"मेरी बीमारी क्या",
    r"मला कोणता आजार", r"मला .{0,20}आजार आहे का", r"माझा आजार काय",
]), re.IGNORECASE)

REACTION_RE = re.compile("|".join([
    r"\b(?:rash|hives|itching|swelling|vomiting|dizz\w*|reaction|side effects?)\b.{0,60}\b(?:medicine|medication|tablet|pill|dose|after taking)\b",
    r"\b(?:medicine|medication|tablet|pill|after taking)\b.{0,60}\b(?:rash|hives|itching|swelling|vomiting|dizz\w*|reaction|side effects?)\b",
    r"दवा.{0,40}(?:रिएक्शन|प्रतिक्रिया|चकत्ते|खुजली|उल्टी|चक्कर|सूजन)", r"(?:रिएक्शन|चकत्ते|खुजली|उल्टी|चक्कर|सूजन).{0,40}दवा",
    r"औषध.{0,40}(?:रिॲक्शन|प्रतिक्रिया|पुरळ|खाज|उलटी|चक्कर|सूज)", r"(?:रिॲक्शन|पुरळ|खाज|उलटी|चक्कर|सूज).{0,40}औषध",
]), re.IGNORECASE)


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("’", "'")).strip().lower()


def check(message: str) -> str | None:
    """EMERGENCY, MED_CHANGE, DIAGNOSIS, REACTION or None. Emergency is checked first and wins."""
    text = _clean(message)
    if EMERGENCY_RE.search(text):
        about_records = RECORD_QUESTION.search(text) or EDUCATIONAL.search(text)
        if not (about_records and not HAPPENING_NOW.search(text)):
            return "EMERGENCY"
    if MED_CHANGE_RE.search(text):
        return "MED_CHANGE"
    if REACTION_RE.search(text):
        return "REACTION"
    if DIAGNOSIS_RE.search(text):
        return "DIAGNOSIS"
    return None
