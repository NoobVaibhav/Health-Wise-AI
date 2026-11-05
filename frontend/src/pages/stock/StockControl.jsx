// Pharmacy stock control: alerts (low stock, expiring, expired, recalled), the ward medicine requests, the history of every stock change, and suppliers.
// Recalled and expired stock can never be dispensed or sold; a recall and a write-off need a reason.
import { useState } from "react";
import { Boxes } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import useSave from "../../hooks/useSave";
import { useAuth } from "../../context/AuthContext";
import { addSupplier, getMedicineRequests, getMovements, getStockAlerts, getSuppliers, issueRequest, recallBatch, rejectRequest, writeOffBatch } from "../../services/operationsApi";
import { Section } from "../../components/HealthCard";
import { EmptyState, ErrorBox, Loading, PageTitle } from "../../components/Feedback";
import { Button, Field, Input, Modal, Tabs, fmtUtc } from "../../components/ui";
import ResponsiveTable from "../../components/ResponsiveTable";

function ReasonDialog({ title, label, onClose, onSave }) {
  const [reason, setReason] = useState("");
  const { problem, busy, run } = useSave();
  return (
    <Modal title={title} onClose={onClose}>
      <Field label={label}><Input maxLength={300} value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
      {problem && <ErrorBox message={problem} />}
      <div className="mt-4 flex justify-end gap-2"><Button variant="secondary" onClick={onClose}>Cancel</Button>
        <Button disabled={busy || reason.trim().length < 3} onClick={async () => { if (await run(() => onSave(reason.trim()))) onClose(true); }}>Confirm</Button></div>
    </Modal>
  );
}

function BatchTable({ rows, empty, canManage, onAction, actions }) {
  if (!rows.length) return <p className="py-3 text-sm text-slate-500">{empty}</p>;
  return (
    <ResponsiveTable caption="Stock batches" rows={rows} columns={[
      { key: "medicine_name", label: "Medicine", priority: 1, render: (r) => <span className="font-semibold">{r.medicine_name}{r.recall_reason && <span className="block text-xs font-normal text-red-700">Recall: {r.recall_reason}</span>}</span> },
      { key: "quantity", label: "Quantity", priority: 1, numeric: true },
      { key: "expiry_date", label: "Expiry", priority: 2, numeric: true, render: (r) => r.expiry_date || "-" },
      { key: "batch_number", label: "Batch", priority: 3, render: (r) => r.batch_number || "-" },
      ...(canManage ? [{ key: "actions", label: "Actions", priority: 1, render: (r) => <span className="flex flex-wrap justify-end gap-2">{actions.map(([key, label]) => <Button key={key} variant="secondary" onClick={() => onAction(key, r)}>{label}</Button>)}</span> }] : []),
    ]} />
  );
}

function Alerts({ canManage }) {
  const { data, loading, error, reload } = useFetch(getStockAlerts);
  const [dialog, setDialog] = useState(null);
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return (
    <div className="space-y-4">
      <Section title={`Low stock (${data.low_stock.length})`}>
        {data.low_stock.length === 0 ? <p className="text-sm text-slate-500">Nothing is running low.</p> : (
          <ul className="divide-y">{data.low_stock.map((m) => <li key={m.medicine_name} className="flex justify-between py-2"><b>{m.medicine_name}</b><span className="text-sm text-slate-600">{m.usable_quantity} usable (reorder at {m.reorder_level})</span></li>)}</ul>)}
      </Section>
      <Section title={`Recalled (${data.recalled.length})`}><BatchTable rows={data.recalled} empty="No recalled batch has stock." canManage={canManage} actions={[["off", "Write off"]]} onAction={(k, r) => setDialog({ kind: k, r })} /></Section>
      <Section title={`Expired (${data.expired.length})`}><BatchTable rows={data.expired} empty="No expired stock." canManage={canManage} actions={[["off", "Write off"]]} onAction={(k, r) => setDialog({ kind: k, r })} /></Section>
      <Section title={`Expiring in 60 days (${data.expiring_soon.length})`}><BatchTable rows={data.expiring_soon} empty="Nothing expires soon." canManage={canManage} actions={[["recall", "Recall"]]} onAction={(k, r) => setDialog({ kind: k, r })} /></Section>
      {data.items_to_reorder.length > 0 && <Section title={`Store items to reorder (${data.items_to_reorder.length})`}><ul className="divide-y">{data.items_to_reorder.map((i) => <li key={i.id} className="flex justify-between py-2"><b>{i.name}</b><span className="text-sm text-slate-600">{i.quantity} left (minimum {i.min_level})</span></li>)}</ul></Section>}
      {dialog?.kind === "recall" && <ReasonDialog title={`Recall ${dialog.r.medicine_name} (batch ${dialog.r.batch_number || "-"})`} label="Why is it recalled? *" onClose={(done) => { setDialog(null); if (done) reload(); }} onSave={(reason) => recallBatch(dialog.r.id, reason)} />}
      {dialog?.kind === "off" && <ReasonDialog title={`Write off ${dialog.r.quantity} of ${dialog.r.medicine_name}`} label="Reason *" onClose={(done) => { setDialog(null); if (done) reload(); }} onSave={(reason) => writeOffBatch(dialog.r.id, reason)} />}
    </div>
  );
}

function Requests() {
  const { data, loading, error, reload } = useFetch(() => getMedicineRequests());
  const { problem, busy, run } = useSave();
  const [rejecting, setRejecting] = useState(null);
  const [reason, setReason] = useState("");
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const open = data.filter((r) => ["PENDING", "PARTIAL"].includes(r.status));
  return (
    <div className="space-y-3">
      {problem && <ErrorBox message={problem} />}
      {open.length === 0 ? <EmptyState message="No ward request is waiting" hint="Nurses and doctors ask for medicines for admitted patients here." icon={Boxes} /> : open.map((r) => (
        <Section key={r.id}>
          <p className="font-bold">{r.patient_name} <span className="text-sm font-normal text-slate-500">({r.patient_code}) {r.status === "PARTIAL" ? "- partly issued" : ""}</span></p>
          <ul className="my-2 text-sm">{r.items.map((i) => <li key={i.id}>{i.medicine_name}: {i.issued_quantity} of {i.quantity} issued</li>)}</ul>
          <div className="flex flex-wrap gap-2">
            <Button disabled={busy} onClick={async () => { const issues = Object.fromEntries(r.items.filter((i) => i.quantity > i.issued_quantity).map((i) => [i.id, i.quantity - i.issued_quantity])); if (await run(() => issueRequest(r.id, issues), "Issued")) reload(); }}>Issue what is left</Button>
            {r.status === "PENDING" && <Button variant="secondary" onClick={() => setRejecting(r.id)}>Reject</Button>}
          </div>
          {rejecting === r.id && <div className="mt-2 flex flex-wrap items-end gap-2 rounded-xl bg-slate-50 p-2"><Field label="Reason *"><Input maxLength={300} value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
            <Button disabled={busy || reason.trim().length < 3} onClick={async () => { if (await run(() => rejectRequest(r.id, reason.trim()), "Rejected")) { setRejecting(null); setReason(""); reload(); } }}>Reject</Button></div>}
        </Section>))}
    </div>
  );
}

function History() {
  const { data, loading, error, reload } = useFetch(() => getMovements({ limit: 150 }));
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return (
    <Section title="Every stock change (newest first)">
      <ResponsiveTable caption="Stock changes" rows={data} columns={[
        { key: "created_at", label: "When", priority: 1, render: (m) => fmtUtc(m.created_at) },
        { key: "kind", label: "What", priority: 1, render: (m) => `${m.kind}${m.reference_type ? ` (${m.reference_type} ${m.reference_id ?? ""})` : ""}` },
        { key: "quantity", label: "Change", priority: 1, numeric: true, render: (m) => <b className={m.quantity < 0 ? "text-red-700" : "text-emerald-700"}>{m.quantity > 0 ? `+${m.quantity}` : m.quantity}</b> },
        { key: "balance_after", label: "Balance", priority: 2, numeric: true },
        { key: "note", label: "Note", priority: 3, render: (m) => <span className="text-slate-600">{m.note || "-"}</span> },
      ]} />
    </Section>
  );
}

function Suppliers({ canManage }) {
  const { data, loading, error, reload } = useFetch(getSuppliers);
  const [form, setForm] = useState({ name: "", phone: "", gstin: "" });
  const { problem, busy, run } = useSave();
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return (
    <div className="space-y-4">
      {canManage && (
        <Section title="Add a supplier">
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Name *"><Input maxLength={150} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></Field>
            <Field label="Phone"><Input maxLength={30} value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></Field>
            <Field label="GSTIN"><Input maxLength={20} value={form.gstin} onChange={(e) => setForm({ ...form, gstin: e.target.value })} /></Field>
          </div>
          {problem && <ErrorBox message={problem} />}
          <Button className="mt-3" disabled={busy || form.name.trim().length < 2} onClick={async () => { if (await run(() => addSupplier({ name: form.name.trim(), phone: form.phone || null, gstin: form.gstin || null }), "Supplier added")) { setForm({ name: "", phone: "", gstin: "" }); reload(); } }}>Add</Button>
        </Section>)}
      <Section title="Suppliers">{data.length === 0 ? <p className="text-sm text-slate-500">No supplier yet.</p> : <ul className="divide-y">{data.map((s) => <li key={s.id} className="py-2"><b>{s.name}</b> <span className="text-sm text-slate-500">{s.phone || ""} {s.gstin || ""}</span></li>)}</ul>}</Section>
    </div>
  );
}

export default function StockControl() {
  const { user } = useAuth();
  const canManage = (user.permissions || []).includes("stock.manage");
  return (
    <div className="space-y-5">
      <PageTitle title="Stock control" subtitle="Recalled and expired stock is never dispensed or sold. Every change of stock is kept." icon={Boxes} />
      <Tabs tabs={[["alerts", "Alerts", <Alerts canManage={canManage} />], ["requests", "Ward requests", <Requests />], ["history", "History", <History />], ["suppliers", "Suppliers", <Suppliers canManage={canManage} />]]} />
    </div>
  );
}
