// The nurse's workspace. Dashboard: alerts and inpatients, overdue medicines first. Chart: vitals, medicines to give (MAR), intake and output, notes, care plan, handover.
// A dose that was given, refused or held is recorded with the name and the time and cannot be changed.
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AlertTriangle, ClipboardList } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import useSave from "../../hooks/useSave";
import { ackAlert, actOnDose, chartIntakeOutput, chartNote, chartVitals, getChart, nurseDashboard } from "../../services/careApi";
import { Section } from "../../components/HealthCard";
import { EmptyState, ErrorBox, Loading, PageTitle } from "../../components/Feedback";
import { Button, Field, Input, Select, Textarea, fmtDateTime, fmtUtc } from "../../components/ui";

const Alert = ({ a, onAck }) => (
  <li className={`flex flex-wrap items-center justify-between gap-2 rounded-xl px-3 py-2 ${a.level === "CRITICAL" ? "bg-red-100 text-red-900" : "bg-amber-100 text-amber-900"}`}>
    <span><b>{a.level}</b> · {a.patient_name} ({a.uhid}): {a.message}</span>{onAck && <Button type="button" variant="secondary" onClick={() => onAck(a)}>Acknowledge</Button>}
  </li>
);

export function NurseDashboard() {
  const { data, loading, error, reload } = useFetch(nurseDashboard);
  const { problem, run } = useSave();
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return (
    <div className="space-y-5">
      <PageTitle title="Ward worklist" subtitle="Alerts first, then the patients who need you" icon={ClipboardList} />
      {problem && <ErrorBox message={problem} />}
      <Section title={`Alerts (${data.open_alerts})`}>
        {data.alerts.length === 0 ? <p className="text-slate-500">No open alerts.</p> : <ul className="space-y-2">{data.alerts.map((a) => <Alert key={a.id} a={a} onAck={async (x) => { if (await run(() => ackAlert(x.id), "Alert acknowledged")) reload(); }} />)}</ul>}
      </Section>
      <Section title="Inpatients">
        {data.patients.length === 0 ? <EmptyState message="No inpatients" hint="Admitted patients appear here." /> : (
          <ul className="divide-y">{data.patients.map((p) => (
            <li key={p.admission_id}><Link to={`/nurse/chart/${p.admission_id}`} className="flex flex-wrap items-center justify-between gap-2 py-3 hover:bg-slate-50">
              <span><b>{p.patient.full_name}</b> <span className="text-sm text-slate-500">{p.patient.uhid} · {p.bed || "no bed"}</span></span>
              <span className="flex items-center gap-2 text-sm">{p.open_alerts > 0 && <span className="rounded-full bg-red-100 px-2 py-0.5 font-bold text-red-800">{p.open_alerts} alert</span>}
                {p.overdue_doses > 0 && <span className="rounded-full bg-amber-100 px-2 py-0.5 font-bold text-amber-900">{p.overdue_doses} overdue</span>}<span className="text-slate-500">{p.pending_doses} doses pending</span></span></Link></li>))}</ul>)}
      </Section>
    </div>
  );
}

const VIT = [["pulse", "Pulse"], ["bp_systolic", "BP upper"], ["bp_diastolic", "BP lower"], ["spo2", "Oxygen %"], ["temperature_f", "Temp °F"], ["resp_rate", "Breathing"], ["gcs", "GCS"], ["pain_score", "Pain 0-10"]];

export function NurseChart() {
  const { id } = useParams();
  const { data, loading, error, reload } = useFetch(() => getChart(id), [id]);
  const { problem, busy, run } = useSave();
  const [vit, setVit] = useState({});
  const [note, setNote] = useState({ kind: "NOTE", shift: "MORNING", text: "" });
  const [io, setIo] = useState({ kind: "INTAKE", item: "", amount_ml: "" });
  const [decline, setDecline] = useState(null);
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const a = data.admission;
  const closed = a.status !== "ADMITTED";
  const act = async (fn, msg) => { if (await run(fn, msg)) reload(); };
  const vitals = Object.fromEntries(Object.entries(vit).filter(([, v]) => v !== "").map(([k, v]) => [k, Number(v)]));
  return (
    <div className="space-y-5">
      <PageTitle title={a.patient.full_name} subtitle={`${a.patient.uhid} · ${a.admission_no} · ${a.bed ? `${a.bed.ward} ${a.bed.code}` : "no bed"} · ${a.admitting_diagnosis || ""}`} />
      {data.alerts.length > 0 && <ul className="space-y-2" aria-label="Open alerts">{data.alerts.map((x) => <Alert key={x.id} a={x} onAck={(y) => act(() => ackAlert(y.id), "Alert acknowledged")} />)}</ul>}
      {problem && <ErrorBox message={problem} />}

      <Section title={`Medicines today (${data.pending_doses} pending${data.overdue_doses ? `, ${data.overdue_doses} overdue` : ""})`}>
        {data.mar.length === 0 ? <p className="text-slate-500">No medicines are scheduled today.</p> : (
          <ul className="divide-y">{data.mar.map((m) => (
            <li key={m.id} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
              <span className={m.status !== "PENDING" ? "text-slate-500" : ""}><b>{fmtDateTime(m.scheduled_at).split(",").pop()}</b> · {m.medicine_name} {m.dose} {m.route || ""}{m.instructions && <span className="text-sm text-slate-500"> ({m.instructions})</span>}{m.overdue && <span className="ml-2 rounded-full bg-amber-100 px-2 py-0.5 text-xs font-bold text-amber-900">Overdue</span>}</span>
              {m.status === "PENDING" && !closed ? (
                <span className="flex gap-2"><Button type="button" disabled={busy} onClick={() => act(() => actOnDose(m.id, "GIVEN"), "Recorded as given")}>Given</Button>
                  <Button type="button" variant="secondary" onClick={() => setDecline({ id: m.id, status: "REFUSED", note: "" })}>Refused</Button><Button type="button" variant="secondary" onClick={() => setDecline({ id: m.id, status: "HELD", note: "" })}>Hold</Button></span>
              ) : <span className="text-sm font-semibold text-slate-600">{m.status.toLowerCase()} {m.acted_at ? fmtUtc(m.acted_at) : ""}{m.note ? ` (${m.note})` : ""}</span>}
            </li>))}</ul>)}
        {decline && (
          <div className="mt-3 flex flex-wrap items-end gap-2 rounded-xl bg-slate-50 p-3"><Field label={`Why was it ${decline.status === "REFUSED" ? "refused" : "held"}? *`}><Input maxLength={300} value={decline.note} onChange={(e) => setDecline({ ...decline, note: e.target.value })} /></Field>
            <Button type="button" disabled={busy || decline.note.trim().length < 2} onClick={async () => { await act(() => actOnDose(decline.id, decline.status, decline.note), "Recorded"); setDecline(null); }}>Save</Button><Button type="button" variant="secondary" onClick={() => setDecline(null)}>Cancel</Button></div>)}
      </Section>

      {!closed && (
        <Section title="Record vital signs">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-8">{VIT.map(([k, l]) => <Field key={k} label={l}><Input type="number" step="any" value={vit[k] ?? ""} onChange={(e) => setVit({ ...vit, [k]: e.target.value })} /></Field>)}</div>
          <div className="mt-2"><Button type="button" disabled={busy || Object.keys(vitals).length === 0} onClick={() => act(() => chartVitals(id, vitals).then(() => setVit({})), "Vitals saved")}>Save vitals</Button></div>
        </Section>)}
      <Section title="Recent vitals">
        {data.vitals.length === 0 ? <p className="text-slate-500">None yet.</p> : <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr className="border-b text-xs uppercase text-slate-500"><th className="py-1">Time</th>{VIT.map(([, l]) => <th key={l}>{l}</th>)}<th>By</th></tr></thead>
          <tbody>{data.vitals.slice(0, 8).map((v) => <tr key={v.id} className="border-b"><td className="py-1">{fmtUtc(v.recorded_at)}</td>{VIT.map(([k]) => <td key={k}>{v[k] ?? "-"}</td>)}<td>{v.recorded_by}</td></tr>)}</tbody></table></div>}
      </Section>

      <Section title={`Intake and output today (balance ${data.totals.balance > 0 ? "+" : ""}${data.totals.balance} ml)`}>
        {!closed && <div className="mb-3 grid gap-2 sm:grid-cols-[8rem_1fr_8rem_auto] sm:items-end"><Field label="Kind"><Select value={io.kind} onChange={(e) => setIo({ ...io, kind: e.target.value })}><option value="INTAKE">Intake</option><option value="OUTPUT">Output</option></Select></Field><Field label="What"><Input maxLength={100} value={io.item} onChange={(e) => setIo({ ...io, item: e.target.value })} /></Field>
          <Field label="ml"><Input type="number" min="1" max="10000" value={io.amount_ml} onChange={(e) => setIo({ ...io, amount_ml: e.target.value })} /></Field><Button type="button" variant="secondary" disabled={busy || io.item.trim().length < 2 || !io.amount_ml} onClick={() => act(() => chartIntakeOutput(id, { kind: io.kind, item: io.item, amount_ml: Number(io.amount_ml) }).then(() => setIo({ ...io, item: "", amount_ml: "" })), "Recorded")}>Add</Button></div>}
        <p className="text-sm text-slate-700">Intake {data.totals.intake} ml · Output {data.totals.output} ml</p>
      </Section>

      <Section title="Notes, care plan and handover">
        {data.care_plan && <p className="mb-2 rounded-xl bg-sky-50 p-3 text-sm"><b>Care plan:</b> {data.care_plan.text} <span className="text-slate-500">({data.care_plan.by})</span></p>}
        {data.handover && <p className="mb-3 rounded-xl bg-violet-50 p-3 text-sm"><b>Last handover ({data.handover.shift.toLowerCase()}):</b> {data.handover.text} <span className="text-slate-500">({data.handover.by})</span></p>}
        {!closed && <div className="grid gap-2 sm:grid-cols-[9rem_8rem_1fr_auto] sm:items-end"><Field label="Kind"><Select value={note.kind} onChange={(e) => setNote({ ...note, kind: e.target.value })}><option value="NOTE">Note</option><option value="CARE_PLAN">Care plan</option><option value="HANDOVER">Handover</option></Select></Field>
          <Field label="Shift"><Select disabled={note.kind !== "HANDOVER"} value={note.shift} onChange={(e) => setNote({ ...note, shift: e.target.value })}><option value="MORNING">Morning</option><option value="EVENING">Evening</option><option value="NIGHT">Night</option></Select></Field>
          <Field label="Text"><Textarea rows={2} maxLength={3000} value={note.text} onChange={(e) => setNote({ ...note, text: e.target.value })} /></Field>
          <Button type="button" disabled={busy || note.text.trim().length < 3} onClick={() => act(() => chartNote(id, { kind: note.kind, shift: note.kind === "HANDOVER" ? note.shift : null, text: note.text }).then(() => setNote({ ...note, text: "" })), "Note saved")}>Save</Button></div>}
        <ul className="mt-3 space-y-1 text-sm">{data.notes.map((n) => <li key={n.id}><b>{fmtUtc(n.at)}</b> · {n.by} · <span className="text-slate-500">{n.kind.toLowerCase().replace("_", " ")}</span><br />{n.text}</li>)}</ul>
      </Section>
    </div>
  );
}
