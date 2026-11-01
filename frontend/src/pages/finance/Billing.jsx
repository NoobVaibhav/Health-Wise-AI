// Billing: find a patient, collect their pending charges, make an invoice, take payments and advances, print receipts, ask for refunds.
// A final invoice is never edited. A refund and a large discount are approved by a different person. Prices come from the price list only.
import { useState } from "react";
import { ReceiptText } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import useSave from "../../hooks/useSave";
import { useAuth } from "../../context/AuthContext";
import { addInvoiceLines, approveDiscount, cancelInvoice, collectCharges, decideRefund, findBillingPatients, finaliseInvoice, getInvoice, getPackages, getPatientBilling, getReceipt, getRefunds, listServices,
  makeInvoice, payInvoice, removeInvoiceLine, requestRefund, setDiscount, takeDeposit } from "../../services/financeApi";
import { getHospitalProfile } from "../../services/hospitalApi";
import { printInvoice, printReceipt } from "../../utils/printDocument";
import { Section } from "../../components/HealthCard";
import { ErrorBox, Loading, PageTitle } from "../../components/Feedback";
import { Button, Field, Input, Modal, Select, Tabs, fmtUtc } from "../../components/ui";

const can = (user, ...p) => (user.permissions || []).some((x) => p.includes(x));
const rupee = (n) => `Rs ${Number(n || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const TONE = { DRAFT: "bg-amber-100 text-amber-900", FINAL: "bg-emerald-100 text-emerald-900", CANCELLED: "bg-slate-200 text-slate-700" };
const METHODS = [["CASH", "Cash"], ["UPI", "UPI"], ["CARD", "Card"], ["BANK", "Bank transfer"]];

export default function Billing() {
  const { user } = useAuth();
  const [q, setQ] = useState("");
  const [found, setFound] = useState([]);
  const [patientId, setPatientId] = useState(null);
  return (
    <div className="space-y-5">
      <PageTitle title="Billing" subtitle="Charges come from the price list. A final invoice is never changed: cancel it with a reason and make a new one." icon={ReceiptText} />
      <Tabs tabs={[["patient", "Patient bills", (
        <div className="space-y-4">
          <Field label="Find a patient" hint="Name, patient ID or UHID">
            <Input value={q} onChange={async (e) => { setQ(e.target.value); setFound(e.target.value.trim().length >= 2 ? await findBillingPatients(e.target.value).catch(() => []) : []); }} />
          </Field>
          {found.length > 0 && <ul className="rounded-xl border bg-white">{found.map((p) => <li key={p.id}><button type="button" className="w-full px-3 py-2 text-left hover:bg-slate-50" onClick={() => { setPatientId(p.id); setFound([]); setQ(`${p.full_name} (${p.patient_code})`); }}>{p.full_name} ({p.patient_code}{p.uhid ? `, ${p.uhid}` : ""})</button></li>)}</ul>}
          {patientId && <PatientBilling key={patientId} patientId={patientId} user={user} />}
        </div>)],
        ...(can(user, "billing.approve") ? [["refunds", "Refunds to approve", <Refunds user={user} />]] : [])]} />
    </div>
  );
}

function PatientBilling({ patientId, user }) {
  const { data, loading, error, reload } = useFetch(() => getPatientBilling(patientId), [patientId]);
  const [selected, setSelected] = useState([]);
  const [open, setOpen] = useState(null);
  const [dep, setDep] = useState({ amount: "", method: "CASH", reference: "" });
  const { problem, busy, run } = useSave();
  const [info, setInfo] = useState("");
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const canCreate = can(user, "billing.create");
  const toggle = (id) => setSelected(selected.includes(id) ? selected.filter((x) => x !== id) : [...selected, id]);
  return (
    <div className="space-y-4">
      <Section title={`${data.patient.full_name} (${data.patient.patient_code})`}>
        {problem && <ErrorBox message={problem} />}
        {info && <p className="mb-2 rounded-xl bg-sky-50 p-2.5 text-sm text-sky-900">{info}</p>}
        <h3 className="font-bold">Pending charges</h3>
        {data.pending_charges.length === 0 ? <p className="text-sm text-slate-500">No pending charge.</p> : (
          <ul className="divide-y">{data.pending_charges.map((c) => <li key={c.id} className="flex items-center justify-between gap-3 py-2"><label className="flex items-center gap-2"><input type="checkbox" checked={selected.includes(c.id)} onChange={() => toggle(c.id)} />{c.description}</label><span className="font-semibold">{rupee(c.amount)}</span></li>)}</ul>)}
        {canCreate && (
          <div className="mt-3 flex flex-wrap gap-2">
            <Button variant="secondary" disabled={busy} onClick={async () => { const r = await run(() => collectCharges(patientId)); if (r) { setInfo(`Added ${r.added.length} charge(s).${r.no_price_in_list.length ? ` No price in the list for: ${r.no_price_in_list.join(", ")}.` : ""}`); reload(); } }}>Collect charges from tests, scans and bed days</Button>
            <Button disabled={busy} onClick={async () => { const inv = await run(() => makeInvoice({ patient_id: patientId, charge_ids: selected, services: [], package_ids: [] }), "Draft invoice made"); if (inv) { setSelected([]); setOpen(inv.id); reload(); } }} >{selected.length ? `Make an invoice of ${selected.length} charge(s)` : "Make an invoice from the price list"}</Button>
          </div>)}
      </Section>
      <Section title="Invoices">
        {data.invoices.length === 0 ? <p className="text-sm text-slate-500">No invoice yet.</p> : (
          <ul className="divide-y">{data.invoices.map((i) => (
            <li key={i.id} className="flex flex-wrap items-center justify-between gap-2 py-2">
              <span><b>{i.number || "Draft"}</b> <span className={`ml-1 rounded-full px-2 py-0.5 text-xs font-bold ${TONE[i.status]}`}>{i.status}</span> <span className="text-sm text-slate-500">{fmtUtc(i.created_at)}</span></span>
              <span className="flex items-center gap-3 text-sm"><span>Total {rupee(i.total)}</span>{i.status === "FINAL" && <span className={i.balance > 0 ? "font-bold text-red-700" : "text-emerald-700"}>Balance {rupee(i.balance)}</span>}<Button variant="secondary" onClick={() => setOpen(i.id)}>Open</Button></span>
            </li>))}</ul>)}
      </Section>
      {can(user, "billing.collect") && (
        <Section title="Advance (deposit)">
          <p className="mb-2 text-sm text-slate-600">{data.deposits.length === 0 ? "No advance taken." : data.deposits.map((d) => `${d.receipt_number}: ${rupee(d.balance)} left of ${rupee(d.amount)}`).join("; ")}</p>
          <div className="flex flex-wrap items-end gap-2"><Field label="Amount"><Input inputMode="decimal" value={dep.amount} onChange={(e) => setDep({ ...dep, amount: e.target.value })} /></Field>
            <Field label="Method"><Select value={dep.method} onChange={(e) => setDep({ ...dep, method: e.target.value })}>{METHODS.map(([k, n]) => <option key={k} value={k}>{n}</option>)}</Select></Field>
            {dep.method !== "CASH" && <Field label="Reference *"><Input maxLength={60} value={dep.reference} onChange={(e) => setDep({ ...dep, reference: e.target.value })} /></Field>}
            <Button disabled={busy || !(Number(dep.amount) > 0)} onClick={async () => { if (await run(() => takeDeposit({ patient_id: patientId, amount: Number(dep.amount), method: dep.method, reference: dep.reference || null }), "Advance received")) { setDep({ amount: "", method: "CASH", reference: "" }); reload(); } }}>Take the advance</Button></div>
        </Section>)}
      {open && <InvoiceDialog id={open} user={user} patient={data} onClose={() => { setOpen(null); reload(); }} />}
    </div>
  );
}

function InvoiceDialog({ id, user, patient, onClose }) {
  const { data: inv, loading, error, reload } = useFetch(() => getInvoice(id), [id]);
  const services = useFetch(() => listServices(), []);
  const packages = useFetch(getPackages, []);
  const { problem, busy, run } = useSave();
  const [f, setF] = useState({ service: "", qty: "1", pkg: "", discount: "", reason: "", pay: "", method: "CASH", ref: "", deposit: "", refund: "", why: "", cancel: "" });
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  if (loading && !inv) return <Modal title="Invoice" onClose={onClose}><Loading /></Modal>;
  if (error) return <Modal title="Invoice" onClose={onClose}><ErrorBox message={error} /></Modal>;
  const draft = inv.status === "DRAFT", final = inv.status === "FINAL";
  const act = (fn, message) => async () => { if (await run(fn, message)) reload(); };
  const printIt = async () => printInvoice(inv, await getHospitalProfile().catch(() => ({})));
  return (
    <Modal title={`Invoice ${inv.number || "(draft)"}`} onClose={onClose} wide>
      <div className="space-y-3">
        <p className="text-sm text-slate-600">{inv.patient_name} ({inv.patient_code}) - <b>{inv.status}</b>{inv.cancel_reason ? `: ${inv.cancel_reason}` : ""}{inv.claim_status ? ` - claim ${inv.claim_status.toLowerCase().replace("_", " ")}` : ""}</p>
        {problem && <ErrorBox message={problem} />}
        <div className="overflow-x-auto"><table className="w-full min-w-[30rem] text-left text-sm"><thead><tr className="border-b text-xs uppercase text-slate-500"><th className="py-1.5 pr-3">Item</th><th className="pr-3">Qty</th><th className="pr-3">Price</th><th className="pr-3">GST</th><th className="text-right">Amount</th><th /></tr></thead>
          <tbody>{inv.lines.map((l) => <tr key={l.id} className="border-b border-slate-100"><td className="py-1.5 pr-3">{l.description}</td><td className="pr-3">{l.quantity}</td><td className="pr-3">{rupee(l.unit_price)}</td><td className="pr-3">{l.gst_percent}%</td><td className="text-right">{rupee(l.amount + l.tax)}</td>
            <td>{draft && <button type="button" className="text-xs font-bold text-red-700 underline" onClick={act(() => removeInvoiceLine(id, l.id), "Line removed")}>Remove</button>}</td></tr>)}</tbody></table></div>
        <div className="space-y-0.5 text-right text-sm"><p>Subtotal {rupee(inv.subtotal)}</p><p>GST {rupee(inv.tax)}</p>{inv.discount > 0 && <p>Discount {rupee(inv.discount)} ({inv.discount_reason})</p>}<p className="text-base font-extrabold">Total {rupee(inv.total)}</p>
          {final && <><p>Paid {rupee(inv.paid)}{inv.refunded ? `, refunded ${rupee(inv.refunded)}` : ""}</p>{inv.insurer_approved > 0 && <p>Insurer approved {rupee(inv.insurer_approved)}, patient pays {rupee(inv.patient_payable)}</p>}<p className={`text-base font-extrabold ${inv.balance > 0 ? "text-red-700" : "text-emerald-700"}`}>Balance {rupee(inv.balance)}</p></>}</div>

        {draft && can(user, "billing.create") && (
          <div className="space-y-3 rounded-2xl bg-slate-50 p-3">
            <div className="flex flex-wrap items-end gap-2"><Field label="Add a service from the price list"><Select value={f.service} onChange={set("service")}><option value="">Choose</option>{(services.data || []).map((s) => <option key={s.id} value={s.id}>{s.name} - {rupee(s.price)}</option>)}</Select></Field>
              <Field label="Qty"><Input inputMode="numeric" value={f.qty} onChange={set("qty")} /></Field>
              <Button variant="secondary" disabled={busy || !f.service} onClick={act(() => addInvoiceLines(id, { services: [{ service_id: Number(f.service), quantity: Number(f.qty) || 1 }] }), "Added")}>Add</Button></div>
            <div className="flex flex-wrap items-end gap-2"><Field label="Add a package"><Select value={f.pkg} onChange={set("pkg")}><option value="">Choose</option>{(packages.data || []).filter((p) => p.is_active).map((p) => <option key={p.id} value={p.id}>{p.name} - {rupee(p.price)}</option>)}</Select></Field>
              <Button variant="secondary" disabled={busy || !f.pkg} onClick={act(() => addInvoiceLines(id, { package_ids: [Number(f.pkg)] }), "Package added")}>Add</Button></div>
            <div className="flex flex-wrap items-end gap-2"><Field label="Discount (Rs)"><Input inputMode="decimal" value={f.discount} onChange={set("discount")} /></Field><Field label="Reason"><Input maxLength={300} value={f.reason} onChange={set("reason")} /></Field>
              <Button variant="secondary" disabled={busy || f.discount === ""} onClick={act(() => setDiscount(id, Number(f.discount), f.reason), "Discount set")}>Apply</Button></div>
            {inv.needs_discount_approval && <p className="rounded-xl bg-amber-50 p-2 text-sm text-amber-900">This discount is large: a second person with approval rights must approve it before the invoice is final.{can(user, "billing.approve") && <Button className="ml-2" variant="secondary" disabled={busy} onClick={act(() => approveDiscount(id), "Discount approved")}>Approve the discount</Button>}</p>}
            <div className="flex flex-wrap gap-2"><Button disabled={busy} onClick={act(() => finaliseInvoice(id), "Invoice is final")}>Make it final</Button><Button variant="secondary" disabled={busy} onClick={printIt}>Print the draft</Button></div>
          </div>)}

        {final && (
          <div className="space-y-3">
            {inv.payments.length > 0 && <div><h3 className="font-bold">Payments</h3><ul className="text-sm">{inv.payments.map((p) => <li key={p.id} className="flex flex-wrap items-center justify-between gap-2 py-1"><span>{p.receipt_number}: {rupee(p.amount)} by {p.method.toLowerCase()}{p.reference ? ` (${p.reference})` : ""}</span>
              <Button variant="soft" onClick={async () => printReceipt(await getReceipt(p.id))}>Print receipt</Button></li>)}</ul></div>}
            {inv.refunds.length > 0 && <ul className="text-sm text-slate-600">{inv.refunds.map((r) => <li key={r.id}>{r.number}: {rupee(r.amount)} - {r.status.toLowerCase()} ({r.reason})</li>)}</ul>}
            {can(user, "billing.collect") && inv.balance > 0 && (
              <div className="flex flex-wrap items-end gap-2 rounded-2xl bg-slate-50 p-3"><Field label="Amount received"><Input inputMode="decimal" value={f.pay} placeholder={String(inv.patient_payable - inv.paid > 0 ? Math.min(inv.balance, inv.patient_payable - inv.paid) : inv.balance)} onChange={set("pay")} /></Field>
                <Field label="Method"><Select value={f.method} onChange={set("method")}>{METHODS.map(([k, n]) => <option key={k} value={k}>{n}</option>)}<option value="ADVANCE">From the advance</option></Select></Field>
                {["UPI", "CARD", "BANK"].includes(f.method) && <Field label="Reference *"><Input maxLength={60} value={f.ref} onChange={set("ref")} /></Field>}
                {f.method === "ADVANCE" && <Field label="Advance"><Select value={f.deposit} onChange={set("deposit")}><option value="">Choose</option>{patient.deposits.filter((d) => d.balance > 0).map((d) => <option key={d.id} value={d.id}>{d.receipt_number} ({rupee(d.balance)} left)</option>)}</Select></Field>}
                <Button disabled={busy || !(Number(f.pay) > 0)} onClick={async () => { const r = await run(() => payInvoice(id, { amount: Number(f.pay), method: f.method, reference: f.ref || null, deposit_id: f.deposit ? Number(f.deposit) : null }), "Payment received"); if (r) { setF({ ...f, pay: "", ref: "" }); reload(); printReceipt(await getReceipt(r.payment_id)); } }}>Receive the payment</Button></div>)}
            {can(user, "billing.collect") && inv.paid - inv.refunded > 0 && (
              <div className="flex flex-wrap items-end gap-2"><Field label="Refund (Rs)"><Input inputMode="decimal" value={f.refund} onChange={set("refund")} /></Field><Field label="Reason *"><Input maxLength={300} value={f.why} onChange={set("why")} /></Field>
                <Button variant="secondary" disabled={busy || !(Number(f.refund) > 0) || f.why.trim().length < 3} onClick={act(() => requestRefund({ invoice_id: id, amount: Number(f.refund), method: "CASH", reason: f.why.trim() }), "Refund requested: a second person approves it")}>Ask for a refund</Button></div>)}
            <div className="flex flex-wrap items-end gap-2"><Button variant="secondary" onClick={printIt}>Print the invoice</Button>
              {can(user, "billing.approve") && inv.paid - inv.refunded === 0 && <><Field label="Cancel this invoice: reason"><Input maxLength={300} value={f.cancel} onChange={set("cancel")} /></Field><Button variant="secondary" disabled={busy || f.cancel.trim().length < 3} onClick={act(() => cancelInvoice(id, f.cancel.trim()), "Invoice cancelled")}>Cancel the invoice</Button></>}</div>
          </div>)}
        {draft && <div className="flex flex-wrap items-end gap-2"><Field label="Throw this draft away: reason"><Input maxLength={300} value={f.cancel} onChange={set("cancel")} /></Field><Button variant="soft" disabled={busy || f.cancel.trim().length < 3} onClick={act(() => cancelInvoice(id, f.cancel.trim()), "Draft cancelled")}>Cancel the draft</Button></div>}
      </div>
    </Modal>
  );
}

function Refunds({ user }) {
  const { data, loading, error, reload } = useFetch(() => getRefunds({ status_filter: "PENDING" }));
  const { problem, busy, run } = useSave();
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return (
    <div className="space-y-2">
      {problem && <ErrorBox message={problem} />}
      {data.length === 0 ? <p className="text-sm text-slate-500">No refund is waiting.</p> : data.map((r) => (
        <Section key={r.id}><p className="font-bold">{r.number}: {rupee(r.amount)} <span className="text-sm font-normal text-slate-500">{r.deposit_id ? "from an advance" : `on invoice ${r.invoice_id}`}, by {r.method.toLowerCase()}</span></p><p className="text-sm text-slate-600">{r.reason}</p>
          <div className="mt-2 flex gap-2"><Button disabled={busy} onClick={async () => { if (await run(() => decideRefund(r.id, true), "Refund approved")) reload(); }}>Approve</Button>
            <Button variant="secondary" disabled={busy} onClick={async () => { const why = window.prompt("Why is it rejected?"); if (why && await run(() => decideRefund(r.id, false, why), "Refund rejected")) reload(); }}>Reject</Button></div></Section>))}
    </div>
  );
}
