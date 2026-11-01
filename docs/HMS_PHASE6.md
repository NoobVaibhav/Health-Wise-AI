# HMS Phase 6: finance (billing, payments, insurance claims, reports)

## Reused
`EncounterCharge` (pending charges from consultations and surgeries), the price list (`ServiceCatalog` with GST), `PatientInsurance`, the hospital profile (name, address, GST number on bills), the pharmacy `Sale` bills (they stay separate and appear in the revenue report), the audit log, and the Phase 2 roles `BILLING_EXECUTIVE`, `ACCOUNTANT`, `INSURANCE_EXECUTIVE`.

## What is new
- **Charges:** "collect charges" turns finished lab tests, approved scans and bed days into pending charges, once each, at the price in the price list. Anything with no price is listed as "no price in the list" and no charge is invented. (Only items that belong to a visit or an admission are collected.)
- **Invoices:** a draft (lines from pending charges, price-list services and packages) is made final once. A final invoice is never edited: it is cancelled with a reason (by someone with approval rights, and only when no money is held) and a new one is made. Price, GST and description are copied onto each line.
- **Payments and receipts:** cash, UPI, card, bank transfer (a reference is required for the last three) and "from advance". Never more than the balance. Each payment has a receipt number and a printable receipt.
- **Advances:** money paid in advance, used against invoices, the unused part refunded.
- **Refunds:** requested by one person, approved by a different one; never more than was paid (or than the advance has left); counted as paid out only when approved.
- **Discounts:** always with a reason. A discount above a share of the bill (setting `discount_approval_percent`, default 10) needs a second person before the invoice can be made final.
- **Packages:** sold as one line at the package price.
- **Insurance claims:** a claim for a final invoice with a valid, active policy: pre-authorisation (asked, approved or refused), the documents the insurer needs (setting `claim_documents`), submission only when the documents are in, the insurer's decision (full, partial with a reason, or rejected), and settlements. The patient then pays only what the insurer did not approve; settlements are payments on the same invoice (method INSURANCE). Every step is kept in the claim history.
- **Reports:** daily cash (by method and by person, refunds paid, advances and insurer settlements shown apart), outstanding balances with ageing, revenue by kind of service with GST and discounts, pharmacy counter sales, and claims by status.
- **Patient:** "My bills" with printable bills and receipts.

## Permissions (new)
`billing.view`, `billing.create`, `billing.collect`, `billing.approve`, `billing.report`, `claims.manage`. Front desk (Receptionist) can view, make invoices and take payments; Billing Executive the same; Accountant views, approves and sees the reports; Insurance Executive handles claims. Billing never sees clinical notes.

## Database changes (idempotent)
New tables: `billing_packages`, `invoices`, `invoice_lines`, `deposits`, `payments`, `refunds`, `insurance_claims`, `claim_documents`, `claim_events`. `encounter_charges` gains `source_type` and `source_id`.

## Limits
- Not built: online payment gateways, GST return filing, e-invoicing, TPA portal integration, credit notes as a separate document (a cancelled invoice and a refund do that job), and corporate or credit accounts.
- A charge that came from a prescription-only lab order (no visit) is not collected automatically; add the test from the price list.
- GST is shown per line as a percentage from the price list; whether it is correct for a service is the hospital's decision.
- Compliance (GST rules, insurance regulations) must be reviewed by qualified professionals.
