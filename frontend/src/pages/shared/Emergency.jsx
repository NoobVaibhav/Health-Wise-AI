// Emergency department: the board (most urgent first), rapid registration (also of an unknown person), triage, and for the doctor the treatment record and the outcome.
// Nothing on this page waits for AI. A critical triage or vital shows as an alert at once.
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Siren, UserPlus } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import useSave from "../../hooks/useSave";
import { useAuth } from "../../context/AuthContext";
import { edAssign, edBoard, edDisposition, edOrder, edRegister, edTimeline, edTriage, edVisit, listWards } from "../../services/careApi";
import { listDoctors } from "../../services/doctorApi";
import PatientPicker from "../../components/PatientPicker";
import { Section } from "../../components/HealthCard";
import { EmptyState, ErrorBox, Loading, PageTitle } from "../../components/Feedback";
import { Button, Field, Input, Modal, Select, Textarea, fmtUtc } from "../../components/ui";

const CATEGORY = { 1: ["1 Resuscitation", "bg-red-600 text-white"], 2: ["2 Emergent", "bg-orange-500 text-white"], 3: ["3 Urgent", "bg-amber-400 text-slate-900"], 4: ["4 Less urgent", "bg-emerald-500 text-white"], 5: ["5 Non-urgent", "bg-sky-500 text-white"] };
const Pill = ({ category }) => (category ? <span className={`rounded-full px-2.5 py-1 text-xs font-extrabold ${CATEGORY[category][1]}`}>{CATEGORY[category][0]}</span> : <span className="rounded-full bg-slate-200 px-2.5 py-1 text-xs font-bold text-slate-700">Not triaged</span>);
const VITALS = [["pulse", "Pulse"], ["bp_systolic", "BP upper"], ["bp_diastolic", "BP lower"], ["spo2", "Oxygen %"], ["temperature_f", "Temp °F"], ["resp_rate", "Breathing"]];

export default function Emergency() {
  const { user } = useAuth();
  const { data, loading, error, reload } = useFetch(edBoard);
  const [open, setOpen] = useState(null);
  const [registering, setRegistering] = useState(false);
  useEffect(() => { const t = setInterval(reload, 20000); return () => clearInterval(t); }, [reload]);
  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <PageTitle title="Emergency" subtitle="Everyone in the emergency department now, most urgent first" icon={Siren} />
        <Button type="button" onClick={() => setRegistering(true)}><UserPlus size={16} className="mr-1 inline" /> Register arrival</Button>
      </div>
      {loading && !data ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> : data.length === 0 ? <EmptyState message="Nobody is waiting" hint="Register an arrival when a patient comes in." icon={Siren} /> : (
        <ul className="space-y-3">
          {data.map((v) => (
            <li key={v.id}>
              <button type="button" onClick={() => setOpen(v.id)} aria-label={`Open emergency visit of ${v.patient.full_name}`} className="flex w-full flex-wrap items-center justify-between gap-2 rounded-2xl border border-slate-200 bg-white p-4 text-left shadow-sm hover:border-brand-300">
                <span><b className="text-slate-900">{v.patient.full_name}</b> <span className="text-sm text-slate-500">{v.patient.uhid} · {v.patient.age != null ? `${v.patient.age} y` : "age unknown"} · {v.chief_complaint}</span>
                  {v.unidentified && <span className="ml-2 rounded-full bg-violet-100 px-2 py-0.5 text-xs font-bold text-violet-800">Unidentified</span>}</span>
                <span className="flex items-center gap-2"><span className="text-sm text-slate-500">{v.waiting_minutes} min</span>{v.assigned_doctor && <span className="text-sm text-slate-600">{v.assigned_doctor}</span>}<Pill category={v.triage_category} /></span>
              </button>
            </li>))}
        </ul>)}
      {registering && <Register onClose={() => setRegistering(false)} onDone={(v) => { setRegistering(false); reload(); setOpen(v.id); }} />}
      {open && <Visit id={open} role={user.role} onClose={() => { setOpen(null); reload(); }} />}
    </div>
  );
}

function Register({ onClose, onDone }) {
  const { problem, busy, run } = useSave();
  const [known, setKnown] = useState(true);
  const [patient, setPatient] = useState(null);
  const [form, setForm] = useState({ chief_complaint: "", arrival_mode: "WALK_IN", gender: "", approx_age: "", description: "" });
  const submit = async (e) => {
    e.preventDefault();
    const body = { chief_complaint: form.chief_complaint, arrival_mode: form.arrival_mode };
    if (known) body.patient_id = patient?.id;
    else body.unidentified = { gender: form.gender || null, approx_age: form.approx_age === "" ? null : Number(form.approx_age), description: form.description || null };
    const result = await run(() => edRegister(body), "Arrival registered");
    if (result && result !== true) onDone(result);
  };
  return (
    <Modal title="Register an arrival" onClose={onClose}>
      <form onSubmit={submit} className="space-y-4" noValidate>
        <div className="flex gap-2">
          <Button type="button" variant={known ? "primary" : "secondary"} onClick={() => setKnown(true)}>Registered patient</Button>
          <Button type="button" variant={known ? "secondary" : "primary"} onClick={() => setKnown(false)}>Unknown person</Button>
        </div>
        {known ? <Field label="Patient"><PatientPicker value={patient} onChange={setPatient} /></Field> : (
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Sex"><Select value={form.gender} onChange={(e) => setForm({ ...form, gender: e.target.value })}><option value="">Not known</option><option value="male">Male</option><option value="female">Female</option><option value="other">Other</option></Select></Field>
            <Field label="Approximate age"><Input type="number" inputMode="decimal" min="0" max="120" value={form.approx_age} onChange={(e) => setForm({ ...form, approx_age: e.target.value })} /></Field>
            <Field label="Description"><Input maxLength={200} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
          </div>)}
        <Field label="What is wrong? *"><Input maxLength={300} value={form.chief_complaint} onChange={(e) => setForm({ ...form, chief_complaint: e.target.value })} /></Field>
        <Field label="Arrived by"><Select value={form.arrival_mode} onChange={(e) => setForm({ ...form, arrival_mode: e.target.value })}><option value="WALK_IN">On foot</option><option value="AMBULANCE">Ambulance</option><option value="POLICE">Police</option><option value="REFERRED">Referred</option></Select></Field>
        {problem && <ErrorBox message={problem} />}
        <Button disabled={busy || form.chief_complaint.trim().length < 2 || (known && !patient)}>{busy ? "Registering..." : "Register"}</Button>
      </form>
    </Modal>
  );
}

function Visit({ id, role, onClose }) {
  const { data, loading, error, reload } = useFetch(() => edVisit(id), [id]);
  const { data: doctors } = useFetch(role === "DOCTOR" ? listDoctors : () => Promise.resolve([]), [role]);
  const { problem, busy, run } = useSave();
  const [triage, setTriage] = useState({ category: "", note: "", vitals: {} });
  const [note, setNote] = useState({ kind: "ASSESSMENT", text: "" });
  const [order, setOrder] = useState({ kind: "LAB", text: "", priority: "URGENT" });
  const [outcome, setOutcome] = useState(null);
  const canTriage = role === "NURSE" || role === "DOCTOR";
  const isDoctor = role === "DOCTOR";
  const act = async (fn, message) => { if (await run(fn, message)) reload(); };
  const vitals = Object.fromEntries(Object.entries(triage.vitals).filter(([, v]) => v !== "").map(([k, v]) => [k, Number(v)]));
  return (
    <Modal title={data ? `${data.patient.full_name} (${data.patient.uhid})` : "Emergency visit"} onClose={onClose} wide>
      {loading && !data ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> : (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2"><Pill category={data.triage_category} /><span className="text-sm text-slate-600">{data.chief_complaint} · arrived {fmtUtc(data.arrival_at)}</span>
            {data.allergies && <span className="rounded-full bg-red-100 px-2.5 py-1 text-xs font-bold text-red-700">Allergy: {data.allergies}</span>}</div>
          {data.alerts.filter((a) => a.status === "OPEN").map((a) => <p key={a.id} role="alert" className={`rounded-xl px-3 py-2 font-bold ${a.level === "CRITICAL" ? "bg-red-100 text-red-800" : "bg-amber-100 text-amber-900"}`}>{a.level}: {a.message}</p>)}
          {data.status !== "DISPOSED" && canTriage && (
            <Section title="Triage">
              <div className="flex flex-wrap items-end gap-2">
                <Field label="Category"><Select value={triage.category} onChange={(e) => setTriage({ ...triage, category: e.target.value })}><option value="">Choose</option>{Object.entries(CATEGORY).map(([k, v]) => <option key={k} value={k}>{v[0]}</option>)}</Select></Field>
                <Field label="Note"><Input maxLength={300} value={triage.note} onChange={(e) => setTriage({ ...triage, note: e.target.value })} /></Field>
              </div>
              <div className="mt-3 grid grid-cols-3 gap-2 sm:grid-cols-6">{VITALS.map(([k, label]) => <Field key={k} label={label}><Input type="number" inputMode="decimal" step="any" value={triage.vitals[k] ?? ""} onChange={(e) => setTriage({ ...triage, vitals: { ...triage.vitals, [k]: e.target.value } })} /></Field>)}</div>
              <div className="mt-3"><Button type="button" disabled={!triage.category || busy} onClick={() => act(() => edTriage(id, { category: Number(triage.category), note: triage.note || null, vitals: Object.keys(vitals).length ? vitals : null }), "Triage saved")}>Save triage</Button></div>
            </Section>)}
          {isDoctor && data.status !== "DISPOSED" && (
            <Section title="Treatment">
              <div className="flex flex-wrap items-end gap-2">
                <Field label="Doctor in charge"><Select value={data.assigned_doctor_id || ""} onChange={(e) => e.target.value && act(() => edAssign(id, Number(e.target.value)), "Doctor assigned")}><option value="">Choose a doctor</option>{(doctors || []).map((d) => <option key={d.id} value={d.id}>{d.full_name}</option>)}</Select></Field>
              </div>
              <div className="mt-3 grid gap-2 sm:grid-cols-[10rem_1fr_auto] sm:items-end">
                <Field label="Entry"><Select value={note.kind} onChange={(e) => setNote({ ...note, kind: e.target.value })}><option value="ASSESSMENT">Assessment</option><option value="TREATMENT">Treatment given</option><option value="NOTE">Note</option></Select></Field>
                <Field label="Text"><Input maxLength={500} value={note.text} onChange={(e) => setNote({ ...note, text: e.target.value })} /></Field>
                <Button type="button" disabled={note.text.trim().length < 3 || busy} onClick={() => act(() => edTimeline(id, note).then(() => setNote({ ...note, text: "" })), "Added to the timeline")}>Add</Button>
              </div>
              <div className="mt-3 grid gap-2 sm:grid-cols-[8rem_1fr_8rem_auto] sm:items-end">
                <Field label="Order"><Select value={order.kind} onChange={(e) => setOrder({ ...order, kind: e.target.value })}>{["LAB", "RADIOLOGY", "PROCEDURE", "OTHER"].map((k) => <option key={k}>{k}</option>)}</Select></Field>
                <Field label="What"><Input maxLength={300} value={order.text} onChange={(e) => setOrder({ ...order, text: e.target.value })} /></Field>
                <Field label="Priority"><Select value={order.priority} onChange={(e) => setOrder({ ...order, priority: e.target.value })}><option>ROUTINE</option><option>URGENT</option><option>STAT</option></Select></Field>
                <Button type="button" disabled={order.text.trim().length < 2 || busy} onClick={() => act(() => edOrder(id, order).then(() => setOrder({ ...order, text: "" })), "Order placed")}>Order</Button>
              </div>
              <div className="mt-4"><Button type="button" variant="secondary" onClick={() => setOutcome({ disposition: "DISCHARGE", note: "", bed_id: "" })}>Decide the outcome</Button></div>
            </Section>)}
          <Section title="Timeline">
            <ol className="space-y-1 text-sm">{data.timeline.map((t) => <li key={t.id}><b>{t.kind}</b> · {t.text} <span className="text-slate-500">· {t.by || "system"} · {fmtUtc(t.at)}</span></li>)}</ol>
            {data.orders.length > 0 && <p className="mt-2 text-sm text-slate-600">Orders: {data.orders.map((o) => `${o.text} (${o.status.toLowerCase()})`).join(", ")}</p>}
            {data.vitals.length > 0 && <p className="mt-2 text-sm text-slate-600">Last vitals: {VITALS.map(([k, l]) => (data.vitals[0][k] != null ? `${l} ${data.vitals[0][k]}` : null)).filter(Boolean).join(" · ")}</p>}
          </Section>
          {data.status === "DISPOSED" && <p className="rounded-xl bg-slate-100 p-3 font-semibold">Outcome: {data.disposition}{data.disposition_note ? ` (${data.disposition_note})` : ""}{data.admission_id && <> · <Link className="text-brand-700 underline" to={`/doctor/inpatients/${data.admission_id}`}>open the admission</Link></>}</p>}
          {problem && <ErrorBox message={problem} />}
        </div>)}
      {outcome && <Outcome outcome={outcome} setOutcome={setOutcome} onClose={() => setOutcome(null)} onDone={() => { setOutcome(null); reload(); }} id={id} />}
    </Modal>
  );
}

function Outcome({ outcome, setOutcome, id, onClose, onDone }) {
  const { data: wards } = useFetch(listWards, []);
  const { problem, busy, run } = useSave();
  const beds = (wards || []).flatMap((w) => w.beds.filter((b) => b.status === "AVAILABLE").map((b) => ({ ...b, ward: w.name })));
  const admitting = outcome.disposition === "ADMIT" || outcome.disposition === "ICU";
  return (
    <Modal title="Outcome of the emergency visit" onClose={onClose}>
      <div className="space-y-3">
        <Field label="Outcome"><Select value={outcome.disposition} onChange={(e) => setOutcome({ ...outcome, disposition: e.target.value })}>
          {[["DISCHARGE", "Send home"], ["ADMIT", "Admit to a ward"], ["ICU", "Admit to ICU"], ["TRANSFER", "Transfer to another hospital"], ["LAMA", "Left against advice"], ["DEATH", "Died"]].map(([v, l]) => <option key={v} value={v}>{l}</option>)}</Select></Field>
        {admitting && <Field label="Bed (optional, can be given later)"><Select value={outcome.bed_id} onChange={(e) => setOutcome({ ...outcome, bed_id: e.target.value })}><option value="">No bed yet</option>{beds.map((b) => <option key={b.id} value={b.id}>{b.ward}: {b.code}</option>)}</Select></Field>}
        <Field label="Note"><Textarea rows={2} maxLength={500} value={outcome.note} onChange={(e) => setOutcome({ ...outcome, note: e.target.value })} /></Field>
        {problem && <ErrorBox message={problem} />}
        <Button type="button" disabled={busy} onClick={async () => { if (await run(() => edDisposition(id, { disposition: outcome.disposition, note: outcome.note || null, bed_id: outcome.bed_id ? Number(outcome.bed_id) : null }), "Outcome saved")) onDone(); }}>Confirm outcome</Button>
      </div>
    </Modal>
  );
}
