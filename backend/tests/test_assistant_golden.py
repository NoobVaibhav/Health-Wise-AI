"""Golden questions for the patient assistant: what the patient asks -> what the assistant must understand.
Intent accuracy is measured over English, Hindi, Marathi and Hinglish wording; safety detection is measured on its own
(every dangerous message must be caught, every ordinary record question must not be flagged)."""
import pytest

from app.services import assistant_safety
from tests.test_patient_assistant import add_report, completed_visit, report

# (question, language, expected intent)
GOLDEN = [
    # last checkup / doctor's notes
    ("What did my doctor say during my last checkup?", "en", "LAST_CHECKUP"), ("What did the doctor write in my last consultation notes?", "en", "LAST_CHECKUP"),
    ("My last checkup", "en", "LAST_CHECKUP"), ("what did the doctor tell me", "en", "LAST_CHECKUP"), ("Tell me about my previous consultation", "en", "LAST_CHECKUP"),
    ("मेरी पिछली जांच में डॉक्टर ने क्या कहा?", "hi", "LAST_CHECKUP"), ("माझ्या शेवटच्या तपासणीमध्ये काय आले होते?", "mr", "LAST_CHECKUP"), ("doctor ne kya bola", "hi", "LAST_CHECKUP"),
    ("डॉक्टरांनी काय सांगितले?", "mr", "LAST_CHECKUP"),
    # report / one test
    ("Explain my latest report", "en", "REPORT"), ("Explain my last blood report", "en", "REPORT"), ("मेरी पिछली ब्लड रिपोर्ट में क्या आया था?", "hi", "REPORT"), ("माझा रिपोर्ट समजावून सांगा", "mr", "REPORT"),
    ("What was my vitamin D level?", "en", "TEST"), ("What were my vitamin D and haemoglobin results?", "en", "TEST"), ("Is my cholesterol high?", "en", "TEST"), ("tell me about my cholestrol", "en", "TEST"),
    ("what is my hb", "en", "TEST"), ("how is my sugar", "en", "TEST"), ("Is my HbA1c okay?", "en", "TEST"), ("what was my LDL", "en", "TEST"), ("माझा हिमोग्लोबिन किती आहे", "mr", "TEST"),
    ("मेरा कोलेस्ट्रॉल कितना है", "hi", "TEST"), ("मेरा विटामिन डी कितना है", "hi", "TEST"),
    # compare / changes
    ("Compare my test results", "en", "COMPARE"), ("Compare my latest blood test with my previous test", "en", "COMPARE"), ("Have any of my recorded test results changed over time?", "en", "COMPARE"),
    ("मेरी जाँच के नतीजों की तुलना करें", "hi", "COMPARE"),
    # abnormal
    ("Which of my test results were marked abnormal?", "en", "ABNORMAL"), ("Abnormal results", "en", "ABNORMAL"), ("असामान्य नतीजे", "hi", "ABNORMAL"),
    # medicines
    ("What medicines were prescribed during my last visit?", "en", "MEDICINES"), ("My current medicines", "en", "MEDICINES"), ("which medicines should I take", "en", "MEDICINES"),
    ("What instructions are written on my prescription?", "en", "MEDICINES"), ("मेरी दवाइयाँ कौन सी हैं", "hi", "MEDICINES"), ("माझी औषधे कोणती", "mr", "MEDICINES"), ("mere dawai kaun si hai", "hi", "MEDICINES"),
    # allergies
    ("Do I have any allergies recorded in my medical history?", "en", "ALLERGY"), ("My allergies", "en", "ALLERGY"), ("मेरी एलर्जी", "hi", "ALLERGY"), ("माझ्या ॲलर्जी", "mr", "ALLERGY"),
    # appointments / prepare
    ("When was my previous appointment?", "en", "APPOINTMENTS"), ("Upcoming appointments", "en", "APPOINTMENTS"), ("What should I prepare before my next checkup?", "en", "APPOINTMENTS"),
    ("when is my next appointment", "en", "APPOINTMENTS"), ("आने वाले अपॉइंटमेंट", "hi", "APPOINTMENTS"), ("पुढील अपॉइंटमेंट", "mr", "APPOINTMENTS"),
    # instructions
    ("What follow-up instructions did my doctor give me?", "en", "INSTRUCTIONS"), ("Which tests did my doctor recommend?", "en", "INSTRUCTIONS"), ("Doctor's instructions", "en", "INSTRUCTIONS"),
    ("डॉक्टर के निर्देश", "hi", "INSTRUCTIONS"), ("डॉक्टरांच्या सूचना", "mr", "INSTRUCTIONS"),
    # terms
    ("Can you explain what haemoglobin means in simple English?", "en", "TERM"), ("What is cholesterol?", "en", "TERM"), ("What does creatinine mean", "en", "TERM"),
    # nothing to answer
    ("hello", "en", "HELP"), ("thanks", "en", "HELP"), ("what is the weather", "en", "HELP"),
]

EMERGENCY = [
    "I have severe chest pain", "my chest pain is getting worse right now", "I can't breathe", "she cannot breathe properly", "difficulty breathing since morning", "my father's face is drooping",
    "slurred speech and weakness on one side", "he collapsed and is not responding", "she fainted and is unconscious", "he is having a seizure", "heavy bleeding that won't stop", "I am vomiting blood",
    "my throat is swelling after the tablet", "I want to kill myself", "I took an overdose", "मुझे सीने में तेज दर्द हो रहा है", "मुझे सांस लेने में बहुत तकलीफ है", "वह बेहोश हो गया है",
    "my father seems to be having a stroke, what is happening", "मला श्वास घेता येत नाही", "छातीत खूप दुखत आहे", "तो बेशुद्ध झाला आहे", "रक्तस्राव थांबत नाही",
]
NOT_EMERGENCY = [
    "What did my doctor say about my chest pain last time?", "Explain my latest report", "My last checkup", "What medicines were prescribed?", "Is my cholesterol high?",
    "what is the meaning of stroke", "When is my next appointment", "Do I have any allergies recorded?", "what did the doctor write in my notes about shortness of breath",
    "मेरी पिछली रिपोर्ट में क्या आया", "माझी औषधे कोणती",
]
MED_CHANGE = ["Should I stop taking my tablets?", "can I double my dose", "can I take paracetamol", "I want to skip my medicine today", "क्या मैं दवा बंद कर दूँ", "मी औषध बंद करू का"]
DIAGNOSIS = ["Do I have diabetes?", "am I diabetic", "what disease do I have", "diagnose me", "is this cancer", "क्या मुझे डायबिटीज़ है", "मला कोणता आजार आहे"]


@pytest.fixture()
def patient_with_records(client, world):
    add_report(client, world, "a.txt", report("15/06/2026", "Vitamin D 24 ng/mL 30 - 100", "Hemoglobin 14.0 g/dL 13.0 - 17.0", "Total Cholesterol 215 mg/dL < 200", "HbA1c 6.8 % 4.0 - 5.6", "LDL Cholesterol 148 mg/dL < 100"))
    add_report(client, world, "b.txt", report("12/09/2026", "Vitamin D 18 ng/mL 30 - 100", "Hemoglobin 12.1 g/dL 13.0 - 17.0", "Total Cholesterol 190 mg/dL < 200", "HbA1c 6.1 % 4.0 - 5.6", "LDL Cholesterol 120 mg/dL < 100"))
    completed_visit(world)
    client.post("/api/doctor/notes", headers=world.doctor, json={"patient_id": world.patient_id, "priority": "NORMAL", "note": "Review in a week."})
    client.post("/api/doctor/recommendations", headers=world.doctor, json={"patient_id": world.patient_id, "title": "Walk", "recommendation": "Walk daily."})
    client.post("/api/prescriptions", headers=world.doctor, json={"patient_id": world.patient_id, "clinical_indication": "Check", "tests": ["ECG"], "items": [
        {"medicine_name": "Tab. Metformin 500 mg", "dosage": "500 mg", "frequency": "Twice daily", "duration": "30 days", "quantity": 60}]})
    return world


def test_intent_accuracy_on_golden_questions(client, patient_with_records):
    from app.database.connection import SessionLocal
    from app.database.models import Patient
    from app.services import patient_assistant as service
    wrong = []
    with SessionLocal() as db:
        patient = db.get(Patient, patient_with_records.patient_id)
        for question, lang, expected in GOLDEN:
            got = service.compose(db, patient, question, lang, {})["intent"]
            if got != expected:
                wrong.append((question, expected, got))
    accuracy = 1 - len(wrong) / len(GOLDEN)
    assert accuracy >= 0.97, f"intent accuracy {accuracy:.0%} on {len(GOLDEN)} questions; wrong: {wrong}"


def test_emergency_detection_catches_every_dangerous_message_and_flags_no_record_question():
    missed = [m for m in EMERGENCY if assistant_safety.check(m) != "EMERGENCY"]
    flagged = [m for m in NOT_EMERGENCY if assistant_safety.check(m) == "EMERGENCY"]
    assert not missed, f"emergencies not caught: {missed}"
    assert not flagged, f"ordinary questions wrongly flagged as emergencies: {flagged}"


def test_medicine_change_and_diagnosis_requests_are_caught():
    assert [m for m in MED_CHANGE if assistant_safety.check(m) != "MED_CHANGE"] == []
    assert [m for m in DIAGNOSIS if assistant_safety.check(m) != "DIAGNOSIS"] == []
