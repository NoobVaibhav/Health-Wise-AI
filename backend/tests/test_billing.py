"""Medical-shop billing: barcode lookup, stock delivery, selling (earliest expiry first), bills and prescriptions."""
from datetime import date, timedelta

PH = "/api/pharmacy"


def receive(client, world, **kw):
    body = {"medicine_name": "Paracetamol 500 mg tablet", "quantity": 10, "unit_price": 2.0, "gst_percent": 12, **kw}
    r = client.post(f"{PH}/inventory/receive", headers=world.pharmacy, json=body)
    assert r.status_code == 201, r.text
    return r.json()


def stock(client, world):
    return {(i["batch_number"]): i["quantity"] for i in client.get(f"{PH}/inventory", headers=world.pharmacy).json()}


def test_receive_stock_makes_and_reuses_barcodes(client, world):
    first = receive(client, world, batch_number="B1", expiry_date=str(date.today() + timedelta(days=200)))
    assert first["barcode"] and first["barcode"].startswith("HW")             # made automatically
    second = receive(client, world, batch_number="B2", expiry_date=str(date.today() + timedelta(days=400)))
    assert second["barcode"] == first["barcode"]                               # same medicine, same barcode
    again = receive(client, world, batch_number="B1", expiry_date=str(date.today() + timedelta(days=200)), quantity=5)
    assert again["id"] == first["id"] and again["quantity"] == 15              # same batch: quantity added
    scanned = receive(client, world, medicine_name="Cetirizine 10 mg tablet", barcode="8901234567890", batch_number="C1")
    assert scanned["barcode"] == "8901234567890"                               # a barcode printed on the pack is kept


def test_barcode_lookup(client, world):
    item = receive(client, world, batch_number="B1", expiry_date=str(date.today() + timedelta(days=100)))
    found = client.get(f"{PH}/inventory/lookup", params={"code": item["barcode"]}, headers=world.pharmacy)
    assert found.status_code == 200
    assert found.json()["medicine_name"] == "Paracetamol 500 mg tablet" and found.json()["available"] == 10
    assert client.get(f"{PH}/inventory/lookup", params={"code": "000"}, headers=world.pharmacy).status_code == 404


def test_sale_takes_earliest_expiry_first_and_makes_the_bill(client, world):
    soon = receive(client, world, batch_number="OLD", quantity=4, expiry_date=str(date.today() + timedelta(days=30)))
    receive(client, world, batch_number="NEW", quantity=10, expiry_date=str(date.today() + timedelta(days=300)))
    receive(client, world, batch_number="GONE", quantity=50, expiry_date=str(date.today() - timedelta(days=5)))  # expired

    sale = client.post(f"{PH}/sales", headers=world.pharmacy, json={
        "customer_name": "Ramesh", "payment_method": "UPI", "discount": 1,
        "items": [{"barcode": soon["barcode"], "quantity": 6}]})
    assert sale.status_code == 201, sale.text
    bill = sale.json()
    assert bill["bill_number"] == f"BILL-{date.today():%Y%m%d}-0001"
    assert [(i["batch_number"], i["quantity"]) for i in bill["items"]] == [("OLD", 4), ("NEW", 2)]   # spills to next batch
    assert bill["subtotal"] == 12.0 and bill["tax"] == 1.44 and bill["discount"] == 1.0 and bill["total"] == 12.44
    assert stock(client, world) == {"OLD": 0, "NEW": 8, "GONE": 50}                                  # expired batch untouched

    second = client.post(f"{PH}/sales", headers=world.pharmacy, json={"items": [{"barcode": soon["barcode"], "quantity": 1}]})
    assert second.json()["bill_number"].endswith("-0002")

    listed = client.get(f"{PH}/sales", headers=world.pharmacy).json()
    assert [b["bill_number"][-4:] for b in listed] == ["0002", "0001"]
    assert client.get(f"{PH}/sales", params={"q": "ramesh"}, headers=world.pharmacy).json()[0]["customer_name"] == "Ramesh"
    assert client.get(f"{PH}/sales/{bill['id']}", headers=world.pharmacy).json()["total"] == 12.44
    summary = client.get(f"{PH}/sales/summary", headers=world.pharmacy).json()
    assert summary["bills_today"] == 2 and summary["by_method"]["UPI"] == 12.44
    assert summary["top_medicines"][0] == {"medicine_name": "Paracetamol 500 mg tablet", "quantity": 7}


def test_sale_is_refused_and_changes_nothing_when_it_cannot_be_done(client, world):
    item = receive(client, world, batch_number="B1", quantity=5, expiry_date=str(date.today() + timedelta(days=100)))
    other = receive(client, world, medicine_name="Cetirizine 10 mg tablet", batch_number="C1", quantity=3)

    too_many = client.post(f"{PH}/sales", headers=world.pharmacy, json={"items": [
        {"barcode": other["barcode"], "quantity": 1}, {"barcode": item["barcode"], "quantity": 6}]})
    assert too_many.status_code == 409 and "Not enough stock" in too_many.json()["detail"]
    assert stock(client, world) == {"B1": 5, "C1": 3}                      # the first line was NOT taken either
    assert client.get(f"{PH}/sales", headers=world.pharmacy).json() == []

    expired = receive(client, world, medicine_name="Old Syrup", batch_number="X", quantity=5, expiry_date=str(date.today() - timedelta(days=1)))
    r = client.post(f"{PH}/sales", headers=world.pharmacy, json={"items": [{"barcode": expired["barcode"], "quantity": 1}]})
    assert r.status_code == 409 and "expired" in r.json()["detail"]

    no_price = receive(client, world, medicine_name="No Price Tablet", batch_number="P", unit_price=None)
    r = client.post(f"{PH}/sales", headers=world.pharmacy, json={"items": [{"barcode": no_price["barcode"], "quantity": 1}]})
    assert r.status_code == 422

    r = client.post(f"{PH}/sales", headers=world.pharmacy, json={"discount": 999, "items": [{"barcode": item["barcode"], "quantity": 1}]})
    assert r.status_code == 422                                              # discount bigger than the bill
    assert client.post(f"{PH}/sales", headers=world.pharmacy, json={"items": [{"barcode": "nope", "quantity": 1}]}).status_code == 404


def test_selling_a_prescription_also_records_dispensing_once(client, world):
    item = receive(client, world, batch_number="B1", quantity=30, expiry_date=str(date.today() + timedelta(days=100)))
    rx = client.post("/api/prescriptions", headers=world.doctor, json={
        "patient_id": world.patient_id, "items": [{"medicine_name": "Paracetamol 500 mg tablet", "dosage": "1 tablet",
                                                   "frequency": "Twice daily", "duration": "5 days", "quantity": 10}]}).json()
    rx_item = rx["items"][0]["id"]

    wrong = client.post(f"{PH}/sales", headers=world.pharmacy, json={"prescription_id": rx["id"], "items": [
        {"barcode": receive(client, world, medicine_name="Cetirizine 10 mg tablet", batch_number="C")["barcode"],
         "quantity": 1, "prescription_item_id": rx_item}]})
    assert wrong.status_code == 409                                         # not the prescribed medicine

    ok = client.post(f"{PH}/sales", headers=world.pharmacy, json={"prescription_id": rx["id"], "items": [
        {"barcode": item["barcode"], "quantity": 10, "prescription_item_id": rx_item}]})
    assert ok.status_code == 201, ok.text
    assert ok.json()["prescription_code"] == f"RX-{rx['id']:05d}"
    assert stock(client, world)["B1"] == 20                                  # taken once, not twice
    done = client.get(f"/api/prescriptions/{rx['id']}", headers=world.pharmacy).json()
    assert done["status"] == "DISPENSED" and done["items"][0]["dispensed_quantity"] == 10
    # the finished prescription cannot be billed again
    again = client.post(f"{PH}/sales", headers=world.pharmacy, json={"prescription_id": rx["id"], "items": [
        {"barcode": item["barcode"], "quantity": 1, "prescription_item_id": rx_item}]})
    assert again.status_code == 409


def test_only_pharmacy_staff_can_use_billing(client, world):
    for who in (world.doctor, world.employee, world.patient, world.admin):
        assert client.get(f"{PH}/sales", headers=who).status_code == 403
        assert client.get(f"{PH}/inventory/lookup", params={"code": "x"}, headers=who).status_code == 403
        assert client.post(f"{PH}/sales", headers=who, json={"items": [{"barcode": "x", "quantity": 1}]}).status_code == 403
        assert client.post(f"{PH}/inventory/receive", headers=who, json={"medicine_name": "Abc", "quantity": 1}).status_code == 403


def test_bill_for_prescription_medicine_after_it_was_given(client, world):
    item = receive(client, world, batch_number="B1", quantity=30, expiry_date=str(date.today() + timedelta(days=100)))
    rx = client.post("/api/prescriptions", headers=world.doctor, json={
        "patient_id": world.patient_id, "items": [{"medicine_name": "Paracetamol 500 mg tablet", "dosage": "1 tablet",
                                                   "frequency": "Twice daily", "duration": "5 days", "quantity": 10}]}).json()
    rx_item = rx["items"][0]["id"]
    url = f"{PH}/prescriptions/{rx['id']}"

    # nothing given yet -> nothing to bill
    assert client.get(f"{url}/bill-preview", headers=world.pharmacy).json()["lines"] == []
    assert client.post(f"{url}/bill", headers=world.pharmacy, json={}).status_code == 409

    # the pharmacy gives 4 tablets (the old Give-medicine screen)
    given = client.post(f"{PH}/dispense", headers=world.pharmacy, json={"prescription_item_id": rx_item, "quantity": 4})
    assert given.status_code == 200, given.text
    preview = client.get(f"{url}/bill-preview", headers=world.pharmacy).json()
    assert [(l["quantity"], l["amount"]) for l in preview["lines"]] == [(4, 8.96)] and preview["total"] == 8.96   # 4 x 2.00 + 12% GST

    bill = client.post(f"{url}/bill", headers=world.pharmacy, json={"payment_method": "UPI", "discount": 0.96})
    assert bill.status_code == 201, bill.text
    assert bill.json()["total"] == 8.0 and bill.json()["customer_name"] == "Rahul Patil"
    assert bill.json()["prescription_code"] == f"RX-{rx['id']:05d}"
    assert stock(client, world)["B1"] == 26                        # stock was taken when given, not again when billed

    # billed once: nothing is left to bill until more is given
    assert client.get(f"{url}/bill-preview", headers=world.pharmacy).json()["lines"] == []
    assert client.get(f"{url}/bill-preview", headers=world.pharmacy).json()["bills"][0]["bill_number"] == bill.json()["bill_number"]
    assert client.post(f"{url}/bill", headers=world.pharmacy, json={}).status_code == 409

    # the rest is given later and billed separately
    client.post(f"{PH}/dispense", headers=world.pharmacy, json={"prescription_item_id": rx_item, "quantity": 6})
    second = client.post(f"{url}/bill", headers=world.pharmacy, json={})
    assert second.status_code == 201 and second.json()["items"][0]["quantity"] == 6
    assert stock(client, world)["B1"] == 20
    assert client.get(f"{PH}/sales", headers=world.pharmacy).json()[0]["prescription_code"] == f"RX-{rx['id']:05d}"

    # only pharmacy staff can bill
    for who in (world.doctor, world.employee, world.patient):
        assert client.get(f"{url}/bill-preview", headers=who).status_code == 403
        assert client.post(f"{url}/bill", headers=who, json={}).status_code == 403


def test_prescription_bill_needs_a_price(client, world):
    receive(client, world, batch_number="B1", quantity=30, unit_price=None)
    rx = client.post("/api/prescriptions", headers=world.doctor, json={
        "patient_id": world.patient_id, "items": [{"medicine_name": "Paracetamol 500 mg tablet", "dosage": "1 tablet",
                                                   "frequency": "Once daily", "duration": "2 days", "quantity": 2}]}).json()
    client.post(f"{PH}/dispense", headers=world.pharmacy, json={"prescription_item_id": rx["items"][0]["id"], "quantity": 2})
    preview = client.get(f"{PH}/prescriptions/{rx['id']}/bill-preview", headers=world.pharmacy).json()
    assert preview["lines"] == [] and "No price" in preview["problems"][0]
    assert client.post(f"{PH}/prescriptions/{rx['id']}/bill", headers=world.pharmacy, json={}).status_code == 422
