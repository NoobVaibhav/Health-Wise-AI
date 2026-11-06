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
    # Hindi and Marathi written in Latin letters (what a recogniser or a keyboard gives for "mujhe saans nahi aa rahi")
    r"\bs(?:aa|a|ah)ns\b.{0,25}\b(?:nahi|nahin|nhi|nai)\b", r"\bs(?:aa|a)ns (?:lene )?(?:me|mein|mai|madhe)\b.{0,15}\b(?:takl[ie]f|dikkat|pareshani|tras)\b",
    r"\bsee?ne (?:me|mein|mai)\b.{0,15}\bdard\b", r"\bchh?a{1,2}ti (?:me|mein|mai)\b.{0,15}\bdard\b", r"\bchh?atit\b.{0,12}\bdukh", r"\bdil ka daura\b", r"\bb[ae]?h?osh\b", r"\bdaura pad",
    r"\blakwa\b", r"\bkhoon (?:band )?nahi (?:ruk|band|ho)", r"\bkhoon ruk(?:ta)? nahi", r"\bkhoon ki ulti\b", r"\bmarna chahta", r"\bkhud ko (?:khatam|maar)", r"\bshwas (?:gheta )?yet nahi", r"\bb[ae]shudh\b",
]
EMERGENCY_RE = re.compile("|".join(EMERGENCY_PATTERNS), re.IGNORECASE)

# "What did the doctor say about my chest pain last time?" is a question about records, not an emergency, unless it also says it is happening now.
RECORD_QUESTION = re.compile(r"\b(?:last|previous|earlier|report|history|notes?|prescri\w*|result|did my|was my|were my|pichl\w*|pehle|pichhle)\b|पिछल|पहले|रिपोर्ट|मागील|आधी|शेवटच्या", re.IGNORECASE)
HAPPENING_NOW = re.compile(r"\b(?:now|right now|currently|at the moment|i am having|i'm having|i have|i feel|suddenly|since (?:morning|today|last night)|help|abhi|ho raha|ho rahi|rahi hai|raha hai|aata nahi|yet nahi)\b|अभी|इस समय|आत्ता|सध्या|होत आहे|हो रहा|हो रही", re.IGNORECASE)

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


# Someone else's records, or an attempt to change the rules by speaking to the assistant. Nothing is looked up for these: the assistant only ever has the signed-in
# patient's own records, so the answer is to say so. (Family members are included: a patient may not read a relative's records through their own login.)
_MY = r"(?:मेरी|मेरा|मेरे|माझी|माझा|माझे|मुझे|मला|आपकी|आपका|तुमची|तुमचा)"
OWN_ONLY_RE = re.compile("|".join([
    r"\b(?:other|another|all|every|everyone's|everybody's|different) (?:the )?(?:patients?|users?)(?:'s|s')?\b", r"\b(?:dusre|doosre|sabhi|baaki|baki) (?:mareez|mariz|marizon|patients?)\b",
    r"\bpatient (?:number|no\.?|id|#)\s*\d+", r"\bpatients? ?(?:id )?#?\d+\b",
    r"\b(?:neighbou?r|friend|colleague|brother|sister|wife|husband|mother|father|mom|dad|son|daughter|uncle|aunt|grandfather|grandmother|cousin)(?:'s)?\s+(?:report|result|medicine|medication|tablet|prescription|record|bill|test|blood)",
    r"\b(?:what|which) (?:medicines?|tablets?|medication|reports?) (?:does|did|is|are) (?:my )?(?:neighbou?r|friend|colleague|brother|sister|wife|husband|mother|father|mom|dad|son|daughter)\b",
    r"(?<!my )(?<!the )(?<!your )(?<!this )(?<!that )\b(?!(?:doctor|doctors|hospital|lab|labs|pharmacy|clinic|my|the|your|this|that|today|yesterday|tomorrow|week|month|year|what|there|here|who|let|latest|recent)\b)[a-z]{3,}'s\s+(?:reports?|results?|medicines?|medication|prescriptions?|records?|bills?|blood)\b",
    r"\bignore (?:all |any |your |the |these |those )*(?:previous |above |earlier |prior |safety )*(?:rules|instructions|guidelines|restrictions|safeguards)\b",
    r"\b(?:forget|disregard|override|bypass) (?:all |any |your |the |these |those )*(?:previous |above |earlier |prior |safety )*(?:rules|instructions|guidelines|restrictions|safeguards)\b",
    r"(?:^|\s)system\s*:", r"\byou (?:are|may) now (?:a |an |allowed|free|able)\b", r"\bpretend (?:to be|you are|that you)\b", r"\bact as (?:a|an|my) (?:doctor|admin|administrator)\b", r"\bdeveloper mode\b|\bjailbreak\b",
    r"\bsay you are (?:a )?doctor\b", r"\bshare (?:other|all) (?:patients?|records)\b",
    r"(?:दूसरे|दुसऱ्या|अन्य|सभी|सर्व|सबके|सगळ्या|सगळ्यांचे|सबकी)\s+(?:मरीज|मरीजों|रुग्ण|रुग्णांचे|रुग्णांचा|लोगों|लोकांचे|लोकांच्या)", r"(?:पड़ोसी|पड़ोसन|शेजारी|दोस्त|मित्र)(?:\s+(?:की|का|के|चा|ची|चे))?\s+(?:रिपोर्ट|दवा|औषध)",
    r"अपने नियम भूल", r"(?:पिछले|ऊपर के|पिछल्या) (?:निर्देश|नियम|सूचना)\w*\s+(?:भूल|अनदेखा|विसर)", r"नियम (?:भूल|विसर)", r"तुझे नियम विसर",
]), re.IGNORECASE)
# a name followed by "ki / ka / cha" and a record word, when the message does not say "my" ("मीरा की रिपोर्ट दिखाओ")
_NAME_POSSESSIVE = re.compile(r"(?<![ऀ-ॿ])[ऀ-ॿ]{2,}\s+(?:की|का|के|चा|ची|चे)\s+(?:रिपोर्ट|दवा|दवाई|औषध|रिकॉर्ड|नतीजे|निकाल)")
_NAME_ATTACHED = re.compile(r"(?<![ऀ-ॿ])([ऀ-ॿ]{2,}?)(?:चा|ची|चे)\s+(?:रिपोर्ट|दवा|दवाई|औषध|रिकॉर्ड|निकाल)")        # Marathi: "मीराचा रिपोर्ट"
_RECORD_WORDS = ("जाँच", "जांच", "तपासणी", "ब्लड", "रक्त", "आज", "काल", "ताज", "शेवटच", "मागील", "डॉक्टर", "लॅब", "आरोग्य", "औषध", "रिपोर्ट", "अहवाल", "मला", "माझ", "तुमच")
_MY_WORDS = re.compile(_MY + r"|माझ्या|तुमच्या")
_NOT_A_NAME = re.compile(r"(?:जाँच|जांच|ब्लड|तपासणी|आज|कल|पिछली|ताज़ा|ताजा|मागील|शेवटच्या|डॉक्टर|डॉक्टरांच्या|पुरानी)\s+(?:की|का|के|चा|ची|चे)")


def wants_other_records(text: str) -> bool:
    if OWN_ONLY_RE.search(text):
        return True
    if _MY_WORDS.search(text):
        return False
    m = _NAME_POSSESSIVE.search(text)
    if m and not _NOT_A_NAME.search(text):
        return True
    a = _NAME_ATTACHED.search(text)
    return bool(a and not a.group(1).startswith(_RECORD_WORDS))


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("’", "'")).strip().lower()


def check(message: str) -> str | None:
    """EMERGENCY, OWN_ONLY, MED_CHANGE, DIAGNOSIS, REACTION or None. Emergency is checked first and wins."""
    text = _clean(message)
    if EMERGENCY_RE.search(text):
        about_records = RECORD_QUESTION.search(text) or EDUCATIONAL.search(text)
        if not (about_records and not HAPPENING_NOW.search(text)):
            return "EMERGENCY"
    if wants_other_records(text):
        return "OWN_ONLY"
    if MED_CHANGE_RE.search(text):
        return "MED_CHANGE"
    if REACTION_RE.search(text):
        return "REACTION"
    if DIAGNOSIS_RE.search(text):
        return "DIAGNOSIS"
    return None
