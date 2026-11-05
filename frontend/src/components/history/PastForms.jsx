// Entry forms for the detailed past history. A doctor fills in what is known; every field can stay empty ("Not recorded").
// Nothing is pre-filled from today's readings, and the doctor chooses where each piece of information came from.
import { useState } from "react";
import { saveAdmission, saveCondition, saveMedicine, saveSurgery } from "../../services/historyApi";
import { getErrorMessage } from "../../services/api";
import { Button, Field, Input, Modal, Select, Textarea } from "../ui";
import { SOURCES, blank, num } from "./pastKit";

const thisYear = new Date().getFullYear();

/** Yes / No / Not recorded as three buttons (an unanswered question is never read as "No"). */
function Answer({ label, value, onChange }) {
  const opts = [["YES", "Yes", "bg-amber-500 text-white"], ["NO", "No", "bg-emerald-600 text-white"], ["UNKNOWN", "Not recorded", "bg-slate-500 text-white"]];
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-2xl bg-slate-50 px-3 py-2">
      <span className="text-sm font-semibold text-slate-700">{label}</span>
      <span className="flex gap-1.5">{opts.map(([key, text, on]) => (
        <button key={key} type="button" onClick={() => onChange(key)} className={`rounded-xl px-3 py-1.5 text-sm font-bold ${(value || "UNKNOWN") === key ? on : "bg-white text-slate-500 ring-1 ring-slate-200"}`}>{text}</button>))}</span>
    </div>
  );
}

const Grid = ({ children, cols = 2 }) => <div className={`grid gap-3 ${cols === 3 ? "sm:grid-cols-3" : cols === 1 ? "" : "sm:grid-cols-2"}`}>{children}</div>;
const SourcePick = ({ value, onChange }) => (
  <Field label="Where does this information come from?" hint="Choose 'Checked by a doctor' only if you have checked it (records, documents or examination).">
    <Select value={value} onChange={(e) => onChange(e.target.value)}>{SOURCES.map(([k, t]) => <option key={k} value={k}>{t}</option>)}</Select>
  </Field>
);
const Sub = ({ children }) => <h4 className="mt-5 border-b border-slate-200 pb-1 text-sm font-extrabold uppercase tracking-wide text-brand-800">{children}</h4>;

function useForm(initial) {
  const [f, setF] = useState(initial);
  return [f, (patch) => setF((x) => ({ ...x, ...patch })), setF];
}

function Footer({ saving, error, onClose, onSave, extra }) {
  return (
    <div className="mt-5 space-y-2">
      {error && <p className="rounded-xl bg-red-50 p-2.5 text-sm font-semibold text-red-700" role="alert">{error}</p>}
      <div className="flex flex-wrap justify-end gap-2">{extra}<Button variant="secondary" type="button" onClick={onClose}>Cancel</Button><Button type="button" onClick={onSave} disabled={saving}>{saving ? "Saving..." : "Save"}</Button></div>
    </div>
  );
}

function useSave(run, onSaved) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const go = async () => {
    setSaving(true); setError("");
    try { onSaved(await run()); } catch (e) { setError(getErrorMessage(e).replace(/^Value error, /, "")); } finally { setSaving(false); }
  };
  return { saving, error, go };
}

// ------------------------------------------------------------------ illness
const COMPLICATIONS = {
  DIABETES: [["retinopathy", "Diabetic retinopathy (eye complications)"], ["neuropathy", "Diabetic neuropathy (nerve damage)"], ["nephropathy", "Diabetic nephropathy (kidney complications)"],
    ["foot", "Diabetic foot or non-healing wounds"], ["cardiovascular", "Cardiovascular complications"], ["hypoglycemia", "Earlier low sugar (hypoglycaemia) or diabetic emergency"]],
  HYPERTENSION: [["heart_disease", "Heart disease"], ["stroke", "Stroke"], ["kidney_damage", "Kidney damage"]],
  OTHER: [],
};
const TYPES = { DIABETES: ["Type 1", "Type 2", "Gestational", "Other", "Unknown"], HYPERTENSION: ["Hypertension", "Other", "Unknown"] };
const TITLE = { DIABETES: "Diabetes mellitus", HYPERTENSION: "Hypertension", OTHER: "Other long-term illness" };
// common long-term illnesses for the name list; anything else is typed under "Other"
const ILLNESSES = ["Bronchial asthma", "COPD (chronic obstructive pulmonary disease)", "Hypothyroidism", "Hyperthyroidism", "Chronic kidney disease", "Coronary artery disease (heart disease)", "Heart failure",
  "Atrial fibrillation", "Previous stroke", "Epilepsy", "Tuberculosis (treated or ongoing)", "Chronic liver disease", "Osteoarthritis", "Rheumatoid arthritis", "Gout", "Migraine", "Depression", "Anxiety disorder",
  "Parkinson's disease", "Alzheimer's disease or dementia", "Cancer", "Chronic anaemia", "Obesity", "High cholesterol (dyslipidaemia)", "PCOS", "Peptic ulcer or GERD", "Osteoporosis",
  "Enlarged prostate (BPH)", "Glaucoma", "Allergic rhinitis", "Sickle cell disease", "Thalassemia", "HIV infection"];
const OTHER_PICK = "__other";

export function ConditionForm({ patientId, kind, record, onSaved, onClose }) {
  const r = record || {};
  const c = r.control || {};
  const h = r.hospitalisation || {};
  const [pick, setPick] = useState(kind !== "OTHER" ? "" : !record ? "" : ILLNESSES.includes(r.name) ? r.name : OTHER_PICK);   // the chosen entry of the illness list
  const [f, set] = useForm({
    name: kind === "OTHER" ? r.name || "" : "", diagnosis_type: r.diagnosis_type || "", duration_text: r.duration_text || "", diagnosis_year: r.diagnosis_year ?? "", control_status: r.control_status || "",
    on_treatment: r.on_treatment == null ? "" : r.on_treatment ? "yes" : "no", fasting: c.fasting ?? "", postprandial: c.postprandial ?? "", random: c.random ?? "", hba1c: c.hba1c ?? "",
    bp_usual: c.bp_usual || "", bp_recent: c.bp_recent || "", noted_on: c.noted_on || "", complications: r.complications || {}, complications_other: r.complications_other || "",
    happened: h.happened || "UNKNOWN", h_reason: h.reason || "", h_date: h.date_text || "", h_treatment: h.treatment || "", h_outcome: h.outcome || "",
    other_details: r.other_details || "", notes: r.notes || "", source: r.source === "EARLIER_ENTRY" ? "PATIENT_REPORTED" : r.source || "PATIENT_REPORTED",
  });
  const body = () => ({
    kind, name: kind === "OTHER" ? blank(pick === OTHER_PICK ? f.name : pick) : null, diagnosis_type: blank(f.diagnosis_type), duration_text: blank(f.duration_text), diagnosis_year: num(f.diagnosis_year),
    control_status: f.control_status || null, on_treatment: f.on_treatment === "" ? null : f.on_treatment === "yes",
    control: kind === "DIABETES" ? { fasting: num(f.fasting), postprandial: num(f.postprandial), random: num(f.random), hba1c: num(f.hba1c), noted_on: blank(f.noted_on) }
      : kind === "HYPERTENSION" ? { bp_usual: blank(f.bp_usual), bp_recent: blank(f.bp_recent), noted_on: blank(f.noted_on) } : {},
    complications: Object.fromEntries(COMPLICATIONS[kind].map(([k]) => [k, f.complications[k] || "UNKNOWN"])), complications_other: blank(f.complications_other),
    hospitalisation: { happened: f.happened, reason: blank(f.h_reason), date_text: blank(f.h_date), treatment: blank(f.h_treatment), outcome: blank(f.h_outcome) },
    other_details: blank(f.other_details), notes: blank(f.notes), source: f.source,
  });
  const { saving, error, go } = useSave(() => saveCondition(patientId, body(), record?.id), onSaved);

  return (
    <Modal wide title={`${record ? "Edit" : "Add"}: ${kind === "OTHER" ? r.name || TITLE.OTHER : TITLE[kind]}`} onClose={onClose}>
      <div className="space-y-3">
        {kind === "OTHER" && (
          <div className="space-y-2">
            <Field label="Name of the illness"><Select value={pick} onChange={(e) => setPick(e.target.value)}>
              <option value="">Choose an illness from the list...</option>
              {ILLNESSES.map((x) => <option key={x} value={x}>{x}</option>)}
              <option value={OTHER_PICK}>Other (type the name)</option>
            </Select></Field>
            {pick === OTHER_PICK && <Field label="Write the name of the illness"><Input autoFocus value={f.name} onChange={(e) => set({ name: e.target.value })} placeholder="Name of the illness" /></Field>}
          </div>)}
        <Grid>
          {kind !== "OTHER" ? (
            <Field label="Diagnosis"><Select value={f.diagnosis_type} onChange={(e) => set({ diagnosis_type: e.target.value })}><option value="">Not recorded</option>{TYPES[kind].map((t) => <option key={t}>{t}</option>)}</Select></Field>
          ) : <Field label="Type or details of the diagnosis"><Input value={f.diagnosis_type} onChange={(e) => set({ diagnosis_type: e.target.value })} /></Field>}
          <Field label="Duration (how long)"><Input value={f.duration_text} onChange={(e) => set({ duration_text: e.target.value })} placeholder="e.g. 5 years" /></Field>
          <Field label="Year of diagnosis"><Input type="number" inputMode="decimal" min="1900" max={thisYear} value={f.diagnosis_year} onChange={(e) => set({ diagnosis_year: e.target.value })} placeholder="e.g. 2021" /></Field>
          <Field label={kind === "OTHER" ? "Disease control" : "Overall control"}><Select value={f.control_status} onChange={(e) => set({ control_status: e.target.value })}><option value="">Not recorded</option><option value="GOOD">Good</option><option value="FAIR">Fair</option><option value="POOR">Poor</option></Select></Field>
          <Field label="Is the patient on treatment?"><Select value={f.on_treatment} onChange={(e) => set({ on_treatment: e.target.value })}><option value="">Not recorded</option><option value="yes">Yes</option><option value="no">No</option></Select></Field>
        </Grid>

        {kind === "DIABETES" && (<><Sub>Blood sugar control (reported values, with the date they were measured)</Sub>
          <Grid cols={3}>
            <Field label="Fasting sugar (mg/dL)"><Input type="number" inputMode="decimal" step="any" value={f.fasting} onChange={(e) => set({ fasting: e.target.value })} /></Field>
            <Field label="After-meal sugar (mg/dL)"><Input type="number" inputMode="decimal" step="any" value={f.postprandial} onChange={(e) => set({ postprandial: e.target.value })} /></Field>
            <Field label="Random sugar (mg/dL)"><Input type="number" inputMode="decimal" step="any" value={f.random} onChange={(e) => set({ random: e.target.value })} /></Field>
            <Field label="HbA1c (%)"><Input type="number" inputMode="decimal" step="any" value={f.hba1c} onChange={(e) => set({ hba1c: e.target.value })} /></Field>
            <Field label="Measured on"><Input value={f.noted_on} onChange={(e) => set({ noted_on: e.target.value })} placeholder="e.g. Sep 2026" /></Field>
          </Grid>
          <p className="text-xs text-slate-500">Results from uploaded laboratory reports are shown separately, with their own dates.</p></>)}

        {kind === "HYPERTENSION" && (<><Sub>Blood pressure control</Sub>
          <Grid cols={3}>
            <Field label="Usual BP range"><Input value={f.bp_usual} onChange={(e) => set({ bp_usual: e.target.value })} placeholder="e.g. 130/80" /></Field>
            <Field label="Recent reading"><Input value={f.bp_recent} onChange={(e) => set({ bp_recent: e.target.value })} placeholder="e.g. 142/90 on 4 Sep" /></Field>
            <Field label="Measured on"><Input value={f.noted_on} onChange={(e) => set({ noted_on: e.target.value })} /></Field>
          </Grid></>)}

        <Sub>{kind === "OTHER" ? "Related complications" : "Has the patient had any of these complications?"}</Sub>
        <div className="space-y-1.5">{COMPLICATIONS[kind].map(([k, label]) => <Answer key={k} label={label} value={f.complications[k]} onChange={(v) => set({ complications: { ...f.complications, [k]: v } })} />)}</div>
        <Field label={kind === "OTHER" ? "Complications (describe)" : "Other complications"}><Input value={f.complications_other} onChange={(e) => set({ complications_other: e.target.value })} /></Field>

        <Sub>Hospital stay because of this illness</Sub>
        <Answer label={`Ever admitted to hospital because of ${kind === "OTHER" ? "this illness" : TITLE[kind].toLowerCase()}?`} value={f.happened} onChange={(v) => set({ happened: v })} />
        {f.happened === "YES" && <Grid>
          <Field label="Reason"><Input value={f.h_reason} onChange={(e) => set({ h_reason: e.target.value })} /></Field>
          <Field label="When"><Input value={f.h_date} onChange={(e) => set({ h_date: e.target.value })} placeholder="date, month or year" /></Field>
          <Field label="Treatment"><Textarea rows={2} value={f.h_treatment} onChange={(e) => set({ h_treatment: e.target.value })} /></Field>
          <Field label="Outcome"><Textarea rows={2} value={f.h_outcome} onChange={(e) => set({ h_outcome: e.target.value })} /></Field>
        </Grid>}

        <Field label="Other relevant details"><Textarea rows={2} value={f.other_details} onChange={(e) => set({ other_details: e.target.value })} /></Field>
        <Field label="Clinical notes"><Textarea rows={2} value={f.notes} onChange={(e) => set({ notes: e.target.value })} /></Field>
        <SourcePick value={f.source} onChange={(v) => set({ source: v })} />
        <p className="text-xs text-slate-500">Medicines for this illness are added under "Medicines taken regularly", linked to this illness.</p>
      </div>
      <Footer saving={saving} error={error} onClose={onClose} onSave={go} />
    </Modal>
  );
}

// ------------------------------------------------------------------ regular medicine
const ROUTES = ["Oral", "Injection", "Inhaled", "Topical", "Eye drops", "Insulin pen", "Other"];
const COMMON = ["Metformin", "Glimepiride", "Gliclazide", "Sitagliptin", "Insulin glargine", "Insulin human mixtard", "Amlodipine", "Telmisartan", "Losartan", "Atenolol", "Metoprolol", "Hydrochlorothiazide", "Atorvastatin", "Aspirin", "Clopidogrel", "Levothyroxine", "Salbutamol inhaler", "Budesonide inhaler", "Levetiracetam", "Furosemide"];

export function MedicineForm({ patientId, record, conditions, presetCondition, onSaved, onClose }) {
  const r = record || {};
  const [f, set] = useForm({ name: r.name || "", dose: r.dose || "", frequency: r.frequency || "", route: r.route || "", since: r.since || "", prescriber: r.prescriber || "", adherence: r.adherence || "",
    reason: r.reason || "", notes: r.notes || "", condition_id: r.condition_id ?? presetCondition ?? "", is_current: r.is_current ?? true, source: r.source === "EARLIER_ENTRY" || !r.source ? "PATIENT_REPORTED" : r.source });
  const body = () => ({ name: blank(f.name) || "", dose: blank(f.dose), frequency: blank(f.frequency), route: blank(f.route), since: blank(f.since), prescriber: blank(f.prescriber), adherence: f.adherence || null,
    reason: blank(f.reason), notes: blank(f.notes), condition_id: f.condition_id === "" ? null : Number(f.condition_id), is_current: f.is_current, source: f.source });
  const { saving, error, go } = useSave(() => saveMedicine(patientId, body(), record?.id), onSaved);
  return (
    <Modal wide title={record ? `Edit medicine: ${r.name}` : "Add a medicine taken regularly"} onClose={onClose}>
      <div className="space-y-3">
        <Grid>
          <Field label="Medicine name" hint="Write what is on the prescription or strip. The list only helps typing."><Input list="common-medicines" value={f.name} onChange={(e) => set({ name: e.target.value })} /></Field>
          <Field label="Taken for (illness)"><Select value={f.condition_id} onChange={(e) => set({ condition_id: e.target.value })}><option value="">Not linked to an illness</option>{conditions.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}</Select></Field>
          <Field label="Dosage"><Input value={f.dose} onChange={(e) => set({ dose: e.target.value })} placeholder="e.g. 500 mg" /></Field>
          <Field label="Frequency"><Input value={f.frequency} onChange={(e) => set({ frequency: e.target.value })} placeholder="e.g. twice daily after food" /></Field>
          <Field label="Route"><Select value={f.route} onChange={(e) => set({ route: e.target.value })}><option value="">Not recorded</option>{ROUTES.map((x) => <option key={x}>{x}</option>)}</Select></Field>
          <Field label="Since (start date or duration)"><Input value={f.since} onChange={(e) => set({ since: e.target.value })} placeholder="e.g. 2021 or 5 years" /></Field>
          <Field label="Prescribing doctor"><Input value={f.prescriber} onChange={(e) => set({ prescriber: e.target.value })} /></Field>
          <Field label="Does the patient take it as advised?"><Select value={f.adherence} onChange={(e) => set({ adherence: e.target.value })}><option value="">Not recorded</option><option value="REGULAR">Takes regularly</option><option value="SOMETIMES_MISSED">Sometimes misses doses</option><option value="OFTEN_MISSED">Often misses doses</option></Select></Field>
        </Grid>
        <Field label="Notes (side effects, reactions to this medicine)"><Textarea rows={2} value={f.notes} onChange={(e) => set({ notes: e.target.value })} /></Field>
        <label className="flex items-center gap-2 text-sm font-semibold text-slate-700"><input type="checkbox" checked={f.is_current} onChange={(e) => set({ is_current: e.target.checked })} className="h-4 w-4" /> The patient still takes this medicine</label>
        <SourcePick value={f.source} onChange={(v) => set({ source: v })} />
        <datalist id="common-medicines">{COMMON.map((x) => <option key={x} value={x} />)}</datalist>
      </div>
      <Footer saving={saving} error={error} onClose={onClose} onSave={go} />
    </Modal>
  );
}

// ------------------------------------------------------------------ hospital admission (sections A to D)
const MED_EMPTY = { name: "", dose: "", frequency: "", route: "", duration: "", category: "" };
const CATEGORIES = [["", "Medicine"], ["ANTIBIOTIC", "Antibiotic"], ["PAINKILLER", "Painkiller"], ["IV_FLUID", "IV fluid"], ["OXYGEN", "Oxygen"], ["OTHER", "Other"]];

function MedRows({ rows, setRows, withCategory, label }) {
  const upd = (i, patch) => setRows(rows.map((m, k) => (k === i ? { ...m, ...patch } : m)));
  return (
    <div className="space-y-2">
      {rows.map((m, i) => (
        <div key={i} className="grid gap-2 rounded-2xl bg-slate-50 p-2.5 sm:grid-cols-6">
          <Input className="sm:col-span-2" placeholder="Name" value={m.name} onChange={(e) => upd(i, { name: e.target.value })} />
          <Input placeholder="Dose" value={m.dose} onChange={(e) => upd(i, { dose: e.target.value })} />
          <Input placeholder="How often" value={m.frequency} onChange={(e) => upd(i, { frequency: e.target.value })} />
          <Input placeholder="Route (IV, oral...)" value={m.route} onChange={(e) => upd(i, { route: e.target.value })} />
          <Input placeholder="For how long" value={m.duration} onChange={(e) => upd(i, { duration: e.target.value })} />
          {withCategory && <Select className="sm:col-span-2" value={m.category} onChange={(e) => upd(i, { category: e.target.value })}>{CATEGORIES.map(([k, t]) => <option key={k} value={k}>{t}</option>)}</Select>}
          <button type="button" className="text-left text-sm font-bold text-red-600 sm:col-span-2" onClick={() => setRows(rows.filter((_, k) => k !== i))}>Remove this line</button>
        </div>))}
      <Button type="button" variant="soft" onClick={() => setRows([...rows, { ...MED_EMPTY }])}>+ {label}</Button>
    </div>
  );
}

const SECTIONS = ["A. Admission", "B. Clinical history", "C. Treatment", "D. Discharge and recovery"];
const dt = (iso) => (iso ? iso.slice(0, 16) : "");
const T = ({ f, set, k, label, rows = 2, hint }) => <Field label={label} hint={hint}><Textarea rows={rows} value={f[k]} onChange={(e) => set({ [k]: e.target.value })} /></Field>;
const I = ({ f, set, k, label, ...rest }) => <Field label={label}><Input value={f[k]} onChange={(e) => set({ [k]: e.target.value })} {...rest} /></Field>;

export function AdmissionForm({ patientId, record, onSaved, onClose }) {
  const r = record || {};
  const v = r.vitals || {};
  const clean = (rows) => rows.map((m) => ({ ...MED_EMPTY, ...m }));
  const [step, setStep] = useState(0);
  const [f, set] = useForm({
    hospital_name: r.hospital_name || "", admitted_at: dt(r.admitted_at), admitted_date_text: r.admitted_date_text || "", discharged_at: dt(r.discharged_at), admission_type: r.admission_type || "",
    main_complaint: r.main_complaint || "", secondary_complaints: r.secondary_complaints || "", provisional_diagnosis: r.provisional_diagnosis || "", final_diagnosis: r.final_diagnosis || "",
    reason: r.reason || "", referred_by: r.referred_by || "", symptoms: r.symptoms || "", history_of_present_illness: r.history_of_present_illness || "", preexisting_conditions: r.preexisting_conditions || "",
    bp_systolic: v.bp_systolic ?? "", bp_diastolic: v.bp_diastolic ?? "", pulse: v.pulse ?? "", resp_rate: v.resp_rate ?? "", temperature_f: v.temperature_f ?? "", spo2: v.spo2 ?? "", pain_score: v.pain_score ?? "", vitals_at: v.recorded_at || "",
    exam_findings: r.exam_findings || "", investigations: r.investigations || "", complications: r.complications || "", treatment_given: r.treatment_given || "",
    medications: clean(r.medications || []), iv_fluids_oxygen: r.iv_fluids_oxygen || "", procedures_supportive: r.procedures_supportive || "", medication_changes: r.medication_changes || "",
    response_to_treatment: r.response_to_treatment || "", stay_complications: r.stay_complications || "", discharge_condition: r.discharge_condition || "", treatment_completed: r.treatment_completed || "",
    discharge_medications: clean(r.discharge_medications || []), discharge_instructions: r.discharge_instructions || "", wound_rehab_instructions: r.wound_rehab_instructions || "",
    followup_date: r.followup_date || "", specialist_review: r.specialist_review || "", recovery_status: r.recovery_status || "", remaining_symptoms: r.remaining_symptoms || "",
    readmission_notes: r.readmission_notes || "", source: r.source === "EARLIER_ENTRY" || !r.source ? "PATIENT_REPORTED" : r.source,
  });
  const meds = (rows) => rows.filter((m) => m.name.trim()).map((m) => Object.fromEntries(Object.entries(m).map(([k, x]) => [k, blank(x)]).filter(([, x]) => x !== null)));
  const body = () => {
    const out = {};
    ["hospital_name", "admitted_date_text", "main_complaint", "secondary_complaints", "provisional_diagnosis", "final_diagnosis", "reason", "referred_by", "symptoms", "history_of_present_illness", "preexisting_conditions",
      "exam_findings", "investigations", "complications", "treatment_given", "iv_fluids_oxygen", "procedures_supportive", "medication_changes", "response_to_treatment", "stay_complications", "discharge_condition",
      "treatment_completed", "discharge_instructions", "wound_rehab_instructions", "specialist_review", "recovery_status", "remaining_symptoms", "readmission_notes"].forEach((k) => { out[k] = blank(f[k]); });
    return { ...out, admitted_at: f.admitted_at || null, discharged_at: f.discharged_at || null, followup_date: f.followup_date || null, admission_type: f.admission_type || null,
      vitals: { bp_systolic: num(f.bp_systolic), bp_diastolic: num(f.bp_diastolic), pulse: num(f.pulse), resp_rate: num(f.resp_rate), temperature_f: num(f.temperature_f), spo2: num(f.spo2), pain_score: num(f.pain_score), recorded_at: blank(f.vitals_at) },
      medications: meds(f.medications), discharge_medications: meds(f.discharge_medications), source: f.source };
  };
  const { saving, error, go } = useSave(() => saveAdmission(patientId, body(), record?.id), onSaved);
  const stay = f.admitted_at && f.discharged_at && f.discharged_at >= f.admitted_at ? (() => { const m = Math.round((new Date(f.discharged_at) - new Date(f.admitted_at)) / 60000); const d = Math.floor(m / 1440); const h = Math.floor((m % 1440) / 60); return `${d ? `${d} day${d > 1 ? "s" : ""} ` : ""}${h ? `${h} hour${h > 1 ? "s" : ""}` : ""}`.trim() || "less than an hour"; })() : null;

  return (
    <Modal wide title={record ? "Edit hospital admission" : "Add a previous hospital admission"} onClose={onClose}>
      <div className="mb-4 grid grid-cols-2 gap-1.5 sm:grid-cols-4">{SECTIONS.map((s, i) => (
        <button key={s} type="button" onClick={() => setStep(i)} className={`rounded-xl px-2 py-2 text-sm font-bold ${i === step ? "bg-brand-700 text-white" : "bg-slate-100 text-slate-700 hover:bg-slate-200"}`}>{s}</button>))}</div>
      <div className="space-y-3">
        {step === 0 && (<>
          <Grid><I f={f} set={set} k="hospital_name" label="Hospital name" />
            <Field label="Admission type"><Select value={f.admission_type} onChange={(e) => set({ admission_type: e.target.value })}><option value="">Not recorded</option><option value="EMERGENCY">Emergency</option><option value="PLANNED">Planned</option><option value="REFERRAL">Referral</option><option value="OTHER">Other</option></Select></Field>
            <Field label="Admission date and time"><Input type="datetime-local" max={new Date().toISOString().slice(0, 16)} value={f.admitted_at} onChange={(e) => set({ admitted_at: e.target.value })} /></Field>
            <Field label="Discharge date and time"><Input type="datetime-local" min={f.admitted_at || undefined} value={f.discharged_at} onChange={(e) => set({ discharged_at: e.target.value })} /></Field>
          </Grid>
          <I f={f} set={set} k="admitted_date_text" label="If the exact date is not known, write what is known" placeholder="e.g. around March 2019" />
          <p className="rounded-xl bg-brand-50 p-2.5 text-sm text-brand-900"><b>Length of stay: </b>{stay || "worked out automatically when both the admission and the discharge time are entered."}</p>
          <T f={f} set={set} k="main_complaint" label="Main complaint at admission" /><T f={f} set={set} k="secondary_complaints" label="Secondary complaints" />
          <Grid><T f={f} set={set} k="provisional_diagnosis" label="Provisional diagnosis" /><T f={f} set={set} k="final_diagnosis" label="Final diagnosis" /></Grid>
          <T f={f} set={set} k="reason" label="Reason for hospitalisation" /><I f={f} set={set} k="referred_by" label="Referring doctor or hospital (if any)" />
        </>)}
        {step === 1 && (<>
          <T f={f} set={set} k="symptoms" label="Symptoms at admission" /><T f={f} set={set} k="history_of_present_illness" label="History of the present illness (at that time)" rows={3} />
          <T f={f} set={set} k="preexisting_conditions" label="Relevant illnesses the patient already had" />
          <Sub>Vital signs measured at admission (leave empty what was not recorded)</Sub>
          <Grid cols={3}>
            <Field label="BP top (mmHg)"><Input type="number" inputMode="decimal" value={f.bp_systolic} onChange={(e) => set({ bp_systolic: e.target.value })} /></Field>
            <Field label="BP bottom (mmHg)"><Input type="number" inputMode="decimal" value={f.bp_diastolic} onChange={(e) => set({ bp_diastolic: e.target.value })} /></Field>
            <Field label="Pulse (per min)"><Input type="number" inputMode="decimal" value={f.pulse} onChange={(e) => set({ pulse: e.target.value })} /></Field>
            <Field label="Breathing rate (per min)"><Input type="number" inputMode="decimal" value={f.resp_rate} onChange={(e) => set({ resp_rate: e.target.value })} /></Field>
            <Field label="Temperature (F)"><Input type="number" inputMode="decimal" step="0.1" value={f.temperature_f} onChange={(e) => set({ temperature_f: e.target.value })} /></Field>
            <Field label="Oxygen SpO2 (%)"><Input type="number" inputMode="decimal" value={f.spo2} onChange={(e) => set({ spo2: e.target.value })} /></Field>
            <Field label="Pain score (0-10)"><Input type="number" inputMode="decimal" min="0" max="10" value={f.pain_score} onChange={(e) => set({ pain_score: e.target.value })} /></Field>
            <Field label="Measured at"><Input value={f.vitals_at} onChange={(e) => set({ vitals_at: e.target.value })} placeholder="time or date" /></Field>
          </Grid>
          <T f={f} set={set} k="exam_findings" label="Important physical examination findings" rows={3} /><T f={f} set={set} k="investigations" label="Laboratory investigations and imaging reports" rows={3} />
          <T f={f} set={set} k="complications" label="Complications associated with the diagnosis" />
        </>)}
        {step === 2 && (<>
          <T f={f} set={set} k="treatment_given" label="Treatment provided" rows={3} />
          <Sub>Medicines given during the stay (name, dose, how often, route, how long)</Sub>
          <MedRows rows={f.medications} setRows={(medications) => set({ medications })} withCategory label="Add a medicine given (antibiotic, painkiller, IV fluid ...)" />
          <T f={f} set={set} k="iv_fluids_oxygen" label="IV fluids and oxygen therapy" /><T f={f} set={set} k="procedures_supportive" label="Other procedures or supportive treatment" />
          <T f={f} set={set} k="medication_changes" label="Important changes in medication" /><T f={f} set={set} k="response_to_treatment" label="Clinical response to treatment" />
          <T f={f} set={set} k="stay_complications" label="Complications during the hospital stay" />
          <p className="rounded-xl bg-slate-50 p-2.5 text-sm text-slate-600">Operations done during this admission are added after saving, with "Add an operation".</p>
        </>)}
        {step === 3 && (<>
          <T f={f} set={set} k="discharge_condition" label="Condition at discharge" /><T f={f} set={set} k="treatment_completed" label="Treatment completed" />
          <Sub>Medicines given at discharge</Sub>
          <MedRows rows={f.discharge_medications} setRows={(discharge_medications) => set({ discharge_medications })} label="Add a discharge medicine" />
          <T f={f} set={set} k="discharge_instructions" label="Discharge instructions" rows={3} /><T f={f} set={set} k="wound_rehab_instructions" label="Wound care or rehabilitation instructions (if relevant)" />
          <Grid><Field label="Follow-up appointment date"><Input type="date" value={f.followup_date} onChange={(e) => set({ followup_date: e.target.value })} /></Field><I f={f} set={set} k="specialist_review" label="Recommended specialist review" /></Grid>
          <T f={f} set={set} k="recovery_status" label="Recovery status" /><T f={f} set={set} k="remaining_symptoms" label="Remaining symptoms" />
          <T f={f} set={set} k="readmission_notes" label="Readmission or complications after discharge (if any)" />
        </>)}
        <SourcePick value={f.source} onChange={(x) => set({ source: x })} />
      </div>
      <Footer saving={saving} error={error} onClose={onClose} onSave={go}
        extra={<>{step > 0 && <Button variant="secondary" type="button" onClick={() => setStep(step - 1)}>Back</Button>}{step < 3 && <Button variant="soft" type="button" onClick={() => setStep(step + 1)}>Next section</Button>}</>} />
    </Modal>
  );
}

// ------------------------------------------------------------------ operation or procedure
export function SurgeryForm({ patientId, record, admissions, presetAdmission, onSaved, onClose }) {
  const r = record || {};
  const [f, set] = useForm({
    admission_id: r.admission_id ?? presetAdmission ?? "", procedure_name: r.procedure_name || "", reason: r.reason || "", body_site: r.body_site || "", operation_date: r.operation_date || "",
    operation_year: r.operation_year ?? "", surgeon: r.surgeon || "", hospital: r.hospital || "", anesthesia: r.anesthesia || "", findings: r.findings || "",
    implant_used: r.implant_used == null ? "" : r.implant_used ? "yes" : "no", implant_type: r.implant_type || "", implant_material: r.implant_material || "", implant_serial: r.implant_serial || "",
    postop_xray: r.postop_xray || "", postop_treatment: r.postop_treatment || "", postop_complications: r.postop_complications || "", recovery_progress: r.recovery_progress || "",
    source: r.source === "EARLIER_ENTRY" || !r.source ? "PATIENT_REPORTED" : r.source,
  });
  const body = () => ({
    admission_id: f.admission_id === "" ? null : Number(f.admission_id), procedure_name: blank(f.procedure_name) || "", reason: blank(f.reason), body_site: blank(f.body_site), operation_date: f.operation_date || null,
    operation_year: num(f.operation_year), surgeon: blank(f.surgeon), hospital: blank(f.hospital), anesthesia: blank(f.anesthesia), findings: blank(f.findings),
    implant_used: f.implant_used === "" ? null : f.implant_used === "yes", implant_type: f.implant_used === "yes" ? blank(f.implant_type) : null, implant_material: f.implant_used === "yes" ? blank(f.implant_material) : null,
    implant_serial: f.implant_used === "yes" ? blank(f.implant_serial) : null, postop_xray: blank(f.postop_xray), postop_treatment: blank(f.postop_treatment), postop_complications: blank(f.postop_complications),
    recovery_progress: blank(f.recovery_progress), source: f.source,
  });
  const { saving, error, go } = useSave(() => saveSurgery(patientId, body(), record?.id), onSaved);
  return (
    <Modal wide title={record ? `Edit operation: ${r.procedure_name}` : "Add an operation or procedure"} onClose={onClose}>
      <div className="space-y-3">
        <Grid>
          <I f={f} set={set} k="procedure_name" label="Operation or procedure" placeholder="e.g. Intramedullary nailing" />
          <Field label="Part of which admission?"><Select value={f.admission_id} onChange={(e) => set({ admission_id: e.target.value })}><option value="">Not linked to an admission</option>{admissions.map((a) => <option key={a.id} value={a.id}>{[a.admitted_at ? a.admitted_at.slice(0, 10) : a.admitted_date_text, a.main_complaint || a.reason || a.final_diagnosis].filter(Boolean).join(" - ") || `Admission ${a.id}`}</option>)}</Select></Field>
          <I f={f} set={set} k="body_site" label="Site (for a fracture: bone and location)" placeholder="e.g. right femur, shaft" />
          <Field label="Operation date"><Input type="date" max={new Date().toISOString().slice(0, 10)} value={f.operation_date} onChange={(e) => set({ operation_date: e.target.value })} /></Field>
          <Field label="Or only the year, if the date is not known"><Input type="number" inputMode="decimal" min="1900" max={thisYear} value={f.operation_year} onChange={(e) => set({ operation_year: e.target.value })} /></Field>
          <I f={f} set={set} k="surgeon" label="Surgeon" /><I f={f} set={set} k="hospital" label="Hospital" /><I f={f} set={set} k="anesthesia" label="Type of anaesthesia (if documented)" />
        </Grid>
        <T f={f} set={set} k="reason" label="Reason for the operation" /><T f={f} set={set} k="findings" label="Surgical findings" />
        <Sub>Implant or device</Sub>
        <Field label="Was an implant or device used?" hint="Not every operation uses one. Leave 'Not documented' if it is not known."><Select value={f.implant_used} onChange={(e) => set({ implant_used: e.target.value })}><option value="">Not documented</option><option value="yes">Yes</option><option value="no">No</option></Select></Field>
        {f.implant_used === "yes" && <Grid cols={3}>
          <Field label="Implant type"><Select value={f.implant_type} onChange={(e) => set({ implant_type: e.target.value })}><option value="">Not recorded</option>{["Plate", "Screws", "Rod / nail", "Prosthesis", "Other"].map((x) => <option key={x}>{x}</option>)}</Select></Field>
          <I f={f} set={set} k="implant_material" label="Material or manufacturer" /><I f={f} set={set} k="implant_serial" label="Implant ID or serial number" />
        </Grid>}
        <T f={f} set={set} k="postop_xray" label="Post-operative X-ray findings (if relevant)" /><T f={f} set={set} k="postop_treatment" label="Post-operative treatment" />
        <T f={f} set={set} k="postop_complications" label="Post-operative complications" /><T f={f} set={set} k="recovery_progress" label="Recovery progress" />
        <SourcePick value={f.source} onChange={(x) => set({ source: x })} />
      </div>
      <Footer saving={saving} error={error} onClose={onClose} onSave={go} />
    </Modal>
  );
}
