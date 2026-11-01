"""Phase 5A: stock history, recall and expiry rules, returns, alerts, ward medicine requests, procurement (requisition -> purchase order -> goods receipt) and stock counts."""
from datetime import date, timedelta

import pytest

from tests.conftest import PASSWORD, login

PH = "/api/pharmacy"
FUTURE = str(date.today() + timedelta(days=200))


@pytest.fixture()
def sw(client, world):
    def person(path, email, name, roles=None, **extra):
        res = client.post(f"/api/admin/{path}", headers=world.admin, json={"email": email, "full_name": name, "password": PASSWORD, **extra})
        assert res.status_code == 201, res.text
        if roles:
            assert client.put(f"/api/access/users/{res.json()['user']['id']}/roles", headers=world.admin, json={"roles": roles}).status_code == 200
        return login(client, email)

    world.inv = person("employees", "inv1@hospital.example.com", "Ila Inventory", ["INVENTORY_MANAGER"], designation="Store manager")
    world.inv2 = person("employees", "inv2@hospital.example.com", "Ivan Inventory", ["INVENTORY_MANAGER"], designation="Store manager")
    world.nurse = person("nurses", "nurse@hospital.example.com", "Nina Nurse", designation="Staff nurse")
    return world


def receive(client, w, name="Paracetamol 500 mg", qty=50, batch="B1", expiry=FUTURE, **kw):
    r = client.post(f"{PH}/inventory/receive", headers=w.pharmacy, json={"medicine_name": name, "batch_number": batch, "quantity": qty, "unit_price": 2.0, "gst_percent": 12, "expiry_date": expiry, **kw})
    assert r.status_code == 201, r.text
    return r.json()


def sell(client, w, barcode, qty):
    return client.post(f"{PH}/sales", headers=w.pharmacy, json={"items": [{"barcode": barcode, "quantity": qty}]})


def moves(client, w, medicine_id):
    return client.get(f"/api/stock/movements?medicine_id={medicine_id}", headers=w.pharmacy).json()


# ------------------------------------------------------------------ stock history
def test_every_stock_change_leaves_a_movement_with_the_balance(client, sw):
    item = receive(client, sw)
    assert sell(client, sw, item["barcode"], 5).status_code == 201
    client.put(f"{PH}/inventory/{item['id']}", headers=sw.pharmacy, json={"quantity": 40})
    rows = moves(client, sw, item["id"])
    assert [(m["kind"], m["quantity"], m["balance_after"]) for m in reversed(rows)] == [("RECEIPT", 50, 50), ("SALE", -5, 45), ("ADJUST", -5, 40)]
    assert rows[1]["reference_type"] == "sale" and rows[1]["reference_id"] is not None
    for who in (sw.patient, sw.doctor, sw.employee, sw.nurse):
        assert client.get("/api/stock/movements", headers=who).status_code == 403


def test_a_prescription_dispense_is_in_the_history(client, sw):
    item = receive(client, sw, name="Tab. Cefixime")
    rx = client.post("/api/prescriptions", headers=sw.doctor, json={"patient_id": sw.patient_id, "items": [{"medicine_name": "Tab. Cefixime", "dosage": "1", "frequency": "Twice a day", "duration": "3 days", "quantity": 6}]}).json()
    assert client.post(f"{PH}/dispense", headers=sw.pharmacy, json={"prescription_item_id": rx["items"][0]["id"], "quantity": 6}).status_code == 200
    assert [m["kind"] for m in moves(client, sw, item["id"])] == ["DISPENSE", "RECEIPT"]


# ------------------------------------------------------------------ recall and expiry
def test_a_recalled_batch_is_never_sold_or_dispensed_and_can_be_written_off(client, sw):
    item = receive(client, sw, name="Tab. Recallable", batch="R1")
    assert client.post(f"/api/stock/batches/{item['id']}/recall", headers=sw.doctor, json={"reason": "Manufacturer recall"}).status_code == 403
    assert client.post(f"/api/stock/batches/{item['id']}/recall", headers=sw.pharmacy, json={"reason": "x"}).status_code == 422
    assert client.post(f"/api/stock/batches/{item['id']}/recall", headers=sw.pharmacy, json={"reason": "Manufacturer recall"}).status_code == 200
    assert client.post(f"/api/stock/batches/{item['id']}/recall", headers=sw.pharmacy, json={"reason": "again"}).status_code == 409
    assert sell(client, sw, item["barcode"], 1).status_code == 409
    rx = client.post("/api/prescriptions", headers=sw.doctor, json={"patient_id": sw.patient_id, "items": [{"medicine_name": "Tab. Recallable", "dosage": "1", "frequency": "Once a day", "duration": "2 days", "quantity": 2}]}).json()
    assert client.post(f"{PH}/dispense", headers=sw.pharmacy, json={"prescription_item_id": rx["items"][0]["id"], "quantity": 2}).status_code == 409
    assert [r["id"] for r in client.get("/api/stock/alerts", headers=sw.pharmacy).json()["recalled"]] == [item["id"]]
    assert client.post(f"/api/stock/batches/{item['id']}/write-off", headers=sw.pharmacy, json={"reason": "Destroyed as per recall"}).status_code == 200
    assert [(m["kind"], m["quantity"]) for m in moves(client, sw, item["id"])][:2] == [("WRITE_OFF", -50), ("RECALL", 0)]
    assert client.post(f"/api/stock/batches/{item['id']}/write-off", headers=sw.pharmacy, json={"reason": "again"}).status_code == 409


def test_only_expired_or_recalled_stock_can_be_written_off(client, sw):
    item = receive(client, sw, name="Tab. Fine")
    assert client.post(f"/api/stock/batches/{item['id']}/write-off", headers=sw.pharmacy, json={"reason": "no reason really"}).status_code == 409


# ------------------------------------------------------------------ returns
def test_a_return_goes_back_on_the_shelf_only_if_in_date_and_not_recalled(client, sw):
    item = receive(client, sw, name="Tab. Returnable", qty=20)
    sale = sell(client, sw, item["barcode"], 6).json()
    line = sale["items"][0]["id"]
    assert client.post("/api/stock/returns", headers=sw.patient, json={"sale_item_id": line, "quantity": 1, "reason": "wrong item"}).status_code == 403
    assert client.post("/api/stock/returns", headers=sw.pharmacy, json={"sale_item_id": line, "quantity": 7, "reason": "wrong item"}).status_code == 409
    ok = client.post("/api/stock/returns", headers=sw.pharmacy, json={"sale_item_id": line, "quantity": 2, "reason": "Patient changed mind"}).json()
    assert ok["restocked"] is True
    assert {i["id"]: i["quantity"] for i in client.get(f"{PH}/inventory", headers=sw.pharmacy).json()}[item["id"]] == 16
    client.post(f"/api/stock/batches/{item['id']}/recall", headers=sw.pharmacy, json={"reason": "Recalled later"})
    later = client.post("/api/stock/returns", headers=sw.pharmacy, json={"sale_item_id": line, "quantity": 4, "reason": "Patient changed mind"}).json()
    assert later["restocked"] is False
    assert {i["id"]: i["quantity"] for i in client.get(f"{PH}/inventory", headers=sw.pharmacy).json()}[item["id"]] == 16
    assert client.post("/api/stock/returns", headers=sw.pharmacy, json={"sale_item_id": line, "quantity": 1, "reason": "too many"}).status_code == 409   # all 6 are back


# ------------------------------------------------------------------ alerts
def test_alerts_for_low_stock_expiry_and_reorder(client, sw):
    receive(client, sw, name="Tab. Scarce", qty=3, batch="S1")
    receive(client, sw, name="Tab. Soon", qty=100, batch="E1", expiry=str(date.today() + timedelta(days=20)))
    low = client.post("/api/procurement/items", headers=sw.inv, json={"code": "GLV-01", "name": "Gloves", "category": "CONSUMABLE", "min_level": 50, "reorder_quantity": 500}).json()
    a = client.get("/api/stock/alerts", headers=sw.pharmacy).json()
    assert [x["medicine_name"] for x in a["low_stock"]] == ["Tab. Scarce"] and a["expiring_soon"][0]["medicine_name"] == "Tab. Soon"
    assert a["items_to_reorder"][0]["code"] == "GLV-01" and low["code"] == "GLV-01"


# ------------------------------------------------------------------ ward medicine requests
def ward_patient(client, sw):
    ward = client.post("/api/ipd/wards", headers=sw.admin, json={"name": "Ward Z", "ward_type": "GENERAL"}).json()
    bed = client.post(f"/api/ipd/wards/{ward['id']}/beds", headers=sw.admin, json={"code": "Z1"}).json()
    res = client.post("/api/ipd/admissions", headers=sw.doctor, json={"patient_id": sw.patient_id, "diagnosis": "Pneumonia", "bed_id": bed["id"]})
    assert res.status_code == 201, res.text
    return res.json()["id"]


def test_ward_requests_are_issued_by_the_pharmacy_from_usable_stock_only(client, sw):
    adm = ward_patient(client, sw)
    good = receive(client, sw, name="Inj. Ceftriaxone", qty=10, batch="G1")
    receive(client, sw, name="Inj. Ceftriaxone", qty=10, batch="OLD", expiry=str(date.today() + timedelta(days=1)))
    body = {"admission_id": adm, "items": [{"medicine_name": "Inj. Ceftriaxone", "quantity": 15}]}
    assert client.post("/api/stock/requests", headers=sw.patient, json=body).status_code == 403
    assert client.post("/api/stock/requests", headers=sw.other_doctor, json=body).status_code == 403          # not this doctor's patient
    req = client.post("/api/stock/requests", headers=sw.nurse, json=body)
    assert req.status_code == 201, req.text
    rid, line = req.json()["id"], req.json()["items"][0]["id"]
    assert client.post(f"/api/stock/requests/{rid}/issue", headers=sw.nurse, json={"issues": {str(line): 5}}).status_code == 403
    assert client.post(f"/api/stock/requests/{rid}/issue", headers=sw.pharmacy, json={"issues": {str(line): 99}}).status_code == 422
    partial = client.post(f"/api/stock/requests/{rid}/issue", headers=sw.pharmacy, json={"issues": {str(line): 8}}).json()
    assert partial["status"] == "PARTIAL" and partial["items"][0]["issued_quantity"] == 8
    assert client.post(f"/api/stock/requests/{rid}/reject", headers=sw.pharmacy, json={"reason": "no stock"}).status_code == 409           # already partly issued
    assert client.post(f"/api/stock/requests/{rid}/issue", headers=sw.pharmacy, json={"issues": {str(line): 7}}).json()["status"] == "ISSUED"
    assert client.post(f"/api/stock/requests/{rid}/issue", headers=sw.pharmacy, json={"issues": {str(line): 1}}).status_code == 409           # already complete
    assert [m["kind"] for m in moves(client, sw, good["id"])][0] == "ISSUE"
    mine = client.get("/api/stock/requests", headers=sw.nurse).json()
    assert [r["id"] for r in mine] == [rid]


def test_a_request_can_be_rejected_or_cancelled_only_while_pending(client, sw):
    adm = ward_patient(client, sw)
    body = {"admission_id": adm, "items": [{"medicine_name": "Inj. Unknown", "quantity": 2}]}
    a = client.post("/api/stock/requests", headers=sw.nurse, json=body).json()["id"]
    assert client.post(f"/api/stock/requests/{a}/reject", headers=sw.pharmacy, json={"reason": "Not stocked here"}).json()["status"] == "REJECTED"
    b = client.post("/api/stock/requests", headers=sw.nurse, json=body).json()["id"]
    assert client.post(f"/api/stock/requests/{b}/cancel", headers=sw.doctor).status_code == 404
    assert client.post(f"/api/stock/requests/{b}/cancel", headers=sw.nurse).json()["status"] == "CANCELLED"
    assert client.post(f"/api/stock/requests/{b}/cancel", headers=sw.nurse).status_code == 409


# ------------------------------------------------------------------ procurement
def supplier(client, w):
    return client.post("/api/stock/suppliers", headers=w.inv, json={"name": "MediSupply Pvt Ltd", "phone": "9876543210", "gstin": "27ABCDE1234F1Z5"}).json()["id"]


def test_requisition_to_purchase_order_to_goods_receipt_updates_stock_once(client, sw):
    glove = client.post("/api/procurement/items", headers=sw.inv, json={"code": "GLV-02", "name": "Surgical gloves", "category": "CONSUMABLE", "min_level": 10}).json()["id"]
    sid = supplier(client, sw)
    assert client.post("/api/stock/suppliers", headers=sw.inv, json={"name": "MediSupply Pvt Ltd"}).status_code == 409
    for who in (sw.patient, sw.employee):
        assert client.post("/api/procurement/requisitions", headers=who, json={"items": [{"inventory_item_id": glove, "quantity": 5}]}).status_code == 403
    assert client.post("/api/procurement/requisitions", headers=sw.nurse, json={"items": [{"inventory_item_id": glove, "medicine_name": "x", "quantity": 5}]}).status_code == 422
    req = client.post("/api/procurement/requisitions", headers=sw.nurse, json={"items": [{"inventory_item_id": glove, "quantity": 100}, {"medicine_name": "Tab. New Medicine", "quantity": 40}]}).json()
    assert client.post(f"/api/procurement/requisitions/{req['id']}/decide", headers=sw.nurse, json={"approve": True}).status_code == 403
    assert client.post(f"/api/procurement/requisitions/{req['id']}/decide", headers=sw.inv, json={"approve": False}).status_code == 422
    assert client.post(f"/api/procurement/requisitions/{req['id']}/decide", headers=sw.inv, json={"approve": True}).json()["status"] == "APPROVED"
    assert client.post(f"/api/procurement/requisitions/{req['id']}/decide", headers=sw.inv, json={"approve": True}).status_code == 409
    lines = [{"inventory_item_id": glove, "quantity": 100, "unit_cost": 4.5}, {"medicine_name": "Tab. New Medicine", "quantity": 40, "unit_cost": 1.2}]
    po = client.post("/api/procurement/orders", headers=sw.inv, json={"supplier_id": sid, "requisition_id": req["id"], "items": lines})
    assert po.status_code == 201, po.text
    po = po.json()
    assert client.post("/api/procurement/orders", headers=sw.inv, json={"supplier_id": sid, "requisition_id": req["id"], "items": lines}).status_code == 409     # the requisition is used
    assert client.post(f"/api/procurement/orders/{po['id']}/receive", headers=sw.inv, json={"items": [{"order_item_id": po["items"][0]["id"], "quantity": 10}]}).status_code == 409   # not approved yet
    assert client.post(f"/api/procurement/orders/{po['id']}/approve", headers=sw.inv).status_code == 409                       # not by its maker
    assert client.post(f"/api/procurement/orders/{po['id']}/approve", headers=sw.inv2).json()["status"] == "APPROVED"
    g, m = po["items"][0]["id"], po["items"][1]["id"]
    assert client.post(f"/api/procurement/orders/{po['id']}/receive", headers=sw.inv, json={"items": [{"order_item_id": g, "quantity": 101}]}).status_code == 409
    assert client.post(f"/api/procurement/orders/{po['id']}/receive", headers=sw.inv, json={"items": [{"order_item_id": m, "quantity": 10, "batch_number": "N1"}]}).status_code == 422     # medicine needs an expiry date
    past = str(date.today() - timedelta(days=1))
    assert client.post(f"/api/procurement/orders/{po['id']}/receive", headers=sw.inv, json={"items": [{"order_item_id": m, "quantity": 10, "batch_number": "N1", "expiry_date": past}]}).status_code == 422
    first = client.post(f"/api/procurement/orders/{po['id']}/receive", headers=sw.inv, json={"items": [{"order_item_id": g, "quantity": 60}, {"order_item_id": m, "quantity": 40, "batch_number": "N1", "expiry_date": FUTURE, "selling_price": 3.0, "gst_percent": 12}]})
    assert first.status_code == 201, first.text
    assert first.json()["order"]["status"] == "PARTIAL"
    second = client.post(f"/api/procurement/orders/{po['id']}/receive", headers=sw.inv, json={"items": [{"order_item_id": g, "quantity": 40}]})
    assert second.json()["order"]["status"] == "RECEIVED"
    assert client.post(f"/api/procurement/orders/{po['id']}/receive", headers=sw.inv, json={"items": [{"order_item_id": g, "quantity": 1}]}).status_code == 409
    assert client.post(f"/api/procurement/orders/{po['id']}/cancel", headers=sw.inv2).status_code == 409
    assert next(i for i in client.get("/api/procurement/items", headers=sw.inv).json() if i["id"] == glove)["quantity"] == 100
    medicine = next(i for i in client.get(f"{PH}/inventory", headers=sw.pharmacy).json() if i["medicine_name"] == "Tab. New Medicine")
    assert medicine["quantity"] == 40 and medicine["batch_number"] == "N1"
    assert moves(client, sw, medicine["id"])[0]["reference_type"] == "grn"


# ------------------------------------------------------------------ counts
def test_a_count_difference_needs_a_reason_and_a_second_person(client, sw):
    item = receive(client, sw, name="Tab. Countable", qty=30)
    assert client.post("/api/procurement/counts", headers=sw.pharmacy, json={"medicine_inventory_id": item["id"], "counted_quantity": 27}).status_code == 422
    c = client.post("/api/procurement/counts", headers=sw.pharmacy, json={"medicine_inventory_id": item["id"], "counted_quantity": 27, "reason": "3 broken strips"}).json()
    assert c["status"] == "PENDING"
    assert {i["id"]: i["quantity"] for i in client.get(f"{PH}/inventory", headers=sw.pharmacy).json()}[item["id"]] == 30        # nothing changed yet
    assert client.post(f"/api/procurement/counts/{c['id']}/decide", headers=sw.pharmacy, json={"approve": True}).status_code == 409   # not by the counter
    assert client.post(f"/api/procurement/counts/{c['id']}/decide", headers=sw.inv, json={"approve": True}).json()["status"] == "APPLIED"
    assert {i["id"]: i["quantity"] for i in client.get(f"{PH}/inventory", headers=sw.pharmacy).json()}[item["id"]] == 27
    assert moves(client, sw, item["id"])[0]["kind"] == "ADJUST" and moves(client, sw, item["id"])[0]["quantity"] == -3
    same = client.post("/api/procurement/counts", headers=sw.pharmacy, json={"medicine_inventory_id": item["id"], "counted_quantity": 27}).json()
    assert same["status"] == "APPLIED"                                                                   # no difference: nothing to approve
    assert client.post("/api/procurement/counts", headers=sw.pharmacy, json={"counted_quantity": 5}).status_code == 422
