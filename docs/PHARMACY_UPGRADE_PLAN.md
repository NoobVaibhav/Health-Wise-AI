# Smart Pharmacy ERP: inspection report and safe implementation plan

Status: **Phase 1 (inspection + baseline) complete. No application code has been changed for the upgrade yet.**

## 1. Baseline (recorded before any change)

| Check | Result |
|---|---|
| Backend: `pytest -q` in `backend/` | **125 passed**, 1 warning, in 66.75 s (run 2026-10-15, before any upgrade change) |
| Frontend: `npm run build` in `frontend/` | **built successfully** (`vite build`, 21 s; only the usual "chunks larger than 500 kB" notice) |
| Git state | Branch `fix/extractor-no-range-and-report-date`. The billing work (barcode, Sell & Bill, bills, prescription billing) is **not yet committed**; commit it before starting Phase 2 so the baseline can be restored. |

## 2. What exists today (verified by reading the code)

**Stack (kept as is):** FastAPI + SQLAlchemy 2 (SQLite for development, PostgreSQL supported via `DATABASE_URL`),
Pydantic v2, JWT + bcrypt, React 18 + Vite + Tailwind 4 + Recharts, pytest (95 test functions, 125 test cases).

**Pharmacy code:**

| Area | Files |
|---|---|
| Routers | `routers/pharmacy.py` (dashboard, prescription search, dispense, history, inventory CRUD), `routers/billing.py` (barcode lookup, receive stock, sales, bills, prescription bill) |
| Services | `services/billing_service.py`, `services/dispensing_service.py`, `services/prescription_service.py`, `services/hospital_catalog.py` |
| Tables | `medicine_inventory` (one row per medicine + batch), `sales`, `sale_items`, `medicine_dispensing`, `prescriptions`, `prescription_items`, `pharmacy_staff`, `audit_logs` |
| Frontend | `pages/pharmacy/*` (Dashboard, Billing, Bills, Dispensing, DispensingHistory, Inventory, Prescriptions), `components/BillView`, `Barcode`, `PrescriptionBill` |
| Access control | One role `PHARMACY` (`core/permissions.py`, `require_roles`). Pharmacy sees prescriptions but not tests, notes of other roles or reports. |

**Rules already enforced on the backend (keep and keep tested):** price/GST from stock, never from the client; earliest
expiry first; expired batches never sold; stock cannot go negative (sale refused, nothing changes); atomic sale
(rollback on any failure); per-day bill numbers; prescription lines tied to dispensing and billed once; partial
dispensing; only pharmacy staff can bill.

## 3. Gaps against the upgrade prompt

| Prompt area | Today | Gap |
|---|---|---|
| Medicine master data (generic, composition, strength, form, HSN, category, min stock, reorder qty, Rx flag) | Only `medicine_name`, barcode, GST on each batch row | **New `medicines` master table**; batches link to it |
| Batch data (purchase date, mfg date, purchase price, MRP, qty received, supplier, invoice ref) | batch no., expiry, qty, selling price, GST | Add the missing batch columns (all nullable, existing rows kept) |
| Suppliers, purchases, supplier payments, purchase returns | none | New tables and workflow |
| Stock ledger (every movement with before/after, reason, user) | none; quantity is changed directly in 4 places | **New `stock_movements`; all quantity changes must go through one service** |
| Payments (mixed, partial) | one `payment_method` string on the sale | New `payments` table (a sale can have several) |
| Returns/refunds | none | New `sale_returns`, `return_items`, adjustment entries, restock rules |
| Customers, credit, loyalty | free-text name/phone on a bill | New `customers`; optional link on sales |
| Expiry/recall | dashboard "expiring in 30 days" list | Dedicated page, quarantine, recall status, configurable periods |
| Reorder suggestions | none | Rule-based, explainable, no auto ordering |
| Analytics / P&L / expenses / cash book | daily sales summary only | New expense + cash-day tables, reports, CSV export |
| Notifications | none | In-app notification table + generators; email/SMS/WhatsApp only with a configured provider |
| Staff sub-roles and permissions | single `PHARMACY` role | Add `pharmacy_role` (Owner, Pharmacist, Cashier, Inventory Manager) and a backend permission map |
| Audit | audit log exists for sales | Extend to adjustments, returns, discounts over the limit, permission changes |
| **Money type** | **`Float` everywhere** | **Move money columns to fixed-point decimals and compute with `Decimal`** |
| **Migrations** | `create_all` + a tiny "add nullable columns" helper; no migration tool | **Introduce Alembic** (details below) |
| Concurrency | read-modify-write on `quantity`, no row locks | Atomic conditional updates + `SELECT ... FOR UPDATE` on PostgreSQL; tests for concurrent sales |
| Invoice PDF | print view only | PDF generation (reportlab is already a dependency) |

## 4. Design decisions (and why)

1. **Extend, do not replace.** `medicine_inventory` stays as the *batch* table (it is already one row per medicine
   batch and is referenced by `sale_items`). A new `medicines` master table is added and each batch gets a nullable
   `medicine_id`. A one-time, idempotent backfill links existing rows by name. Old endpoints keep their behaviour.
2. **One stock service.** All quantity changes (purchase, sale, dispensing, return, adjustment, write-off, transfer,
   recall) go through `stock_service.move(...)`, which updates the batch with a guarded conditional update (so stock
   can never become negative, even with two sales at once) and writes a `stock_movements` row in the same transaction.
   Existing code paths (`create_sale`, `dispense`, `receive_stock`, `PUT /inventory/{id}`) are rewired to it one at a
   time, with the existing 125 tests as the safety net. History is append-only; corrections are reversal entries.
3. **Money as decimals.** Money columns become `Numeric(12, 2)`; all calculation uses `Decimal` with explicit rounding
   (half-up). Existing float values are converted by migration. The API keeps returning numbers, so the current
   frontend and tests continue to work.
4. **Alembic migrations.** Add Alembic, create a *baseline* revision that matches the current schema (existing
   databases are stamped, not recreated), then one revision per phase. `init_db()`/`add_missing_columns()` stay for
   tests and fresh SQLite files until Phase 12. No migration deletes data.
5. **Pharmacy sub-roles stay inside the `PHARMACY` login role.** A `pharmacy_role` column on `pharmacy_staff`
   (Owner/Pharmacist/Cashier/Inventory Manager) plus a permission map checked by a `require_pharmacy_permission(...)`
   dependency. Existing demo pharmacy accounts become **Owner**, so nothing they use today is lost.
6. **Honest analytics.** Gross sales, discounts, returns, net sales, COGS, gross profit and operating profit are
   separate numbers. COGS uses purchase cost recorded on each batch; where a batch has no purchase price the report
   says so and excludes it from profit instead of guessing. Operating profit is shown only when expenses exist for the
   period, with the limitation text beside it.
7. **No fake features.** Camera scanning is not implemented and will not be claimed. Email/SMS/WhatsApp are "not
   configured" until a real provider is set through environment variables; nothing says "sent" without provider
   confirmation. Reorder suggestions are a transparent rule (average daily sales over a window, lead time, minimum
   stock) with the formula shown; they are never auto-ordered.
8. **Privacy.** Pharmacy users keep seeing only prescription data needed for dispensing (not tests, reports or doctor
   notes). Customer records are retail only and are not linked to medical history unless an authorized link is made.

## 5. Risks to manage

- Rewiring stock changes touches code that billing and dispensing both use. Each rewire is its own small step with the
  full suite run after it.
- SQLite cannot alter column types in place. The Decimal migration uses Alembic batch mode (table copy) on SQLite and
  a plain `ALTER` on PostgreSQL. Tested on a copy of the current database first.
- Concurrent-sales tests are only meaningful on PostgreSQL row locking; on SQLite they verify the conditional-update
  guard. Both are tested; the difference is documented.
- The scope is large (12 phases). Each phase ends with a working, tested application and a written report, as the
  prompt requires. A phase does not start while the previous one has a failing test.

## 6. Phase plan

| Phase | Scope | New migrations | Exit test |
|---|---|---|---|
| 1 | Inspection, baseline, this plan | none | baseline recorded (done) |
| 2 | Pharmacy shell: sidebar with all sections, top bar, new dashboard cards and charts fed by one `/pharmacy/analytics/dashboard` endpoint; inventory page filters (name, barcode, manufacturer, supplier, batch, expiry, stock status); medicine master + batch columns; Alembic baseline | `medicines`, batch columns | dashboard numbers equal DB queries; inventory filters |
| 3 | Suppliers, purchases (draft/received/partially paid/paid/cancelled), duplicate-invoice guard, supplier payments, purchase returns; stock service + ledger introduced for purchases | `suppliers`, `purchases`, `purchase_items`, `supplier_payments`, `stock_movements` | duplicate invoice adds stock once; balances |
| 4 | Billing on decimals; `payments` (mixed/partial), discount limit + authorization, invoice PDF, monthly summaries; sale/dispense rewired to the stock service | `payments`, money columns -> Numeric | GST/discount cases, numbering, rollback, concurrent sale |
| 5 | Returns and refunds with adjustment entries and restock eligibility | `sale_returns`, `return_items` | over-return refused, restock rules |
| 6 | Customers (optional), history, credit, loyalty switch | `customers` | walk-in still works |
| 7 | Expiry page, quarantine, recall, write-off, manual adjustments with reasons | batch status/recall columns | expired/recalled blocked in backend |
| 8 | Reports (daily to yearly), P&L with limitations, expenses, cash book, CSV exports | `expenses`, `cash_days` | profit maths on fixtures |
| 9 | Reorder suggestions, notification centre + generators, optional provider hooks | `notifications` | reorder formula |
| 10 | Staff sub-roles, permission map, authorization for sensitive actions, audit extensions | `pharmacy_role`, `permission_overrides` | role matrix tests |
| 11 | Prescription dispensing polish inside the new layout (verification view, availability check, notify-when-ready) | none | no duplicate dispensing/billing |
| 12 | Full regression, docs: setup guide, API docs, ER diagram, user guide, sample invoice and labels, demo data, final report | none | all tests + build |

After every phase I will report: files changed, features finished, migrations applied, tests run (with real results),
remaining problems, and the exact commands to run the app.

## 7. Before Phase 2 starts

1. Commit the current billing work (so there is a clean restore point) and work on a new branch, for example
   `feature/smart-pharmacy-erp`.
2. Confirm the three decisions that change data: moving money columns to decimals, adding Alembic, and
   using `pharmacy_role` inside the existing `PHARMACY` login role.
