"""Cross-check of the main calculation modules against independently computed answers (not copied from the code under test)."""
import random
from datetime import date, timedelta

import pytest

from app.services import report_trends
from app.services.safety_filter import is_safe, is_safe_for_doctor
from tests.test_patient_assistant import add_report, report

PH = "/api/pharmacy"


# ------------------------------------------------------------------ unit conversions (textbook factors, computed by hand)
@pytest.mark.parametrize("name,value,src,dst,expected", [
    ("Glucose", 100, "mg/dL", "mmol/L", 5.55), ("Glucose", 5.55, "mmol/L", "mg/dL", 100.0),
    ("Creatinine", 1.0, "mg/dL", "umol/L", 88.4), ("Creatinine", 88.4, "µmol/L", "mg/dL", 1.0),
    ("Hemoglobin", 14.0, "g/dL", "g/L", 140.0), ("Hemoglobin", 140, "g/L", "g/dL", 14.0),
    ("Total Cholesterol", 200, "mg/dL", "mmol/L", 5.17), ("LDL", 100, "mg/dL", "mmol/L", 2.59),
    ("Triglycerides", 150, "mg/dL", "mmol/L", 1.69),
])
def test_validated_unit_conversions_match_reference_values(name, value, src, dst, expected):
    got = report_trends.convert(name, value, src, dst)
    assert got is not None and abs(got - expected) / expected < 0.01, (name, got, expected)


@pytest.mark.parametrize("name,src,dst", [("Vitamin D", "ng/mL", "nmol/L"), ("TSH", "uIU/mL", "mIU/L"), ("HbA1c", "%", "mmol/mol"), ("Glucose", "mg/dL", "g/L"), ("Hemoglobin", "g/dL", "mg/dL")])
def test_conversions_without_a_validated_factor_are_refused(name, src, dst):
    assert report_trends.convert(name, 10, src, dst) is None


# ------------------------------------------------------------------ trend verdicts
def point(value, low=None, high=None, unit="mg/dL", status=None, known=True):
    if status is None:
        status = "UNKNOWN" if low is None and high is None else "BELOW_RANGE" if low is not None and value < low else "ABOVE_RANGE" if high is not None and value > high else "WITHIN_RANGE"
    text = None if low is None and high is None else (f"{low:g} - {high:g}" if low is not None and high is not None else f"< {high:g}" if high is not None else f"> {low:g}")
    return {"report_id": 1, "report_name": "r", "date": "2026-01-01", "date_known": known, "value": value, "unit": unit, "status": status, "reference_text": text, "reference_low": low, "reference_high": high, "review_status": "REVIEWED"}


@pytest.mark.parametrize("prev,latest,assessment,status", [
    (point(7.2, 4, 5.6, "%"), point(5.4, 4, 5.6, "%"), "IMPROVED", "RETURNED_WITHIN_RANGE"),
    (point(14, 13, 17, "g/dL"), point(12.1, 13, 17, "g/dL"), "WORSENED", "NEWLY_OUTSIDE_RANGE"),
    (point(8.0, 4, 5.6, "%"), point(6.5, 4, 5.6, "%"), "IMPROVED", "STILL_OUTSIDE_RANGE"),
    (point(6.0, 4, 5.6, "%"), point(7.5, 4, 5.6, "%"), "WORSENED", "STILL_OUTSIDE_RANGE"),
    (point(20, 30, 100, "ng/mL"), point(10, 30, 100, "ng/mL"), "WORSENED", "STILL_OUTSIDE_RANGE"),     # further below the range
    (point(10, 30, 100, "ng/mL"), point(20, 30, 100, "ng/mL"), "IMPROVED", "STILL_OUTSIDE_RANGE"),    # closer to the range
    (point(14, 13, 17, "g/dL"), point(14, 13, 17, "g/dL"), "STABLE", "WITHIN_RANGE"),
    (point(17, 40), point(55), "NEUTRAL", "NO_REFERENCE_RANGE"),
])
def test_trend_verdicts_follow_the_printed_range(prev, latest, assessment, status):
    prev, latest = dict(prev), dict(latest)
    if status == "NO_REFERENCE_RANGE":
        prev = point(17); latest = point(27)                      # no printed range at all: never "improved" or "worsened"
    row = report_trends.compare_points("X", prev, latest)
    assert (row["assessment"], row["status"]) == (assessment, status), row


def test_trend_arithmetic_and_unit_rules():
    row = report_trends.compare_points("Glucose", point(180, 70, 100, "mg/dL"), point(7.0, 3.9, 5.6, "mmol/L"))
    assert row["converted"] and abs(row["change"] - (7.0 - 180 / 18.016)) < 0.01 and row["status"] == "STILL_OUTSIDE_RANGE" and row["assessment"] == "IMPROVED"   # 180 mg/dL is 9.99 mmol/L
    different = report_trends.compare_points("Vitamin D", point(20, unit="ng/mL"), point(50, unit="nmol/L"))
    assert different["status"] == "NOT_COMPARABLE" and different["change"] is None
    pct = report_trends.compare_points("Hemoglobin", point(10, 13, 17, "g/dL"), point(12, 13, 17, "g/dL"))
    assert pct["change"] == 2 and pct["change_percent"] == 20.0


# ------------------------------------------------------------------ safety filter wording
@pytest.mark.parametrize("text", ["You have diabetes.", "This is a diagnosis of anaemia.", "You should stop taking your medicine.", "Take 500 mg daily.", "This cures it.", "You are 100% healthy.", "Start taking tablets today."])
def test_patient_facing_safety_filter_rejects_diagnosis_and_dose_language(text):
    assert not is_safe(text)


@pytest.mark.parametrize("text", ["The result is higher than the printed range. Please discuss it with your doctor.", "Haemoglobin carries oxygen in the blood.", "Your report was reviewed on 5 October."])
def test_patient_facing_safety_filter_allows_plain_statements(text):
    assert is_safe(text)


@pytest.mark.parametrize("text", ["Take 5 mg of it.", "You have cancer.", "This will become normal."])
def test_doctor_facing_filter_still_blocks_doses_and_verdicts(text):
    assert not is_safe_for_doctor(text)


# ------------------------------------------------------------------ billing and stock: randomised invariants
def test_random_sales_keep_money_and_stock_consistent(client, world):
    rng = random.Random(7)
    stock = {}
    for i, name in enumerate(["Para 500", "Cetri 10", "Amox 250", "Pan 40"]):
        price, gst, qty = round(rng.uniform(1, 40), 2), rng.choice([0, 5, 12, 18]), rng.randint(20, 80)
        item = client.post(f"{PH}/inventory/receive", headers=world.pharmacy, json={"medicine_name": name, "batch_number": f"B{i}", "quantity": qty, "unit_price": price, "gst_percent": gst, "expiry_date": str(date.today() + timedelta(days=200))}).json()
        stock[item["barcode"]] = {"qty": qty, "price": price, "gst": gst}
    for _ in range(25):
        lines = [{"barcode": bc, "quantity": rng.randint(1, 6)} for bc in rng.sample(list(stock), rng.randint(1, 3))]
        bill_amount = sum(round(l["quantity"] * stock[l["barcode"]]["price"], 2) + round(round(l["quantity"] * stock[l["barcode"]]["price"], 2) * stock[l["barcode"]]["gst"] / 100, 2) for l in lines)
        discount = round(min(rng.uniform(0, 5), bill_amount), 2)
        r = client.post(f"{PH}/sales", headers=world.pharmacy, json={"items": lines, "discount": discount})
        if any(stock[l["barcode"]]["qty"] < l["quantity"] for l in lines):
            assert r.status_code == 409                                            # overselling is refused, nothing changes
            continue
        assert r.status_code == 201, r.text
        sub = tax = 0.0
        for l in lines:
            s = stock[l["barcode"]]
            net = round(l["quantity"] * s["price"], 2)
            sub += net
            tax += round(net * s["gst"] / 100, 2)
            s["qty"] -= l["quantity"]
        bill = r.json()
        assert abs(bill["subtotal"] - round(sub, 2)) < 0.011 and abs(bill["tax"] - round(tax, 2)) < 0.011
        assert abs(bill["total"] - round(sub + tax - discount, 2)) < 0.011
    left = {i["barcode"]: i["quantity"] for i in client.get(f"{PH}/inventory", headers=world.pharmacy).json()}
    assert left == {bc: s["qty"] for bc, s in stock.items()}                        # stock equals what was received minus what was sold


def test_billing_refuses_negative_quantity_discount_over_bill_and_expired_stock(client, world):
    item = client.post(f"{PH}/inventory/receive", headers=world.pharmacy, json={"medicine_name": "Para 500", "batch_number": "B", "quantity": 10, "unit_price": 10, "gst_percent": 0, "expiry_date": str(date.today() + timedelta(days=100))}).json()
    old = client.post(f"{PH}/inventory/receive", headers=world.pharmacy, json={"medicine_name": "Old drug", "batch_number": "X", "quantity": 10, "unit_price": 10, "expiry_date": str(date.today() - timedelta(days=1))}).json()
    assert client.post(f"{PH}/sales", headers=world.pharmacy, json={"items": [{"barcode": item["barcode"], "quantity": -2}]}).status_code == 422
    assert client.post(f"{PH}/sales", headers=world.pharmacy, json={"items": [{"barcode": item["barcode"], "quantity": 1}], "discount": 11}).status_code == 422     # more than the bill
    assert client.post(f"{PH}/sales", headers=world.pharmacy, json={"items": [{"barcode": old["barcode"], "quantity": 1}]}).status_code == 409                      # expired
    assert client.post(f"{PH}/sales", headers=world.pharmacy, json={"items": [{"barcode": item["barcode"], "quantity": 11}]}).status_code == 409                     # not enough stock
    assert {i["barcode"]: i["quantity"] for i in client.get(f"{PH}/inventory", headers=world.pharmacy).json()}[item["barcode"]] == 10


# ------------------------------------------------------------------ medicine matching
def test_medicine_names_are_matched_across_strengths_and_allergies_are_flagged(client, world):
    from app.services.medication_history import base_name
    assert base_name("Tab. Metformin 500 mg") == base_name("Metformin 1000 mg") == "metformin"
    assert base_name("Syrup Cofsil 5 ml") == "cofsil" and base_name("Inj. Insulin 10 IU") == "insulin"
    client.put(f"/api/health-history/patient/{world.patient_id}", headers=world.doctor, json={"allergies": [{"name": "Penicillin", "kind": "DRUG", "reaction": "rash"}]})
    for medicine in ("Penicillin V 250 mg", "Amoxicillin 500 mg"):
        client.post("/api/prescriptions", headers=world.doctor, json={"patient_id": world.patient_id, "clinical_indication": "x", "items": [{"medicine_name": medicine, "dosage": "1", "frequency": "daily", "duration": "5 days", "quantity": 5}]})
    meds = client.get(f"/api/doctor/patients/{world.patient_id}/medication-history", headers=world.doctor).json()
    flagged = {m["name"] for m in meds["medicines"] if m["allergy_match"]}
    assert flagged == {"Penicillin V 250 mg"}              # by name only: a related antibiotic is not guessed (and the text says it is for clinical review)
    assert "For clinical review" in next(m["allergy_match"] for m in meds["medicines"] if m["allergy_match"])


# ------------------------------------------------------------------ clinical summary thresholds
def test_summary_marks_a_value_far_outside_the_range_as_urgent_and_a_mild_one_not(client, world):
    add_report(client, world, "mild.txt", report("01/10/2026", "Hemoglobin 12.5 g/dL 13.0 - 17.0"))
    mild = client.get(f"/api/doctor/patients/{world.patient_id}/clinical-summary", headers=world.doctor).json()
    assert not mild["urgent_notice"]
    add_report(client, world, "severe.txt", report("02/10/2026", "Hemoglobin 3.0 g/dL 13.0 - 17.0"))
    severe = client.get(f"/api/doctor/patients/{world.patient_id}/clinical-summary", headers=world.doctor).json()
    assert severe["urgent_notice"] and "immediate professional assessment" in severe["urgent_notice"]
