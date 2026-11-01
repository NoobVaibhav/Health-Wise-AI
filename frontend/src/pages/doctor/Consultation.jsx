// The consultation of one visit: vitals, the doctor's record (saved as a draft by itself), diagnoses, orders, the prescription, then sign.
// A signed consultation is locked; later changes are dated addenda. Nothing here is written by AI.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { CheckCircle2, CloudOff, Loader2, Lock, Pill } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import useSave from "../../hooks/useSave";
import { addAddendum, addDiagnosis, addOrder, addVitals, getWorkspace, saveConsultation, signConsultation, withdrawDiagnosis } from "../../services/careApi";
import { PrescriptionModal } from "../../components/DoctorForms";
import { AdmitDialog, ReferDialog } from "../../components/ClinicalDialogs";
import { Section } from "../../components/HealthCard";
import { ErrorBox, Loading, PageTitle } from "../../components/Feedback";
import { Button, Field, Input, Select, Textarea, fmtUtc } from "../../components/ui";
import { useAuth } from "../../context/AuthContext";

const CORE = [["complaint", "Complaint *", 2], ["hpi", "History of present illness", 4], ["past_history", "Past history", 2], ["family_history", "Family history", 2], ["examination", "Examination", 3], ["assessment", "Assessment", 3], ["plan", "Plan", 3], ["advice", "Advice to the patient", 3]];
const EMPTY = { complaint: "", hpi: "", past_history: "", family_history: "", examination: "", assessment: "", plan: "", advice: "", follow_up_date: "", data: {} };
const VITALS = [["pulse", "Pulse"], ["bp_systolic", "BP upper"], ["bp_diastolic", "BP lower"], ["spo2", "Oxygen %"], ["temperature_f", "Temp °F"], ["resp_rate", "Breathing"], ["weight_kg", "Weight kg"], ["height_cm", "Height cm"]];

export default function Consultation() {
  const { encounterId } = useParams();
  const { data: ws, loading, error, reload } = useFetch(() => getWorkspace(encounterId), [encounterId]);
  if (loading && !ws) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return <Workspace key={encounterId} ws={ws} reload={reload} />;
}

function Workspace({ ws, reload }) {
  const { user } = useAuth();
  const grade = user.grade || "CONSULTANT";
  const eid = ws.encounter.id;
  const signed = ws.consultation?.status === "SIGNED";
  const closed = ws.encounter.status !== "OPEN";
  const [form, setForm] = useState(() => ({ ...EMPTY, ...Object.fromEntries(Object.entries(ws.consultation || {}).filter(([k]) => k in EMPTY).map(([k, v]) => [k, v ?? EMPTY[k]])) }));
  const [saveState, setSaveState] = useState("idle");
  const [dx, setDx] = useState({ text: "", code: "" });
  const [order, setOrder] = useState({ kind: "LAB", text: "", priority: "ROUTINE" });
  const [vit, setVit] = useState({});
  const [addendum, setAddendum] = useState("");
  const [dialog, setDialog] = useState(null);
  const { problem, busy, run } = useSave();
  const dirty = useRef(false);
  const latest = useRef(form);
  latest.current = form;
  const readOnly = signed || closed;

  const save = useCallback(async () => {
    setSaveState("saving");
    const f = latest.current;
    try {
      await saveConsultation(eid, { ...Object.fromEntries(CORE.map(([k]) => [k, f[k] || null])), follow_up_date: f.follow_up_date || null, template_id: ws.template?.id ?? null, data: f.data });
      dirty.current = false;
      setSaveState("saved");
      return true;
    } catch { setSaveState("failed"); return false; }       // what was typed stays on the screen
  }, [eid, ws.template]);
  useEffect(() => {
    if (!dirty.current || readOnly) return undefined;
    const t = setTimeout(save, 1500);
    return () => clearTimeout(t);
  }, [form, readOnly, save]);
  useEffect(() => {
    const warn = (e) => { if (dirty.current) { e.preventDefault(); e.returnValue = ""; } };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, []);

  const set = (k) => (e) => { dirty.current = true; setForm((f) => ({ ...f, [k]: e.target.value })); };
  const setData = (k) => (e) => { dirty.current = true; setForm((f) => ({ ...f, data: { ...f.data, [k]: e.target.value } })); };
  const vitals = useMemo(() => Object.fromEntries(Object.entries(vit).filter(([, v]) => v !== "" && v != null).map(([k, v]) => [k, Number(v)])), [vit]);
  const sign = async () => {
    if (!(await save())) return;
    if (await run(() => signConsultation(eid), "Consultation signed")) reload();
  };
  const p = ws.patient;

  return (
    <div className="space-y-5 pb-4">
      <PageTitle title={p.full_name} subtitle={`${p.uhid} · ${p.age ?? "?"} years · ${p.gender || ""} ${ws.encounter.department_name ? "· " + ws.encounter.department_name : ""}`} />
      {p.allergies && <p role="alert" className="rounded-2xl bg-red-100 p-3 font-bold text-red-800">Allergies: {p.allergies}</p>}
      <div className="flex flex-wrap gap-2">
        <Link to={`/doctor/patients/${p.id}`} className="inline-flex min-h-11 items-center rounded-xl border-2 border-brand-700 bg-white px-4 py-2 font-bold text-brand-800">Full record</Link>
        {!closed && <Button type="button" variant="secondary" onClick={() => setDialog("refer")}>Refer to a department</Button>}
        <Button type="button" variant="secondary" onClick={() => setDialog("admit")}>Admit to a ward</Button>
        {grade !== "INTERN" && <Button type="button" variant="secondary" onClick={() => setDialog("rx")}><Pill size={15} className="mr-1 inline" /> {grade === "CONSULTANT" ? "Prescription" : "Prescription (consultant countersigns)"}</Button>}
      </div>
      {signed && <p className="flex items-center gap-2 rounded-2xl bg-emerald-50 p-3 font-semibold text-emerald-900"><Lock size={16} /> Signed {fmtUtc(ws.consultation.signed_at)}. It can no longer be changed; add an addendum below if something must be added.</p>}

      <Section title="Vital signs">
        {ws.vitals[0] && <p className="mb-2 text-sm text-slate-600">Last: {VITALS.map(([k, l]) => (ws.vitals[0][k] != null ? `${l} ${ws.vitals[0][k]}` : null)).filter(Boolean).join(" · ")} <span className="text-slate-400">({ws.vitals[0].recorded_by}, {fmtUtc(ws.vitals[0].recorded_at)})</span></p>}
        {!closed && (
          <>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-8">{VITALS.map(([k, l]) => <Field key={k} label={l}><Input type="number" step="any" value={vit[k] ?? ""} onChange={(e) => setVit({ ...vit, [k]: e.target.value })} /></Field>)}</div>
            <div className="mt-2"><Button type="button" variant="secondary" disabled={busy || Object.keys(vitals).length === 0} onClick={async () => { const r = await run(() => addVitals(eid, vitals), "Vitals saved"); if (r) { setVit({}); reload(); } }}>Save vitals</Button></div>
          </>)}
      </Section>

      <Section title="Consultation">
        <div className="space-y-4">
          {CORE.map(([k, label, rows]) => <Field key={k} label={label}><Textarea rows={rows} maxLength={4000} disabled={readOnly} value={form[k]} onChange={set(k)} /></Field>)}
          {ws.template && ws.template.fields.length > 0 && (
            <div className="rounded-2xl bg-slate-50 p-3"><p className="mb-2 font-bold text-slate-800">{ws.template.name}</p>
              <div className="grid gap-3 sm:grid-cols-2">{ws.template.fields.map((f) => (
                <Field key={f.key} label={f.label}>
                  {f.kind === "choice" ? <Select disabled={readOnly} value={form.data[f.key] ?? ""} onChange={setData(f.key)}><option value="">Not recorded</option>{f.options.map((o) => <option key={o}>{o}</option>)}</Select>
                    : f.kind === "longtext" ? <Textarea rows={2} disabled={readOnly} maxLength={3000} value={form.data[f.key] ?? ""} onChange={setData(f.key)} />
                      : <Input type={f.kind === "number" ? "number" : "text"} disabled={readOnly} maxLength={300} value={form.data[f.key] ?? ""} onChange={setData(f.key)} />}
                </Field>))}</div></div>)}
          <Field label="Follow-up on"><Input type="date" disabled={readOnly} min={new Date().toISOString().slice(0, 10)} value={form.follow_up_date} onChange={set("follow_up_date")} /></Field>
        </div>
      </Section>

      <Section title="Diagnosis">
        <ul className="mb-3 space-y-1">{ws.diagnoses.map((d) => <li key={d.id} className="flex items-center justify-between gap-2"><span><b>{d.text}</b> {d.code && <span className="text-sm text-slate-500">({d.code})</span>}</span>{!readOnly && <button type="button" className="text-sm font-semibold text-red-700 underline" onClick={async () => { if (await run(() => withdrawDiagnosis(d.id))) reload(); }}>Withdraw</button>}</li>)}
          {ws.diagnoses.length === 0 && <li className="text-slate-500">None yet.</li>}</ul>
        {!readOnly && <div className="grid gap-2 sm:grid-cols-[1fr_10rem_auto] sm:items-end"><Field label="Diagnosis"><Input maxLength={300} value={dx.text} onChange={(e) => setDx({ ...dx, text: e.target.value })} /></Field><Field label="Code (optional)"><Input maxLength={20} value={dx.code} onChange={(e) => setDx({ ...dx, code: e.target.value })} /></Field>
          <Button type="button" variant="secondary" disabled={busy || dx.text.trim().length < 2} onClick={async () => { if (await run(() => addDiagnosis(eid, { text: dx.text, code: dx.code || null }))) { setDx({ text: "", code: "" }); reload(); } }}>Add</Button></div>}
      </Section>

      <Section title="Orders">
        <ul className="mb-3 space-y-1">{ws.orders.map((o) => <li key={o.id}><b>{o.kind}</b> · {o.text} <span className="text-sm text-slate-500">· {o.priority.toLowerCase()} · {o.status.toLowerCase()}</span></li>)}{ws.orders.length === 0 && <li className="text-slate-500">None yet.</li>}</ul>
        {!closed && <div className="grid gap-2 sm:grid-cols-[9rem_1fr_9rem_auto] sm:items-end"><Field label="Kind"><Select value={order.kind} onChange={(e) => setOrder({ ...order, kind: e.target.value })}>{["LAB", "RADIOLOGY", "PROCEDURE", "DIET", "NURSING", "OTHER"].map((k) => <option key={k}>{k}</option>)}</Select></Field>
          <Field label="What"><Input maxLength={300} value={order.text} onChange={(e) => setOrder({ ...order, text: e.target.value })} /></Field><Field label="Priority"><Select value={order.priority} onChange={(e) => setOrder({ ...order, priority: e.target.value })}><option>ROUTINE</option><option>URGENT</option><option>STAT</option></Select></Field>
          <Button type="button" variant="secondary" disabled={busy || order.text.trim().length < 2} onClick={async () => { if (await run(() => addOrder(eid, order))) { setOrder({ ...order, text: "" }); reload(); } }}>Order</Button></div>}
        {ws.prescriptions.length > 0 && <p className="mt-3 text-sm text-slate-600">Prescriptions in this visit: {ws.prescriptions.length}</p>}
      </Section>

      {ws.previous_consultations.length > 0 && <Section title="Earlier consultations"><ul className="space-y-2">{ws.previous_consultations.map((c) => <li key={c.id} className="text-sm"><b>{fmtUtc(c.signed_at)}</b> · {c.doctor_name}<br />{c.complaint}{c.assessment ? ` → ${c.assessment}` : ""}</li>)}</ul></Section>}
      {ws.charges.length > 0 && <Section title="Charges (to be billed)"><ul>{ws.charges.map((c) => <li key={c.id}>{c.description}: Rs {c.amount} <span className="text-sm text-slate-500">({c.status.toLowerCase()})</span></li>)}</ul></Section>}
      {signed && (
        <Section title="Addenda">
          <ul className="mb-3 space-y-1">{ws.addenda.map((a) => <li key={a.id} className="text-sm"><b>{fmtUtc(a.added_at)}</b> · {a.text}</li>)}{ws.addenda.length === 0 && <li className="text-slate-500">None.</li>}</ul>
          <div className="flex gap-2"><Input aria-label="Addendum" maxLength={3000} value={addendum} onChange={(e) => setAddendum(e.target.value)} /><Button type="button" variant="secondary" disabled={busy || addendum.trim().length < 3} onClick={async () => { if (await run(() => addAddendum(ws.consultation.id, addendum), "Addendum added")) { setAddendum(""); reload(); } }}>Add</Button></div>
        </Section>)}
      {problem && <ErrorBox message={problem} />}

      {!readOnly && (
        <div className="sticky bottom-0 z-10 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white/95 p-3 shadow-lg backdrop-blur">
          <span className="text-sm">{saveState === "saving" ? <span className="text-slate-500"><Loader2 size={14} className="mr-1 inline animate-spin" />Saving...</span> : saveState === "saved" ? <span className="text-emerald-700"><CheckCircle2 size={14} className="mr-1 inline" />Draft saved</span>
            : saveState === "failed" ? <span role="alert" className="font-semibold text-red-700"><CloudOff size={14} className="mr-1 inline" />Not saved. What you typed is still here. <button type="button" className="underline" onClick={save}>Try again</button></span> : <span className="text-slate-400">Saved automatically as you type</span>}</span>
          <span className="flex gap-2"><Button type="button" variant="secondary" onClick={save}>Save draft</Button>{grade !== "INTERN" ? <Button type="button" disabled={busy} onClick={sign}>Review and sign</Button> : <span className="self-center text-sm font-semibold text-slate-600">Your consultant signs this</span>}</span>
        </div>)}

      {dialog === "rx" && <PrescriptionModal patientId={p.id} encounterId={eid} onClose={() => setDialog(null)} onSaved={() => { setDialog(null); reload(); }} />}
      {dialog === "refer" && <ReferDialog patientId={p.id} encounterId={eid} onClose={() => setDialog(null)} />}
      {dialog === "admit" && <AdmitDialog patientId={p.id} encounterId={eid} onClose={() => setDialog(null)} />}
    </div>
  );
}
