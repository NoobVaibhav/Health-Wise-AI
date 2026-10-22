"""'Points to check' for the doctor, worked out from a patient's medical history by fixed rules.

This is NOT a diagnosis and NOT a medicine suggestion. Each point only says what a doctor often reviews when a patient
takes a certain medicine, has a certain condition or habit, or has a certain complaint. The doctor decides.
Nothing here names a dose or tells the doctor which medicine to give (see safety_filter.is_safe_for_doctor)."""
import re

# ---------------------------------------------------------------- medicines (matched on the medicine name)
MEDICINE_RULES = [
    (("spironolactone", "eplerenone"), "Raises potassium",
     "These medicines can raise potassium. Potassium and kidney function (RFT) are worth checking."),
    (("enalapril", "ramipril", "lisinopril", "perindopril", "captopril", "losartan", "telmisartan", "olmesartan", "valsartan",
      "candesartan", "irbesartan"), "Kidney function and potassium",
     "ACE inhibitors and ARBs can affect kidney function and potassium. Both are worth checking."),
    (("furosemide", "torsemide", "torasemide", "hydrochlorothiazide", "chlorthalidone", "indapamide"), "Salts and kidney function",
     "Diuretics can change sodium, potassium and kidney function. Electrolytes are worth checking. Ask about dizziness."),
    (("atorvastatin", "rosuvastatin", "simvastatin", "pravastatin", "pitavastatin"), "Lipids and liver",
     "A lipid profile and liver function tests (LFT) are commonly reviewed with a statin. Ask about muscle pain."),
    (("aspirin", "clopidogrel", "prasugrel", "ticagrelor", "dipyridamole"), "Bleeding risk (antiplatelet)",
     "Antiplatelet medicines raise the chance of bleeding. Ask about black stools, bruising or bleeding."),
    (("warfarin", "acenocoumarol", "rivaroxaban", "apixaban", "dabigatran", "edoxaban", "enoxaparin", "heparin"),
     "Bleeding risk (anticoagulant)",
     "Anticoagulants raise the chance of bleeding. INR is used to follow warfarin and acenocoumarol; kidney function matters for the newer ones."),
    (("metformin",), "Kidney function", "Kidney function is commonly checked in patients who take metformin."),
    (("insulin", "glimepiride", "glibenclamide", "glyburide", "gliclazide", "glipizide"), "Low blood sugar",
     "These medicines can cause low blood sugar, a possible cause of giddiness or blackouts. A blood sugar check is worth considering."),
    (("levothyroxine", "thyroxine", "eltroxin"), "Thyroid", "Thyroid function (TSH) is commonly checked with thyroid hormone tablets."),
    (("digoxin",), "Pulse and potassium", "Digoxin can slow the pulse. Pulse, potassium and kidney function are worth checking."),
    (("amiodarone",), "Thyroid, liver, lung", "Amiodarone is followed with thyroid, liver and lung checks."),
    (("metoprolol", "atenolol", "bisoprolol", "carvedilol", "propranolol", "nebivolol"), "Slow pulse, low blood pressure",
     "Beta blockers can slow the pulse and lower blood pressure. Pulse and ECG are worth checking if there is dizziness or fainting."),
    (("donepezil", "rivastigmine", "galantamine"), "Can slow the heart rate",
     "These medicines for memory loss can slow the heart rate. Pulse and ECG are worth checking if there is fainting, dizziness or a slow pulse."),
    (("tamsulosin", "alfuzosin", "silodosin", "prazosin", "doxazosin", "terazosin"), "Drop in blood pressure on standing",
     "These medicines can lower blood pressure on standing. Blood pressure lying and standing is worth checking if there is dizziness."),
    (("ibuprofen", "diclofenac", "naproxen", "aceclofenac", "etoricoxib", "ketorolac", "nimesulide"), "Kidneys and stomach",
     "Pain-killers of this group can harm the kidneys and stomach and can raise blood pressure. Kidney function is worth checking."),
    (("prednisolone", "prednisone", "dexamethasone", "methylprednisolone", "hydrocortisone"), "Steroids",
     "Steroids can raise blood sugar and blood pressure. Both are worth checking."),
    (("lithium",), "Lithium", "Lithium level, kidney function and thyroid function are commonly followed."),
    (("alprazolam", "clonazepam", "diazepam", "lorazepam", "zolpidem"), "Drowsiness and falls",
     "Sedating medicines can cause drowsiness, confusion and falls, especially in older people."),
]
BLOOD_THINNERS = ("aspirin", "clopidogrel", "prasugrel", "ticagrelor", "dipyridamole", "warfarin", "acenocoumarol", "rivaroxaban",
                  "apixaban", "dabigatran", "edoxaban", "enoxaparin", "heparin")

# ---------------------------------------------------------------- conditions (matched on the condition name)
CONDITION_RULES = [
    (r"hypertension|high blood pressure|high bp|\bhtn\b", "Long-standing high blood pressure",
     "Kidney function, urine protein, ECG, lipid profile and an eye check are commonly reviewed."),
    (r"diabet|\bdm\b|sugar", "Diabetes",
     "HbA1c, kidney function with urine albumin, lipid profile, and eye and foot examination are commonly reviewed."),
    (r"ihd|ischemic|ischaemic|coronary|angina|myocardial|heart attack|\bcad\b|\bmi\b", "Heart disease",
     "ECG, 2D echo and lipid profile are commonly reviewed. Check that the antiplatelet and statin treatment is continuing as intended."),
    (r"heart failure|cardiac failure|cardiomyopathy", "Heart failure",
     "Echo, kidney function, electrolytes and fluid status (weight, swelling) are commonly reviewed."),
    (r"arrhythmia|atrial fibrillation|\baf\b|palpitation", "Heart rhythm problem",
     "ECG, rhythm monitoring and thyroid function are commonly reviewed; ask about stroke risk."),
    (r"stroke|\btia\b|paralysis|hemiparesis", "Past stroke",
     "Blood pressure, lipid profile and heart rhythm are commonly reviewed."),
    (r"asthma|copd|bronchitis|emphysema|tuberculosis|\btb\b", "Lung disease",
     "Oxygen saturation, spirometry or peak flow and a chest X-ray are commonly reviewed."),
    (r"thyroid", "Thyroid disease", "Thyroid function (TSH) is commonly reviewed."),
    (r"kidney|\bckd\b|renal", "Kidney disease",
     "Kidney function, electrolytes and urine are commonly reviewed; medicines that affect the kidneys deserve a second look."),
    (r"liver|hepatitis|cirrhosis|jaundice", "Liver disease", "Liver function tests (LFT) and clotting are commonly reviewed."),
    (r"anemia|anaemia", "Anaemia", "Complete blood count and iron studies are commonly reviewed."),
    (r"epilep|seizure|\bfits?\b", "Seizures", "Seizure control and regular intake of the medicines are worth confirming."),
    (r"cancer|carcinoma|tumou?r|malignan|lymphoma|leuk", "Cancer", "The current treatment and the follow-up plan are worth confirming with the patient's oncologist."),
    (r"dementia|alzheimer", "Memory loss",
     "Medicines deserve a review (some slow the heart rate), as does the risk of falls. Check who looks after the patient and who can give the history."),
    (r"\bbph\b|prostat", "Enlarged prostate", "Urine routine and kidney function are commonly reviewed."),
]

# ---------------------------------------------------------------- the complaint of today (matched on the written complaint)
SYMPTOM_RULES = [
    (r"syncope|faint|black ?out|loss of consciousness|passed out|collaps", "Fainting or loss of consciousness",
     "ECG, pulse, blood pressure (lying and standing) and blood sugar are commonly checked; rhythm monitoring (Holter) can be considered if the cause is not clear."),
    (r"chest pain|chest discomfort|chest tightness", "Chest pain", "An ECG and cardiac markers are commonly checked without delay."),
    (r"breathless|shortness of breath|dyspn|difficulty breathing", "Breathlessness",
     "Oxygen saturation, chest examination, ECG and chest X-ray are commonly checked; echo if a heart cause is suspected."),
    (r"giddiness|dizz|vertigo|light.?headed", "Giddiness", "Pulse, blood pressure (lying and standing), blood sugar and ECG are commonly checked."),
    (r"palpitation|racing heart|skipped beat", "Palpitations", "ECG, thyroid function and rhythm monitoring are commonly considered."),
    (r"fever", "Fever", "Complete blood count and a search for the source of infection are commonly done."),
    (r"weight loss|losing weight", "Weight loss", "Blood sugar, thyroid function and a complete blood count are commonly checked, along with appetite and diet."),
    (r"swelling|oedema|edema", "Swelling of the feet or face", "Kidney function, urine protein, heart and liver assessment are commonly considered."),
]


# Words in a point that call for a test, and the name of that test as it appears in the hospital's test list.
TEST_WORDS = [
    (r"potassium|electrolyte|sodium", "Serum electrolytes (Na, K, Cl)"),
    (r"kidney function|\brft\b|\bkft\b", "Kidney function test (KFT)"),
    (r"liver function|\blft\b", "Liver function test (LFT)"),
    (r"lipid", "Lipid profile"),
    (r"hba1c", "HbA1c (glycated haemoglobin)"),
    (r"blood sugar|low blood sugar", "Random blood sugar"),
    (r"\btsh\b|thyroid function", "Thyroid profile (T3, T4, TSH)"),
    (r"complete blood count|\bcbc\b|haemoglobin", "Complete Blood Count (CBC)"),
    (r"\becg\b", "ECG"),
    (r"echo", "2D echo"),
    (r"holter|rhythm monitoring", "Holter monitoring (24 hour ECG)"),
    (r"cardiac markers", "Troponin / CPK-MB"),
    (r"chest x-ray", "Chest X-ray"),
    (r"spirometry|peak flow", "Spirometry (PFT)"),
    (r"\binr\b", "PT / INR"),
    (r"urine", "Urine routine and microscopy"),
    (r"iron studies", "Serum iron and ferritin"),
]


def suggested_tests(points: list[dict]) -> list[str]:
    """Test names that the points above talk about, so the doctor can add them to 'investigations advised' with one tap.
    They are suggestions to consider. The doctor chooses."""
    text = " ".join(p["title"] + " " + p["detail"] for p in points if p["category"] != "missing").lower()
    found: list[str] = []
    for pattern, name in TEST_WORDS:
        if re.search(pattern, text) and name not in found:
            found.append(name)
    return found


def _has(text: str, pattern: str) -> bool:
    return re.search(pattern, text.lower()) is not None


def _name_matches(medicine: str, words: tuple[str, ...]) -> bool:
    lowered = medicine.lower()
    return any(re.search(r"(?<![a-z])" + re.escape(w), lowered) for w in words)


def _point(category: str, title: str, detail: str) -> dict:
    return {"category": category, "title": title, "detail": detail}


def baseline_points(vitals: dict | None, baseline: dict | None) -> list[dict]:
    """Today's reading compared with the patient's own usual value (the permanent history). A big change from the usual
    matters even when the number alone looks acceptable."""
    if not vitals or not baseline:
        return []
    out = []
    pulse, usual = vitals.get("pulse"), baseline.get("pulse")
    if pulse and usual and abs(pulse - usual) / usual >= 0.25:
        way = "lower" if pulse < usual else "higher"
        out.append(_point("vitals", f"Pulse {pulse} is much {way} than the usual {usual}",
                          f"Today's pulse is {abs(pulse - usual)} per minute {way} than this patient's usual. Medicines, rhythm and ECG are worth reviewing."))
    sys_, usual_sys = vitals.get("bp_systolic"), baseline.get("bp_systolic")
    if sys_ and usual_sys and abs(sys_ - usual_sys) >= 30:
        way = "lower" if sys_ < usual_sys else "higher"
        out.append(_point("vitals", f"Blood pressure {sys_} is much {way} than the usual {usual_sys}",
                          f"The top number is {abs(sys_ - usual_sys)} mmHg {way} than usual for this patient. Repeat the reading and review medicines and hydration."))
    spo2, usual_spo2 = vitals.get("spo2"), baseline.get("spo2")
    if spo2 and usual_spo2 and usual_spo2 - spo2 >= 4:
        out.append(_point("vitals", f"Oxygen saturation {spo2}% is lower than the usual {usual_spo2}%",
                          "A fall from the usual level is worth a chest examination and a chest X-ray."))
    return out


def vitals_points(vitals: dict | None, age: int | None) -> list[dict]:
    """Recorded vitals that are outside the limits commonly used for adults. The doctor decides what they mean."""
    if not vitals or (age is not None and age < 18):
        return []
    out = []
    pulse, sys_, dia, spo2, temp, rr = (vitals.get(k) for k in ("pulse", "bp_systolic", "bp_diastolic", "spo2", "temperature_f", "resp_rate"))
    if pulse is not None and pulse < 50:
        out.append(_point("vitals", f"Slow pulse ({pulse} per minute)", "Below 50 per minute. Medicines that slow the heart and the ECG are worth reviewing."))
    if pulse is not None and pulse > 120:
        out.append(_point("vitals", f"Fast pulse ({pulse} per minute)", "Above 120 per minute. ECG, fever, pain, anaemia and thyroid function are commonly considered."))
    if sys_ is not None and (sys_ >= 180 or (dia or 0) >= 110):
        out.append(_point("vitals", f"Very high blood pressure ({sys_}/{dia or '?'})", "Repeat the reading and look for symptoms or organ effects."))
    if sys_ is not None and sys_ < 90:
        out.append(_point("vitals", f"Low blood pressure ({sys_}/{dia or '?'})", "Check for dehydration, bleeding, heart problems and the effect of medicines."))
    if spo2 is not None and spo2 < 92:
        out.append(_point("vitals", f"Low oxygen saturation ({spo2}%)", "Below 92%. Chest examination and a chest X-ray are commonly considered."))
    if temp is not None and temp >= 100.4:
        out.append(_point("vitals", f"Fever ({temp:g} F)", "At or above 100.4 F. Look for the source of infection."))
    if rr is not None and rr > 24:
        out.append(_point("vitals", f"Fast breathing ({rr} per minute)", "Above 24 per minute. Chest and heart examination are commonly considered."))
    return out


def points_to_check(history: dict, age: int | None = None, vitals: dict | None = None) -> list[dict]:
    """history = the stored history with a 'medications' list. Returns a list of {category, title, detail}."""
    points: list[dict] = []
    medicines = [m for m in history.get("medications", []) if m.get("is_current", True)]
    names = [m["name"] for m in medicines]

    # 1. safety first: an allergy that matches a listed medicine
    for allergy in history.get("allergies", []):
        word = allergy["name"].strip().lower()
        for medicine in names:
            if len(word) >= 4 and word in medicine.lower():
                points.append(_point("safety", f"Allergy to {allergy['name']} and {medicine} is listed",
                                     f"The patient has a recorded allergy to {allergy['name']}"
                                     + (f" ({allergy['reaction']})" if allergy.get("reaction") else "")
                                     + f", and {medicine} is among the current medicines. Please check this."))
    # 2. more than one blood-thinning medicine
    thinners = [n for n in names if _name_matches(n, BLOOD_THINNERS)]
    if len(thinners) >= 2:
        points.append(_point("safety", "More than one blood-thinning medicine",
                             f"{', '.join(thinners)} are listed together. The bleeding risk is higher; the doctor may want to confirm that the combination is intended."))
    # 3. each medicine
    seen = set()
    for words, title, detail in MEDICINE_RULES:
        matched = [n for n in names if _name_matches(n, words)]
        if matched and title not in seen:
            seen.add(title)
            points.append(_point("medicine", f"{title} ({', '.join(matched)})", detail))
    # 4. each condition
    condition_text = [c["name"] for c in history.get("conditions", [])]
    for pattern, title, detail in CONDITION_RULES:
        hits = [c for c in condition_text if _has(c, pattern)]
        if hits:
            points.append(_point("condition", f"{title} ({', '.join(hits)})", detail))
    # 5. habits
    habits = history.get("habits", {}) or {}
    if habits.get("tobacco") in ("SMOKER", "CHEWER"):
        years = habits.get("tobacco_years")
        points.append(_point("habit", "Tobacco use" + (f" for {years} years" if years else ""),
                             "Chest examination and ECG are commonly reviewed; look inside the mouth in tobacco chewers; a chest X-ray can be considered."))
    if habits.get("alcohol") == "REGULAR" or (habits.get("alcohol_years") or 0) >= 10:
        points.append(_point("habit", "Long-term alcohol use", "Liver function tests and a complete blood count are commonly reviewed; ask about withdrawal if the patient is admitted."))
    # 6. today's complaint
    problem = history.get("current_problem", {}) or {}
    complaint_text = " ".join([problem.get("complaint") or "", problem.get("details") or "", " ".join(problem.get("symptoms", []))])
    for pattern, title, detail in SYMPTOM_RULES:
        if _has(complaint_text, pattern):
            points.append(_point("complaint", title, detail))
    # 7. recorded vitals
    points += baseline_points(vitals, history.get("baseline"))
    points += vitals_points(vitals, age)
    # 8. what is still missing (important in an emergency)
    if not medicines and not history.get("no_regular_medicines"):
        points.append(_point("missing", "Medicines not recorded", "Ask the patient or the family which medicines are taken regularly."))
    if not history.get("allergies") and not history.get("no_known_allergies"):
        points.append(_point("missing", "Allergies not recorded", "Ask about drug allergies before giving any medicine."))
    return points
