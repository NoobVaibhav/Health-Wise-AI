// A nurse or doctor asks the pharmacy for medicines for an admitted patient, and sees what the pharmacy answered.
// Requested, issued by the pharmacy and given to the patient (the MAR) are three different records.
import { useState } from "react";
import { Pill } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import useSave from "../../hooks/useSave";
import { listAdmissions } from "../../services/careApi";
import { createMedicineRequest, getMedicineRequests } from "../../services/operationsApi";
import { Section } from "../../components/HealthCard";
import { EmptyState, ErrorBox, Loading, PageTitle } from "../../components/Feedback";
import { Button, Field, Input, Select } from "../../components/ui";

export default function WardRequests() {
  const admissions = useFetch(() => listAdmissions());
  const mine = useFetch(() => getMedicineRequests());
  const [form, setForm] = useState({ admission_id: "", medicine_name: "", quantity: "1" });
  const [lines, setLines] = useState([]);
  const { problem, busy, run } = useSave();
  if (admissions.loading && !admissions.data) return <Loading />;
  if (admissions.error) return <ErrorBox message={admissions.error} onRetry={admissions.reload} />;
  return (
    <div className="space-y-5">
      <PageTitle title="Medicines for the ward" subtitle="Ask the pharmacy for medicines for an admitted patient." icon={Pill} />
      <Section title="New request">
        <Field label="Patient *"><Select value={form.admission_id} onChange={(e) => setForm({ ...form, admission_id: e.target.value })}><option value="">Choose</option>{(admissions.data || []).map((a) => <option key={a.id} value={a.id}>{a.patient.full_name} ({a.bed ? `${a.bed.ward} ${a.bed.code}` : "no bed"})</option>)}</Select></Field>
        <div className="mt-2 flex flex-wrap items-end gap-2"><Field label="Medicine"><Input maxLength={200} value={form.medicine_name} onChange={(e) => setForm({ ...form, medicine_name: e.target.value })} /></Field><Field label="Quantity"><Input inputMode="numeric" value={form.quantity} onChange={(e) => setForm({ ...form, quantity: e.target.value })} /></Field>
          <Button variant="secondary" disabled={form.medicine_name.trim().length < 2 || !(Number(form.quantity) > 0)} onClick={() => { setLines([...lines, { medicine_name: form.medicine_name.trim(), quantity: Number(form.quantity) }]); setForm({ ...form, medicine_name: "", quantity: "1" }); }}>Add to the list</Button></div>
        <ul className="my-2 text-sm">{lines.map((l, i) => <li key={i}>{l.medicine_name} x {l.quantity}</li>)}</ul>
        {problem && <ErrorBox message={problem} />}
        <Button disabled={busy || !form.admission_id || lines.length === 0} onClick={async () => { if (await run(() => createMedicineRequest({ admission_id: Number(form.admission_id), items: lines }), "Request sent to the pharmacy")) { setLines([]); mine.reload(); } }}>Send to the pharmacy</Button>
      </Section>
      <Section title="My requests">
        {mine.loading && !mine.data ? <Loading /> : (mine.data || []).length === 0 ? <EmptyState message="No request yet" icon={Pill} /> : mine.data.map((r) => (
          <div key={r.id} className="border-b border-slate-100 py-2 last:border-0"><p className="font-bold">{r.patient_name} <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs">{r.status}</span></p>
            <ul className="text-sm text-slate-700">{r.items.map((i) => <li key={i.id}>{i.medicine_name}: {i.issued_quantity} of {i.quantity} issued</li>)}</ul>{r.decision_note && <p className="text-sm text-slate-500">{r.decision_note}</p>}</div>))}
      </Section>
    </div>
  );
}
