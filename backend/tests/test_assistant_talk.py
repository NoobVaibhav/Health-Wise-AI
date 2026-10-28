"""The conversational side of the patient assistant: greeting, thanks, goodbye, what it can do, the time, "open my reports" and "brief me"."""
from datetime import datetime

import pytest

from app.routers import patient_assistant as assistant_router
from app.services import assistant_talk as talk
from tests.test_patient_assistant import add_report, completed_visit, reply, report


@pytest.fixture(autouse=True)
def _reset_limits():
    assistant_router._recent.clear()
    yield
    assistant_router._recent.clear()


def test_detection_only_takes_real_small_talk():
    assert talk.detect("hello")[0] == "GREETING" and talk.detect("good morning")[0] == "GREETING" and talk.detect("नमस्ते")[0] == "GREETING"
    assert talk.detect("thank you so much")[0] == "THANKS" and talk.detect("bye")[0] == "BYE" and talk.detect("that's all")[0] == "BYE"
    assert talk.detect("what can you do")[0] == "WHO" and talk.detect("what time is it")[0] == "TIME" and talk.detect("brief me")[0] == "BRIEFING"
    assert talk.detect("open my reports")[0] == "NAVIGATE" and talk.detect("रिपोर्ट खोलो")[0] == "NAVIGATE"
    # a question about the records is left to the record intents
    for question in ("what did my doctor say at my last checkup", "explain my latest report", "what medicines am i taking", "is my prescription open",
                     "hello doctor, what is my hba1c level and what does it mean"):
        assert talk.detect(question) is None, question
    assert talk.detect("thanks, now tell me about my medicines and also my last blood report results please") is None      # too long to be only thanks


def test_the_pages_are_found_by_name_in_three_languages():
    assert talk.detect("open my medicines")[1]["to"] == "/patient/prescriptions"
    assert talk.detect("go to appointments")[1]["to"] == "/patient/appointments"
    assert talk.detect("open health history")[1]["to"] == "/patient/health-history"      # not "reports" or "history" alone
    assert talk.detect("take me to my profile")[1]["to"] == "/patient/profile"
    assert talk.detect("अपॉइंटमेंट खोलो")[1]["to"] == "/patient/appointments" and talk.detect("औषधे उघडा")[1]["to"] == "/patient/prescriptions"


def test_the_answers_use_the_name_the_time_of_day_and_the_language():
    morning, evening = datetime(2026, 10, 28, 9, 5), datetime(2026, 10, 28, 19, 40)
    assert talk.answer("GREETING", {}, "en", "Rahul", morning)["text"].startswith("Good morning, Rahul!")
    assert talk.answer("GREETING", {}, "en", "Rahul", evening)["text"].startswith("Good evening, Rahul!")
    assert talk.answer("GREETING", {}, "hi", "Rahul", morning)["text"].startswith("सुप्रभात, Rahul!")
    assert "9:05 AM on Wednesday, 28 Oct 2026" in talk.answer("TIME", {}, "en", "x", morning)["text"]
    assert talk.answer("BYE", {}, "en", "Rahul")["action"] == {"type": "end_conversation"}
    nav = talk.answer("NAVIGATE", talk.detect("open my reports")[1], "en", "Rahul")
    assert nav["action"] == {"type": "navigate", "to": "/patient/reports", "label": "your reports"} and nav["text"] == "Opening your reports."


def test_through_the_chat_small_talk_needs_no_record_and_keeps_the_topic_of_the_conversation(client, world):
    first = client.post("/api/patient-assistant/chat", headers=world.patient, json={"message": "hello", "language": "en"}).json()
    assert first["reply"]["intent"] == "GREETING" and first["reply"]["text"].split(",")[1].strip().startswith("Rahul") and first["reply"]["sources"] == []
    assert first["reply"]["follow_ups"]                                         # a greeting is followed by things worth asking
    nav = client.post("/api/patient-assistant/chat", headers=world.patient, json={"message": "open my medicines", "language": "en", "conversation_id": first["conversation_id"]}).json()["reply"]
    assert nav["intent"] == "NAVIGATE" and nav["action"]["to"] == "/patient/prescriptions"
    assert reply(client, world.patient, "thank you")["intent"] == "THANKS"
    assert reply(client, world.patient, "bye")["action"] == {"type": "end_conversation"}
    assert "9:" not in reply(client, world.patient, "who are you")["text"] and "Brief me" in reply(client, world.patient, "what can you do")["text"]


def test_an_emergency_is_never_taken_for_small_talk(client, world):
    out = reply(client, world.patient, "hello I have severe chest pain right now")
    assert out["safety"] == "EMERGENCY" and out["action"] is None and out["follow_ups"] == []


def test_the_briefing_is_built_only_from_the_patients_own_records(client, world):
    empty = reply(client, world.patient, "brief me")
    assert empty["intent"] == "BRIEFING" and "No reviewed test result is on record yet." in empty["text"] and "No upcoming appointment" in empty["text"]
    add_report(client, world, "r.txt", report("03/07/2026", "Hemoglobin 14.0 g/dL 13.0 - 17.0", "Vitamin D 14 ng/mL 30 - 100", "HbA1c 7.4 % 4.0 - 5.7"))
    completed_visit(world)
    full = reply(client, world.patient, "what's new")
    assert full["intent"] == "BRIEFING" and "2 of your reviewed results are outside the printed range" in full["text"] and "Vitamin D" in full["text"] and "HbA1c" in full["text"]
    assert "Hemoglobin" not in full["text"].split("outside the printed range")[1].split(".")[0]
    assert full["text"].startswith(("Good morning, Rahul", "Good afternoon, Rahul", "Good evening, Rahul")) and "talk to your doctor" in full["text"].lower()
    assert any(s["type"] == "report" for s in full["sources"]) and "follow_ups" in full
    hindi = reply(client, world.patient, "आज की जानकारी", lang="hi")
    assert hindi["intent"] == "BRIEFING" and "Vitamin D" in hindi["text"]
    other = client.get("/api/patient-assistant/suggestions", headers=world.patient)
    assert other.status_code == 200


def test_the_briefing_does_not_show_another_patients_records(client, world):
    from tests.test_patient_assistant import second_patient
    pid, other = second_patient(client, world)
    add_report(client, world, "mine.txt", report("03/07/2026", "Vitamin D 14 ng/mL 30 - 100"))
    out = reply(client, other, "brief me")
    assert "Vitamin D" not in out["text"] and "No reviewed test result is on record yet." in out["text"]
