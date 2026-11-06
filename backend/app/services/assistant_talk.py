"""The conversational side of the patient assistant: greeting, thanks, goodbye, "what can you do", the date and time, "open my reports",
and "brief me" (the daily update). Everything is fixed rules and fixed wording in English, Hindi and Marathi: no outside service is used.

A conversation like this needs no medical record, so nothing here reads one. The "brief me" update is built in patient_assistant from the
patient's own records. The Hindi and Marathi wording should be reviewed by a native speaker, as for the rest of the assistant."""
import re
from datetime import datetime

from app.services.assistant_text import fdate
from app.utils.clock import hospital_now

# ------------------------------------------------------------------ what was said
GREETING = re.compile(r"^(?:hi+|hello+|hey+|hai|namaste|namaskar|good (?:morning|afternoon|evening|night)|नमस्ते|नमस्कार|हॅलो|हेलो|हैलो|सुप्रभात)"
                      r"(?:\s+(?:there|healthwise|health wise|assistant|friend))?[\s!.,]*$", re.IGNORECASE)
THANKS = re.compile(r"\b(?:thank|thanks|thx|धन्यवाद|शुक्रिया|आभार)", re.IGNORECASE)
BYE = re.compile(r"^(?:ok(?:ay)?[, ]*)?(?:bye|goodbye|good bye|see you|that'?s all|that is all|stop listening|talk later|बाय|अलविदा|बस इतना|बस)\b", re.IGNORECASE)
WHO = re.compile(r"\b(?:who are you|what are you|what can you do|what can i ask|what do you do|how do you work|help me|तुम कौन|आप कौन|आप क्या कर|तू कोण|तुम्ही कोण|तुम्ही काय)", re.IGNORECASE)
TIME = re.compile(r"\b(?:what(?:'s| is)? the time|what time|time now|current time|today'?s date|what(?:'s| is)? (?:the )?date|what day|which day|"
                  r"आज की तारीख|आज कौन सा दिन|समय क्या|कितने बजे|आजची तारीख|किती वाजले|आज कोणता दिवस)", re.IGNORECASE)
BRIEF = re.compile(r"\b(?:brief me|my briefing|briefing|what(?:'s| is) new|anything new|update me|what do i need to know|what should i know|my day|how am i doing|catch me up|"
                   r"आज की जानकारी|मेरा अपडेट|ताज़ा जानकारी|माझे अपडेट|आजची माहिती)", re.IGNORECASE)
OPEN_VERB = re.compile(r"(?<![a-z])(?:open|go to|take me to|navigate to)(?![a-z])|खोलो|खोलें|खोलिए|जाओ|उघडा|उघड", re.IGNORECASE)
QUESTION_WORDS = re.compile(r"\b(?:what|why|how many|how much|is my|are my|क्या|क्यों|काय|का)\b", re.IGNORECASE)

# the page names, longest phrase first so "health history" is not taken for "history" or "report"
PAGES = [
    ("health history", r"health history|medical history|past history|आरोग्य इतिहास|स्वास्थ्य इतिहास|मेडिकल हिस्ट्री", "/patient/health-history",
     {"en": "your health history", "hi": "आपका स्वास्थ्य इतिहास", "mr": "तुमचा आरोग्य इतिहास"}),
    ("timeline", r"timeline|टाइमलाइन|टाईमलाईन", "/patient/history", {"en": "your timeline", "hi": "आपकी टाइमलाइन", "mr": "तुमची टाइमलाइन"}),
    ("appointments", r"appointment|अपॉइंटमेंट|अपॉईंटमेंट|भेट", "/patient/appointments", {"en": "your appointments", "hi": "आपके अपॉइंटमेंट", "mr": "तुमचे अपॉइंटमेंट"}),
    ("medicines", r"medicine|medication|prescription|dawa|दवा|दवाई|औषध|प्रिस्क्रिप्शन", "/patient/prescriptions", {"en": "your medicines", "hi": "आपकी दवाइयाँ", "mr": "तुमची औषधे"}),
    ("advice", r"advice|recommendation|सलाह|सल्ला|सूचना", "/patient/recommendations", {"en": "your doctor's advice", "hi": "डॉक्टर की सलाह", "mr": "डॉक्टरांचा सल्ला"}),
    ("notes", r"notes?\b|नोट", "/patient/notes", {"en": "your doctor's notes", "hi": "डॉक्टर के नोट", "mr": "डॉक्टरांच्या नोंदी"}),
    ("profile", r"profile|प्रोफाइल|प्रोफाईल", "/patient/profile", {"en": "your profile", "hi": "आपकी प्रोफाइल", "mr": "तुमची प्रोफाइल"}),
    ("reports", r"report|रिपोर्ट|अहवाल", "/patient/reports", {"en": "your reports", "hi": "आपकी रिपोर्ट", "mr": "तुमचे रिपोर्ट"}),
    ("dashboard", r"dashboard|home page|home|डैशबोर्ड|होम", "/patient", {"en": "your home page", "hi": "आपका होम पेज", "mr": "तुमचे होम पेज"}),
]

# ------------------------------------------------------------------ what is answered
PART = {
    "morning": {"en": "Good morning", "hi": "सुप्रभात", "mr": "सुप्रभात"},
    "afternoon": {"en": "Good afternoon", "hi": "नमस्कार", "mr": "शुभ दुपार"},
    "evening": {"en": "Good evening", "hi": "शुभ संध्या", "mr": "शुभ संध्याकाळ"},
}
TEXT = {
    "greet": {
        "en": "{part}, {name}! I am HealthWise, your health assistant. Ask me about your last checkup, reports, medicines or appointments. Or say \"brief me\" for today's update.",
        "hi": "{part}, {name}! मैं हेल्थवाइज़ हूँ, आपका स्वास्थ्य सहायक। आप पिछले चेकअप, रिपोर्ट, दवाइयों या अपॉइंटमेंट के बारे में पूछ सकते हैं। या \"आज की जानकारी\" कहें।",
        "mr": "{part}, {name}! मी हेल्थवाइज आहे, तुमचा आरोग्य सहाय्यक. तुम्ही मागील तपासणी, रिपोर्ट, औषधे किंवा अपॉइंटमेंटबद्दल विचारू शकता. किंवा \"आजची माहिती\" म्हणा.",
    },
    "thanks": {
        "en": "You are welcome! Ask me anything else about your records whenever you like.",
        "hi": "आपका स्वागत है! अपने रिकॉर्ड के बारे में जब चाहें कुछ भी पूछिए।",
        "mr": "तुमचे स्वागत आहे! तुमच्या नोंदींबद्दल केव्हाही काहीही विचारा.",
    },
    "bye": {
        "en": "Goodbye, {name}. Take care! I am here whenever you need me.",
        "hi": "अलविदा, {name}। अपना ध्यान रखिए! जब ज़रूरत हो मैं यहीं हूँ।",
        "mr": "निरोप, {name}. काळजी घ्या! गरज असेल तेव्हा मी इथेच आहे.",
    },
    "who": {
        "en": "I am HealthWise, a helper inside this app. I answer only from your own records, and I am not a doctor.\nYou can ask me:\n- \"What did my doctor say at my last checkup?\"\n- \"Explain my latest report\" or \"What is my HbA1c?\"\n- \"Which results are outside the range?\"\n- \"What medicines am I taking?\"\n- \"When is my next appointment?\"\n- \"Brief me\" for a short update\n- \"Open my reports\" to go to a page\nYou can type or speak, and I can read the answers aloud.",
        "hi": "मैं हेल्थवाइज़ हूँ, इस ऐप में आपका सहायक। मैं सिर्फ़ आपके अपने रिकॉर्ड से जवाब देता हूँ, और मैं डॉक्टर नहीं हूँ।\nआप पूछ सकते हैं:\n- \"पिछले चेकअप में डॉक्टर ने क्या कहा?\"\n- \"मेरी ताज़ा रिपोर्ट समझाइए\" या \"मेरा HbA1c क्या है?\"\n- \"कौन से नतीजे रेंज से बाहर हैं?\"\n- \"मैं कौन सी दवाइयाँ ले रहा हूँ?\"\n- \"मेरा अगला अपॉइंटमेंट कब है?\"\n- \"आज की जानकारी\" छोटे अपडेट के लिए\n- \"रिपोर्ट खोलो\" किसी पेज पर जाने के लिए\nआप टाइप कर सकते हैं या बोल सकते हैं, और मैं जवाब पढ़कर सुना सकता हूँ।",
        "mr": "मी हेल्थवाइज आहे, या ॲपमधला तुमचा सहाय्यक. मी फक्त तुमच्या स्वतःच्या नोंदींमधून उत्तर देतो, आणि मी डॉक्टर नाही.\nतुम्ही विचारू शकता:\n- \"मागील तपासणीत डॉक्टर काय म्हणाले?\"\n- \"माझा ताजा रिपोर्ट समजावून सांगा\" किंवा \"माझा HbA1c किती आहे?\"\n- \"कोणते निकाल श्रेणीबाहेर आहेत?\"\n- \"मी कोणती औषधे घेत आहे?\"\n- \"माझी पुढची भेट कधी आहे?\"\n- \"आजची माहिती\" थोडक्यात अपडेटसाठी\n- \"रिपोर्ट उघडा\" एखाद्या पानावर जाण्यासाठी\nतुम्ही टाइप करू शकता किंवा बोलू शकता, आणि मी उत्तरे वाचून दाखवू शकतो.",
    },
    "time": {
        "en": "It is {time} on {weekday}, {date}.",
        "hi": "अभी {time} बजे हैं, {weekday}, {date}।",
        "mr": "आत्ता {time} वाजले आहेत, {weekday}, {date}.",
    },
    "opening": {"en": "Opening {x}.", "hi": "{x} खोल रहा हूँ।", "mr": "{x} उघडत आहे."},
    "brief_head": {"en": "{part}, {name}. Here is your update from your records:", "hi": "{part}, {name}। आपके रिकॉर्ड से आपका अपडेट:", "mr": "{part}, {name}. तुमच्या नोंदींमधील तुमचे अपडेट:"},
    "brief_results": {
        "en": "{n} of your reviewed results {be} outside the printed range: {names}.",
        "hi": "आपके जाँचे गए नतीजों में से {n} छपी हुई रेंज से बाहर हैं: {names}।",
        "mr": "तपासलेल्या निकालांपैकी {n} छापलेल्या श्रेणीबाहेर आहेत: {names}.",
    },
    "brief_clear": {"en": "None of your reviewed results is outside the printed range.", "hi": "आपका कोई भी जाँचा गया नतीजा छपी हुई रेंज से बाहर नहीं है।", "mr": "तपासलेल्या निकालांपैकी कोणताही छापलेल्या श्रेणीबाहेर नाही."},
    "brief_none": {"en": "No reviewed test result is on record yet.", "hi": "अभी कोई जाँचा गया टेस्ट नतीजा दर्ज नहीं है।", "mr": "अजून तपासलेला कोणताही टेस्ट निकाल नोंदलेला नाही."},
    "brief_meds": {"en": "You have {n} medicine{s} on your open prescriptions.", "hi": "आपकी चालू पर्चियों में {n} दवाइयाँ हैं।", "mr": "तुमच्या चालू प्रिस्क्रिप्शनमध्ये {n} औषधे आहेत."},
    "brief_follow": {"en": "Your doctor asked for a follow-up by {d}.", "hi": "डॉक्टर ने {d} तक फॉलो-अप के लिए कहा है।", "mr": "डॉक्टरांनी {d} पर्यंत फॉलो-अप सांगितला आहे."},
    "brief_end": {
        "en": "This is only what your records say. Ask me about any of it, and talk to your doctor about what it means for you.",
        "hi": "यह सिर्फ़ वही है जो आपके रिकॉर्ड में लिखा है। इनमें से कुछ भी पूछिए, और इसका आपके लिए क्या मतलब है यह डॉक्टर से बात करके जानिए।",
        "mr": "हे फक्त तुमच्या नोंदींमध्ये जे लिहिले आहे तेच आहे. यातील काहीही विचारा, आणि तुमच्यासाठी याचा अर्थ काय हे डॉक्टरांशी बोलून जाणून घ्या.",
    },
}
WEEKDAYS = {
    "en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    "hi": ["सोमवार", "मंगलवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"],
    "mr": ["सोमवार", "मंगळवार", "बुधवार", "गुरुवार", "शुक्रवार", "शनिवार", "रविवार"],
}


def say(key: str, lang: str, **kw) -> str:
    entry = TEXT[key]
    return (entry.get(lang) or entry["en"]).format(**kw)


def part_of_day(now: datetime, lang: str) -> str:
    key = "morning" if now.hour < 12 else "afternoon" if now.hour < 17 else "evening"
    return PART[key].get(lang) or PART[key]["en"]


def first_name(full_name: str | None) -> str:
    words = [w for w in (full_name or "").replace("Dr.", "").split() if w]
    return words[0] if words else ""


def detect(text: str) -> tuple[str, dict] | None:
    """(intent, details) for a conversational message, or None. `text` is lower-case. A real question about the records is never taken for small talk."""
    stripped = text.strip()
    words = stripped.split()
    if GREETING.match(stripped):
        return "GREETING", {}
    if OPEN_VERB.search(stripped) and not QUESTION_WORDS.search(stripped) and len(words) <= 7:
        for key, pattern, route, labels in PAGES:
            if re.search(pattern, stripped, re.IGNORECASE):
                return "NAVIGATE", {"to": route, "labels": labels, "page": key}
    if BYE.match(stripped) and len(words) <= 6:
        return "BYE", {}
    if THANKS.search(stripped) and len(words) <= 7:
        return "THANKS", {}
    if WHO.search(stripped):
        return "WHO", {}
    if TIME.search(stripped):
        return "TIME", {}
    if BRIEF.search(stripped):
        return "BRIEFING", {}
    return None


def answer(intent: str, details: dict, lang: str, name: str, now: datetime | None = None) -> dict:
    """{text, action?} for GREETING, THANKS, BYE, WHO, TIME and NAVIGATE. (BRIEFING is built from the records elsewhere.)"""
    now = now or hospital_now()
    name = name or {"en": "there", "hi": "जी", "mr": "तुम्ही"}.get(lang, "there")
    if intent == "GREETING":
        return {"text": say("greet", lang, part=part_of_day(now, lang), name=name)}
    if intent == "THANKS":
        return {"text": say("thanks", lang)}
    if intent == "BYE":
        return {"text": say("bye", lang, name=name), "action": {"type": "end_conversation"}}
    if intent == "WHO":
        return {"text": say("who", lang)}
    if intent == "TIME":
        hour = now.hour % 12 or 12
        clock = f"{hour}:{now.minute:02d} {'AM' if now.hour < 12 else 'PM'}" if lang == "en" else f"{hour}:{now.minute:02d}"
        return {"text": say("time", lang, time=clock, weekday=WEEKDAYS.get(lang, WEEKDAYS["en"])[now.weekday()], date=fdate(now.date(), lang))}
    if intent == "NAVIGATE":
        label = details["labels"].get(lang) or details["labels"]["en"]
        return {"text": say("opening", lang, x=label), "action": {"type": "navigate", "to": details["to"], "label": label}}
    raise ValueError(intent)
