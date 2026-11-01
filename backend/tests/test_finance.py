"""Phase 6: finance. Charges, invoices (draft then final), payments and receipts, advances, refunds, discounts, packages, insurance claims and the reports."""
from datetime import date, timedelta

import pytest

from app.database.connection import SessionLocal
from app.database.models import EncounterCharge, LabTestOrder
from tests.conftest import PASSWORD, login

PH = "/api/pharmacy"


@pytest.fixture()
def fw(client, world):
    def person(path, email, name, roles=None, **extra):
        res = client.post(f"/api/admin/{path}", headers=world.admin, json={"email": email, "full_name": name, "password": PASSWORD, **extra})
        assert res.status_code == 201, res.text
        if roles:
            assert client.put(f"/api/access/users/{res.json()['user']['id']}/roles", headers=world.admin, json={"roles": roles}).status_code == 200
        return login(client, email)

    world.b1 = person("employees", "b1@hospital.example.com", "Bina Billing", ["BILLING_EXECUTIVE"], designation="Billing")
    world.b2 = person("employees", "b2@hospital.example.com", "Bhanu Billing", ["BILLING_EXECUTIVE"], designation="Billing")
    world.acc = person("employees", "acc@hospital.example.com", "Asha Accounts", ["ACCOUNTANT"], designation="Accountant")
    world.ins = person("employees", "ins@hospital.example.com", "Indu Insurance", ["INSURANCE_EXECUTIVE"], designation="TPA desk")
    svc = lambda code, name, cat, price, gst=0: client.post("/api/hospital/services", headers=world.admin, json={"code": code, "name": name, "category": cat, "price": price, "gst_percent": gst}).json()["id"]
    world.s_consult = svc("CONS-1", "General consultation", "CONSULTATION", 500, 0)
    world.s_lab = svc("LAB-1", "Serum Electrolytes", "LAB", 400, 5)
    world.s_xray = svc("RAD-1", "Chest X-ray", "RADIOLOGY", 300, 12)
    world.s_bed = svc("BED-G", "General ward bed per day", "BED", 1000, 0)
    enc = client.post("/api/opd/walk-in", headers=world.employee, json={"patient_id": world.patient_id, "doctor_id": world.doctor_id})
    assert enc.status_code == 201, enc.text
    world.enc = enc.json()["encounter_id"]
    return world


def charge(w, description="Consultation", amount=500.0, gst=0.0):
    with SessionLocal() as db:
        c = EncounterCharge(encounter_id=w.enc, patient_id=w.patient_id, description=description, amount=amount, gst_percent=gst, status="PENDING")
        db.add(c)
        db.commit()
        return c.id


def draft(client, w, who=None, **over):
    body = {"patient_id": w.patient_id, "charge_ids": [], "services": [], "package_ids": [], **over}
    r = client.post("/api/finance/invoices", headers=who or w.b1, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def final(client, w, amount=500.0, gst=0.0, who=None):
    inv = draft(client, w, charge_ids=[charge(w, "Consultation", amount, gst)])
    r = client.post(f"/api/finance/invoices/{inv['id']}/finalise", headers=who or w.b1)
    assert r.status_code == 200, r.text
    return r.json()


def pay(client, w, inv_id, amount, method="CASH", who=None, **extra):
    return client.post(f"/api/finance/invoices/{inv_id}/pay", headers=who or w.b1, json={"amount": amount, "method": method, **extra})


# ------------------------------------------------------------------ access
def test_who_may_see_billing(client, fw):
    for who in (fw.patient, fw.doctor, fw.pharmacy, fw.other_doctor):
        assert client.get("/api/finance/invoices", headers=who).status_code == 403
        assert client.post("/api/finance/invoices", headers=who, json={"patient_id": fw.patient_id, "services": [{"service_id": fw.s_consult}]}).status_code == 403
    assert client.get("/api/finance/invoices", headers=fw.b1).status_code == 200
    assert client.get("/api/finance/reports/daily-cash", headers=fw.b1).status_code == 403                     # reports are for the accountant
    assert client.get("/api/finance/reports/daily-cash", headers=fw.acc).status_code == 200
    me = client.get("/api/auth/me", headers=fw.b1).json()
    assert "billing.collect" in me["permissions"] and "billing.approve" not in me["permissions"]


# ------------------------------------------------------------------ invoices
def test_invoice_totals_use_the_price_list_and_gst_and_are_copied_to_the_line(client, fw):
    inv = draft(client, fw, services=[{"service_id": fw.s_lab, "quantity": 2}, {"service_id": fw.s_xray}])
    assert [(l["description"], l["amount"], l["tax"]) for l in inv["lines"]] == [("Serum Electrolytes", 800.0, 40.0), ("Chest X-ray", 300.0, 36.0)]
    assert (inv["subtotal"], inv["tax"], inv["total"], inv["status"], inv["number"]) == (1100.0, 76.0, 1176.0, "DRAFT", None)
    client.put(f"/api/hospital/services/{fw.s_lab}", headers=fw.admin, json={"price": 999})
    final = client.post(f"/api/finance/invoices/{inv['id']}/finalise", headers=fw.b1).json()
    assert final["status"] == "FINAL" and final["number"].startswith("INV-") and final["total"] == 1176.0                     # the later price change did not touch it
    assert client.post(f"/api/finance/invoices/{inv['id']}/finalise", headers=fw.b1).status_code == 409
    assert client.post(f"/api/finance/invoices/{inv['id']}/lines", headers=fw.b1, json={"services": [{"service_id": fw.s_lab}]}).status_code == 409   # final is never edited
    assert client.delete(f"/api/finance/invoices/{inv['id']}/lines/{inv['lines'][0]['id']}", headers=fw.b1).status_code == 409


def test_an_invoice_needs_lines_and_valid_references(client, fw):
    assert client.post("/api/finance/invoices", headers=fw.b1, json={"patient_id": fw.patient_id}).status_code == 422
    assert client.post("/api/finance/invoices", headers=fw.b1, json={"patient_id": 99999, "services": [{"service_id": fw.s_lab}]}).status_code == 404
    assert client.post("/api/finance/invoices", headers=fw.b1, json={"patient_id": fw.patient_id, "services": [{"service_id": 99999}]}).status_code == 422
    assert client.post("/api/finance/invoices", headers=fw.b1, json={"patient_id": fw.patient_id, "services": [{"service_id": fw.s_lab, "quantity": 0}]}).status_code == 422
    assert client.post("/api/finance/invoices", headers=fw.b1, json={"patient_id": fw.patient_id, "charge_ids": [99999]}).status_code == 422
    assert client.post("/api/finance/invoices", headers=fw.b1, json={"patient_id": fw.patient_id, "package_ids": [99999]}).status_code == 422


def test_a_pending_charge_is_billed_once_and_comes_back_when_the_invoice_is_cancelled(client, fw):
    cid = charge(fw)
    assert [c["id"] for c in client.get(f"/api/finance/patients/{fw.patient_id}/overview", headers=fw.b1).json()["pending_charges"]] == [cid]
    one = draft(client, fw, charge_ids=[cid])
    assert client.post("/api/finance/invoices", headers=fw.b1, json={"patient_id": fw.patient_id, "charge_ids": [cid]}).status_code == 409        # already on a draft
    assert client.get(f"/api/finance/patients/{fw.patient_id}/overview", headers=fw.b1).json()["pending_charges"] == []
    client.post(f"/api/finance/invoices/{one['id']}/finalise", headers=fw.b1)
    with SessionLocal() as db:
        assert db.get(EncounterCharge, cid).status == "INVOICED"
    assert client.post(f"/api/finance/invoices/{one['id']}/cancel", headers=fw.b1, json={"reason": "Wrong patient bill"}).status_code == 403      # cancelling a final invoice is approved by another role
    assert client.post(f"/api/finance/invoices/{one['id']}/cancel", headers=fw.acc, json={"reason": "x"}).status_code == 422
    assert client.post(f"/api/finance/invoices/{one['id']}/cancel", headers=fw.acc, json={"reason": "Wrong patient bill"}).json()["status"] == "CANCELLED"
    assert [c["id"] for c in client.get(f"/api/finance/patients/{fw.patient_id}/overview", headers=fw.b1).json()["pending_charges"]] == [cid]
    again = draft(client, fw, charge_ids=[cid])
    assert again["total"] == 500.0


def test_other_patients_charges_cannot_be_billed(client, fw):
    other = client.post("/api/patients", headers=fw.employee, json={"email": "other@example.com", "full_name": "Other Person", "password": PASSWORD, "gender": "male", "date_of_birth": "1990-01-01", "phone": "8888888888"}).json()["patient"]["id"]
    cid = charge(fw)
    assert client.post("/api/finance/invoices", headers=fw.b1, json={"patient_id": other, "charge_ids": [cid]}).status_code == 422


def test_collecting_charges_from_finished_tests_scans_and_bed_days(client, fw):
    with SessionLocal() as db:
        db.add(LabTestOrder(encounter_id=fw.enc, patient_id=fw.patient_id, doctor_id=fw.doctor_id, test_name="Serum Electrolytes", status="COMPLETED", test_id=None))
        db.add(LabTestOrder(encounter_id=fw.enc, patient_id=fw.patient_id, doctor_id=fw.doctor_id, test_name="Rare Marker Panel", status="COMPLETED"))
        db.add(LabTestOrder(encounter_id=fw.enc, patient_id=fw.patient_id, doctor_id=fw.doctor_id, test_name="Serum Electrolytes", status="ORDERED"))
        db.commit()
    first = client.post(f"/api/finance/patients/{fw.patient_id}/collect-charges", headers=fw.b1).json()
    assert first["added"] == ["Serum Electrolytes"] and first["no_price_in_list"] == ["Rare Marker Panel"]                      # no price, no invented charge
    assert client.post(f"/api/finance/patients/{fw.patient_id}/collect-charges", headers=fw.b1).json()["added"] == []             # once each
    pending = client.get(f"/api/finance/patients/{fw.patient_id}/overview", headers=fw.b1).json()["pending_charges"]
    assert [(c["description"], c["amount"]) for c in pending] == [("Lab: Serum Electrolytes", 400.0)]
    assert client.post(f"/api/finance/patients/{fw.patient_id}/collect-charges", headers=fw.doctor).status_code == 403


def test_packages_are_one_line_at_the_package_price(client, fw):
    pkg = client.post("/api/finance/packages", headers=fw.admin, json={"name": "Normal delivery", "price": 25000, "gst_percent": 0, "inclusions": "3 days stay, delivery, baby care"})
    assert pkg.status_code == 201
    assert client.post("/api/finance/packages", headers=fw.b1, json={"name": "Hack", "price": 1}).status_code == 403
    assert client.post("/api/finance/packages", headers=fw.admin, json={"name": "Normal delivery", "price": 1}).status_code == 409
    inv = draft(client, fw, package_ids=[pkg.json()["id"]])
    assert inv["lines"][0]["description"] == "Package: Normal delivery" and inv["total"] == 25000.0


# ------------------------------------------------------------------ discounts
def test_a_discount_needs_a_reason_and_a_large_one_needs_a_second_person(client, fw):
    inv = draft(client, fw, charge_ids=[charge(fw, amount=1000)])
    d = f"/api/finance/invoices/{inv['id']}/discount"
    assert client.post(d, headers=fw.b1, json={"amount": 50}).status_code == 422                                              # no reason
    assert client.post(d, headers=fw.b1, json={"amount": 5000, "reason": "Staff relative"}).status_code == 422                   # more than the bill
    small = client.post(d, headers=fw.b1, json={"amount": 100, "reason": "Senior citizen"}).json()                             # exactly 10%
    assert small["total"] == 900.0 and small["needs_discount_approval"] is False
    big = client.post(d, headers=fw.b1, json={"amount": 300, "reason": "Financial hardship"}).json()
    assert big["total"] == 700.0 and big["needs_discount_approval"] is True
    assert client.post(f"/api/finance/invoices/{inv['id']}/finalise", headers=fw.b1).status_code == 409
    assert client.post(f"/api/finance/invoices/{inv['id']}/discount/approve", headers=fw.b2).status_code == 403                   # no approve permission
    assert client.post(f"/api/finance/invoices/{inv['id']}/discount/approve", headers=fw.acc).json()["needs_discount_approval"] is False
    assert client.post(f"/api/finance/invoices/{inv['id']}/finalise", headers=fw.b1).json()["total"] == 700.0
    client.post(d, headers=fw.b1, json={"amount": 0})
    own = draft(client, fw, who=fw.acc, charge_ids=[charge(fw, amount=1000)])
    client.post(f"/api/finance/invoices/{own['id']}/discount", headers=fw.acc, json={"amount": 500, "reason": "Charity"})
    assert client.post(f"/api/finance/invoices/{own['id']}/discount/approve", headers=fw.acc).status_code == 409               # not your own


# ------------------------------------------------------------------ payments
def test_payments_never_exceed_the_balance_and_get_a_receipt(client, fw):
    inv = final(client, fw, amount=1000, gst=0)
    assert pay(client, fw, inv["id"], 2000).status_code == 409
    assert pay(client, fw, inv["id"], -5).status_code == 422
    assert pay(client, fw, inv["id"], 100, "BITCOIN").status_code == 422
    assert pay(client, fw, inv["id"], 100, "UPI").status_code == 422                                                           # a reference is needed
    assert pay(client, fw, inv["id"], 100, who=fw.doctor).status_code == 403
    first = pay(client, fw, inv["id"], 400).json()
    assert first["invoice"]["balance"] == 600.0 and first["receipt_number"].startswith("REC-")
    second = pay(client, fw, inv["id"], 600, "UPI", reference="UPI123").json()
    assert second["invoice"]["balance"] == 0.0 and second["invoice"]["paid"] == 1000.0
    assert pay(client, fw, inv["id"], 1).status_code == 409
    rec = client.get(f"/api/finance/payments/{second['payment_id']}/receipt", headers=fw.b2).json()
    assert rec["amount"] == 600.0 and rec["balance_after"] == 0.0 and rec["method"] == "UPI" and rec["patient_name"] == "Rahul Patil"
    mine = client.get(f"/api/finance/payments/{second['payment_id']}/receipt", headers=fw.patient)
    assert mine.status_code == 200
    assert client.get(f"/api/finance/payments/{second['payment_id']}/receipt", headers=fw.doctor).status_code == 403
    assert pay(client, fw, draft(client, fw, charge_ids=[charge(fw)])["id"], 10).status_code == 409                              # a draft takes no money


def test_the_patient_sees_only_their_own_final_bills(client, fw):
    inv = final(client, fw)
    draft(client, fw, charge_ids=[charge(fw)])
    mine = client.get("/api/finance/my-invoices", headers=fw.patient).json()
    assert [i["id"] for i in mine] == [inv["id"]]
    assert client.get("/api/finance/my-invoices", headers=fw.b1).status_code == 403
    assert client.get("/api/finance/my-invoices", headers=fw.doctor).status_code == 403


def test_cancelling_a_paid_invoice_needs_the_money_back_first(client, fw):
    inv = final(client, fw, amount=1000)
    pay(client, fw, inv["id"], 1000)
    assert client.post(f"/api/finance/invoices/{inv['id']}/cancel", headers=fw.acc, json={"reason": "Billed in error"}).status_code == 409


# ------------------------------------------------------------------ advances and refunds
def test_advance_is_used_against_a_bill_and_the_unused_part_is_refunded(client, fw):
    dep = client.post("/api/finance/deposits", headers=fw.b1, json={"patient_id": fw.patient_id, "amount": 5000, "method": "CASH"}).json()
    assert dep["receipt_number"].startswith("DEP-") and dep["balance"] == 5000.0
    assert client.post("/api/finance/deposits", headers=fw.b1, json={"patient_id": fw.patient_id, "amount": 100, "method": "ADVANCE"}).status_code == 422
    assert client.post("/api/finance/deposits", headers=fw.b1, json={"patient_id": fw.patient_id, "amount": 100, "method": "CARD"}).status_code == 422
    inv = final(client, fw, amount=3000)
    assert pay(client, fw, inv["id"], 3000, "ADVANCE").status_code == 422                                                        # which advance?
    assert pay(client, fw, inv["id"], 3000, "ADVANCE", deposit_id=99999).status_code == 422
    assert pay(client, fw, inv["id"], 3000, "ADVANCE", deposit_id=dep["id"]).json()["invoice"]["balance"] == 0.0
    ov = client.get(f"/api/finance/patients/{fw.patient_id}/overview", headers=fw.b1).json()
    assert ov["deposits"][0]["balance"] == 2000.0
    over = client.post("/api/finance/refunds", headers=fw.b1, json={"deposit_id": dep["id"], "amount": 2500, "method": "CASH", "reason": "Patient left"})
    assert over.status_code == 409
    r = client.post("/api/finance/refunds", headers=fw.b1, json={"deposit_id": dep["id"], "amount": 2000, "method": "CASH", "reason": "Unused advance returned"}).json()
    assert client.post(f"/api/finance/refunds/{r['id']}/decide", headers=fw.b1, json={"approve": True}).status_code == 403
    assert client.post(f"/api/finance/refunds/{r['id']}/decide", headers=fw.acc, json={"approve": True}).json()["status"] == "APPROVED"
    assert client.get(f"/api/finance/patients/{fw.patient_id}/overview", headers=fw.b1).json()["deposits"][0]["balance"] == 0.0


def test_refund_rules_for_an_invoice(client, fw):
    inv = final(client, fw, amount=1000)
    pay(client, fw, inv["id"], 700)
    body = {"invoice_id": inv["id"], "method": "CASH", "reason": "Service not given"}
    assert client.post("/api/finance/refunds", headers=fw.b1, json={**body, "amount": 800}).status_code == 409                    # more than paid
    assert client.post("/api/finance/refunds", headers=fw.b1, json={**body, "amount": 100, "reason": "x"}).status_code == 422
    assert client.post("/api/finance/refunds", headers=fw.b1, json={"amount": 100, "method": "CASH", "reason": "no target"}).status_code == 422
    assert client.post("/api/finance/refunds", headers=fw.b1, json={**body, "deposit_id": 1, "amount": 100}).status_code == 422
    r = client.post("/api/finance/refunds", headers=fw.b1, json={**body, "amount": 300}).json()
    assert client.post("/api/finance/refunds", headers=fw.b1, json={**body, "amount": 500}).status_code == 409                    # 400 is left, 300 already waits
    assert client.post(f"/api/finance/refunds/{r['id']}/decide", headers=fw.acc, json={"approve": False}).status_code == 422
    assert client.get(f"/api/finance/invoices/{inv['id']}", headers=fw.b1).json()["balance"] == 300.0                               # not paid out yet
    assert client.post(f"/api/finance/refunds/{r['id']}/decide", headers=fw.acc, json={"approve": True}).json()["status"] == "APPROVED"
    after = client.get(f"/api/finance/invoices/{inv['id']}", headers=fw.b1).json()
    assert (after["paid"], after["refunded"], after["balance"]) == (700.0, 300.0, 600.0)
    assert client.post(f"/api/finance/refunds/{r['id']}/decide", headers=fw.acc, json={"approve": True}).status_code == 409
    own = client.post("/api/finance/refunds", headers=fw.acc, json={**body, "amount": 100}).json()
    assert client.post(f"/api/finance/refunds/{own['id']}/decide", headers=fw.acc, json={"approve": True}).status_code == 409                # not your own request


# ------------------------------------------------------------------ insurance claims
def policy(client, w):
    r = client.post(f"/api/patient-registry/{w.patient_id}/insurance", headers=w.employee, json={"insurer_name": "Star Health", "tpa_name": "MediAssist", "policy_number": "POL123", "member_id": "M1"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_the_claim_flow_from_preauth_to_settlement_and_what_the_patient_pays(client, fw):
    pid = policy(client, fw)
    inv = final(client, fw, amount=10000)
    c = client.post("/api/claims", headers=fw.ins, json={"invoice_id": inv["id"], "patient_insurance_id": pid})
    assert c.status_code == 201, c.text
    c = c.json()
    assert c["status"] == "DRAFT" and len(c["documents"]) == 5
    for who in (fw.b1, fw.doctor, fw.patient):
        assert client.post("/api/claims", headers=who, json={"invoice_id": inv["id"], "patient_insurance_id": pid}).status_code == 403
    assert client.post("/api/claims", headers=fw.ins, json={"invoice_id": inv["id"], "patient_insurance_id": pid}).status_code == 409           # one claim per invoice
    cid = f"/api/claims/{c['id']}"
    assert client.post(f"{cid}/preauth", headers=fw.ins, json={"amount": 20000}).status_code == 422
    assert client.post(f"{cid}/preauth", headers=fw.ins, json={"amount": 8000, "reference": "PA-1"}).json()["status"] == "PREAUTH_SENT"
    assert client.post(f"{cid}/preauth/decision", headers=fw.ins, json={"approved_amount": 9000}).status_code == 422
    assert client.post(f"{cid}/preauth/decision", headers=fw.ins, json={"approved_amount": 8000}).json()["status"] == "PREAUTH_APPROVED"
    assert client.post(f"{cid}/submit", headers=fw.ins, json={"amount": 8000}).status_code == 409                                              # documents missing
    for d in c["documents"]:
        client.post(f"{cid}/documents/{d['id']}", headers=fw.ins, json={"received": True})
    assert client.post(f"{cid}/submit", headers=fw.ins, json={"amount": 20000}).status_code == 422
    assert client.post(f"{cid}/submit", headers=fw.ins, json={"amount": 8000}).json()["status"] == "SUBMITTED"
    assert client.post(f"{cid}/decision", headers=fw.ins, json={"approved_amount": 9000}).status_code == 422
    assert client.post(f"{cid}/decision", headers=fw.ins, json={"approved_amount": 6000}).status_code == 422                                  # a part needs a reason
    part = client.post(f"{cid}/decision", headers=fw.ins, json={"approved_amount": 6000, "reason": "Room rent capped by policy"}).json()
    assert part["status"] == "PARTIAL" and part["rejected_amount"] == 2000.0 and part["patient_payable"] == 4000.0
    inv_now = client.get(f"/api/finance/invoices/{inv['id']}", headers=fw.b1).json()
    assert (inv_now["insurer_approved"], inv_now["patient_payable"], inv_now["claim_status"]) == (6000.0, 4000.0, "PARTIAL")
    assert pay(client, fw, inv["id"], 4500).status_code == 409                                                                                 # the patient pays 4000 at most
    assert pay(client, fw, inv["id"], 4000).status_code == 201
    assert client.post(f"{cid}/settle", headers=fw.ins, json={"amount": 7000, "reference": "UTR1"}).status_code == 422
    assert client.post(f"{cid}/settle", headers=fw.ins, json={"amount": 2000, "reference": "UTR1"}).json()["status"] == "PARTIAL"
    done = client.post(f"{cid}/settle", headers=fw.ins, json={"amount": 4000, "reference": "UTR2"}).json()
    assert done["status"] == "SETTLED" and done["settled_amount"] == 6000.0
    final_inv = client.get(f"/api/finance/invoices/{inv['id']}", headers=fw.b1).json()
    assert final_inv["balance"] == 0.0 and sorted(p["method"] for p in final_inv["payments"]) == ["CASH", "INSURANCE", "INSURANCE"]
    assert [e["text"] for e in done["events"]][0].startswith("Claim made with Star Health")
    assert client.post(f"{cid}/settle", headers=fw.ins, json={"amount": 1, "reference": "UTR3"}).status_code == 409
    assert client.post(f"/api/finance/invoices/{inv['id']}/cancel", headers=fw.acc, json={"reason": "Billed in error"}).status_code == 409
    summary = client.get("/api/claims/summary", headers=fw.ins).json()
    assert summary == [{"status": "SETTLED", "count": 1, "claimed": 8000.0, "approved": 6000.0, "rejected": 2000.0, "settled": 6000.0}]


def test_claim_rules(client, fw):
    pid = policy(client, fw)
    draft_inv = draft(client, fw, charge_ids=[charge(fw)])
    assert client.post("/api/claims", headers=fw.ins, json={"invoice_id": draft_inv["id"], "patient_insurance_id": pid}).status_code == 409        # not final
    inv = final(client, fw)
    assert client.post("/api/claims", headers=fw.ins, json={"invoice_id": inv["id"], "patient_insurance_id": 99999}).status_code == 422
    assert client.post("/api/claims", headers=fw.ins, json={"invoice_id": 99999, "patient_insurance_id": pid}).status_code == 404
    c = client.post("/api/claims", headers=fw.ins, json={"invoice_id": inv["id"], "patient_insurance_id": pid}).json()
    assert client.post(f"/api/claims/{c['id']}/decision", headers=fw.ins, json={"approved_amount": 100}).status_code == 409                    # not submitted
    assert client.post(f"/api/claims/{c['id']}/settle", headers=fw.ins, json={"amount": 100, "reference": "X1"}).status_code == 409
    assert client.post(f"/api/claims/{c['id']}/preauth/decision", headers=fw.ins, json={"approved_amount": 0, "reason": "x"}).status_code == 409
    client.post(f"/api/claims/{c['id']}/preauth", headers=fw.ins, json={"amount": 100})
    assert client.post(f"/api/claims/{c['id']}/preauth/decision", headers=fw.ins, json={"approved_amount": 0}).status_code == 422
    assert client.post(f"/api/claims/{c['id']}/preauth/decision", headers=fw.ins, json={"approved_amount": 0, "reason": "Waiting period"}).json()["status"] == "REJECTED"
    assert client.get("/api/claims", headers=fw.b1).status_code == 200 and client.get("/api/claims", headers=fw.patient).status_code == 403
    assert client.post(f"/api/claims/{c['id']}/documents/99999", headers=fw.ins, json={"received": True}).status_code == 404


# ------------------------------------------------------------------ reports
def test_daily_cash_outstanding_and_revenue_reports(client, fw):
    a = final(client, fw, amount=1000)
    b = final(client, fw, amount=2000, gst=18)
    pay(client, fw, a["id"], 1000, who=fw.b1)
    pay(client, fw, b["id"], 1000, "UPI", who=fw.b2, reference="U9")
    dep = client.post("/api/finance/deposits", headers=fw.b2, json={"patient_id": fw.patient_id, "amount": 500, "method": "CASH"}).json()
    r = client.post("/api/finance/refunds", headers=fw.b1, json={"invoice_id": a["id"], "amount": 200, "method": "CASH", "reason": "Overcharged"}).json()
    client.post(f"/api/finance/refunds/{r['id']}/decide", headers=fw.acc, json={"approve": True})
    cash = client.get("/api/finance/reports/daily-cash", headers=fw.acc).json()
    assert cash["by_method"] == {"CASH": 1500.0, "UPI": 1000.0} and cash["by_user"] == {"Bina Billing": 1000.0, "Bhanu Billing": 1500.0}
    assert (cash["collected"], cash["refunds_paid"], cash["net"], cash["invoices_final"]) == (2500.0, 200.0, 2300.0, 2)
    yesterday = client.get(f"/api/finance/reports/daily-cash?day={date.today() - timedelta(days=1)}", headers=fw.acc).json()
    assert yesterday["collected"] == 0.0
    out = client.get("/api/finance/reports/outstanding", headers=fw.acc).json()
    assert out["total_outstanding"] == 1360.0 + 200.0 and out["aging"]["0-30"] == 1560.0                                                      # a: 200 owed after the refund, b: 2360 - 1000
    assert {i["number"]: i["balance"] for i in out["invoices"]} == {a["number"]: 200.0, b["number"]: 1360.0}
    rev = client.get("/api/finance/reports/revenue", headers=fw.acc).json()
    assert rev["by_category"][0]["category"] == "OTHER" and rev["by_category"][0]["amount"] == 3000.0 and rev["by_category"][0]["tax"] == 360.0
    assert client.get("/api/finance/reports/revenue?from_day=2026-01-01&to_day=2024-01-01", headers=fw.acc).status_code == 422
    assert client.get("/api/finance/reports/revenue?from_day=2020-01-01&to_day=2026-12-31", headers=fw.acc).status_code == 422
    assert client.get("/api/finance/reports/daily-cash?day=not-a-date", headers=fw.acc).status_code == 422
    assert dep["balance"] == 500.0


def test_invoice_numbers_have_no_gaps_even_when_drafts_are_thrown_away(client, fw):
    a = draft(client, fw, charge_ids=[charge(fw)])
    b = draft(client, fw, charge_ids=[charge(fw)])
    thrown = draft(client, fw, charge_ids=[charge(fw)])
    client.post(f"/api/finance/invoices/{thrown['id']}/cancel", headers=fw.b1, json={"reason": "Made by mistake"})
    first = client.post(f"/api/finance/invoices/{b['id']}/finalise", headers=fw.b1).json()
    second = client.post(f"/api/finance/invoices/{a['id']}/finalise", headers=fw.b1).json()
    year = date.today().year
    assert (first["number"], second["number"]) == (f"INV-{year}-00001", f"INV-{year}-00002")
