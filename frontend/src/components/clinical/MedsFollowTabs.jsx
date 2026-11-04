// Medication history (prescribed, dispensed and taken are different facts) and the follow-up tracker.
import { useState } from "react";
import { Plus } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import { createFollowUp, getFollowUps, getMedicationHistory, updateFollowUp } from "../../services/clinicalApi";
import { getErrorMessage } from "../../services/api";
import { Section } from "../HealthCard";
import { Button, Input, Textarea, fmtDate, inputClass } from "../ui";
import { ErrorBox, Loading } from "../Feedback";
import { useToast } from "../Toast";
import { SourceChip } from "./Statement";

const Flags = ({ title, items, tone, onOpen }) => items?.length ? (
  <div className={`mb-2 rounded-2xl border p-3 ${tone}`}><p className="mb-1 text-sm font-extrabold">{title}</p>
    <ul className="space-y-1 text-sm">{items.map((x, i) => <li key={i} className="flex flex-wrap items-center gap-2"><span>{x.text}</span>{x.source && <SourceChip source={x.source} onOpen={onOpen} />}</li>)}</ul></div>
) : null;

export function MedicationsTab({ patientId, onOpen }) {
  const { data, loading, error, reload } = useFetch(() => getMedicationHistory(patientId), [patientId]);
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return (
    <div className="space-y-4">
      <Section title="Medication history">
        <p className="-mt-2 mb-3 rounded-xl bg-slate-100 p-3 text-sm text-slate-700">{data.note}</p>
        <Flags title="For clinical review: allergy matches" items={data.allergy_flags} tone="border-red-300 bg-red-50 text-red-900" />
        <Flags title="For clinical review: possible duplicate therapy" items={data.duplicates} tone="border-amber-300 bg-amber-50 text-amber-900" onOpen={onOpen} />
        <Flags title="Changed between prescriptions" items={data.changes} tone="border-sky-200 bg-sky-50 text-sky-900" onOpen={onOpen} />
        <Flags title="Newly prescribed (last 30 days)" items={data.new} tone="border-emerald-200 bg-emerald-50 text-emerald-900" onOpen={onOpen} />
        <Flags title="Stopped (prescription cancelled)" items={data.stopped} tone="border-slate-300 bg-slate-50 text-slate-800" onOpen={onOpen} />
        {data.medicines.length === 0 ? <p className="text-slate-500">No prescriptions have been written for this patient.</p> : (
          <div className="mt-3 space-y-3">{data.medicines.map((m) => (
            <div key={m.name} className="rounded-2xl border border-slate-200 bg-white p-4">
              <div className="flex flex-wrap items-center justify-between gap-2"><p className="text-lg font-extrabold text-slate-900">{m.name}</p>
                <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${m.status === "OPEN" ? "bg-emerald-100 text-emerald-800" : m.status === "STOPPED" ? "bg-slate-200 text-slate-700" : "bg-slate-100 text-slate-600"}`}>{m.status === "OPEN" ? "Prescription open" : m.status === "STOPPED" ? "Prescription cancelled" : m.status.toLowerCase()}</span></div>
              {m.allergy_match && <p className="mt-1 text-sm font-bold text-red-800">{m.allergy_match}</p>}
              <table className="mt-2 w-full text-sm"><thead><tr className="text-left text-xs uppercase text-slate-400"><th className="pb-1">Prescribed</th><th>Doctor</th><th>Strength and how often</th><th>For</th><th>Dispensed by the pharmacy</th></tr></thead>
                <tbody>{m.entries.map((e) => (
                  <tr key={e.prescription_id + e.name} className="border-t border-slate-100 align-top"><td className="py-1.5">{fmtDate(e.prescribed_on)}<br /><SourceChip source={e.source} onOpen={onOpen} /></td><td>{e.doctor}</td>
                    <td>{[e.dose, e.frequency, e.duration].filter(Boolean).join(", ") || <i className="text-slate-400">not recorded</i>}</td><td>{e.indication || <i className="text-slate-400">not recorded</i>}</td>
                    <td>{e.dispensed.length ? e.dispensed.map((d) => `${d.quantity} on ${fmtDate(d.date)}`).join("; ") : <i className="text-slate-400">nothing dispensed</i>} <span className="text-xs text-slate-400">(of {e.prescribed_quantity} prescribed)</span></td></tr>))}</tbody></table>
              <p className="mt-2 text-xs text-slate-500">{m.start_note} {m.stop_note} Adherence: {m.adherence}</p>
            </div>))}</div>
        )}
        {data.reported_only.length > 0 && <div className="mt-4"><p className="mb-1 text-sm font-bold text-slate-700">Also entered in the permanent history (no prescription here)</p>
          <ul className="list-disc pl-5 text-sm text-slate-700">{data.reported_only.map((m) => <li key={m.name}>{m.name}{m.dose ? `, ${m.dose}` : ""}{m.frequency ? `, ${m.frequency}` : ""}{m.reason ? ` (for ${m.reason})` : ""}</li>)}</ul></div>}
        <Flags title="Details missing from the prescriptions" items={data.missing_details} tone="border-slate-200 bg-slate-50 text-slate-800" onOpen={onOpen} />
      </Section>
    </div>
  );
}

export function FollowUpsTab({ patientId, onOpen }) {
  const toast = useToast();
  const { data, loading, error, reload, setData } = useFetch(() => getFollowUps(patientId), [patientId]);
  const [form, setForm] = useState({ title: "", due_date: "", details: "" });
  const [closing, setClosing] = useState(null);
  const [outcome, setOutcome] = useState("");
  const [busy, setBusy] = useState(false);                // one request at a time: a double click must not add the task twice
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;

  const add = async (e) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    try { setData(await createFollowUp(patientId, { title: form.title, due_date: form.due_date || null, details: form.details || null })); setForm({ title: "", due_date: "", details: "" }); toast("Follow-up added"); } catch (err) { toast(getErrorMessage(err), "error"); } finally { setBusy(false); }
  };
  const close = async (task, status) => {
    if (busy) return;
    setBusy(true);
    try { setData(await updateFollowUp(patientId, task.id, { status, outcome: outcome || null })); setClosing(null); setOutcome(""); toast(status === "DONE" ? "Marked done" : "Cancelled"); } catch (err) { toast(getErrorMessage(err), "error"); } finally { setBusy(false); }
  };
  const pending = data.tasks.filter((t) => t.status === "PENDING");
  const closed = data.tasks.filter((t) => t.status !== "PENDING");

  return (
    <div className="space-y-4">
      <Section title="Follow-up tracker">
        <form onSubmit={add} className="mb-4 grid gap-2 rounded-2xl bg-slate-50 p-3 sm:grid-cols-[1fr_11rem_auto]">
          <Input required minLength={3} placeholder="What must happen? e.g. Repeat ECG, HbA1c in 3 months" value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} />
          <input type="date" aria-label="Due date" max={new Date(Date.now() + 730 * 864e5).toISOString().slice(0, 10)} className={inputClass} value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} />
          <Button disabled={busy}><Plus size={15} className="mr-1 inline" />Add</Button>
        </form>
        {pending.length === 0 && data.derived.length === 0 && <p className="text-slate-500">Nothing is pending.</p>}
        <ul className="space-y-2">
          {pending.map((t) => (
            <li key={t.id} className={`rounded-2xl border p-3 ${t.overdue ? "border-red-300 bg-red-50" : "border-slate-200 bg-white"}`}>
              <div className="flex flex-wrap items-center justify-between gap-2"><p className="font-bold text-slate-900">{t.title}</p>
                <span className={`rounded-full px-2 py-0.5 text-xs font-bold ${t.overdue ? "bg-red-600 text-white" : "bg-amber-100 text-amber-900"}`}>{t.due_date ? `${t.overdue ? "Overdue, due" : "Due"} ${fmtDate(t.due_date)}` : "No due date"}</span></div>
              <p className="text-xs text-slate-500">Added by {t.created_by}</p>
              {closing === t.id ? (
                <div className="mt-2 space-y-2"><Textarea rows={2} placeholder="Outcome (what was found or done)" value={outcome} onChange={(e) => setOutcome(e.target.value)} />
                  <div className="flex gap-2"><Button disabled={busy} onClick={() => close(t, "DONE")}>Mark done</Button><Button variant="secondary" disabled={busy} onClick={() => close(t, "CANCELLED")}>Cancel the task</Button><Button variant="secondary" onClick={() => setClosing(null)}>Back</Button></div></div>
              ) : <button type="button" onClick={() => setClosing(t.id)} className="mt-1 text-sm font-bold text-brand-700 hover:underline">Record the outcome</button>}
            </li>))}
          {data.derived.map((d, i) => (
            <li key={i} className={`rounded-2xl border p-3 ${d.overdue ? "border-amber-300 bg-amber-50" : "border-slate-200 bg-white"}`}>
              <p className="font-bold text-slate-900">{d.title}</p><p className="text-sm text-slate-700">{d.text}</p><div className="mt-1 flex items-center gap-2"><SourceChip source={d.source} onOpen={onOpen} />
                <button type="button" className="text-xs font-bold text-brand-700 hover:underline" onClick={() => setForm({ title: d.title.slice(0, 190), due_date: d.due_date || "", details: d.text })}>Make it a task</button></div>
            </li>))}
        </ul>
      </Section>
      {data.upcoming_appointments.length > 0 && <Section title="Upcoming appointments"><ul className="space-y-1.5 text-sm">{data.upcoming_appointments.map((a) => <li key={a.id} className="flex flex-wrap items-center gap-2"><b>{fmtDate(a.scheduled_at)}</b> with {a.doctor}{a.reason ? ` - ${a.reason}` : ""}<SourceChip source={a.source} onOpen={onOpen} /></li>)}</ul></Section>}
      {closed.length > 0 && <Section title="Closed"><ul className="space-y-1.5 text-sm">{closed.map((t) => <li key={t.id}><b>{t.title}</b> - {t.status === "DONE" ? "done" : "cancelled"}{t.outcome ? `: ${t.outcome}` : ""}</li>)}</ul></Section>}
    </div>
  );
}
