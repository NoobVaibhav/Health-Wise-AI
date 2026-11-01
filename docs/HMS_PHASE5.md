# HMS Phase 5: pharmacy and operations (stock control, procurement, operation theatre, blood bank)

## Reused
`MedicineInventory` (batches, expiry, barcode, GST), sales and dispensing, the Phase 2 roles and permissions (`INVENTORY_MANAGER`, `OT_STAFF`, `BLOOD_BANK_STAFF` already existed), `EncounterCharge` and the price list, the MAR (what was given), the audit log.

## A. Pharmacy stock control and procurement
- **Stock history:** `stock_movements` is written by every receipt, dispense, sale, return, adjustment, write-off, recall, ward issue and theatre consumption (signed quantity, balance after, who, why). It is never edited or deleted.
- **Rules:** a recalled or expired batch is never dispensed, sold or issued. A write-off needs an expired or recalled batch and a reason. A returned medicine goes back on the shelf only if it is in date and not recalled.
- **Alerts:** low stock (per medicine, reorder level, default 10), expiring in 60 days, expired, recalled, and store items below their minimum.
- **Ward requests:** a nurse or doctor asks for medicines for an admitted patient; the pharmacy issues from usable stock (earliest expiry first), partly or fully, or rejects with a reason. Requested, issued and given (MAR) stay separate records.
- **Procurement:** store items (`inventory_items`), requisitions, purchase orders, goods receipts. A requisition or order is approved by someone other than its maker. A receipt adds stock once (medicines need batch and a future expiry). A stock count with a difference needs a reason and a second person's approval. Reorder and consumption reports.
- **Permissions (new):** `stock.view`, `stock.manage`, `inventory.manage`, `procure.request`, `procure.order`, `procure.approve`.

## B. Operation theatre
- Tables: `operation_theatres`, `surgeries` (with pre-op, consent, anaesthesia and operation note), `surgery_checklist_items`, `surgery_events`, `surgery_consumables`.
- No overlap in one theatre, for one surgeon, or for one anaesthetist (a person cannot be surgeon of one and anaesthetist of another at the same time). Back-to-back is allowed. An intern cannot be surgeon or anaesthetist.
- To start: a fit pre-op assessment by the anaesthetist, consent for this surgery, the sign-in checklist complete. To move to recovery: time-out complete and an operation note. To complete: sign-out complete, the operation note final (by the surgeon), the anaesthesia record. Consumables reduce the store. Completion creates a pending charge from the price list when a service is chosen and the patient is admitted.
- Permissions (new): `ot.view`, `ot.schedule`, `ot.record`.

## C. Blood bank
- Tables: `blood_donors`, `blood_donations`, `blood_units`, `blood_requests`, `blood_crossmatches`, `blood_issues`, `transfusions`.
- Donor eligibility (age, weight, haemoglobin, interval since the last donation, deferral) is checked before blood is taken. Units stay in QUARANTINE until a second person records a CLEARED screening; REACTIVE discards them and defers the donor. Units expire by component shelf life.
- Matching: same component, ABO/Rh rule computed, then the technician's cross-match is recorded; only a compatible match reserves the unit. Issue by one person, verification by another. Return only within the window with the cold chain kept, otherwise discarded.
- Transfusion: started by a nurse after checking patient and unit, checked at the bedside by a second person, ended with volume and any reaction (a reaction stops it). Interns cannot request blood; the group must match the patient's record, and only an emergency may go without a known group (then O negative red cells, AB plasma).
- Permissions (new): `bloodbank.manage`, `bloodbank.request`, `transfusion.give`.

## How people get access
Staff for stores, theatre and the blood bank are existing Employee logins given the extra role (Admin, People, roles). The sidebar shows the pages their permissions open (`/api/auth/me` now returns `permissions`).

## Database changes (idempotent, at start-up)
New tables listed above plus `suppliers`, `inventory_items`, `stock_movements`, `medicine_returns`, `medicine_requests`(+items), `requisitions`(+items), `purchase_orders`(+items), `goods_receipts`(+items), `stock_counts`. `medicine_inventory` gains generic_name, reorder_level, supplier_id, recalled, recall_reason.

## Limits (to be honest about)
- The blood bank limits (age, weight, haemoglobin, intervals, shelf life, the 30-minute return window) and the ABO/Rh rule are common defaults. The blood bank medical officer must review them for the hospital. Platelets use the Rh rule only (ABO-identical is preferred).
- Not built: pharmacy transfers between stores, barcode-scanner hardware, medicine-batch counts in the screen (the API supports them), return of a prescribed medicine does not reopen the prescription, and no billing beyond pending charges (Phase 6).
- A returned sale line is matched by sale line id; the bill output now carries it.
- Compliance and clinical limits must be reviewed by qualified professionals.
