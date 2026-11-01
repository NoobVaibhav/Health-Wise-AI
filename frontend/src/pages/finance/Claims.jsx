// Insurance and TPA claims: make a claim for a final invoice, ask for pre-authorisation, tick the documents, submit, record the insurer's decision and settlement.
// The patient pays only what the insurer did not approve.
import { useState } from "react";
import { ShieldCheck } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import useSave from "../../hooks/useSave";
import { useAuth } from "../../context/AuthContext";
import { claimAction, findBillingPatients, getClaimSummary, getClaims, getPatientBilling, makeClaim, markClaimDocument } from "../../services/financeApi";
import { Section } from "../../components/HealthCard";
import { EmptyState, ErrorBox, Loading, PageTitle } from "../../components/Feedback";
import { Button, Field, Input, Modal, Select, Tabs, fmtUtc } from "../../components/ui";

const rupee = (n) => `Rs ${Number(n || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const LABEL = { DRAFT: "Started", PREAUTH_SENT: "Pre-authorisation sent", PREAUTH_APPROVED: "Pre-authorisation approved", SUBMITTED: "Submitted", APPROVED: "Approved", PARTIAL: "Partly approved", REJECTED: "Rejected", SETTLED: "Settled" };
const TONE = { DRAFT: "bg-slate-100", PREAUTH_SENT: "bg-amber-100 text-amber-900", PREAUTH_APPROVED: "bg-sky-100 text-sky-900", SUBMITTED: "bg-violet-100 text-violet-900", APPROVED: "bg-emerald-100 text-emerald-900", PARTIAL: "bg-amber-100 text-amber-900", REJECTED: "bg-red-100 text-red-900", SETTLED: "bg-emerald-200 text-emerald-900" };

export default function Claims() {
  const { user } = useAuth();
  const manage = (user.permissions || []).includes("claims.manage");
  return (
    <div className="space-y-5">
      <PageTitle title="Insurance claims" subtitle="From pre-authorisation to settlement. The patient pays only what the insurer did not approve." icon={ShieldCheck} />
      <Tabs tabs={[["list", "Claims", <List manage={manage} />], ["summary", "Summary", <Summary />], ...(manage ? [["new", "New claim", <NewClaim />]] : [])]} />
    </div>
  );
}

function Summary() {
  const { data, loading, error, reload } = useFetch(getClaimSummary);
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return (
    <Section title="Claims by status">{data.length === 0 ? <p className="text-sm text-slate-500">No claim yet.</p> : (
      <div className="overflow-x-auto"><table className="w-full min-w-[30rem] text-left text-sm"><thead><tr className="border-b text-xs uppercase text-slate-500"><th className="py-1.5 pr-3">Status</th><th className="pr-3">Claims</th><th className="pr-3">Claimed</th><th className="pr-3">Approved</th><th className="pr-3">Rejected</th><th>Settled</th></tr></thead>
        <tbody>{data.map((r) => <tr key={r.status} className="border-b border-slate-100"><td className="py-1.5 pr-3 font-semibold">{LABEL[r.status]}</td><td className="pr-3">{r.count}</td><td className="pr-3">{rupee(r.claimed)}</td><td className="pr-3">{rupee(r.approved)}</td><td className="pr-3">{rupee(r.rejected)}</td><td>{rupee(r.settled)}</td></tr>)}</tbody></table></div>)}</Section>
  );
}

function List({ manage }) {
  const [status, setStatus] = useState("");
  const { data, loading, error, reload } = useFetch(() => getClaims(status ? { status_filter: status } : undefined), [status]);
  const [open, setOpen] = useState(null);
  return (
    <div className="space-y-3">
      <div className="max-w-xs"><Select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status"><option value="">All claims</option>{Object.entries(LABEL).map(([k, n]) => <option key={k} value={k}>{n}</option>)}</Select></div>
      {loading && !data ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> : data.length === 0 ? <EmptyState message="No claim" hint="Start one from a final invoice (New claim)." icon={ShieldCheck} /> : data.map((c) => (
        <Section key={c.id}>
          <div className="flex flex-wrap items-center justify-between gap-2"><p className="font-bold">{c.claim_number} <span className="text-sm font-normal text-slate-500">{c.patient_name} ({c.patient_code}) - {c.insurer}{c.tpa ? ` / ${c.tpa}` : ""}</span></p><span className={`rounded-full px-3 py-1 text-sm font-bold ${TONE[c.status]}`}>{LABEL[c.status]}</span></div>
          <p className="text-sm text-slate-600">Invoice {c.invoice_number}: {rupee(c.invoice_total)}. Claimed {rupee(c.claimed_amount)}, approved {rupee(c.approved_amount)}, settled {rupee(c.settled_amount)}. Patient pays {rupee(c.patient_payable)}.</p>
          <Button className="mt-2" variant="secondary" onClick={() => setOpen(c)}>Open</Button>
        </Section>))}
      {open && <ClaimDialog claim={open} manage={manage} onClose={() => { setOpen(null); reload(); }} />}
    </div>
  );
}

function ClaimDialog({ claim: first, manage, onClose }) {
  const [c, setC] = useState(first);
  const [f, setF] = useState({ pre: "", ref: "", approved: "", reason: "", amount: "", settle: "", sref: "" });
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const { problem, busy, run } = useSave();
  const go = (fn, message) => async () => { const r = await run(fn, message); if (r && r !== true) setC(r); };
  const act = (action, body, message) => go(() => claimAction(c.id, action, body), message);
  return (
    <Modal title={`${c.claim_number}: ${c.patient_name}`} onClose={onClose} wide>
      <div className="space-y-3">
        <p className="text-sm text-slate-600">{c.insurer}{c.tpa ? ` via ${c.tpa}` : ""}, policy {c.policy_number}{c.member_id ? `, member ${c.member_id}` : ""}. Invoice {c.invoice_number} {rupee(c.invoice_total)}. Status: <b>{LABEL[c.status]}</b>.</p>
        {problem && <ErrorBox message={problem} />}
        <Section title="Documents the insurer needs"><ul className="text-sm">{c.documents.map((d) => <li key={d.id} className="flex items-center justify-between py-1"><span>{d.received ? "Received" : "Needed"}: {d.name}</span>
          {manage && !["SETTLED", "REJECTED"].includes(c.status) && <Button variant="soft" disabled={busy} onClick={go(() => markClaimDocument(c.id, d.id, !d.received))}>{d.received ? "Mark not received" : "Mark received"}</Button>}</li>)}</ul></Section>
        {manage && c.status === "DRAFT" && <div className="flex flex-wrap items-end gap-2"><Field label="Pre-authorisation amount"><Input inputMode="decimal" value={f.pre} onChange={set("pre")} /></Field><Field label="Reference"><Input maxLength={60} value={f.ref} onChange={set("ref")} /></Field><Button disabled={busy || !(Number(f.pre) > 0)} onClick={act("preauth", { amount: Number(f.pre), reference: f.ref || null }, "Pre-authorisation requested")}>Ask the insurer</Button></div>}
        {manage && c.status === "PREAUTH_SENT" && <div className="flex flex-wrap items-end gap-2"><Field label={`Insurer approved (asked ${rupee(c.preauth_requested)}; 0 = refused)`}><Input inputMode="decimal" value={f.approved} onChange={set("approved")} /></Field><Field label="Reason if refused"><Input maxLength={300} value={f.reason} onChange={set("reason")} /></Field><Button disabled={busy || f.approved === ""} onClick={act("preauth/decision", { approved_amount: Number(f.approved), reason: f.reason || null }, "Recorded")}>Record the answer</Button></div>}
        {manage && ["DRAFT", "PREAUTH_APPROVED"].includes(c.status) && <div className="flex flex-wrap items-end gap-2"><Field label="Amount to claim"><Input inputMode="decimal" value={f.amount} placeholder={String(c.invoice_total)} onChange={set("amount")} /></Field><Button disabled={busy || !(Number(f.amount) > 0)} onClick={act("submit", { amount: Number(f.amount) }, "Claim submitted")}>Submit the claim</Button></div>}
        {manage && c.status === "SUBMITTED" && <div className="flex flex-wrap items-end gap-2"><Field label={`Insurer approved (claimed ${rupee(c.claimed_amount)})`}><Input inputMode="decimal" value={f.approved} onChange={set("approved")} /></Field><Field label="Reason if not in full"><Input maxLength={300} value={f.reason} onChange={set("reason")} /></Field><Button disabled={busy || f.approved === ""} onClick={act("decision", { approved_amount: Number(f.approved), reason: f.reason || null }, "Decision recorded")}>Record the decision</Button></div>}
        {manage && ["APPROVED", "PARTIAL"].includes(c.status) && <div className="flex flex-wrap items-end gap-2"><Field label={`Insurer paid (up to ${rupee(c.approved_amount - c.settled_amount)})`}><Input inputMode="decimal" value={f.settle} onChange={set("settle")} /></Field><Field label="Reference *"><Input maxLength={60} value={f.sref} onChange={set("sref")} /></Field><Button disabled={busy || !(Number(f.settle) > 0) || f.sref.trim().length < 2} onClick={act("settle", { amount: Number(f.settle), reference: f.sref.trim() }, "Settlement recorded")}>Record the payment</Button></div>}
        {c.rejection_reason && <p className="rounded-xl bg-red-50 p-2.5 text-sm text-red-800">{c.rejection_reason}</p>}
        <Section title="History"><ul className="text-sm">{c.events.map((e, i) => <li key={i}>{fmtUtc(e.at)}: {e.text}</li>)}</ul></Section>
      </div>
    </Modal>
  );
}

function NewClaim() {
  const [q, setQ] = useState("");
  const [found, setFound] = useState([]);
  const [overview, setOverview] = useState(null);
  const [f, setF] = useState({ invoice: "", policy: "" });
  const { problem, busy, run } = useSave();
  return (
    <div className="space-y-3">
      <Field label="Find the patient"><Input value={q} onChange={async (e) => { setQ(e.target.value); setFound(e.target.value.trim().length >= 2 ? await findBillingPatients(e.target.value).catch(() => []) : []); }} /></Field>
      {found.length > 0 && <ul className="rounded-xl border bg-white">{found.map((p) => <li key={p.id}><button type="button" className="w-full px-3 py-2 text-left hover:bg-slate-50" onClick={async () => { setFound([]); setQ(`${p.full_name} (${p.patient_code})`); setOverview(await getPatientBilling(p.id)); }}>{p.full_name} ({p.patient_code})</button></li>)}</ul>}
      {overview && (
        <Section title={`For ${overview.patient.full_name}`}>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Final invoice"><Select value={f.invoice} onChange={(e) => setF({ ...f, invoice: e.target.value })}><option value="">Choose</option>{overview.invoices.filter((i) => i.status === "FINAL" && !i.claim_status).map((i) => <option key={i.id} value={i.id}>{i.number} - {rupee(i.total)}</option>)}</Select></Field>
            <Field label="Policy"><Select value={f.policy} onChange={(e) => setF({ ...f, policy: e.target.value })}><option value="">Choose</option>{overview.policies.filter((p) => p.is_active).map((p) => <option key={p.id} value={p.id}>{p.insurer_name} {p.policy_number}</option>)}</Select></Field>
          </div>
          {overview.policies.length === 0 && <p className="mt-2 text-sm text-amber-800">This patient has no insurance policy on record. Reception adds it in the patient registry.</p>}
          {problem && <ErrorBox message={problem} />}
          <Button className="mt-3" disabled={busy || !f.invoice || !f.policy} onClick={async () => { if (await run(() => makeClaim(Number(f.invoice), Number(f.policy)), "Claim started")) { setOverview(await getPatientBilling(overview.patient.id)); setF({ invoice: "", policy: "" }); } }}>Start the claim</Button>
        </Section>)}
    </div>
  );
}
