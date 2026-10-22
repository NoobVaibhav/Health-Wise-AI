"""The health-history form: who can fill it, who can read it, and the 'points to check' for the doctor.
All patients and medicines in these tests are invented."""
from app.services.history_insights import CONDITION_RULES, MEDICINE_RULES, SYMPTOM_RULES, points_to_check
from app.services.safety_filter import is_safe_for_doctor

FORM = {
    "height_cm": 168, "weight_kg": 71,
    "conditions": [{"name": "Hypertension", "since": "25 years", "on_treatment": True},
                   {"name": "Ischaemic heart disease", "since": "2003", "on_treatment": True},
                   {"name": "Alzheimer's disease", "since": "2 years", "on_treatment": True}],
    "allergies": [{"name": "Penicillin", "kind": "DRUG", "reaction": "skin rash"}],
    "medications": [
        {"name": "Tab. Spironolactone", "dose": "12.5 mg", "frequency": "once daily", "reason": "blood pressure"},
        {"name": "Tab. Donepezil", "dose": "5 mg", "frequency": "once daily", "reason": "memory"},
        {"name": "Tab. Aspirin", "dose": "75 mg", "frequency": "once daily", "reason": "heart"},
        {"name": "Tab. Clopidogrel", "dose": "75 mg", "frequency": "once daily", "reason": "heart"},
        {"name": "Penicillin V", "dose": "250 mg", "frequency": "twice daily", "reason": "infection"}],
    "surgeries": [], "no_past_surgery": True, "family": [], "no_family_history": True,
    "habits": {"tobacco": "CHEWER", "tobacco_years": 50, "alcohol": "OCCASIONAL", "alcohol_years": 30, "diet": "VEG"},
    "current_problem": {"complaint": "Giddiness and one episode of fainting yesterday night", "duration": "1 day",
                        "symptoms": ["giddiness", "sweating"], "denies": ["fever", "chest pain", "palpitations"]},
}


def test_patient_saves_and_reads_own_history(client, world):
    empty = client.get("/api/health-history/me", headers=world.patient).json()
    assert empty["completeness"]["percent"] == 0 and empty["history"]["saved_before"] is False
    saved = client.put("/api/health-history/me", headers=world.patient, json=FORM)
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert [m["name"] for m in body["card"]["medicines"]][:2] == ["Tab. Spironolactone", "Tab. Donepezil"]
    assert body["card"]["bmi"] == 25.2 and body["card"]["allergies"][0]["name"] == "Penicillin"
    assert body["completeness"]["percent"] > 70
    # saving again replaces the medicine list, it does not add to it
    FORM2 = {**FORM, "medications": FORM["medications"][:1]}
    again = client.put("/api/health-history/me", headers=world.patient, json=FORM2).json()
    assert len(again["history"]["medications"]) == 1
    # the older one-line fields on the profile stay in step
    me = client.get("/api/patients/%d" % world.patient_id, headers=world.patient).json()
    assert "Spironolactone" in me["current_medications"] and "Penicillin" in me["allergies"]


def test_only_the_patient_and_authorised_doctors_can_see_it(client, world):
    client.put("/api/health-history/me", headers=world.patient, json=FORM)
    pid = world.patient_id
    assert client.get(f"/api/health-history/patient/{pid}", headers=world.doctor).status_code == 200
    # a doctor who has nothing to do with this patient, and every other role, are refused
    assert client.get(f"/api/health-history/patient/{pid}", headers=world.other_doctor).status_code == 403
    for who in (world.employee, world.admin, world.pharmacy, world.patient):
        assert client.get(f"/api/health-history/patient/{pid}", headers=who).status_code == 403
    for who in (world.doctor, world.employee, world.admin, world.pharmacy):
        assert client.get("/api/health-history/me", headers=who).status_code == 403
        assert client.put("/api/health-history/me", headers=who, json=FORM).status_code == 403
    assert client.put(f"/api/health-history/patient/{pid}", headers=world.other_doctor, json=FORM).status_code == 403
    # opening the history is written to the audit log
    logs = client.get("/api/admin/audit-logs?action=HISTORY_VIEWED", headers=world.admin).json()
    assert len(logs) == 1 and logs[0]["user_name"] == "Dr. Anjali Sharma"


def test_points_to_check_for_the_doctor(client, world):
    client.put("/api/health-history/me", headers=world.patient, json=FORM)
    view = client.get(f"/api/health-history/patient/{world.patient_id}", headers=world.doctor).json()
    points = view["points_to_check"]
    titles = " | ".join(p["title"] + " " + p["detail"] for p in points).lower()
    by_category = {p["category"] for p in points}
    assert {"safety", "medicine", "condition", "habit", "complaint"} <= by_category
    assert "penicillin" in titles and "allergy" in titles                       # allergy matches a listed medicine
    assert "more than one blood-thinning" in titles                            # aspirin + clopidogrel
    assert "slow the heart rate" in titles                                     # donepezil
    assert "potassium" in titles                                               # spironolactone
    assert "fainting" in titles and "holter" in titles                         # today's complaint
    assert "tobacco" in titles
    assert points[0]["category"] == "safety"                                   # the safety items come first


def test_missing_information_is_pointed_out(client, world):
    view = client.get(f"/api/health-history/patient/{world.patient_id}", headers=world.doctor).json()
    titles = [p["title"] for p in view["points_to_check"]]
    assert "Medicines not recorded" in titles and "Allergies not recorded" in titles
    # "I checked: nothing" is different from "not filled in"
    client.put("/api/health-history/me", headers=world.patient, json={"no_known_allergies": True, "no_regular_medicines": True})
    titles = [p["title"] for p in client.get(f"/api/health-history/patient/{world.patient_id}", headers=world.doctor).json()["points_to_check"]]
    assert "Medicines not recorded" not in titles and "Allergies not recorded" not in titles


def test_doctor_assessment_and_vitals(client, world):
    body = {"chief_complaint": "Giddiness and loss of consciousness since yesterday", "history_of_present_illness": "Two or three episodes.",
            "vitals": {"pulse": 46, "bp_systolic": 138, "bp_diastolic": 60, "spo2": 95, "temperature_f": 97.6, "resp_rate": 16},
            "examination": {"general": "Conscious, oriented to time, place and person", "cardiovascular": "S1 S2 normal, no murmur"},
            "provisional_diagnosis": "To be decided after the ECG", "investigations_advised": "ECG, CPK-MB, CBC, RFT",
            "plan_type": "MEDICAL", "special_note": "Repeat ECG after 4 hours"}
    made = client.post(f"/api/health-history/patient/{world.patient_id}/assessments", headers=world.doctor, json=body)
    assert made.status_code == 201 and made.json()["doctor_name"] == "Dr. Anjali Sharma"
    assert client.post(f"/api/health-history/patient/{world.patient_id}/assessments", headers=world.other_doctor, json=body).status_code == 403
    assert client.post(f"/api/health-history/patient/{world.patient_id}/assessments", headers=world.patient, json=body).status_code == 403
    view = client.get(f"/api/health-history/patient/{world.patient_id}", headers=world.doctor).json()
    assert view["assessments"][0]["provisional_diagnosis"] == "To be decided after the ECG"     # written by the doctor
    assert any(p["category"] == "vitals" and "Slow pulse" in p["title"] for p in view["points_to_check"])


def test_invalid_forms_are_refused(client, world):
    assert client.put("/api/health-history/me", headers=world.patient, json={"height_cm": 5}).status_code == 422
    assert client.put("/api/health-history/me", headers=world.patient, json={"medications": [{"name": "x"}]}).status_code == 422
    assert client.put("/api/health-history/me", headers=world.patient, json={"habits": {"tobacco": "SOMETIMES"}}).status_code == 422


def test_rule_texts_never_name_a_dose_or_prescribe():
    texts = [d for _, _, d in MEDICINE_RULES] + [d for _, _, d in CONDITION_RULES] + [d for _, _, d in SYMPTOM_RULES]
    assert all(is_safe_for_doctor(t) for t in texts), [t for t in texts if not is_safe_for_doctor(t)]
    assert points_to_check({"medications": [], "conditions": [], "allergies": [], "habits": {}, "current_problem": {}}, 40)


def test_preview_gives_points_and_suggested_tests_without_saving(client, world):
    body = {"history": FORM, "vitals": {"pulse": 46}}
    r = client.post(f"/api/health-history/patient/{world.patient_id}/preview", headers=world.doctor, json=body)
    assert r.status_code == 200
    data = r.json()
    assert any(p["category"] == "safety" for p in data["points_to_check"])
    assert {"Serum electrolytes (Na, K, Cl)", "ECG", "Lipid profile"} <= set(data["suggested_tests"])
    assert "Holter monitoring (24 hour ECG)" in data["suggested_tests"]
    # nothing was saved
    mine = client.get("/api/health-history/me", headers=world.patient).json()
    assert mine["history"]["saved_before"] is False
    # only the patient's own doctors may ask
    assert client.post(f"/api/health-history/patient/{world.patient_id}/preview", headers=world.other_doctor, json=body).status_code == 403
    assert client.post(f"/api/health-history/patient/{world.patient_id}/preview", headers=world.patient, json=body).status_code == 403


def test_usual_values_and_latest_blood_tests(client, world):
    from tests import sample_data as sd
    from tests.conftest import upload
    form = {**FORM, "baseline": {"pulse": 72, "bp_systolic": 130, "bp_diastolic": 80, "sugar_fasting": 98, "hba1c": 5.6,
                                 "others": [{"name": "Uric acid", "value": "5.1", "unit": "mg/dL"}], "noted_on": "March 2026"}}
    saved = client.put("/api/health-history/me", headers=world.patient, json=form).json()
    assert saved["history"]["baseline"]["pulse"] == 72 and saved["card"]["usual_values"]["hba1c"] == 5.6
    assert any(p["name"] == "Usual values" and p["done"] for p in saved["completeness"]["parts"])
    # the newest value of every test in the reports is shown from the reports themselves
    rep = upload(client, world.employee, world.patient_id, "july.pdf", sd.lines_to_pdf(sd.REPORT_A_LINES)).json()
    view = client.get(f"/api/health-history/patient/{world.patient_id}", headers=world.doctor).json()
    assert {"HbA1c", "LDL"} <= {l["name"] for l in view["latest_labs"]}
    assert view["latest_labs"][0]["status"] in ("ABOVE_RANGE", "BELOW_RANGE")            # values outside the range come first
    assert saved["card"]["latest_labs"] == []                                            # the patient's card: reviewed reports only
    client.put(f"/api/doctor/reports/{rep['id']}/review", headers=world.doctor, json={"decision": "APPROVED"})
    assert client.get("/api/health-history/me", headers=world.patient).json()["card"]["latest_labs"]
    # today's pulse is compared with the patient's own usual pulse
    prev = client.post(f"/api/health-history/patient/{world.patient_id}/preview", headers=world.doctor,
                       json={"history": form, "vitals": {"pulse": 46, "bp_systolic": 128}}).json()
    titles = [p["title"] for p in prev["points_to_check"]]
    assert "Pulse 46 is much lower than the usual 72" in titles
    assert not any("Blood pressure" in t and "usual" in t for t in titles)                # 128 against 130 is no change
