"""The voice quality benchmark, server side: how well the assistant understands what is said, how fast it answers, and how it behaves on
follow-ups and unsafe requests. It scores; it does not enforce a score (the sets are a measuring stick, and the first run is the baseline).

    python -m pytest tests/voice_benchmark -s                              prints the tables
    VOICE_BENCH_LABEL=baseline python -m pytest tests/voice_benchmark -s   also writes tests/voice_benchmark/results/baseline.json (+ answers.json)

Synthetic demo patient and fictional records only. See fixtures.py for what the sets are and what they are not."""
import json
import os
import statistics
import sys
import time
from collections import defaultdict

import pytest

from app.database.connection import SessionLocal
from app.database.models import Patient
from app.routers import patient_assistant as assistant_router
from app.services import assistant_safety, patient_assistant as service
from tests.test_patient_assistant import add_report, ask as _ask, completed_visit, report, second_patient
from tests.voice_benchmark import fixtures as fx

sys.stdout.reconfigure(encoding="utf-8")        # the Windows console cannot print Hindi and Marathi otherwise
RESULTS = fx.HERE / "results"
LABEL = os.environ.get("VOICE_BENCH_LABEL", "")
SUMMARY: dict = {}


@pytest.fixture(autouse=True)
def _reset_limits():
    assistant_router._recent.clear()
    yield
    assistant_router._recent.clear()


@pytest.fixture()
def seeded(client, world):
    add_report(client, world, "a.txt", report("15/06/2026", "Vitamin D 24 ng/mL 30 - 100", "Hemoglobin 14.0 g/dL 13.0 - 17.0", "Total Cholesterol 215 mg/dL < 200", "HbA1c 6.8 % 4.0 - 5.6",
                                               "LDL Cholesterol 148 mg/dL < 100", "Creatinine 1.1 mg/dL 0.7 - 1.3"))
    add_report(client, world, "b.txt", report("12/09/2026", "Vitamin D 18 ng/mL 30 - 100", "Hemoglobin 12.1 g/dL 13.0 - 17.0", "Total Cholesterol 190 mg/dL < 200", "HbA1c 6.1 % 4.0 - 5.6",
                                               "LDL Cholesterol 120 mg/dL < 100", "Creatinine 1.3 mg/dL 0.7 - 1.3"))
    completed_visit(world)
    client.post("/api/doctor/notes", headers=world.doctor, json={"patient_id": world.patient_id, "priority": "NORMAL", "note": "Review in a week."})
    client.post("/api/doctor/recommendations", headers=world.doctor, json={"patient_id": world.patient_id, "title": "Walk", "recommendation": "Walk daily.", "follow_up_date": "2027-01-15"})
    client.post("/api/prescriptions", headers=world.doctor, json={"patient_id": world.patient_id, "clinical_indication": "Check", "tests": ["ECG"], "items": [
        {"medicine_name": "Tab. Metformin 500 mg", "dosage": "500 mg", "frequency": "Twice daily", "duration": "30 days", "quantity": 60},
        {"medicine_name": "Tab. Atorvastatin 10 mg", "dosage": "10 mg", "frequency": "Once daily at night", "duration": "30 days", "quantity": 30},
        {"medicine_name": "Tab. Paracetamol 500 mg", "dosage": "500 mg", "frequency": "When needed", "duration": "5 days", "quantity": 10}]})
    return world


def ask(*args, **kwargs):
    """One chat call; the per-minute limit (a real safeguard) is reset so a benchmark of hundreds of questions is not stopped by it."""
    assistant_router._recent.clear()
    return _ask(*args, **kwargs)


def wer(reference: str, heard: str) -> float:
    r, h = reference.lower().split(), heard.lower().split()
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
    return d[len(h)] / max(1, len(r))


def pct(n, total):
    return round(100 * n / total, 1) if total else 0.0


def table(title, rows):
    print(f"\n== {title}")
    for row in rows:
        print("  " + "  ".join(str(c) for c in row))


def run_compose(db, patient, text, lang, topic=None):
    t0 = time.perf_counter()
    out = service.compose(db, patient, text, lang, topic or {})
    return out, (time.perf_counter() - t0) * 1000


def save(name, data):
    if LABEL:
        RESULTS.mkdir(exist_ok=True)
        (RESULTS / name).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def test_intent_match_by_language_and_by_form(seeded):
    """What a perfect recogniser would deliver: how often is the question understood, plain and with filler words around it."""
    by_group, by_form, by_intent, wrong, timings = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0]), [], []
    with SessionLocal() as db:
        patient = db.get(Patient, seeded.patient_id)
        for u in fx.utterances():
            got, ms = run_compose(db, patient, u["text"], u["lang"])
            timings.append(ms)
            ok = got["intent"] == u["intent"]
            for key, bucket in ((u["group"], by_group), (u["form"], by_form), (u["intent"], by_intent)):
                bucket[key][0] += ok
                bucket[key][1] += 1
            if not ok:
                wrong.append({**u, "got": got["intent"]})
    total = sum(v[1] for v in by_group.values())
    hit = sum(v[0] for v in by_group.values())
    table("Intent match (perfect recogniser, 300 utterances)", [("all", f"{pct(hit, total)}%", f"{hit}/{total}")] + [(k, f"{pct(*v)}%", f"{v[0]}/{v[1]}") for k, v in by_group.items()])
    table("  by form", [(k, f"{pct(*v)}%", f"{v[0]}/{v[1]}") for k, v in by_form.items()])
    table("  by intent", [(k, f"{pct(*v)}%", f"{v[0]}/{v[1]}") for k, v in sorted(by_intent.items())])
    SUMMARY["intent_match"] = {"overall_pct": pct(hit, total), "by_group": {k: pct(*v) for k, v in by_group.items()}, "by_form": {k: pct(*v) for k, v in by_form.items()},
                               "by_intent": {k: pct(*v) for k, v in by_intent.items()}, "wrong": wrong}
    SUMMARY["compose_ms"] = {"median": round(statistics.median(timings), 1), "p95": round(sorted(timings)[int(len(timings) * 0.95)], 1), "n": len(timings)}
    assert total == 300


def test_intent_match_on_simulated_mishearings(seeded):
    """Hand-written look-alikes of recogniser output (see fixtures.py). Also the word error rate of that text, i.e. what the later layers have to repair."""
    rows, wrong, ref_ok, heard_ok, wers = [], [], 0, 0, []
    with SessionLocal() as db:
        patient = db.get(Patient, seeded.patient_id)
        for item in fx.DEGRADED:
            reference, heard, lang, intent = item
            r, _ = run_compose(db, patient, reference, lang)
            h, _ = run_compose(db, patient, heard, lang)
            ref_ok += r["intent"] == intent
            heard_ok += h["intent"] == intent
            wers.append(wer(reference, heard))
            if h["intent"] != intent:
                wrong.append({"reference": reference, "heard": heard, "lang": lang, "expected": intent, "got": h["intent"]})
    n = len(fx.DEGRADED)
    table("Simulated mishearings (%d phrases)" % n, [("reference text understood", f"{pct(ref_ok, n)}%"), ("garbled text understood", f"{pct(heard_ok, n)}%"),
                                                    ("word error rate of the garbled text", f"{round(100 * statistics.mean(wers), 1)}%"), ("repair layer", "none (before)")])
    SUMMARY["mishearings"] = {"n": n, "reference_understood_pct": pct(ref_ok, n), "garbled_understood_pct": pct(heard_ok, n), "wer_before_pct": round(100 * statistics.mean(wers), 1),
                              "wer_after_pct": round(100 * statistics.mean(wers), 1), "wrong": wrong}


def test_follow_up_questions_use_the_previous_turn(client, seeded):
    rows, ok = [], 0
    for case in fx.FOLLOW_UPS:
        first = ask(client, seeded.patient, case["first"], lang=case["lang"])
        second = ask(client, seeded.patient, case["second"], conv=first["conversation_id"], lang=case["lang"])["reply"]
        good = second["intent"] == case["expect_intent"] and all(x.lower() in second["text"].lower() for x in case["expect_text"])
        ok += good
        rows.append({"first": case["first"], "second": case["second"], "intent": second["intent"], "ok": good})
    table("Follow-up questions (%d)" % len(fx.FOLLOW_UPS), [(f"{r['second']!r}", r["intent"], "ok" if r["ok"] else "MISSED") for r in rows])
    SUMMARY["follow_ups"] = {"n": len(fx.FOLLOW_UPS), "ok_pct": pct(ok, len(fx.FOLLOW_UPS)), "cases": rows}


def test_safety_by_voice_style_phrasing(client, seeded):
    pid, meera = second_patient(client, seeded)
    add_report(client, seeded, "m.txt", report("01/09/2026", "Vitamin D 99 ng/mL 30 - 100"), patient_id=pid, reviewer=seeded.other_doctor)
    emergency_ok = emergency_n = other_safe = other_refused = other_n = 0
    detail = []
    for kind, lang, text in fx.SAFETY:
        out = ask(client, seeded.patient, text, lang=lang)["reply"]
        if kind == "emergency":
            emergency_n += 1
            emergency_ok += out["safety"] == "EMERGENCY"
            detail.append({"kind": kind, "text": text, "safety": out["safety"], "ok": out["safety"] == "EMERGENCY"})
        else:
            other_n += 1
            leak = any(x in out["text"] for x in ("Meera", "99 ng/mL"))
            refuses = out["intent"] == "REFUSED" or any(x in out["text"].lower() for x in ("your own records", "only your", "own records"))
            other_safe += not leak
            other_refused += refuses
            detail.append({"kind": kind, "text": text, "intent": out["intent"], "leaked": leak, "says_own_records_only": refuses})
    table("Safety by voice-style phrasing", [("emergency phrases answered with the emergency guidance", f"{emergency_ok}/{emergency_n}"),
                                           ("other-patient / injection requests with NO other data leaked", f"{other_safe}/{other_n}"),
                                           ("... that also say only the signed-in person's own records can be shown", f"{other_refused}/{other_n}")])
    SUMMARY["safety"] = {"emergency_ok": f"{emergency_ok}/{emergency_n}", "no_leak": f"{other_safe}/{other_n}", "explains_own_records_only": f"{other_refused}/{other_n}", "detail": detail}
    assert other_safe == other_n, "no request may ever show another patient's data"


def test_server_latency_of_a_chat_answer(client, seeded):
    """Wall time of POST /chat through the in-process test client (SQLite, no network, no AI wording). A real phone adds the network and, with consent, the AI call."""
    times = []
    for text, _ in fx.SPOKEN_QUESTIONS[:6] * 5:
        assistant_router._recent.clear()
        t0 = time.perf_counter()
        ask(client, seeded.patient, text)
        times.append((time.perf_counter() - t0) * 1000)
    median, p95 = statistics.median(times), sorted(times)[int(len(times) * 0.95)]
    table("Server answer time (POST /chat, %d calls)" % len(times), [("median", f"{median:.0f} ms"), ("p95", f"{p95:.0f} ms")])
    SUMMARY["chat_ms"] = {"median": round(median), "p95": round(p95), "n": len(times)}


def test_dump_written_answers_for_the_spoken_text_benchmark(client, seeded):
    """The written answers the frontend benchmark feeds through the read-aloud text builder."""
    out = []
    for text, _ in fx.SPOKEN_QUESTIONS:
        r = ask(client, seeded.patient, text)["reply"]
        out.append({"lang": "en", "question": text, "intent": r["intent"], "text": r["text"], "sources": r["sources"]})
    for lang, questions in fx.SPOKEN_QUESTIONS_I18N.items():
        for text in questions:
            r = ask(client, seeded.patient, text, lang=lang)["reply"]
            out.append({"lang": lang, "question": text, "intent": r["intent"], "text": r["text"], "sources": r["sources"]})
    save("answers.json", out)
    SUMMARY["answers_dumped"] = len(out)
    assert len(out) >= 20


def test_write_summary():
    save(f"{LABEL or 'latest'}.json", SUMMARY) if LABEL else None
    print("\nsummary keys:", sorted(SUMMARY))
