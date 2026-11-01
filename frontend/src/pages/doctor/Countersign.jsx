// A consultant: "Awaiting my countersign" (prescriptions, orders and discharge summaries of the junior doctors under them) with Approve, Edit and approve, and Return with
// a comment. A junior doctor: "Pending approval", what they sent, its status and the consultant's comment. Nothing reaches the pharmacy or the lab before the countersign.
import { useState } from "react";
import { ListChecks } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import useSave from "../../hooks/useSave";
import { useAuth } from "../../context/AuthContext";
import { approveCountersign, getCountersign, listAwaiting, listMySubmissions, returnCountersign } from "../../services/traineeApi";
import { Section } from "../../components/HealthCard";
import { EmptyState, ErrorBox, Loading, PageTitle } from "../../components/Feedback";
import { Button, Field, Input, Modal, Tabs, fmtUtc } from "../../components/ui";

const KIND = { PRESCRIPTION: "Prescription", ORDER: "Order", DISCHARGE_SUMMARY: "Discharge summary" };
const TONE = { PENDING: "bg-amber-100 text-amber-900", APPROVED: "bg-emerald-100 text-emerald-800", EDITED: "bg-sky-100 text-sky-800", RETURNED: "bg-red-100 text-red-800" };
const STATUS_LABEL = { PENDING: "Waiting", APPROVED: "Approved", EDITED: "Edited and approved", RETURNED: "Returned" };

const Row = ({ r, children }) => (
  <li className="space-y-1 py-3">
    <div className="flex flex-wrap items-center justify-between gap-2">
      <span><b>{KIND[r.kind]}</b> · {r.patient_name} <span className="text-sm text-slate-500">{r.uhid}</span></span>
      <span className={`rounded-full px-2.5 py-1 text-xs font-bold ${TONE[r.status]}`}>{STATUS_LABEL[r.status]}</span>
    </div>
    <p className="text-sm text-slate-700">{r.summary}</p>
    <p className="text-xs text-slate-500">By {r.requested_by} · {fmtUtc(r.created_at)}{r.decided_at ? ` · decided ${fmtUtc(r.decided_at)}` : ""}</p>
    {r.comment && <p className="rounded-xl bg-slate-50 p-2 text-sm"><b>Comment:</b> {r.comment}</p>}
    {children}
  </li>
);

function EditDialog({ id, onClose, onDone }) {
  const { data, loading, error } = useFetch(() => getCountersign(id), [id]);
  const [items, setItems] = useState(null);
  const { problem, busy, run } = useSave();
  if (loading) return <Modal title="Edit and approve" onClose={onClose}><Loading /></Modal>;
  if (error) return <Modal title="Edit and approve" onClose={onClose}><ErrorBox message={error} /></Modal>;
  const list = items || data.prescription.items.map((i) => ({ ...i, quantity: String(i.quantity) }));
  const set = (idx, key) => (e) => setItems(list.map((x, j) => (j === idx ? { ...x, [key]: e.target.value } : x)));
  const body = list.map((i) => ({ medicine_name: i.medicine_name, dosage: i.dosage, frequency: i.frequency, duration: i.duration, quantity: Number(i.quantity), instructions: i.instructions || null }));
  return (
    <Modal title="Edit the prescription and approve it" onClose={onClose} wide>
      <div className="space-y-3">
        <p className="text-sm text-slate-600">The resident's own version is kept. Reason: {data.prescription.indication || "not written"}.</p>
        {list.map((i, idx) => (
          <div key={idx} className="grid gap-2 rounded-xl bg-slate-50 p-2 sm:grid-cols-5">
            <Field label="Medicine"><Input maxLength={200} value={i.medicine_name} onChange={set(idx, "medicine_name")} /></Field><Field label="Dose"><Input maxLength={100} value={i.dosage} onChange={set(idx, "dosage")} /></Field>
            <Field label="How often"><Input maxLength={100} value={i.frequency} onChange={set(idx, "frequency")} /></Field><Field label="For how long"><Input maxLength={100} value={i.duration} onChange={set(idx, "duration")} /></Field>
            <Field label="Quantity"><Input type="number" min="1" value={i.quantity} onChange={set(idx, "quantity")} /></Field>
          </div>))}
        {problem && <ErrorBox message={problem} />}
        <Button type="button" disabled={busy} onClick={async () => { if (await run(() => approveCountersign(id, { items: body }), "Edited and approved")) onDone(); }}>Save the changes and approve</Button>
      </div>
    </Modal>
  );
}

function Awaiting() {
  const { data, loading, error, reload } = useFetch(() => listAwaiting("PENDING"));
  const decided = useFetch(() => listAwaiting("DECIDED"));
  const { problem, busy, run } = useSave();
  const [editing, setEditing] = useState(null);
  const [returning, setReturning] = useState(null);
  const [comment, setComment] = useState("");
  const done = () => { setEditing(null); setReturning(null); setComment(""); reload(); decided.reload(); };
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return (
    <div className="space-y-4">
      {problem && <ErrorBox message={problem} />}
      {data.length === 0 ? <EmptyState message="Nothing is waiting for you" hint="What your residents and interns prepare appears here." icon={ListChecks} /> : (
        <ul className="divide-y">{data.map((r) => (
          <Row key={r.id} r={r}>
            <div className="flex flex-wrap items-end gap-2">
              <Button type="button" disabled={busy} onClick={async () => { if (await run(() => approveCountersign(r.id), "Approved")) done(); }}>Approve</Button>
              {r.kind === "PRESCRIPTION" && <Button type="button" variant="secondary" onClick={() => setEditing(r.id)}>Edit and approve</Button>}
              <Button type="button" variant="secondary" onClick={() => setReturning(r.id)}>Return with a comment</Button>
            </div>
            {returning === r.id && (
              <div className="flex flex-wrap items-end gap-2 rounded-xl bg-slate-50 p-2"><Field label="What should change? *"><Input maxLength={500} value={comment} onChange={(e) => setComment(e.target.value)} /></Field>
                <Button type="button" disabled={busy || comment.trim().length < 3} onClick={async () => { if (await run(() => returnCountersign(r.id, comment.trim()), "Returned")) done(); }}>Return</Button></div>)}
          </Row>))}</ul>)}
      {decided.data && decided.data.length > 0 && <details className="text-sm"><summary className="cursor-pointer font-semibold text-slate-700">Decided earlier ({decided.data.length})</summary><ul className="divide-y">{decided.data.map((r) => <Row key={r.id} r={r} />)}</ul></details>}
      {editing && <EditDialog id={editing} onClose={() => setEditing(null)} onDone={done} />}
    </div>
  );
}

function Mine() {
  const { data, loading, error, reload } = useFetch(listMySubmissions);
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return data.length === 0 ? <EmptyState message="You have not sent anything for countersign" hint="Prescriptions (residents) and orders (interns) wait here for your consultant." icon={ListChecks} /> : <ul className="divide-y">{data.map((r) => <Row key={r.id} r={r} />)}</ul>;
}

export default function Countersign() {
  const { user } = useAuth();
  const consultant = !user.grade || user.grade === "CONSULTANT";
  return (
    <div className="space-y-5">
      <PageTitle title={consultant ? "Awaiting my countersign" : "Pending approval"} subtitle={consultant ? "Prescriptions, orders and discharge summaries prepared by the doctors you supervise" : "What you sent to your consultant, and what they answered"} icon={ListChecks} />
      <Section>{consultant ? <Awaiting /> : <Mine />}</Section>
    </div>
  );
}
