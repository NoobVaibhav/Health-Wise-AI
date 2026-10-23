// The detailed past medical history. Section 1 (long-term illnesses and regular medicines) is the most important part of the history:
// a doctor reads it first. Section 2 lists earlier hospital admissions and operations. Doctors can add, edit, check and hide records;
// patients see the same information read-only.
import { useState } from "react";
import { BadgeCheck, ChevronDown, ChevronUp, Pencil, Plus, Trash2 } from "lucide-react";
import { removeAdmission, removeCondition, removeMedicine, removeSurgery, verifyRecord } from "../../services/historyApi";
import { getErrorMessage } from "../../services/api";
import { Button, fmtDate, fmtDateTime } from "../ui";
import { ADHERENCE, ADMISSION_TYPE, ANSWER, CONTROL, Fact, Nr, SourceBadge, medLine, show, stayText } from "./pastKit";
import { AdmissionForm, ConditionForm, MedicineForm, SurgeryForm } from "./PastForms";

const Bar = ({ n, title, sub }) => (
  <div className="rounded-2xl bg-gradient-to-r from-brand-800 to-brand-600 px-5 py-3 text-white shadow">
    <h2 className="flex items-center gap-3 text-xl font-extrabold"><span className="flex h-8 w-8 items-center justify-center rounded-full bg-white text-base text-brand-800">{n}</span>{title}</h2>
    {sub && <p className="mt-0.5 pl-11 text-sm text-brand-50">{sub}</p>}
  </div>
);
const Sub = ({ title, action }) => <div className="mb-2 mt-5 flex items-center justify-between gap-2 border-b-2 border-brand-200 pb-1"><h3 className="text-lg font-extrabold text-brand-900">{title}</h3>{action}</div>;
const Card = ({ children, tone = "border-slate-200" }) => <div className={`rounded-2xl border bg-white p-4 shadow-sm ${tone}`}>{children}</div>;
const Mini = ({ onClick, icon: Icon, children, danger }) => <button type="button" onClick={onClick} className={`inline-flex items-center gap-1 rounded-lg px-2.5 py-1 text-sm font-bold ${danger ? "text-red-600 hover:bg-red-50" : "text-brand-700 hover:bg-brand-50"}`}><Icon size={14} />{children}</button>;

const when = (a) => (a.admitted_at ? fmtDateTime(a.admitted_at) : a.admitted_date_text || null);
const opDate = (s) => (s.operation_date ? fmtDate(s.operation_date) : s.operation_year ? String(s.operation_year) : null);

const withDate = (text, c) => (text ? `${text}${c.control.noted_on ? ` (${c.control.noted_on})` : ""}` : null);
const sugarText = (c) => withDate([c.control.fasting != null && `fasting ${c.control.fasting} mg/dL`, c.control.postprandial != null && `after meal ${c.control.postprandial} mg/dL`,
  c.control.random != null && `random ${c.control.random} mg/dL`, c.control.hba1c != null && `HbA1c ${c.control.hba1c}%`].filter(Boolean).join(", "), c);
const bpText = (c) => withDate([c.control.bp_usual && `usual ${c.control.bp_usual}`, c.control.bp_recent && `recent ${c.control.bp_recent}`].filter(Boolean).join(", "), c);

export default function PastHistory({ patientId, past, labs = [], editable = false, onChange }) {
  const [modal, setModal] = useState(null);
  const [error, setError] = useState("");
  const [open, setOpen] = useState({});
  const conditions = [past.diabetes, past.hypertension, ...past.other_conditions].filter(Boolean);
  const admissions = past.admissions;
  const done = (p) => { onChange?.(p); setModal(null); };

  const act = async (fn) => { setError(""); try { onChange?.(await fn()); } catch (e) { setError(getErrorMessage(e)); } };
  const hide = (what, fn) => { if (window.confirm(`Hide this ${what}? It is removed from the history and the printed sheet, but the record and its change log are kept.`)) act(fn); };
  const Actions = ({ item, entity, onEdit, onHide, what }) => (editable ? (
    <div className="flex flex-wrap items-center gap-1">
      {!item.verified && <Mini icon={BadgeCheck} onClick={() => act(() => verifyRecord(patientId, entity, item.id))}>Mark as checked</Mini>}
      <Mini icon={Pencil} onClick={onEdit}>Edit</Mini><Mini icon={Trash2} danger onClick={() => hide(what, onHide)}>Remove</Mini>
    </div>) : null);

  // ------------------------------------------------------------------ illness cards
  const Complications = ({ c }) => {
    const entries = Object.entries(c.complications || {});
    if (!entries.length && !c.complications_other) return null;
    const labelOf = { retinopathy: "Eye (retinopathy)", neuropathy: "Nerves (neuropathy)", nephropathy: "Kidney (nephropathy)", foot: "Foot or non-healing wounds", cardiovascular: "Heart and vessels", hypoglycemia: "Low sugar episodes or emergency", heart_disease: "Heart disease", stroke: "Stroke", kidney_damage: "Kidney damage" };
    return (
      <div className="py-1"><dt className="mb-1 text-sm font-bold text-slate-500">Complications</dt>
        <dd className="flex flex-wrap gap-1.5">{entries.map(([k, v]) => <span key={k} className={`rounded-lg px-2.5 py-1 text-sm ${v === "YES" ? "bg-amber-100 font-bold text-amber-900" : v === "NO" ? "bg-emerald-50 text-emerald-800" : "bg-slate-100 text-slate-500"}`}>{labelOf[k] || k}: {ANSWER[v]}</span>)}
          {c.complications_other && <span className="rounded-lg bg-amber-100 px-2.5 py-1 text-sm font-bold text-amber-900">Other: {c.complications_other}</span>}</dd></div>
    );
  };
  const Stay = ({ h }) => {
    if (!h || h.happened === "UNKNOWN") return <Fact label="Hospital stay for this illness">{null}</Fact>;
    if (h.happened === "NO") return <Fact label="Hospital stay for this illness">No</Fact>;
    return <Fact label="Hospital stay for this illness">Yes{[h.reason && `reason: ${h.reason}`, h.date_text && `when: ${h.date_text}`, h.treatment && `treatment: ${h.treatment}`, h.outcome && `outcome: ${h.outcome}`].filter(Boolean).map((t) => <span key={t} className="block pl-3 text-slate-700">{t}</span>)}</Fact>;
  };
  const MedsOf = ({ c }) => (
    <div className="mt-2">
      <p className="text-sm font-bold text-slate-500">Current medicines for this illness</p>
      {c.medications.length ? <ul className="mt-1 space-y-1">{c.medications.map((m) => <li key={m.id} className="flex flex-wrap items-center gap-2 text-slate-900"><b>{m.name}</b><span>{[m.dose, m.frequency, m.route].filter(Boolean).join(", ") || <Nr />}</span>{!m.is_current && <span className="rounded bg-slate-200 px-1.5 text-xs font-bold">stopped</span>}<SourceBadge item={m} /></li>)}</ul> : <p><Nr /></p>}
      {editable && <Mini icon={Plus} onClick={() => setModal({ type: "medicine", preset: c.id })}>Add a medicine for this illness</Mini>}
    </div>
  );
  const duration = (c) => c.duration_text || (c.years_since_diagnosis != null ? `about ${c.years_since_diagnosis} year${c.years_since_diagnosis === 1 ? "" : "s"} (calculated from the year of diagnosis)` : null);
  const ConditionCard = ({ c, label }) => (
    <Card tone={c.verified ? "border-emerald-200" : "border-slate-200"}>
      <div className="mb-2 flex flex-wrap items-start justify-between gap-2"><div><h4 className="text-lg font-extrabold text-slate-900">{label || c.name}</h4><SourceBadge item={c} /></div>
        <Actions item={c} entity="condition" what="illness record" onEdit={() => setModal({ type: "condition", kind: c.kind, record: c })} onHide={() => removeCondition(patientId, c.id)} /></div>
      <dl className="divide-y divide-slate-100">
        <Fact label={c.kind === "OTHER" ? "Diagnosis details" : "Diagnosis"}>{c.diagnosis_type}</Fact>
        <Fact label="Duration">{duration(c)}</Fact><Fact label="Year of diagnosis">{c.diagnosis_year}</Fact>
        <Fact label="On treatment">{c.on_treatment == null ? null : c.on_treatment ? "Yes" : "No"}</Fact>
        <Fact label={c.kind === "OTHER" ? "Disease control" : "Overall control"}>{c.control_status ? CONTROL[c.control_status] : null}</Fact>
        {c.kind === "DIABETES" && <Fact label="Blood sugar (reported)">{sugarText(c)}</Fact>}
        {c.kind === "DIABETES" && labs.length > 0 && <Fact label="Latest laboratory reports">{labs.map((l) => `${l.name} ${l.value} ${l.unit || ""} (${fmtDate(l.date)})`).join("; ")}</Fact>}
        {c.kind === "HYPERTENSION" && <Fact label="Blood pressure (reported)">{bpText(c)}</Fact>}
        <Complications c={c} /><Stay h={c.hospitalisation} />
        <Fact label="Other details" hideEmpty>{c.other_details}</Fact><Fact label="Clinical notes" hideEmpty>{c.notes}</Fact>
      </dl>
      <MedsOf c={c} />
    </Card>
  );
  const Empty = ({ text, kind }) => (
    <Card><p className="text-slate-600">{text} <Nr /></p>{editable && <Button className="mt-2" variant="soft" onClick={() => setModal({ type: "condition", kind })}><Plus size={16} />Add {kind === "DIABETES" ? "diabetes history" : "hypertension history"}</Button>}</Card>
  );

  // ------------------------------------------------------------------ admissions
  const SurgeryBlock = ({ s }) => (
    <div className="mt-3 rounded-xl border border-violet-200 bg-violet-50/50 p-3">
      <div className="flex flex-wrap items-start justify-between gap-2"><p className="font-extrabold text-violet-900">Operation: {s.procedure_name}{opDate(s) ? ` (${opDate(s)})` : ""}</p>
        <Actions item={s} entity="surgery" what="operation record" onEdit={() => setModal({ type: "surgery", record: s })} onHide={() => removeSurgery(patientId, s.id)} /></div>
      <SourceBadge item={s} />
      <dl className="mt-1 divide-y divide-violet-100">
        <Fact label="Reason">{s.reason}</Fact><Fact label="Site" hideEmpty>{s.body_site}</Fact><Fact label="Surgeon and hospital">{[s.surgeon, s.hospital].filter(Boolean).join(", ") || null}</Fact>
        <Fact label="Anaesthesia">{s.anesthesia}</Fact><Fact label="Surgical findings" hideEmpty>{s.findings}</Fact>
        <Fact label="Implant or device">{s.implant_used === null ? "Not documented" : s.implant_used ? ["Yes", s.implant_type, s.implant_material, s.implant_serial && `ID ${s.implant_serial}`].filter(Boolean).join(" - ") : "No implant used"}</Fact>
        <Fact label="Post-operative X-ray" hideEmpty>{s.postop_xray}</Fact><Fact label="Post-operative treatment" hideEmpty>{s.postop_treatment}</Fact>
        <Fact label="Post-operative complications" hideEmpty>{s.postop_complications}</Fact><Fact label="Recovery progress" hideEmpty>{s.recovery_progress}</Fact>
      </dl>
    </div>
  );
  const MedList = ({ rows }) => (rows?.length ? <ul className="space-y-0.5">{rows.map((m, i) => <li key={i}><b>{m.name}</b>{[m.dose, m.frequency, m.route, m.duration].filter(Boolean).length ? ` - ${[m.dose, m.frequency, m.route && `route ${m.route}`, m.duration].filter(Boolean).join(", ")}` : ""}{m.category && m.category !== "OTHER" ? ` (${m.category.replace("_", " ").toLowerCase()})` : ""}</li>)}</ul> : null);
  const AdmissionCard = ({ a }) => {
    const v = a.vitals || {};
    const vit = [v.bp_systolic != null && `BP ${v.bp_systolic}/${v.bp_diastolic ?? "?"} mmHg`, v.pulse != null && `pulse ${v.pulse}/min`, v.resp_rate != null && `breathing ${v.resp_rate}/min`, v.temperature_f != null && `temperature ${v.temperature_f} F`, v.spo2 != null && `SpO2 ${v.spo2}%`, v.pain_score != null && `pain ${v.pain_score}/10`].filter(Boolean);
    const isOpen = !!open[a.id];
    const title = a.main_complaint || a.reason || a.final_diagnosis || a.provisional_diagnosis || "Hospital admission";
    return (
      <Card tone={a.verified ? "border-emerald-200" : "border-slate-200"}>
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div><h4 className="text-lg font-extrabold text-slate-900">{title}</h4>
            <p className="text-sm text-slate-600">{[when(a), a.hospital_name, a.admission_type && ADMISSION_TYPE[a.admission_type]].filter(Boolean).join("  |  ") || <Nr />}</p><SourceBadge item={a} /></div>
          <Actions item={a} entity="admission" what="admission record" onEdit={() => setModal({ type: "admission", record: a })} onHide={() => removeAdmission(patientId, a.id)} />
        </div>
        <dl className="mt-2 divide-y divide-slate-100">
          <Fact label="Final diagnosis">{a.final_diagnosis}</Fact><Fact label="Length of stay">{stayText(a)}</Fact><Fact label="Discharged">{a.discharged_at ? fmtDateTime(a.discharged_at) : null}</Fact>
        </dl>
        {a.surgeries.map((s) => <SurgeryBlock key={s.id} s={s} />)}
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <button type="button" onClick={() => setOpen({ ...open, [a.id]: !isOpen })} className="inline-flex items-center gap-1 text-sm font-bold text-brand-700">{isOpen ? <ChevronUp size={16} /> : <ChevronDown size={16} />}{isOpen ? "Hide full details" : "Show full details"}</button>
          {editable && <Mini icon={Plus} onClick={() => setModal({ type: "surgery", preset: a.id })}>Add an operation</Mini>}
        </div>
        {isOpen && (
          <div className="mt-2 space-y-4 border-t border-slate-100 pt-3">
            <div><h5 className="mb-1 font-extrabold text-brand-900">A. Admission details</h5><dl className="divide-y divide-slate-100">
              <Fact label="Secondary complaints" hideEmpty>{a.secondary_complaints}</Fact><Fact label="Provisional diagnosis">{a.provisional_diagnosis}</Fact><Fact label="Reason for hospitalisation">{a.reason}</Fact><Fact label="Referred by" hideEmpty>{a.referred_by}</Fact></dl></div>
            <div><h5 className="mb-1 font-extrabold text-brand-900">B. Clinical history during the admission</h5><dl className="divide-y divide-slate-100">
              <Fact label="Symptoms at admission">{a.symptoms}</Fact><Fact label="History of the illness">{a.history_of_present_illness}</Fact><Fact label="Illnesses already present" hideEmpty>{a.preexisting_conditions}</Fact>
              <Fact label={`Vital signs at admission${v.recorded_at ? ` (${v.recorded_at})` : ""}`}>{vit.join(", ") || null}</Fact>
              <Fact label="Examination findings">{a.exam_findings}</Fact><Fact label="Investigations and imaging">{a.investigations}</Fact><Fact label="Complications of the diagnosis" hideEmpty>{a.complications}</Fact></dl></div>
            <div><h5 className="mb-1 font-extrabold text-brand-900">C. Treatment and medicines during the stay</h5><dl className="divide-y divide-slate-100">
              <Fact label="Treatment provided">{a.treatment_given}</Fact><Fact label="Medicines given">{a.medications.length ? <MedList rows={a.medications} /> : null}</Fact>
              <Fact label="IV fluids and oxygen" hideEmpty>{a.iv_fluids_oxygen}</Fact><Fact label="Procedures and supportive care" hideEmpty>{a.procedures_supportive}</Fact><Fact label="Changes in medication" hideEmpty>{a.medication_changes}</Fact>
              <Fact label="Response to treatment">{a.response_to_treatment}</Fact><Fact label="Complications during the stay" hideEmpty>{a.stay_complications}</Fact></dl></div>
            <div><h5 className="mb-1 font-extrabold text-brand-900">E. Discharge summary and recovery</h5><dl className="divide-y divide-slate-100">
              <Fact label="Condition at discharge">{a.discharge_condition}</Fact><Fact label="Treatment completed" hideEmpty>{a.treatment_completed}</Fact>
              <Fact label="Discharge medicines">{a.discharge_medications.length ? <MedList rows={a.discharge_medications} /> : null}</Fact><Fact label="Discharge instructions">{a.discharge_instructions}</Fact>
              <Fact label="Wound care or rehabilitation" hideEmpty>{a.wound_rehab_instructions}</Fact><Fact label="Follow-up date">{a.followup_date ? fmtDate(a.followup_date) : null}</Fact><Fact label="Specialist review" hideEmpty>{a.specialist_review}</Fact>
              <Fact label="Recovery status">{a.recovery_status}</Fact><Fact label="Remaining symptoms" hideEmpty>{a.remaining_symptoms}</Fact><Fact label="After discharge" hideEmpty>{a.readmission_notes}</Fact></dl></div>
          </div>
        )}
      </Card>
    );
  };

  return (
    <div className="space-y-4">
      {error && <p className="rounded-xl bg-red-50 p-3 font-semibold text-red-700" role="alert">{error}</p>}
      {editable && past.unverified > 0 && <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900"><b>{past.unverified} record{past.unverified === 1 ? "" : "s"}</b> {past.unverified === 1 ? "has" : "have"} not been checked by a doctor yet. Use "Mark as checked" after confirming with the patient or the documents.</p>}

      <Bar n="1" title="Detailed medical history" sub="Long-term illnesses, the medicines taken for them, and any complications" />
      <Sub title="A. Diabetes mellitus" />
      {past.diabetes ? <ConditionCard c={past.diabetes} label="Diabetes mellitus" /> : <Empty kind="DIABETES" text="No diabetes history is recorded." />}
      <Sub title="B. Hypertension (high blood pressure)" />
      {past.hypertension ? <ConditionCard c={past.hypertension} label="Hypertension" /> : <Empty kind="HYPERTENSION" text="No hypertension history is recorded." />}
      <Sub title="C. Other chronic illnesses" action={editable && <Button variant="soft" onClick={() => setModal({ type: "condition", kind: "OTHER" })}><Plus size={16} />Add an illness</Button>} />
      {past.other_conditions.length ? <div className="space-y-3">{past.other_conditions.map((c) => <ConditionCard key={c.id} c={c} />)}</div> : <Card><Nr /></Card>}
      <Sub title="D. Medicines taken regularly" action={editable && <Button variant="soft" onClick={() => setModal({ type: "medicine" })}><Plus size={16} />Add a medicine</Button>} />
      {past.medications.length ? (
        <Card><div className="overflow-x-auto"><table className="w-full min-w-[640px] text-left text-sm">
          <thead><tr className="border-b-2 border-slate-300 text-xs uppercase tracking-wide text-slate-500"><th className="py-1.5">Medicine</th><th>Dosage and frequency</th><th>Route</th><th>For</th><th>Since</th><th>Prescribed by</th><th>Takes it</th><th>Source</th>{editable && <th />}</tr></thead>
          <tbody>{past.medications.map((m) => {
            const cond = conditions.find((c) => c.id === m.condition_id);
            return (
              <tr key={m.id} className="border-b border-slate-100 align-top">
                <td className="py-2 font-bold">{m.name}{!m.is_current && <span className="ml-1 rounded bg-slate-200 px-1.5 text-xs">stopped</span>}</td><td>{[m.dose, m.frequency].filter(Boolean).join(", ") || <Nr />}</td><td>{show(m.route)}</td>
                <td>{cond ? cond.name : m.reason || <span className="text-slate-400">not linked</span>}</td><td>{show(m.since)}</td><td>{show(m.prescriber)}</td><td>{m.adherence ? ADHERENCE[m.adherence] : <Nr />}</td><td><SourceBadge item={m} /></td>
                {editable && <td className="whitespace-nowrap"><Mini icon={Pencil} onClick={() => setModal({ type: "medicine", record: m })}>Edit</Mini>{!m.verified && <Mini icon={BadgeCheck} onClick={() => act(() => verifyRecord(patientId, "medication", m.id))}>Check</Mini>}<Mini icon={Trash2} danger onClick={() => hide("medicine", () => removeMedicine(patientId, m.id))}>Remove</Mini></td>}
              </tr>);
          })}</tbody></table></div></Card>
      ) : <Card><Nr /></Card>}

      <div className="pt-4" />
      <Bar n="2" title="Previous hospital admission history" sub="Every significant earlier admission: acute illness, accident, injury or operation" />
      <div className="flex flex-wrap gap-2">{editable && <><Button onClick={() => setModal({ type: "admission" })}><Plus size={16} />Add an admission</Button><Button variant="secondary" onClick={() => setModal({ type: "surgery" })}><Plus size={16} />Add an operation</Button></>}</div>
      {admissions.length ? <div className="space-y-3">{admissions.map((a) => <AdmissionCard key={a.id} a={a} />)}</div> : <Card><p className="text-slate-700">No earlier hospital admission is recorded. <Nr /></p></Card>}
      {past.standalone_surgeries.length > 0 && (<><Sub title="Operations not linked to an admission" /><div className="space-y-2">{past.standalone_surgeries.map((s) => <Card key={s.id}><SurgeryBlock s={s} /></Card>)}</div></>)}

      {modal?.type === "condition" && <ConditionForm patientId={patientId} kind={modal.kind} record={modal.record} onSaved={done} onClose={() => setModal(null)} />}
      {modal?.type === "medicine" && <MedicineForm patientId={patientId} record={modal.record} conditions={conditions} presetCondition={modal.preset} onSaved={done} onClose={() => setModal(null)} />}
      {modal?.type === "admission" && <AdmissionForm patientId={patientId} record={modal.record} onSaved={done} onClose={() => setModal(null)} />}
      {modal?.type === "surgery" && <SurgeryForm patientId={patientId} record={modal.record} admissions={admissions} presetAdmission={modal.preset} onSaved={done} onClose={() => setModal(null)} />}
    </div>
  );
}
