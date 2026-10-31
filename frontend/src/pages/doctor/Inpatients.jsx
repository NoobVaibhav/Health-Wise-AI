// The doctor's inpatients: the list, and one stay (progress notes, medicines, orders, nursing chart summary, discharge summary and discharge).
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { BedDouble } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import useSave from "../../hooks/useSave";
import { addAdmissionOrder, addMedicationOrder, addProgressNote, approveDischargeSummary, assignStaff, dischargePatient, getAdmission, getChart, listAdmissions, saveDischargeSummary, staffOptions, stopMedication } from "../../services/careApi";
import { Section } from "../../components/HealthCard";
import { EmptyState, ErrorBox, Loading, PageTitle } from "../../components/Feedback";
import { Button, Field, Input, Select, Textarea, fmtUtc } from "../../components/ui";

export default function Inpatients() {
  const { data, loading, error, reload } = useFetch(() => listAdmissions("ADMITTED"), []);
  return (
    <div className="space-y-5">
      <PageTitle title="My inpatients" subtitle="Patients admitted under you or where you are a consulting doctor" icon={BedDouble} />
      {loading && !data ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> : data.length === 0 ? <EmptyState message="No inpatients" hint="Admit a patient from a consultation or from the emergency department." icon={BedDouble} /> : (
        <ul className="space-y-3">{data.map((a) => (
          <li key={a.id}><Link to={`/doctor/inpatients/${a.id}`} className="flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm hover:border-brand-300">
            <span><b>{a.patient.full_name}</b> <span className="text-sm text-slate-500">{a.patient.uhid} · {a.admission_no} · {a.admitting_diagnosis || "no diagnosis yet"}</span></span>
            <span className="text-sm text-slate-600">{a.bed ? `${a.bed.ward} ${a.bed.code}` : "No bed yet"} · since {fmtUtc(a.admitted_at)}</span></Link></li>))}</ul>)}
    </div>
  );
}

export function InpatientDetail() {
  const { id } = useParams();
  const { data, loading, error, reload } = useFetch(() => getAdmission(id), [id]);
  const chart = useFetch(() => getChart(id), [id]);
  const { problem, busy, run } = useSave();
  const [note, setNote] = useState("");
  const [med, setMed] = useState({ medicine_name: "", dose: "", route: "", times: "08:00,20:00" });
  const [order, setOrder] = useState({ kind: "LAB", text: "", priority: "ROUTINE" });
  const [summary, setSummary] = useState(null);
  const [staff, setStaff] = useState({ user_id: "", kind: "CONSULTING_DOCTOR" });
  const options = useFetch(() => staffOptions(staff.kind), [staff.kind]);
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const a = data.admission;
  const done = a.status === "DISCHARGED";
  const sum = summary || data.discharge_summary || {};
  const set = (k) => (e) => setSummary({ ...sum, [k]: e.target.value });
  const act = async (fn, msg) => { if (await run(fn, msg)) { reload(); chart.reload(); } };
  const times = med.times.split(",").map((t) => t.trim()).filter(Boolean);

  return (
    <div className="space-y-5">
      <PageTitle title={a.patient.full_name} subtitle={`${a.patient.uhid} · ${a.admission_no} · ${a.bed ? `${a.bed.ward} ${a.bed.code}` : "no bed yet"} · ${done ? "discharged" : "admitted " + fmtUtc(a.admitted_at)}`} />
      <p className="text-sm text-slate-600">Treating doctor: <b>{a.attending_doctor}</b> · {a.admitting_diagnosis} {a.staff.length > 0 && <>· Team: {a.staff.map((s) => `${s.name} (${s.kind === "NURSE" ? "nurse" : "consultant"})`).join(", ")}</>}</p>
      {data.alerts.map((x) => <p key={x.id} role="alert" className={`rounded-xl px-3 py-2 font-bold ${x.level === "CRITICAL" ? "bg-red-100 text-red-800" : "bg-amber-100 text-amber-900"}`}>{x.level}: {x.message}</p>)}
      {problem && <ErrorBox message={problem} />}

      {!done && (
        <Section title="Progress note">
          <div className="space-y-2"><Textarea rows={3} maxLength={4000} aria-label="Progress note" value={note} onChange={(e) => setNote(e.target.value)} />
            <Button type="button" disabled={busy || note.trim().length < 3} onClick={() => act(() => addProgressNote(id, note).then(() => setNote("")), "Note added")}>Add note</Button>
            <p className="text-xs text-slate-500">A note is never edited. A correction is a new note.</p></div>
        </Section>)}
      <Section title="Notes so far">
        <ul className="space-y-2">{data.progress_notes.map((n) => <li key={n.id} className="rounded-xl bg-slate-50 p-3 text-sm"><b>{fmtUtc(n.created_at)}</b> · {n.doctor}{n.corrects_id && <span className="text-amber-700"> · correction of note {n.corrects_id}</span>}<br /><span className="whitespace-pre-line">{n.note}</span></li>)}{data.progress_notes.length === 0 && <li className="text-slate-500">None yet.</li>}</ul>
      </Section>

      <Section title="Medicines ordered">
        <ul className="mb-3 space-y-1">{data.medication_orders.map((m) => <li key={m.id} className="flex flex-wrap items-center justify-between gap-2"><span className={m.status === "STOPPED" ? "text-slate-400 line-through" : ""}><b>{m.medicine_name}</b> {m.dose} {m.route || ""} at {m.times.join(", ")}</span>
          {m.status === "ACTIVE" && !done && <button type="button" className="text-sm font-semibold text-red-700 underline" onClick={() => act(() => stopMedication(m.id), "Medicine stopped")}>Stop</button>}</li>)}{data.medication_orders.length === 0 && <li className="text-slate-500">None yet.</li>}</ul>
        {!done && <div className="grid gap-2 sm:grid-cols-[1fr_8rem_7rem_1fr_auto] sm:items-end"><Field label="Medicine"><Input maxLength={200} value={med.medicine_name} onChange={(e) => setMed({ ...med, medicine_name: e.target.value })} /></Field><Field label="Dose"><Input maxLength={100} value={med.dose} onChange={(e) => setMed({ ...med, dose: e.target.value })} /></Field>
          <Field label="Route"><Input maxLength={40} placeholder="IV, oral" value={med.route} onChange={(e) => setMed({ ...med, route: e.target.value })} /></Field><Field label="Times (HH:MM, comma)"><Input value={med.times} onChange={(e) => setMed({ ...med, times: e.target.value })} /></Field>
          <Button type="button" variant="secondary" disabled={busy || med.medicine_name.trim().length < 2 || !med.dose.trim() || times.length === 0} onClick={() => act(() => addMedicationOrder(id, { medicine_name: med.medicine_name, dose: med.dose, route: med.route || null, times }).then(() => setMed({ ...med, medicine_name: "", dose: "" })), "Medicine ordered")}>Order</Button></div>}
      </Section>

      <Section title="Orders">
        <ul className="mb-3 space-y-1">{data.orders.map((o) => <li key={o.id}><b>{o.kind}</b> · {o.text} <span className="text-sm text-slate-500">· {o.priority.toLowerCase()} · {o.status.toLowerCase()}</span></li>)}{data.orders.length === 0 && <li className="text-slate-500">None yet.</li>}</ul>
        {!done && <div className="grid gap-2 sm:grid-cols-[9rem_1fr_9rem_auto] sm:items-end"><Field label="Kind"><Select value={order.kind} onChange={(e) => setOrder({ ...order, kind: e.target.value })}>{["LAB", "RADIOLOGY", "PROCEDURE", "DIET", "NURSING", "OTHER"].map((k) => <option key={k}>{k}</option>)}</Select></Field>
          <Field label="What"><Input maxLength={300} value={order.text} onChange={(e) => setOrder({ ...order, text: e.target.value })} /></Field><Field label="Priority"><Select value={order.priority} onChange={(e) => setOrder({ ...order, priority: e.target.value })}><option>ROUTINE</option><option>URGENT</option><option>STAT</option></Select></Field>
          <Button type="button" variant="secondary" disabled={busy || order.text.trim().length < 2} onClick={() => act(() => addAdmissionOrder(id, order).then(() => setOrder({ ...order, text: "" })), "Order placed")}>Order</Button></div>}
      </Section>

      {!done && (
        <Section title="Care team">
          <div className="grid gap-2 sm:grid-cols-[10rem_1fr_auto] sm:items-end"><Field label="Add"><Select value={staff.kind} onChange={(e) => setStaff({ user_id: "", kind: e.target.value })}><option value="CONSULTING_DOCTOR">Consulting doctor</option><option value="NURSE">Nurse</option></Select></Field>
            <Field label="Person"><Select value={staff.user_id} onChange={(e) => setStaff({ ...staff, user_id: e.target.value })}><option value="">Choose</option>{(options.data || []).filter((o) => o.name !== a.attending_doctor).map((o) => <option key={o.user_id} value={o.user_id}>{o.name}</option>)}</Select></Field>
            <Button type="button" variant="secondary" disabled={busy || !staff.user_id} onClick={() => act(() => assignStaff(id, Number(staff.user_id), staff.kind), "Assigned")}>Assign</Button></div>
        </Section>)}

      {chart.data && <Section title="Nursing at a glance" action={<span className="text-sm text-slate-500">{chart.data.pending_doses} doses pending, {chart.data.overdue_doses} overdue</span>}>
        <p className="text-sm text-slate-700">{chart.data.vitals[0] ? `Last vitals ${fmtUtc(chart.data.vitals[0].recorded_at)}: pulse ${chart.data.vitals[0].pulse ?? "-"}, BP ${chart.data.vitals[0].bp_systolic ?? "-"}/${chart.data.vitals[0].bp_diastolic ?? "-"}, oxygen ${chart.data.vitals[0].spo2 ?? "-"}` : "No vitals recorded yet."}</p>
        <p className="text-sm text-slate-700">Today: intake {chart.data.totals.intake} ml, output {chart.data.totals.output} ml</p>
        {chart.data.care_plan && <p className="mt-1 text-sm"><b>Care plan:</b> {chart.data.care_plan.text}</p>}
      </Section>}

      <Section title="Discharge summary">
        {sum.status === "APPROVED" && <p className="mb-3 rounded-xl bg-emerald-50 p-3 font-semibold text-emerald-900">Approved {fmtUtc(sum.approved_at)}. It can no longer be changed.</p>}
        <div className="grid gap-3 sm:grid-cols-2">{[["final_diagnosis", "Final diagnosis *"], ["hospital_course", "Hospital course *"], ["procedures", "Procedures"], ["investigations_summary", "Investigations"], ["discharge_medicines", "Discharge medicines"], ["follow_up", "Follow-up *"], ["diet_advice", "Diet"], ["warning_signs", "Warning signs"]].map(([k, l]) => (
          <Field key={k} label={l}><Textarea rows={3} maxLength={5000} disabled={done || sum.status === "APPROVED"} value={sum[k] ?? ""} onChange={set(k)} /></Field>))}</div>
        {!done && sum.status !== "APPROVED" && <div className="mt-3 flex flex-wrap gap-2"><Button type="button" variant="secondary" disabled={busy} onClick={() => act(() => saveDischargeSummary(id, Object.fromEntries(["final_diagnosis", "hospital_course", "procedures", "investigations_summary", "discharge_medicines", "follow_up", "diet_advice", "warning_signs"].map((k) => [k, sum[k] || null]))).then(() => setSummary(null)), "Summary saved")}>Save summary</Button>
          <Button type="button" disabled={busy} onClick={() => act(() => approveDischargeSummary(id), "Summary approved")}>Approve as the treating doctor</Button></div>}
        {!done && sum.status === "APPROVED" && <div className="mt-3"><Button type="button" variant="danger" disabled={busy} onClick={() => { if (window.confirm("Discharge this patient now? The bed will be sent to cleaning.")) act(() => dischargePatient(id), "Patient discharged"); }}>Discharge the patient</Button></div>}
      </Section>
    </div>
  );
}
