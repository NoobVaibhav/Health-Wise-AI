"""Which department fits a complaint. A plain table (no AI): the first rule whose words appear in the complaint and symptoms wins, so the order below
matters (more specific first). Every answer comes with a reason the trainee can read, and the trainee can always choose another department."""
import re

# (words that may appear, department, specialization hint or None, reason)
RULES: list[tuple[tuple[str, ...], str, str | None, str]] = [
    (("chest pain", "chest tightness", "palpitation", "heart attack", "angina", "irregular heartbeat"), "Cardiology", None, "Chest or heart symptoms"),
    (("seizure", "fits", "convulsion", "stroke", "paralysis", "weakness of one side", "tingling", "numbness", "migraine", "headache", "giddiness", "vertigo", "fainting"), "Neurology", None, "Brain or nerve symptoms"),
    (("pregnan", "antenatal", "missed period", "menstrual", "periods", "vaginal", "white discharge", "labour", "infertility"), "Gynecology & Obstetrics", None, "Pregnancy or women's health"),
    (("rash", "itching", "itch", "skin", "acne", "hair fall", "eczema", "psoriasis", "fungal", "boils", "allergic skin"), "Dermatology", None, "Skin or hair problem"),
    (("fracture", "joint pain", "knee pain", "back pain", "neck pain", "shoulder pain", "swollen joint", "sprain", "bone"), "Orthopedics", None, "Bone, joint or back problem"),
    (("ear pain", "earache", "hearing", "sore throat", "tonsil", "sinus", "nose bleed", "blocked nose", "hoarse"), "ENT", None, "Ear, nose or throat symptoms"),
    (("eye pain", "red eye", "blurred vision", "vision", "watering eye", "cataract"), "Ophthalmology", None, "Eye symptoms"),
    (("anxiety", "depression", "low mood", "sleeplessness", "insomnia", "panic", "hallucination", "suicid", "addiction"), "Psychiatry", None, "Mental health symptoms"),
    (("breathless", "shortness of breath", "wheez", "asthma", "chronic cough", "cough with blood", "tuberculosis"), "Pulmonology", None, "Breathing problem"),
    (("abdominal pain", "stomach pain", "vomiting", "diarrhoea", "diarrhea", "constipation", "acidity", "jaundice", "blood in stool", "heartburn", "indigestion"), "Gastroenterology", None, "Stomach or bowel symptoms"),
    (("burning urine", "burning while urinating", "kidney stone", "blood in urine", "urinary", "prostate", "swelling of feet"), "Urology", None, "Urine or kidney-related symptoms"),
    (("diabetes", "thyroid", "sugar high", "weight gain", "excessive thirst"), "Endocrinology", None, "Hormone or sugar problem"),
    (("lump", "cancer", "tumor", "tumour", "weight loss"), "Oncology", None, "Lump or unexplained weight loss, to be checked for cancer"),
    (("toothache", "tooth", "gum", "dental"), "Dentistry", None, "Tooth or gum problem"),
    (("fever", "cough", "cold", "body ache", "weakness", "tiredness", "viral", "loose motion"), "General Medicine", None, "Common illness: fever, cough or general weakness"),
]
CHILD_AGE = 12
FALLBACK = ("General Medicine", None, "No specific match, so a general physician should see the patient first")


def _has(text: str, word: str) -> bool:
    return re.search(rf"(?<![a-z]){re.escape(word)}", text) is not None


def suggest_department(complaint: str | None, symptoms: list[str] | None = None, age: int | None = None, gender: str | None = None) -> dict:
    """{department, specialization, reason, matched}. A child under 12 goes to Pediatrics unless the rule is an emergency-type chest or brain problem."""
    text = " ".join([complaint or ""] + list(symptoms or [])).lower()
    matched_rule = None
    matched: list[str] = []
    for words, department, specialization, reason in RULES:
        hits = [w for w in words if _has(text, w)]
        if hits:
            matched_rule, matched = (department, specialization, reason), hits
            break
    if matched_rule is None:
        return {"department": FALLBACK[0], "specialization": FALLBACK[1], "reason": FALLBACK[2], "matched": []}
    department, specialization, reason = matched_rule
    if age is not None and age < CHILD_AGE and department not in ("Cardiology", "Neurology", "Dentistry"):
        return {"department": "Pediatrics", "specialization": None, "reason": f"{reason}, and the patient is a child ({age} years)", "matched": matched}
    if department == "Gynecology & Obstetrics" and (gender or "").lower() == "male":
        return {"department": "General Medicine", "specialization": None, "reason": "The words matched a women's-health rule, but the patient is male", "matched": matched}
    return {"department": department, "specialization": specialization, "reason": f"{', '.join(matched[:3]).capitalize()}: {reason.lower()}" if matched else reason, "matched": matched}
