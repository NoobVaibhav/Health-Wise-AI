"""Fill EVERY demo profile with realistic sample data, for a college demonstration.   Run:  python -m app.seed_showcase

Run `python -m app.seed_demo` first (it creates the accounts). This script then uses the application's own API
(the same calls the screens make), so every record is valid and every dashboard shows real-looking content:
staff profile details and photos, patients with histories, OPD visits, prescriptions, lab and radiology results,
an admitted patient with a nursing chart, an emergency visit, surgeries, blood bank stock, procurement, bills,
insurance claims and trainee case histories.  All people and values are FICTIONAL.  Safe to run more than once.
"""
import io
from datetime import date, datetime, timedelta

from fastapi.testclient import TestClient

from app.main import app
from app.seed_demo import DEMO_PASSWORD

MARKER = "sneha.kulkarni@healthwise.demo.com"
client: TestClient
_tokens: dict[str, dict] = {}
failures: list[str] = []


# ------------------------------------------------------------------ helpers
def H(email: str) -> dict:
    if email not in _tokens:
        res = client.post("/api/auth/login", json={"email": email, "password": DEMO_PASSWORD})
        if res.status_code != 200:
            raise RuntimeError(f"cannot log in as {email}: {res.status_code} {res.text[:120]}")
        _tokens[email] = {"Authorization": f"Bearer {res.json()['access_token']}"}
    return _tokens[email]


def call(method: str, path: str, who: str, ok=(200, 201), **kw):
    """One API call as a demo user. Returns the JSON, or None (and notes the failure) so one bad step never stops the rest."""
    res = client.request(method, path, headers=H(who), **kw)
    if res.status_code not in ok:
        failures.append(f"{method} {path} as {who.split('@')[0]}: {res.status_code} {res.text[:160]}")
        return None
    if res.status_code >= 300:               # a tolerated "already exists" style answer: nothing to use
        return None
    try:
        return res.json()
    except ValueError:
        return {}


def step(title: str, fn) -> None:
    print(f"  {title} ...", end=" ", flush=True)
    before = len(failures)
    try:
        fn()
    except Exception as exc:                 # keep going: the demo data is best effort
        line = exc.__traceback__.tb_next.tb_lineno if exc.__traceback__ and exc.__traceback__.tb_next else "?"
        failures.append(f"{title}: {type(exc).__name__}: {exc} (line {line})")
    print("ok" if len(failures) == before else f"{len(failures) - before} problem(s)")


_slot = [0]


def slot(hours: float) -> str:
    """A distinct time for every appointment, so no doctor is double booked."""
    _slot[0] += 1
    return at(hours + _slot[0] * 0.5)


def at(hours: float) -> str:
    return (datetime.now() + timedelta(hours=hours)).replace(microsecond=0, second=0).isoformat()


def ago(days: int, hour: int = 10) -> str:
    return (datetime.now() - timedelta(days=days)).replace(hour=hour, minute=0, second=0, microsecond=0).isoformat()


DOCTOR_NAMES = {"anjali.sharma@healthwise.demo.com": "Dr. Anjali Sharma", "rohan.mehta@healthwise.demo.com": "Dr. Rohan Mehta", "sana.khan@healthwise.demo.com": "Dr. Sana Khan"}


def doctor_ids(who: str) -> dict[str, int]:
    """Doctor email -> doctor id (the doctor list carries names, not emails)."""
    by_name = {d["full_name"]: d["id"] for d in call("GET", "/api/doctors", who) or []}
    return {email: by_name.get(name) for email, name in DOCTOR_NAMES.items()}


ADMIN = "admin@healthwise.demo.com"
DR = "anjali.sharma@healthwise.demo.com"
DR2 = "rohan.mehta@healthwise.demo.com"
DR3 = "sana.khan@healthwise.demo.com"
EMP = "priya.joshi@healthwise.demo.com"
PHARM = "pharmacy@healthwise.demo.com"
LABT = "lab@healthwise.demo.com"
PATH = "pathologist@healthwise.demo.com"
RTECH = "radiology.tech@healthwise.demo.com"
RAD = "radiologist@healthwise.demo.com"
STORE = "inventory@healthwise.demo.com"
OT = "ot@healthwise.demo.com"
BB1 = "bloodbank@healthwise.demo.com"
BB2 = "bloodbank2@healthwise.demo.com"
BILL = "billing@healthwise.demo.com"
BILL2 = "billing2@healthwise.demo.com"
ACC = "accounts@healthwise.demo.com"
TPA = "tpa@healthwise.demo.com"
NURSE = "nurse@healthwise.demo.com"
NURSE2 = "nurse2@healthwise.demo.com"
INTERN = "intern@healthwise.demo.com"
PG = "pg.student@healthwise.demo.com"
RAHUL = "rahul.patil@healthwise.demo.com"

# ------------------------------------------------------------------ 1. staff profiles (details + a photo)
PROFILES = {
    DR: {"phone": "9000000101", "qualification": "MBBS, MD (General Medicine)", "registration_number": "MMC-2009-45821", "experience_years": 15},
    DR2: {"phone": "9000000121", "qualification": "MBBS, MD, DM (Cardiology)", "registration_number": "MMC-2011-51734", "experience_years": 12},
    DR3: {"phone": "9000000122", "qualification": "MBBS, MS (General Surgery)", "registration_number": "MMC-2013-60218", "experience_years": 9},
    INTERN: {"phone": "9000000106", "qualification": "MBBS", "registration_number": "MMC-2025-90412", "experience_years": 0},
    PG: {"phone": "9000000107", "qualification": "MBBS", "registration_number": "MMC-2021-77305", "experience_years": 3},
    EMP: {"phone": "9000000102", "address": "Flat 12, Shivaji Nagar, Pune 411005"},
    STORE: {"phone": "9000000111", "address": "Staff quarters B-4, Hospital campus, Pune"},
    OT: {"phone": "9000000112", "address": "Staff quarters B-7, Hospital campus, Pune"},
    BB1: {"phone": "9000000113", "address": "12 Karve Road, Pune 411004"},
    BB2: {"phone": "9000000114", "address": "5 Law College Road, Pune 411004"},
    BILL: {"phone": "9000000115", "address": "27 Baner Road, Pune 411045"},
    BILL2: {"phone": "9000000116", "address": "9 Aundh, Pune 411007"},
    ACC: {"phone": "9000000117", "address": "44 Kothrud, Pune 411038"},
    TPA: {"phone": "9000000118", "address": "18 Viman Nagar, Pune 411014"},
    PHARM: {"phone": "9000000103", "license_number": "MH-PUN-20B-4471", "address": "MediCare Pharmacy, Ground floor, Main building"},
    LABT: {"phone": "9000000104", "registration_number": "DMLT-MH-33210", "address": "City Diagnostic Lab, First floor, Main building"},
    PATH: {"phone": "9000000108", "registration_number": "MMC-PATH-2010-18842", "address": "City Diagnostic Lab, First floor, Main building"},
    RTECH: {"phone": "9000000109", "registration_number": "AERB-RT-5521"},
    RAD: {"phone": "9000000110", "registration_number": "MMC-RAD-2008-30217"},
    NURSE: {"phone": "9000000105", "registration_number": "MNC-2016-118342"},
    NURSE2: {"phone": "9000000123", "registration_number": "MNC-2018-129907"},
}
PATIENT_PROFILE = {RAHUL: {"address": "Plot 21, Sahakar Nagar, Pune 411009", "emergency_contact": "Sunita Patil (mother) 9822100001"}}
COLOURS = ["#0e7490", "#7c3aed", "#be123c", "#15803d", "#b45309", "#1d4ed8", "#9333ea", "#0f766e"]


def avatar_png(name: str, colour: str) -> bytes:
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (256, 256), colour)
    draw = ImageDraw.Draw(img)
    initials = "".join(w[0] for w in name.replace("Dr.", "").split()[:2]).upper()
    box = draw.textbbox((0, 0), initials, font_size=110) if hasattr(draw, "textbbox") else (0, 0, 100, 100)
    try:
        draw.text(((256 - (box[2] - box[0])) / 2 - box[0], (256 - (box[3] - box[1])) / 2 - box[1]), initials, fill="white", font_size=110)
    except TypeError:
        draw.text((90, 100), initials, fill="white")
    out = io.BytesIO()
    img.save(out, "PNG")
    return out.getvalue()


def make_more_staff():
    """A second doctor in Cardiology, a surgeon and a second nurse, so every department-wise screen has people."""
    depts = {d["name"]: d["id"] for d in call("GET", "/api/catalog/departments", ADMIN) or []}
    for email, name, dept, extra in ((DR2, "Dr. Rohan Mehta", "Cardiology", {}), (DR3, "Dr. Sana Khan", "General Surgery", {})):
        if dept not in depts:
            dept = "General Medicine"
        call("POST", "/api/admin/doctors", ADMIN, ok=(201, 409, 422), json={"email": email, "full_name": name, "password": DEMO_PASSWORD, "department_id": depts[dept], **extra})
    call("POST", "/api/admin/nurses", ADMIN, ok=(201, 409, 422), json={"email": NURSE2, "full_name": "Kavya Naik", "password": DEMO_PASSWORD, "designation": "Senior staff nurse"})


def fill_profiles():
    emails = [ADMIN, *PROFILES, *PATIENT_PROFILE]
    for i, email in enumerate(emails):
        mine = H(email)
        profile = call("GET", "/api/profile", email)
        if not profile:
            continue
        values = {**PROFILES.get(email, {}), **PATIENT_PROFILE.get(email, {})}
        fields = {f["key"]: f for f in profile["fields"] if f["editable"]}
        todo = {k: v for k, v in values.items() if k in fields and not fields[k]["value"]}
        if todo:
            call("PUT", "/api/profile", email, json={"values": todo})
        if not profile["user"]["has_avatar"]:
            png = avatar_png(profile["user"]["full_name"], COLOURS[i % len(COLOURS)])
            res = client.post("/api/profile/avatar", headers=mine, files={"file": ("avatar.png", png, "image/png")})
            if res.status_code not in (200, 201):
                failures.append(f"avatar for {email}: {res.status_code} {res.text[:100]}")


# ------------------------------------------------------------------ 2. patients
PATIENTS = [
    # email, name, gender, dob, phone, blood, doctor, address, emergency contact, allergies, history, medicines
    (MARKER, "Sneha Kulkarni", "female", "1985-08-22", "9822200011", "B+", DR, "B-304, Green Heights, Baner, Pune 411045", "Amit Kulkarni (husband) 9822200012", "Sulfa drugs (rash)", "Type 2 diabetes for 6 years, hypertension for 3 years", "Tab. Metformin 500 mg twice daily, Tab. Telmisartan 40 mg once daily"),
    ("mohan.deshpande@healthwise.demo.com", "Mohan Deshpande", "male", "1958-02-10", "9822200021", "O+", DR2, "14 Prabhat Road, Pune 411004", "Seema Deshpande (wife) 9822200022", "None known", "Ischaemic heart disease, stent in 2019, hypertension", "Tab. Aspirin 75 mg, Tab. Atorvastatin 20 mg, Tab. Metoprolol 25 mg"),
    ("farida.shaikh@healthwise.demo.com", "Farida Shaikh", "female", "1972-11-03", "9822200031", "A+", DR3, "7 Camp Area, Pune 411001", "Imran Shaikh (son) 9822200032", "None known", "Gallstones with repeated pain; mild anaemia", "Tab. Ferrous sulphate 200 mg once daily"),
    ("kiran.rao@healthwise.demo.com", "Kiran Rao", "male", "1990-04-17", "9822200041", "AB+", DR, "22 Hadapsar, Pune 411028", "Lata Rao (mother) 9822200042", "Penicillin (hives)", "Occasional asthma since childhood", "Inhaler Salbutamol when needed"),
    ("lata.pawar@healthwise.demo.com", "Lata Pawar", "female", "1949-06-30", "9822200051", "O-", DR, "3 Sadashiv Peth, Pune 411030", "Rakesh Pawar (son) 9822200052", "None known", "Osteoarthritis of both knees, type 2 diabetes, mild kidney disease", "Tab. Glimepiride 1 mg, Tab. Paracetamol 650 mg when needed"),
]
PID: dict[str, int] = {}


def register_patients():
    by_email = doctor_ids(EMP)
    for email, name, gender, dob, phone, blood, doc, address, emergency, allergies, history, meds in PATIENTS:
        made = call("POST", "/api/patients", EMP, ok=(201, 409, 422), json={
            "email": email, "full_name": name, "password": DEMO_PASSWORD, "gender": gender, "date_of_birth": dob, "phone": phone, "address": address,
            "emergency_contact": emergency, "blood_group": blood, "allergies": allergies, "medical_history_text": history, "current_medications": meds,
            "assigned_doctor_id": by_email.get(doc)})
        if made:
            PID[email] = made["patient"]["id"]
    # the existing demo patient Rahul: richer personal details
    rahul = call("GET", "/api/patient/profile", RAHUL) or {}
    PID[RAHUL] = rahul.get("id") or PID.get(RAHUL)
    if not PID.get(RAHUL):
        for p in call("GET", "/api/patients", EMP) or []:
            if p.get("email") == RAHUL:
                PID[RAHUL] = p["id"]
    if PID.get(RAHUL):
        call("PUT", f"/api/patients/{PID[RAHUL]}", EMP, json={"blood_group": "B+", "allergies": "Dust and pollen (sneezing)", "current_medications": "Tab. Cetirizine 10 mg at night when needed",
                                                               "medical_history_text": "Seasonal allergic rhinitis. No surgeries.", "address": "Plot 21, Sahakar Nagar, Pune 411009", "emergency_contact": "Sunita Patil (mother) 9822100001"})
    for email, pid in PID.items():
        if pid:
            call("POST", f"/api/patient-registry/{pid}/consents", EMP, ok=(200, 201, 409, 422), json={"kind": "TREATMENT", "note": "General consent for treatment given at registration"})


# ------------------------------------------------------------------ 3. health history (conditions, medicines, surgeries, past admissions)
def health_histories():
    sneha, mohan, farida, lata = PID[MARKER], PID["mohan.deshpande@healthwise.demo.com"], PID["farida.shaikh@healthwise.demo.com"], PID["lata.pawar@healthwise.demo.com"]
    forms = {
        sneha: {"conditions": [{"name": "Type 2 diabetes mellitus", "since": "6 years", "on_treatment": True}, {"name": "Hypertension", "since": "3 years", "on_treatment": True}],
                "allergies": [{"name": "Sulfa drugs", "kind": "DRUG", "reaction": "skin rash"}],
                "medications": [{"name": "Tab. Metformin", "dose": "500 mg", "frequency": "twice daily", "reason": "diabetes"}, {"name": "Tab. Telmisartan", "dose": "40 mg", "frequency": "once daily", "reason": "blood pressure"}],
                "surgeries": [], "no_past_surgery": True, "family": [{"relation": "Mother", "condition": "Type 2 diabetes"}], "no_family_history": False,
                "habits": {"tobacco": "NONE", "alcohol": "NONE", "diet": "VEG"},
                "current_problem": {"complaint": "Tingling in both feet for 2 weeks", "duration": "2 weeks", "symptoms": ["tingling", "increased thirst"], "denies": ["chest pain", "fever"]}},
        mohan: {"conditions": [{"name": "Ischaemic heart disease", "since": "2019", "on_treatment": True}, {"name": "Hypertension", "since": "15 years", "on_treatment": True}],
                "allergies": [], "medications": [{"name": "Tab. Aspirin", "dose": "75 mg", "frequency": "once daily", "reason": "heart"}, {"name": "Tab. Atorvastatin", "dose": "20 mg", "frequency": "at night", "reason": "cholesterol"},
                                                  {"name": "Tab. Metoprolol", "dose": "25 mg", "frequency": "twice daily", "reason": "heart rate"}],
                "surgeries": [], "no_past_surgery": False, "family": [{"relation": "Father", "condition": "Heart attack at 60"}], "no_family_history": False,
                "habits": {"tobacco": "FORMER", "tobacco_years": 20, "alcohol": "OCCASIONAL", "diet": "MIXED"},
                "current_problem": {"complaint": "Chest tightness on walking for 3 days", "duration": "3 days", "symptoms": ["chest tightness", "sweating"], "denies": ["fever", "cough"]}},
        farida: {"conditions": [{"name": "Gallstones", "since": "1 year", "on_treatment": False}, {"name": "Iron deficiency anaemia", "since": "6 months", "on_treatment": True}],
                 "allergies": [], "medications": [{"name": "Tab. Ferrous sulphate", "dose": "200 mg", "frequency": "once daily", "reason": "anaemia"}],
                 "surgeries": [], "no_past_surgery": True, "family": [], "no_family_history": True,
                 "habits": {"tobacco": "NONE", "alcohol": "NONE", "diet": "MIXED"},
                 "current_problem": {"complaint": "Upper abdominal pain after fatty meals", "duration": "3 months", "symptoms": ["abdominal pain", "nausea"], "denies": ["fever", "jaundice"]}},
        lata: {"conditions": [{"name": "Osteoarthritis of both knees", "since": "12 years", "on_treatment": True}, {"name": "Type 2 diabetes mellitus", "since": "10 years", "on_treatment": True}, {"name": "Chronic kidney disease stage 2", "since": "2 years", "on_treatment": True}],
               "allergies": [], "medications": [{"name": "Tab. Glimepiride", "dose": "1 mg", "frequency": "once daily", "reason": "diabetes"}, {"name": "Tab. Paracetamol", "dose": "650 mg", "frequency": "when needed", "reason": "knee pain"}],
               "surgeries": [], "no_past_surgery": True, "family": [], "no_family_history": True,
               "habits": {"tobacco": "NONE", "alcohol": "NONE", "diet": "VEG"},
               "current_problem": {"complaint": "Knee pain while climbing stairs", "duration": "6 months", "symptoms": ["knee pain", "stiffness"], "denies": ["fever", "chest pain"]}},
    }
    for pid, form in forms.items():
        call("PUT", f"/api/health-history/patient/{pid}", DR, ok=(200, 201, 403), json=form)
    # Mohan's earlier stent operation as a past surgery
    call("POST", f"/api/health-history/patient/{mohan}/surgeries", DR2, ok=(200, 201, 403, 422), json={"procedure": "Coronary angioplasty with stent (LAD)", "hospital_name": "Ruby Hall Clinic, Pune", "surgery_date": "2019-09-12", "outcome": "Uneventful recovery"})


# ------------------------------------------------------------------ 4. OPD: appointment, check-in, vitals, consultation, diagnosis, prescription
OPD = [
    (MARKER, DR, "Tingling in feet, thirst", "Poorly controlled diabetes with early neuropathy", "Increase Metformin; HbA1c and fasting glucose; foot care advice; review in 2 weeks", "Type 2 diabetes mellitus", "E11.9",
     {"pulse": 82, "bp_systolic": 138, "bp_diastolic": 88, "spo2": 98, "temperature_f": 98.4}, "Diabetes with tingling feet",
     [{"medicine_name": "Tab. Metformin", "dosage": "1000 mg", "frequency": "Twice a day", "duration": "30 days", "quantity": 60}, {"medicine_name": "Tab. Methylcobalamin", "dosage": "1500 mcg", "frequency": "Once a day", "duration": "30 days", "quantity": 30}],
     ["Blood Glucose (Fasting)"]),
    ("kiran.rao@healthwise.demo.com", DR, "Cough and wheeze for 4 days", "Mild asthma exacerbation after a viral cold", "Salbutamol inhaler, steam inhalation, review if breathless", "Bronchial asthma", "J45.9",
     {"pulse": 96, "bp_systolic": 118, "bp_diastolic": 76, "spo2": 95, "temperature_f": 99.1}, "Cough and wheeze",
     [{"medicine_name": "Salbutamol inhaler", "dosage": "100 mcg, 2 puffs", "frequency": "Every 6 hours when needed", "duration": "7 days", "quantity": 1}, {"medicine_name": "Tab. Montelukast", "dosage": "10 mg", "frequency": "At night", "duration": "10 days", "quantity": 10}],
     ["Complete Blood Count"]),
    ("lata.pawar@healthwise.demo.com", DR, "Knee pain and fatigue", "Osteoarthritis flare; kidney function to be rechecked", "Avoid NSAIDs, physiotherapy, creatinine and electrolytes, review with reports", "Osteoarthritis of knee", "M17.9",
     {"pulse": 78, "bp_systolic": 146, "bp_diastolic": 90, "spo2": 97, "temperature_f": 98.2}, "Knee pain",
     [{"medicine_name": "Tab. Paracetamol", "dosage": "650 mg", "frequency": "Three times a day when needed", "duration": "7 days", "quantity": 15}],
     ["Serum Creatinine", "Serum Electrolytes"]),
    (RAHUL, DR, "Sneezing and itchy eyes", "Seasonal allergic rhinitis", "Antihistamine at night, avoid dust, review if not better", "Allergic rhinitis", "J30.4",
     {"pulse": 74, "bp_systolic": 116, "bp_diastolic": 74, "spo2": 99, "temperature_f": 98.0}, "Allergy symptoms",
     [{"medicine_name": "Tab. Cetirizine", "dosage": "10 mg", "frequency": "At night", "duration": "10 days", "quantity": 10}], []),
]
ENCOUNTERS: dict[str, int] = {}


def opd_visits():
    doc_id = doctor_ids(EMP)
    for email, doctor, complaint, assessment, plan, dx, code, vitals, reason, rx, tests in OPD:
        pid = PID.get(email)
        if not pid:
            continue
        appt = call("POST", "/api/appointments", EMP, json={"patient_id": pid, "doctor_id": doc_id[doctor], "scheduled_at": slot(1), "reason": reason})
        token = appt and call("POST", "/api/opd/check-in", EMP, json={"appointment_id": appt["id"]})
        if not token:
            continue
        eid = token["encounter_id"]
        ENCOUNTERS[email] = eid
        call("POST", f"/api/opd/encounters/{eid}/vitals", NURSE, json=vitals)
        call("PUT", f"/api/opd/encounters/{eid}/consultation", doctor, json={"complaint": complaint, "assessment": assessment, "plan": plan})
        call("POST", f"/api/opd/encounters/{eid}/diagnoses", doctor, json={"text": dx, "code": code})
        for test in tests:
            call("POST", f"/api/opd/encounters/{eid}/orders", doctor, json={"kind": "LAB", "text": test, "priority": "ROUTINE"})
        call("POST", f"/api/opd/encounters/{eid}/sign", doctor)
        call("POST", "/api/prescriptions", doctor, json={"patient_id": pid, "clinical_indication": dx, "items": rx})
    # appointments still to come, so the schedules are not empty
    for email, doctor, hours, reason in ((MARKER, DR, 336, "Diabetes review with reports"), ("lata.pawar@healthwise.demo.com", DR, 120, "Review kidney tests"), (RAHUL, DR, 200, "Follow-up visit"),
                                         ("mohan.deshpande@healthwise.demo.com", DR2, 72, "Cardiology follow-up")):
        if PID.get(email):
            call("POST", "/api/appointments", EMP, json={"patient_id": PID[email], "doctor_id": doc_id[doctor], "scheduled_at": slot(hours), "reason": reason})


# ------------------------------------------------------------------ 5. laboratory and radiology
RESULTS = {  # test name -> {analyte name: value}
    "Blood Glucose (Fasting)": {"Glucose (fasting)": "168"},
    "Complete Blood Count": {"Haemoglobin": "13.2", "WBC count": "11.8", "Platelet count": "265"},
    "Serum Creatinine": {"Creatinine": "1.6"},
    "Serum Electrolytes": {"Sodium": "138", "Potassium": "5.4"},
}


def lab_work():
    tests = call("GET", "/api/diagnostics/tests", ADMIN) or []
    analytes = {}
    for t in tests:
        for a in t.get("analytes", []):
            analytes[(t["name"], a["name"])] = a["id"]
    worklist = (call("GET", "/api/lab/worklist?status_filter=OPEN", LABT) or {}).get("tests", [])
    for order in worklist:
        wanted = RESULTS.get(order["test_name"])
        if not wanted:
            continue
        call("POST", f"/api/lab/tests/{order['id']}/status", LABT, json={"status": "SAMPLE_COLLECTED", "sample_type": "Blood"})
        rows = [{"analyte_id": analytes[(order["test_name"], name)], "value": value} for name, value in wanted.items() if (order["test_name"], name) in analytes]
        call("POST", f"/api/lab/tests/{order['id']}/results", LABT, json={"submit": True, "results": rows})
        call("POST", f"/api/lab/tests/{order['id']}/approve", PATH, json={"note": "Checked and approved"})
        call("POST", f"/api/lab/tests/{order['id']}/seen", DR, ok=(200, 201, 403, 404))


def radiology_work():
    for email, doctor, scan in (("kiran.rao@healthwise.demo.com", DR, "Chest X-ray"), ("mohan.deshpande@healthwise.demo.com", DR2, "2D Echo"), ("farida.shaikh@healthwise.demo.com", DR3, "Ultrasound Abdomen")):
        eid = (call("POST", "/api/opd/walk-in", EMP, json={"patient_id": PID[email], "doctor_id": doctor_ids(EMP)[doctor]}) or {}).get("encounter_id")
        if eid:
            call("POST", f"/api/opd/encounters/{eid}/orders", doctor, json={"kind": "RADIOLOGY", "text": scan, "priority": "ROUTINE"})
    findings = {"Chest X-ray": ("Mild bronchial wall thickening. No consolidation or effusion. Heart size normal.", "No acute lung disease"),
                "2D Echo": ("Mild left ventricular hypertrophy. Ejection fraction 50 percent. No significant valve disease.", "Mildly reduced LV function"),
                "Ultrasound Abdomen": ("Gallbladder contains multiple stones, wall thickness 3 mm. Liver and kidneys normal.", "Cholelithiasis")}
    for study in (call("GET", "/api/radiology/worklist", RTECH) or {}).get("studies", []):
        f = findings.get(study["study"])
        if not f:
            continue
        call("POST", f"/api/radiology/orders/{study['id']}/start", RTECH, ok=(200, 201, 409))
        call("POST", f"/api/radiology/orders/{study['id']}/report", RAD, json={"findings": f[0], "impression": f[1]})
        call("POST", f"/api/radiology/orders/{study['id']}/approve", RAD)
        call("POST", f"/api/radiology/orders/{study['id']}/seen", DR, ok=(200, 201, 403, 404))


# ------------------------------------------------------------------ 6. pharmacy stock and dispensing
MEDICINES = [("Tab. Metformin", "MET-24A", 400, 1.8, 12), ("Tab. Methylcobalamin", "MCB-11C", 300, 4.5, 12), ("Tab. Cetirizine", "CTZ-08B", 250, 1.2, 12), ("Salbutamol inhaler", "SAL-19D", 60, 95.0, 12),
             ("Tab. Montelukast", "MON-31A", 150, 6.0, 12), ("Tab. Paracetamol", "PCM-02E", 600, 1.0, 12), ("Tab. Telmisartan", "TEL-14F", 200, 5.5, 12), ("Tab. Atorvastatin", "ATV-09G", 200, 7.0, 12),
             ("Tab. Aspirin", "ASP-05H", 500, 0.8, 12), ("Inj. Ceftriaxone", "CEF-27J", 120, 48.0, 12), ("Tab. Ferrous sulphate", "FER-16K", 300, 1.5, 12), ("Tab. Amoxicillin", "AMX-22L", 25, 6.0, 12)]


def pharmacy_work():
    for name, batch, qty, price, gst in MEDICINES:
        call("POST", "/api/pharmacy/inventory/receive", PHARM, ok=(200, 201, 409, 422), json={"medicine_name": name, "batch_number": batch, "quantity": qty, "unit_price": price, "gst_percent": gst,
                                                                                         "expiry_date": str(date.today() + timedelta(days=420)), "manufacturer": "Sun Pharma (demo)"})
    # one near-expiry batch and one low stock line so the alerts panel has something to show
    call("POST", "/api/pharmacy/inventory/receive", PHARM, ok=(200, 201, 409, 422), json={"medicine_name": "Syp. Cough linctus", "batch_number": "CGH-01", "quantity": 8, "unit_price": 55.0, "gst_percent": 12,
                                                                                     "expiry_date": str(date.today() + timedelta(days=25)), "manufacturer": "Cipla (demo)"})
    for rx in call("GET", "/api/pharmacy/prescriptions", PHARM) or []:
        if rx.get("status") not in (None, "ACTIVE", "PENDING", "ISSUED"):
            continue
        for item in rx.get("items", []):
            call("POST", "/api/pharmacy/dispense", PHARM, ok=(200, 201, 409, 422), json={"prescription_item_id": item["id"], "quantity": item.get("quantity") or 1})
        call("POST", f"/api/pharmacy/prescriptions/{rx['id']}/bill", PHARM, ok=(200, 201, 409, 422), json={})


# ------------------------------------------------------------------ 7. inpatient: one current stay with a nursing chart, one discharged stay
def inpatient():
    wards = call("GET", "/api/ipd/wards", ADMIN) or []
    beds = [b for w in wards for b in w.get("beds", []) if b.get("status") == "AVAILABLE"]
    if len(beds) < 2:
        failures.append("not enough free beds for the inpatient demo")
        return
    mohan, farida = PID["mohan.deshpande@healthwise.demo.com"], PID["farida.shaikh@healthwise.demo.com"]
    options = call("GET", "/api/ipd/staff-options?kind=NURSE", ADMIN) or []
    nurse_uid = next((p.get("user_id") or p.get("id") for p in options if "Meera" in p.get("full_name", "")), None)
    # 1. Mohan: admitted now with a heart problem (stays admitted for the demo)
    adm = call("POST", "/api/ipd/admissions", DR2, json={"patient_id": mohan, "diagnosis": "Unstable angina", "bed_id": beds[0]["id"]})
    if adm:
        aid = adm["id"]
        if nurse_uid:
            call("POST", f"/api/ipd/admissions/{aid}/staff", ADMIN, ok=(200, 201, 409, 422), json={"user_id": nurse_uid, "kind": "NURSE"})
        call("POST", f"/api/ipd/admissions/{aid}/notes", DR2, json={"note": "Day 1: chest pain settled with nitrates. ECG shows ST depression in V4-V6. Troponin pending. Continue dual antiplatelets."})
        call("POST", f"/api/ipd/admissions/{aid}/notes", DR2, json={"note": "Day 2: pain free overnight. Echo planned. Plan angiography if troponin rises."})
        for med in ({"medicine_name": "Tab. Aspirin", "dose": "75 mg", "route": "ORAL", "times": ["08:00"]}, {"medicine_name": "Tab. Atorvastatin", "dose": "40 mg", "route": "ORAL", "times": ["21:00"]},
                    {"medicine_name": "Inj. Enoxaparin", "dose": "60 mg", "route": "SC", "times": ["09:00", "21:00"]}):
            call("POST", f"/api/ipd/admissions/{aid}/medication-orders", DR2, ok=(200, 201, 422), json=med)
        call("POST", f"/api/nursing/admissions/{aid}/vitals", NURSE, json={"pulse": 92, "bp_systolic": 142, "bp_diastolic": 88, "spo2": 96, "temperature_f": 98.6, "resp_rate": 18})
        call("POST", f"/api/nursing/admissions/{aid}/vitals", NURSE, json={"pulse": 84, "bp_systolic": 130, "bp_diastolic": 82, "spo2": 98, "temperature_f": 98.4, "resp_rate": 16})
        call("POST", f"/api/nursing/admissions/{aid}/notes", NURSE, json={"text": "Patient comfortable, no chest pain since morning. Ambulated to washroom with assistance. Diet taken."})
        call("POST", f"/api/nursing/admissions/{aid}/intake-output", NURSE, ok=(200, 201, 422), json={"kind": "INTAKE", "amount_ml": 800, "note": "Oral fluids"})
        call("POST", f"/api/nursing/admissions/{aid}/intake-output", NURSE, ok=(200, 201, 422), json={"kind": "OUTPUT", "amount_ml": 650, "note": "Urine"})
        chart = call("GET", f"/api/nursing/admissions/{aid}/chart", NURSE) or {}
        for dose in (chart.get("mar") or chart.get("doses") or [])[:2]:
            call("POST", f"/api/nursing/mar/{dose['id']}/act", NURSE, ok=(200, 201, 409, 422), json={"status": "GIVEN"})
        call("POST", f"/api/ipd/admissions/{aid}/orders", DR2, ok=(200, 201, 422), json={"kind": "LAB", "text": "Troponin I", "priority": "URGENT"})
        call("POST", f"/api/finance/deposits", BILL, ok=(200, 201, 422), json={"patient_id": mohan, "admission_id": aid, "amount": 20000, "method": "CASH"})
    # 2. Farida: a short stay for gallbladder surgery, already discharged
    adm2 = call("POST", "/api/ipd/admissions", DR3, json={"patient_id": farida, "diagnosis": "Symptomatic gallstones", "bed_id": beds[1]["id"]})
    if adm2:
        aid = adm2["id"]
        call("POST", f"/api/ipd/admissions/{aid}/notes", DR3, json={"note": "Admitted for laparoscopic cholecystectomy. Fit for anaesthesia."})
        call("POST", f"/api/nursing/admissions/{aid}/vitals", NURSE, json={"pulse": 78, "bp_systolic": 124, "bp_diastolic": 80, "spo2": 99, "temperature_f": 98.2, "resp_rate": 16})
        call("PUT", f"/api/ipd/admissions/{aid}/discharge-summary", DR3, json={"final_diagnosis": "Symptomatic cholelithiasis, post laparoscopic cholecystectomy", "hospital_course": "Uneventful surgery and recovery. Pain controlled with oral analgesics. Tolerating diet.",
                                                                             "follow_up": "Wound review and histopathology in 10 days", "discharge_medicines": "Tab. Paracetamol 650 mg three times a day for 5 days; Tab. Pantoprazole 40 mg once daily for 7 days",
                                                                             "warning_signs": "Fever, jaundice, vomiting or wound discharge"})
        call("POST", f"/api/ipd/admissions/{aid}/discharge-summary/approve", DR3)
        call("POST", f"/api/ipd/admissions/{aid}/discharge", DR3, json={})


# ------------------------------------------------------------------ 8. emergency visits
def emergency():
    kiran = PID["kiran.rao@healthwise.demo.com"]
    docs = doctor_ids(EMP)
    for pid, complaint, category, vitals, note in ((kiran, "Severe breathlessness", 2, {"pulse": 118, "spo2": 89, "bp_systolic": 126, "bp_diastolic": 80}, "Wheeze on both sides, accessory muscle use. Nebulisation started."),
                                                  (PID[RAHUL], "Road accident, pain in left forearm", 3, {"pulse": 96, "spo2": 98, "bp_systolic": 122, "bp_diastolic": 78}, "Swelling and tenderness over the left wrist. X-ray requested.")):
        v = call("POST", "/api/emergency/visits", EMP, json={"patient_id": pid, "chief_complaint": complaint, "arrival_mode": "WALK_IN"})
        if not v:
            continue
        call("POST", f"/api/emergency/visits/{v['id']}/triage", NURSE, json={"category": category, "vitals": vitals})
        call("POST", f"/api/emergency/visits/{v['id']}/assign", DR, json={"doctor_id": docs.get(DR)})
        call("POST", f"/api/emergency/visits/{v['id']}/timeline", DR, json={"kind": "ASSESSMENT", "text": note})
        if category == 3:
            call("POST", f"/api/emergency/visits/{v['id']}/disposition", DR, ok=(200, 201, 422), json={"disposition": "DISCHARGE", "diagnosis": "Wrist sprain, no fracture seen"})


# ------------------------------------------------------------------ 9. operation theatre
def surgeries():
    ths = {t["name"]: t["id"] for t in call("GET", "/api/ot/theatres", OT) or []}
    docs = doctor_ids(EMP)
    surgeon, anaes = docs.get(DR3), docs.get(DR)
    farida = PID["farida.shaikh@healthwise.demo.com"]
    if not (ths and surgeon and anaes):
        failures.append("theatres or doctors missing for the OT demo")
        return
    first = call("POST", "/api/ot/surgeries", DR3, json={"patient_id": farida, "theatre_id": ths.get("OT 1") or list(ths.values())[0], "procedure": "Laparoscopic cholecystectomy", "surgeon_id": surgeon,
                                                         "anaesthetist_id": anaes, "scheduled_start": at(26), "scheduled_end": at(28)})
    if first:
        sid = first["id"]
        call("POST", f"/api/ot/surgeries/{sid}/preop", DR, json={"fit": True, "notes": "ASA II, fasting confirmed, blood group A+ matched"})
        call("POST", f"/api/ot/surgeries/{sid}/consent", DR3, json={"given": True, "by_name": "Farida Shaikh"})
        call("POST", f"/api/ot/surgeries/{sid}/checklist", OT, json={"phase": "SIGN_IN", "items": ["Patient identity and procedure confirmed", "Surgical site marked", "Consent checked", "Anaesthesia machine and medicines checked", "Allergies reviewed"]})
    for patient, procedure, hours in ((PID["mohan.deshpande@healthwise.demo.com"], "Coronary angiography", 50), (PID["lata.pawar@healthwise.demo.com"], "Arthroscopic knee lavage", 75)):
        call("POST", "/api/ot/surgeries", OT, ok=(200, 201, 409, 422), json={"patient_id": patient, "theatre_id": ths.get("OT 2") or list(ths.values())[-1], "procedure": procedure, "surgeon_id": surgeon,
                                                                                "anaesthetist_id": anaes, "scheduled_start": at(hours), "scheduled_end": at(hours + 2)})


# ------------------------------------------------------------------ 10. blood bank
def blood_bank():
    donors = (("Vivek Joshi", "male", "1991-03-12", "O+", "9811100001"), ("Pooja Nair", "female", "1994-07-25", "B+", "9811100002"), ("Sameer Khan", "male", "1988-10-02", "A+", "9811100003"),
              ("Ritu Sharma", "female", "1996-01-19", "AB+", "9811100004"), ("Arun Patil", "male", "1985-12-08", "O-", "9811100005"), ("Neelam Gupta", "female", "1992-05-30", "A-", "9811100006"))
    units = {}
    for name, gender, dob, group, phone in donors:
        d = call("POST", "/api/bloodbank/donors", BB1, ok=(200, 201, 409, 422), json={"full_name": name, "gender": gender, "date_of_birth": dob, "blood_group": group, "phone": phone})
        if not d:
            continue
        don = call("POST", f"/api/bloodbank/donors/{d['id']}/donations", BB1, ok=(200, 201, 409, 422), json={"volume_ml": 450, "haemoglobin": 14.2, "weight_kg": 68, "components": ["PRBC", "FFP"]})
        if don:
            call("POST", f"/api/bloodbank/donations/{don['id']}/screening", BB2, ok=(200, 201, 409, 422), json={"result": "CLEARED"})
            units[group] = [u["id"] for u in don.get("units", [])]
    # a request for Farida (B+) before her surgery, matched and issued
    farida = PID["farida.shaikh@healthwise.demo.com"]
    req = call("POST", "/api/bloodbank/requests", DR3, ok=(200, 201, 409, 422), json={"patient_id": farida, "component": "PRBC", "units_requested": 1, "urgency": "ROUTINE", "indication": "Anaemia, Hb 9.1 before surgery"})
    if req and units.get("A+"):
        call("POST", f"/api/bloodbank/requests/{req['id']}/crossmatch", BB1, ok=(200, 201, 409, 422), json={"unit_id": units["A+"][0], "result": "COMPATIBLE"})
        call("POST", f"/api/bloodbank/requests/{req['id']}/issue", BB1, ok=(200, 201, 409, 422), json={"unit_id": units["A+"][0]})
    # an urgent request that is still waiting
    mohan = PID["mohan.deshpande@healthwise.demo.com"]
    call("POST", "/api/bloodbank/requests", DR2, ok=(200, 201, 409, 422), json={"patient_id": mohan, "component": "PRBC", "units_requested": 2, "urgency": "URGENT", "indication": "Anaemia, planned for angiography"})


# ------------------------------------------------------------------ 11. store and procurement
def store_and_procurement():
    sup = call("POST", "/api/stock/suppliers", STORE, ok=(200, 201, 409, 422), json={"name": "Apex Surgicals Pvt Ltd (demo)", "phone": "9876500001", "gstin": "27ABCDE1234F1Z5"})
    suppliers = call("GET", "/api/stock/suppliers", STORE) or []
    sid = (sup or (suppliers[0] if suppliers else {})).get("id")
    items = call("GET", "/api/procurement/items", STORE) or []
    if not (sid and items):
        failures.append("no supplier or store items for procurement")
        return
    req = call("POST", "/api/procurement/requisitions", NURSE, json={"items": [{"inventory_item_id": items[0]["id"], "quantity": 200}, {"medicine_name": "Tab. Pantoprazole", "quantity": 150}]})
    if req:
        call("POST", f"/api/procurement/requisitions/{req['id']}/decide", STORE, json={"approve": True})
        po = call("POST", "/api/procurement/orders", STORE, ok=(200, 201, 409, 422), json={"supplier_id": sid, "requisition_id": req["id"],
                                                                                          "items": [{"inventory_item_id": items[0]["id"], "quantity": 200, "unit_cost": 6.5}, {"medicine_name": "Tab. Pantoprazole", "quantity": 150, "unit_cost": 2.2}]})
        if po:
            call("POST", f"/api/procurement/orders/{po['id']}/approve", ADMIN, ok=(200, 201, 403, 409))
    # a second requisition left pending for the store manager's screen
    call("POST", "/api/procurement/requisitions", NURSE, ok=(200, 201, 422), json={"items": [{"inventory_item_id": items[-1]["id"], "quantity": 60}]})


# ------------------------------------------------------------------ 12. billing, payments, insurance claims
def finance():
    sneha, lata, mohan = PID[MARKER], PID["lata.pawar@healthwise.demo.com"], PID["mohan.deshpande@healthwise.demo.com"]
    services = {s["code"]: s["id"] for s in call("GET", "/api/hospital/services", ADMIN) or []}
    insurance = {}
    for pid, insurer, tpa, policy in ((lata, "Star Health Insurance", "MediAssist TPA", "SH-2024-558812"), (mohan, "HDFC ERGO Health", "Paramount TPA", "HE-2023-770145")):
        res = call("POST", f"/api/patient-registry/{pid}/insurance", TPA, ok=(200, 201, 409, 422), json={"insurer_name": insurer, "tpa_name": tpa, "policy_number": policy, "member_id": f"M{pid:05d}"})
        if res:
            insurance[pid] = res["id"]
    for pid, paid_in_full in ((sneha, True), (lata, False), (PID[RAHUL], True)):
        call("POST", f"/api/finance/patients/{pid}/collect-charges", BILL, ok=(200, 201, 422))
        overview = call("GET", f"/api/finance/patients/{pid}/overview", BILL) or {}
        charge_ids = [c["id"] for c in overview.get("pending_charges", [])]
        lines = [{"service_id": services["OPD-GEN"]}] if "OPD-GEN" in services and not charge_ids else []
        inv = call("POST", "/api/finance/invoices", BILL, ok=(200, 201, 409, 422), json={"patient_id": pid, "charge_ids": charge_ids, "services": lines})
        if not inv:
            continue
        final = call("POST", f"/api/finance/invoices/{inv['id']}/finalise", BILL, ok=(200, 201, 409, 422))
        if final and paid_in_full:
            call("POST", f"/api/finance/invoices/{final['id']}/pay", BILL, ok=(200, 201, 409, 422), json={"amount": final["total"], "method": "UPI", "reference": "UPI-DEMO-8841"})
        elif final:
            call("POST", f"/api/finance/invoices/{final['id']}/pay", BILL2, ok=(200, 201, 409, 422), json={"amount": round(final["total"] / 2, 2), "method": "CASH"})
            if pid in insurance:
                claim = call("POST", "/api/claims", TPA, ok=(200, 201, 409, 422), json={"invoice_id": final["id"], "patient_insurance_id": insurance[pid]})
                if claim:
                    call("POST", f"/api/claims/{claim['id']}/preauth", TPA, ok=(200, 201, 409, 422), json={"amount": max(1, int(final["total"] / 2)), "reference": "PA-DEMO-1042"})
    call("POST", "/api/finance/packages", ADMIN, ok=(200, 201, 409, 422), json={"name": "Senior citizen health check (demo)", "price": 3500, "gst_percent": 0, "inclusions": "Consultation, CBC, sugar, kidney tests, ECG"})


# ------------------------------------------------------------------ 13. trainee case histories and referrals
def trainees():
    kiran, rahul = PID["kiran.rao@healthwise.demo.com"], PID[RAHUL]
    docs = doctor_ids(INTERN)
    cases = ((INTERN, kiran, {"chief_complaint": "Cough and wheeze for 4 days", "duration": "4 days", "allergies": "YES", "allergy_details": "Penicillin (hives)", "present_illness": "Wheeze worse at night after a viral cold. No fever. Uses a reliever inhaler occasionally.",
                              "smoking": "NONE", "alcohol": "NONE", "vitals": {"pulse": 96, "bp_systolic": 118, "bp_diastolic": 76, "spo2": 95}}),
             (PG, PID["lata.pawar@healthwise.demo.com"], {"chief_complaint": "Knee pain on climbing stairs", "duration": "6 months", "allergies": "NONE", "present_illness": "Gradual pain in both knees, worse in the evening, morning stiffness under 20 minutes.",
                                                          "smoking": "NONE", "alcohol": "NONE", "vitals": {"pulse": 78, "bp_systolic": 146, "bp_diastolic": 90, "spo2": 97}}),
             (INTERN, rahul, {"chief_complaint": "Sneezing and itchy eyes", "duration": "2 weeks", "allergies": "YES", "allergy_details": "Dust and pollen", "present_illness": "Seasonal symptoms every spring, relieved by antihistamines.",
                              "smoking": "NONE", "alcohol": "NONE", "vitals": {"pulse": 74, "bp_systolic": 116, "bp_diastolic": 74, "spo2": 99}}))
    for who, pid, data in cases:
        h = call("POST", "/api/trainee/histories", who, ok=(200, 201, 403, 409), json={"patient_id": pid})
        if not h:
            continue
        call("PUT", f"/api/trainee/histories/{h['id']}", who, json={"data": data})
        done = call("POST", f"/api/trainee/histories/{h['id']}/complete", who, ok=(200, 201, 409, 422))
        if done and who == INTERN and pid == kiran:
            call("POST", "/api/trainee/referrals", INTERN, ok=(200, 201, 409, 422), json={"history_id": h["id"], "doctor_id": docs.get(DR), "reason": "Recurrent wheeze, please review the asthma plan"})


# ------------------------------------------------------------------ 14. the patient's assistant and the doctor's follow-ups / notes
def notes_and_assistant():
    for email, doctor, note in ((MARKER, DR, "Counselled on diet, daily foot checks and regular walking. Advised to bring the glucose log at the next visit."),
                                ("lata.pawar@healthwise.demo.com", DR, "Avoid painkillers other than paracetamol because of the kidney disease. Physiotherapy twice a week."),
                                ("mohan.deshpande@healthwise.demo.com", DR2, "Strict rest, low salt diet. Family counselled about warning signs of a heart attack.")):
        pid = PID.get(email)
        if pid:
            call("POST", "/api/doctor/notes", doctor, ok=(200, 201, 422), json={"patient_id": pid, "content": note})
            call("POST", "/api/doctor/recommendations", doctor, ok=(200, 201, 422), json={"patient_id": pid, "content": "Take medicines on time and keep all follow-up visits."})
            call("POST", f"/api/doctor/patients/{pid}/follow-ups", doctor, ok=(200, 201, 422), json={"title": "Review with reports", "due_date": str(date.today() + timedelta(days=14))})
    for email in (MARKER, RAHUL):
        for message in ("what medicines am I taking", "when is my next appointment"):
            call("POST", "/api/patient-assistant/chat", email, ok=(200, 201, 422), json={"message": message, "language": "en"})


def more_billing():
    """A fuller billing desk: paid, part paid, discounted, cancelled and draft invoices, an advance, a refund, and one claim taken all the way to settlement."""
    if len(call("GET", "/api/finance/invoices", BILL) or []) >= 12:
        return
    services = {x["code"]: x["id"] for x in call("GET", "/api/hospital/services", ADMIN) or []}
    emails = {e: PID_OF(e) for e in (MARKER, "kiran.rao@healthwise.demo.com", "farida.shaikh@healthwise.demo.com", "lata.pawar@healthwise.demo.com", "mohan.deshpande@healthwise.demo.com", RAHUL)}
    sneha, kiran, farida, lata, mohan, rahul = emails.values()

    def invoice(pid, codes, who=BILL):
        lines = [{"service_id": services[c], "quantity": q} for c, q in codes if c in services]
        inv = call("POST", "/api/finance/invoices", who, ok=(200, 201, 409, 422), json={"patient_id": pid, "services": lines})
        return inv

    def final(pid, codes, who=BILL):
        inv = invoice(pid, codes, who)
        return inv and call("POST", f"/api/finance/invoices/{inv['id']}/finalise", who, ok=(200, 201, 409, 422))

    def pay(inv, amount, method, who=BILL, **extra):
        return inv and call("POST", f"/api/finance/invoices/{inv['id']}/pay", who, ok=(200, 201, 409, 422), json={"amount": amount, "method": method, **extra})

    # fully paid, by different methods and two billing executives
    for pid, codes, method, who in ((sneha, (("LAB-CBC", 1), ("OPD-FU", 1)), "CARD", BILL), (kiran, (("OPD-GEN", 1), ("XRAY-CH", 1)), "UPI", BILL2), (farida, (("RAD-CXR", 1), ("LAB-ELEC", 1)), "CASH", BILL2),
                                    (rahul, (("OPD-FU", 1),), "CASH", BILL)):
        inv = final(pid, codes, who)
        if inv:
            pay(inv, inv["total"], method, who, **({"reference": "TXN-DEMO-" + str(inv["id"])} if method != "CASH" else {}))
    # part paid, the rest still due
    inv = final(sneha, (("LAB-ELEC", 1), ("OPD-GEN", 1)))
    if inv:
        pay(inv, round(inv["total"] / 2, 2), "CASH")
    # final bills left completely unpaid (the "outstanding" list)
    final(kiran, (("LAB-CBC", 1),))
    final(lata, (("OPD-GEN", 1), ("LAB-ELEC", 1)))
    # discounted: a small one by the biller, a larger one approved by the accountant
    inv = invoice(lata, (("OPD-GEN", 2), ("LAB-CBC", 1)))
    if inv:
        call("POST", f"/api/finance/invoices/{inv['id']}/discount", ACC, ok=(200, 201, 409, 422), json={"amount": 150, "reason": "Senior citizen concession"})
        done = call("POST", f"/api/finance/invoices/{inv['id']}/finalise", BILL, ok=(200, 201, 409, 422))
        pay(done, done and done["total"], "UPI", BILL, reference="UPI-DEMO-5521")
    inv = invoice(rahul, (("OPD-GEN", 1), ("XRAY-CH", 1)))
    if inv:
        call("POST", f"/api/finance/invoices/{inv['id']}/discount", BILL, ok=(200, 201, 409, 422), json={"amount": 90, "reason": "Staff relative"})
        call("POST", f"/api/finance/invoices/{inv['id']}/discount/approve", ACC, ok=(200, 201, 403, 409, 422))
    # a draft still being prepared, and one cancelled by the accountant
    invoice(farida, (("OPD-FU", 1), ("LAB-CBC", 1)))
    wrong = final(rahul, (("LAB-ELEC", 1),))
    if wrong:
        call("POST", f"/api/finance/invoices/{wrong['id']}/cancel", ACC, ok=(200, 201, 409, 422), json={"reason": "Billed to the wrong patient"})
    # an advance, then part of it returned
    dep = call("POST", "/api/finance/deposits", BILL, ok=(200, 201, 422), json={"patient_id": farida, "amount": 15000, "method": "CARD"})
    if dep:
        ref = call("POST", "/api/finance/refunds", BILL, ok=(200, 201, 409, 422), json={"deposit_id": dep["id"], "amount": 4000, "method": "CASH", "reason": "Unused advance returned"})
        if ref:
            call("POST", f"/api/finance/refunds/{ref['id']}/decide", ACC, ok=(200, 201, 409, 422), json={"approve": True})
    # a refund of part of a paid bill
    paid = final(kiran, (("OPD-GEN", 1),))
    if paid:
        pay(paid, paid["total"], "CASH")
        ref = call("POST", "/api/finance/refunds", BILL, ok=(200, 201, 409, 422), json={"invoice_id": paid["id"], "amount": 100, "method": "CASH", "reason": "Consultation fee waived by the doctor"})
        if ref:
            call("POST", f"/api/finance/refunds/{ref['id']}/decide", ACC, ok=(200, 201, 409, 422), json={"approve": True})
    # Mohan's stay: ICU and ward days on a final bill, paid partly from his advance, then an insurance claim taken to settlement
    stay = final(mohan, (("BED-ICU", 2), ("BED-GEN", 1), ("RAD-CXR", 1), ("LAB-CBC", 2)))
    if stay:
        deposits = (call("GET", f"/api/finance/patients/{mohan}/overview", BILL) or {}).get("deposits", [])
        if deposits:
            pay(stay, min(stay["total"], deposits[0].get("balance") or 0) or 1, "ADVANCE", deposit_id=deposits[0]["id"])
        policies = call("GET", f"/api/patient-registry/{mohan}", EMP) or {}
        pol = next(iter(policies.get("insurance", []) or []), None)
        claim = call("POST", "/api/claims", TPA, ok=(200, 201, 409, 422), json={"invoice_id": stay["id"], "patient_insurance_id": pol["id"]}) if pol else None
        if claim:
            cid = f"/api/claims/{claim['id']}"
            amount = int(stay["total"] * 0.8)
            call("POST", f"{cid}/preauth", TPA, ok=(200, 201, 409, 422), json={"amount": amount, "reference": "PA-DEMO-2210"})
            call("POST", f"{cid}/preauth/decision", TPA, ok=(200, 201, 409, 422), json={"approved_amount": amount})
            for doc in claim.get("documents", []):
                call("POST", f"{cid}/documents/{doc['id']}", TPA, ok=(200, 201, 409, 422), json={"received": True})
            call("POST", f"{cid}/submit", TPA, ok=(200, 201, 409, 422), json={"amount": amount})
            approved = int(amount * 0.9)
            call("POST", f"{cid}/decision", TPA, ok=(200, 201, 409, 422), json={"approved_amount": approved, "reason": "Room rent capped by policy"})
            call("POST", f"{cid}/settle", TPA, ok=(200, 201, 409, 422), json={"amount": approved, "reference": "UTR-DEMO-778812"})


def PID_OF(email: str) -> int:
    """Patient id of a demo patient, looked up through the registry list."""
    if email not in PID or not PID[email]:
        for p in call("GET", "/api/patients", EMP) or []:
            if p.get("email") == email:
                PID[email] = p["id"]
    return PID[email]


NAMESAKES = (   # a second, DIFFERENT person with the same name: the registry warns about it and each record keeps its own data
    ("rahul.patil2@healthwise.demo.com", "Rahul Patil", "male", "1975-11-02", "9822300001", "O+", "88 Kothrud Gaothan, Pune 411038", "Meena Patil (wife) 9822300002", DR, "Chronic obstructive lung disease"),
    ("sneha.kulkarni2@healthwise.demo.com", "Sneha Kulkarni", "female", "1993-02-14", "9822300011", "A+", "C-12, Lotus Park, Wakad, Pune 411057", "Nikhil Kulkarni (brother) 9822300012", DR, "Migraine"),
    ("mohan.deshpande2@healthwise.demo.com", "Mohan Deshpande", "male", "1981-09-09", "9822300021", "B-", "5 Deccan Gymkhana, Pune 411004", "Anita Deshpande (wife) 9822300022", DR2, "Lower back pain"),
)
def reports_and_namesakes():
    """Patients who share a name (the registry warns about it). No reports are created here: sample reports are real-format files uploaded by hand, never generated text."""
    if any(p.get("email") == NAMESAKES[0][0] for p in call("GET", "/api/patients", EMP) or []):
        return
    people = {p[0]: (PID_OF(p[0]), p[1]) for p in PATIENTS}
    docs = doctor_ids(EMP)
    for email, name, gender, dob, phone, blood, address, emergency, doc, history in NAMESAKES:
        made = call("POST", "/api/patients", EMP, ok=(201, 409, 422), json={
            "email": email, "full_name": name, "password": DEMO_PASSWORD, "gender": gender, "date_of_birth": dob, "phone": phone, "blood_group": blood, "address": address,
            "emergency_contact": emergency, "medical_history_text": history, "assigned_doctor_id": docs[doc], "allow_duplicate": True})
        if made:
            people[email] = (made["patient"]["id"], name)
            PID[email] = made["patient"]["id"]
    for email, doc in (("rahul.patil2@healthwise.demo.com", DR), ("sneha.kulkarni2@healthwise.demo.com", DR), ("mohan.deshpande2@healthwise.demo.com", DR2)):
        if email in people:
            call("POST", "/api/appointments", EMP, ok=(200, 201, 409, 422), json={"patient_id": people[email][0], "doctor_id": docs[doc], "scheduled_at": slot(30), "reason": "New patient consultation"})


def patient_avatars():
    for i, (email, name, *_rest) in enumerate(PATIENTS):
        profile = call("GET", "/api/profile", email)
        if profile and not profile["user"]["has_avatar"]:
            res = client.post("/api/profile/avatar", headers=H(email), files={"file": ("avatar.png", avatar_png(name, COLOURS[(i + 3) % len(COLOURS)]), "image/png")})
            if res.status_code not in (200, 201):
                failures.append(f"avatar for {email}: {res.status_code} {res.text[:100]}")


def repair_stale_tables() -> None:
    """An older development database may hold an EMPTY table from an earlier model version (the checklist table once used checked_by).
    An empty table is simply rebuilt from the current model; a table with rows is never touched."""
    from sqlalchemy import inspect, text
    from app.database.connection import Base, engine
    from app.database import models
    insp = inspect(engine)
    for model in (models.SurgeryChecklistItem,):
        table = model.__table__
        if not insp.has_table(table.name):
            continue
        have = {c["name"] for c in insp.get_columns(table.name)}
        if {c.name for c in table.columns} <= have:
            continue
        with engine.begin() as conn:
            if conn.execute(text(f'SELECT COUNT(*) FROM "{table.name}"')).scalar() == 0:
                conn.execute(text(f'DROP TABLE "{table.name}"'))
                table.create(conn)


def main() -> None:
    global client
    repair_stale_tables()
    with TestClient(app) as client:
        print("Filling the demo profiles through the application's own API ...")
        step("extra staff (doctors, nurse)", make_more_staff)
        if H(ADMIN) and client.get("/api/patients", headers=H(EMP)).status_code == 200:
            existing = [p for p in client.get("/api/patients", headers=H(EMP)).json() if p.get("email") == MARKER]
        else:
            existing = []
        step("staff profile details and photos", fill_profiles)
        if existing:
            print("Clinical showcase data is already present, skipping it (staff profiles above were topped up).")
            step("patient photos", patient_avatars)
        else:
            step("patients", register_patients)
            step("health histories", health_histories)
            step("OPD visits and prescriptions", opd_visits)
            step("laboratory results", lab_work)
            step("radiology reports", radiology_work)
            step("pharmacy stock and dispensing", pharmacy_work)
            step("inpatient stays and nursing chart", inpatient)
            step("emergency visits", emergency)
            step("operation theatre", surgeries)
            step("blood bank", blood_bank)
            step("store and procurement", store_and_procurement)
            step("bills, payments and claims", finance)
            step("trainee case histories", trainees)
            step("doctor notes and the assistant", notes_and_assistant)
            step("patient photos", patient_avatars)
        step("more billing data", more_billing)
        step("same-name patients", reports_and_namesakes)
    if failures:
        print(f"\n{len(failures)} step(s) did not apply (the rest did):")
        for line in failures:
            print("  -", line)
    print("\nDone. Log in with password %s, for example as %s, %s or %s." % (DEMO_PASSWORD, DR, RAHUL, ADMIN))


if __name__ == "__main__":
    main()
