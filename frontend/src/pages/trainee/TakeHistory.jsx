// A trainee takes a patient's history. Step 1: choose the patient. Step 2: the structured form, saved automatically as a draft. Step 3: Complete, then Select doctor.
// A draft is never lost: when a save fails the typed values stay on the screen and the save is tried again.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { CheckCircle2, CloudOff, Loader2, Search } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import { completeTraineeHistory, listTraineePatients, saveTraineeHistory, startTraineeHistory } from "../../services/traineeApi";
import { getErrorMessage } from "../../services/api";
import { Block, Chips } from "../../components/historyKit";
import { EmptyState, ErrorBox, Loading, PageTitle } from "../../components/Feedback";
import { FormField } from "../../components/FormField";
import { Button, Input, Select, Textarea } from "../../components/ui";
import * as v from "../../utils/validators";

export const COMMON_SYMPTOMS = ["Fever", "Cough", "Chest pain", "Breathlessness", "Headache", "Giddiness", "Vomiting", "Abdominal pain", "Diarrhoea", "Skin rash", "Joint pain", "Burning urine", "Weakness", "Weight loss"];
export const EMPTY = {
  chief_complaint: "", duration: "", symptoms: [], present_illness: "", past_medical: "", past_surgical: "", medications: "", allergies: "", allergy_details: "",
  family_history: "", smoking: "", alcohol: "", personal_social: "", menstrual_obstetric: "",
  vitals: { pulse: "", bp_systolic: "", bp_diastolic: "", temperature_f: "", resp_rate: "", spo2: "", weight_kg: "", height_cm: "" },
};
// the same ranges as the server (docs/VALIDATION_RULES.md)
const VITAL_FIELDS = [
  ["pulse", "Pulse (beats a minute)", 20, 250], ["bp_systolic", "BP upper (mmHg)", 50, 300], ["bp_diastolic", "BP lower (mmHg)", 30, 200], ["temperature_f", "Temperature (°F)", 86, 113],
  ["resp_rate", "Breathing rate (a minute)", 4, 80], ["spo2", "Oxygen (%)", 50, 100], ["weight_kg", "Weight (kg)", 1, 500], ["height_cm", "Height (cm)", 30, 260],
];

export function vitalError(key, value) {
  const spec = VITAL_FIELDS.find((f) => f[0] === key);
  if (!spec || value === "" || value == null) return "";
  const n = Number(value);
  if (!Number.isFinite(n)) return "Please type a number.";
  return n < spec[2] || n > spec[3] ? `Should be between ${spec[2]} and ${spec[3]}.` : "";
}

/** The rules for completing a history (the same as the server): complaint, duration and an explicit allergy answer. */
export function completionErrors(d) {
  const e = {};
  if (!String(d.chief_complaint || "").trim()) e.chief_complaint = "Please write the main complaint.";
  if (!String(d.duration || "").trim()) e.duration = "Please write how long it has been going on.";
  if (!d.allergies) e.allergies = "Please choose None or Yes. None is an answer too.";
  else if (d.allergies === "YES" && !String(d.allergy_details || "").trim()) e.allergy_details = "Please write what the patient is allergic to.";
  return e;
}

const fromServer = (data) => ({ ...EMPTY, ...Object.fromEntries(Object.entries(data || {}).map(([k, val]) => [k, val ?? EMPTY[k] ?? ""])),
  vitals: { ...EMPTY.vitals, ...Object.fromEntries(Object.entries(data?.vitals || {}).map(([k, val]) => [k, val ?? ""])) } });
const toServer = (d) => ({
  ...d, symptoms: d.symptoms, smoking: d.smoking || null, alcohol: d.alcohol || null, allergies: d.allergies || null,
  chief_complaint: d.chief_complaint.trim() || null, duration: d.duration.trim() || null,
  vitals: Object.fromEntries(Object.entries(d.vitals).map(([k, val]) => [k, val === "" ? null : Number(val)])),
});

function PatientPicker() {
  const [q, setQ] = useState("");
  const { data, loading, error, reload } = useFetch(() => listTraineePatients(q), [q]);
  return (
    <div className="space-y-4">
      <PageTitle title="Take history" subtitle="Choose the patient. You see patients of your department and patients who have just been registered." />
      <div className="relative">
        <Search className="pointer-events-none absolute left-3.5 top-3 text-slate-400" size={18} />
        <Input aria-label="Search patients" className="pl-10" placeholder="Search by name, patient ID or phone" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      {loading && !data ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> : data.length === 0 ? (
        <EmptyState message={q ? "Nobody matches your search" : "No patients waiting"} hint="New patients appear here as soon as reception registers them." />
      ) : (
        <ul className="space-y-2">
          {data.map((p) => (
            <li key={p.id} className="flex items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-4">
              <div><p className="font-bold text-slate-900">{p.full_name}</p><p className="text-sm text-slate-500">{p.patient_code} · {p.age ?? "?"} years · {p.gender || "gender not set"}</p></div>
              <Link to={`/trainee/take-history/${p.id}`} aria-label={`Take history of ${p.full_name}`}><Button type="button">Take history</Button></Link>
            </li>))}
        </ul>)}
    </div>
  );
}

function SaveState({ state, onRetry }) {
  if (state === "saving") return <span className="inline-flex items-center gap-1 text-sm text-slate-500"><Loader2 size={14} className="animate-spin" /> Saving...</span>;
  if (state === "saved") return <span className="inline-flex items-center gap-1 text-sm text-emerald-700"><CheckCircle2 size={14} /> Draft saved</span>;
  if (state === "failed") return <span role="alert" className="inline-flex items-center gap-2 text-sm font-semibold text-red-700"><CloudOff size={14} /> Not saved yet. What you typed is still here. <button type="button" className="underline" onClick={onRetry}>Try again</button></span>;
  if (state === "invalid") return <span className="text-sm font-semibold text-amber-700">Fix the marked values to save the draft.</span>;
  return <span className="text-sm text-slate-400">Saved automatically as you type</span>;
}

function HistoryForm({ patientId }) {
  const navigate = useNavigate();
  const [load, setLoad] = useState({ loading: true, error: "" });
  const [history, setHistory] = useState(null);
  const [d, setD] = useState(EMPTY);
  const [saveState, setSaveState] = useState("idle");
  const [shown, setShown] = useState({});                       // errors shown under the fields
  const [problem, setProblem] = useState("");
  const [busy, setBusy] = useState(false);
  const dirty = useRef(false);
  const latest = useRef(d);
  latest.current = d;

  useEffect(() => {
    let current = true;
    startTraineeHistory(Number(patientId))
      .then((h) => { if (current) { setHistory(h); setD(fromServer(h.data)); setLoad({ loading: false, error: "" }); } })
      .catch((err) => { if (current) setLoad({ loading: false, error: getErrorMessage(err) }); });
    return () => { current = false; };
  }, [patientId]);

  const vitalProblems = useMemo(() => Object.fromEntries(Object.keys(d.vitals).map((k) => [k, vitalError(k, d.vitals[k])]).filter(([, m]) => m)), [d.vitals]);
  const invalid = Object.keys(vitalProblems).length > 0;

  const save = useCallback(async () => {
    if (!history) return false;
    if (Object.keys(latest.current.vitals).some((k) => vitalError(k, latest.current.vitals[k]))) { setSaveState("invalid"); return false; }
    setSaveState("saving");
    const sent = latest.current;
    try {
      await saveTraineeHistory(history.id, toServer(sent));
      if (latest.current === sent) dirty.current = false;
      setSaveState("saved");
      return true;
    } catch (err) {
      setSaveState("failed");                                   // the form keeps every value
      setProblem(getErrorMessage(err));
      return false;
    }
  }, [history]);

  useEffect(() => {                                              // autosave a moment after the last change
    if (!dirty.current || !history) return undefined;
    const timer = setTimeout(save, 1200);
    return () => clearTimeout(timer);
  }, [d, history, save]);

  useEffect(() => {                                              // do not close the page on unsaved typing
    const warn = (e) => { if (dirty.current) { e.preventDefault(); e.returnValue = ""; } };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, []);

  const set = (key) => (e) => { dirty.current = true; setProblem(""); setD((x) => ({ ...x, [key]: e.target.value })); setShown((s) => (s[key] ? { ...s, [key]: "" } : s)); };
  const setVital = (key) => (e) => { dirty.current = true; setD((x) => ({ ...x, vitals: { ...x.vitals, [key]: e.target.value } })); };
  const toggleSymptom = (s) => { dirty.current = true; setD((x) => ({ ...x, symptoms: x.symptoms.includes(s) ? x.symptoms.filter((y) => y !== s) : [...x.symptoms, s] })); };
  const setAllergy = (value) => { dirty.current = true; setD((x) => ({ ...x, allergies: value, allergy_details: value === "NONE" ? "" : x.allergy_details })); setShown((s) => ({ ...s, allergies: "" })); };

  const complete = async () => {
    const errors = completionErrors(d);
    setShown(errors);
    if (Object.keys(errors).length) { document.getElementById(Object.keys(errors)[0])?.focus(); return; }
    if (invalid) return;
    setBusy(true);
    setProblem("");
    try {
      if (!(await save())) return;
      await completeTraineeHistory(history.id);
      dirty.current = false;
      navigate(`/trainee/select-doctor/${history.id}`);
    } catch (err) { setProblem(getErrorMessage(err)); } finally { setBusy(false); }
  };

  if (load.loading) return <Loading />;
  if (load.error) return <div className="space-y-3"><ErrorBox message={load.error} /><Link to="/trainee/take-history" className="font-semibold text-brand-700 underline">Choose another patient</Link></div>;
  const p = history.patient;
  const female = String(p.gender || "").toLowerCase() === "female";

  return (
    <div className="space-y-5 pb-24">
      <PageTitle title={`History: ${p.full_name}`} subtitle={`${p.patient_code} · ${p.age ?? "?"} years · ${p.gender || "gender not set"}`} />
      <Block title="Why the patient came" hint="The main complaint and how long it has been going on are needed to finish.">
        <div className="space-y-4">
          <FormField label="Main complaint *" name="chief_complaint" error={shown.chief_complaint}><Input maxLength={300} placeholder="For example: chest pain on climbing stairs" value={d.chief_complaint} onChange={set("chief_complaint")} /></FormField>
          <FormField label="For how long? *" name="duration" error={shown.duration}><Input maxLength={60} placeholder="For example: 2 weeks" value={d.duration} onChange={set("duration")} /></FormField>
          <div><p className="mb-1.5 text-sm font-semibold text-slate-700">Tap what the patient has</p><Chips items={COMMON_SYMPTOMS} selected={d.symptoms} onToggle={toggleSymptom} /></div>
          <FormField label="History of present illness" name="present_illness"><Textarea rows={4} maxLength={3000} value={d.present_illness} onChange={set("present_illness")} /></FormField>
        </div>
      </Block>

      <Block title="Past history">
        <div className="space-y-4">
          <FormField label="Past medical history" name="past_medical"><Textarea maxLength={2000} placeholder="Diabetes, high blood pressure, asthma ..." value={d.past_medical} onChange={set("past_medical")} /></FormField>
          <FormField label="Past surgical history" name="past_surgical"><Textarea maxLength={2000} value={d.past_surgical} onChange={set("past_surgical")} /></FormField>
          <FormField label="Medicines the patient takes" name="medications"><Textarea maxLength={1500} placeholder="Name, dose, how often" value={d.medications} onChange={set("medications")} /></FormField>
          <fieldset aria-describedby={shown.allergies ? "allergies-error" : undefined}>
            <legend className="mb-1.5 text-sm font-semibold text-slate-700">Allergies *</legend>
            <div className="flex gap-2">
              {[["NONE", "None"], ["YES", "Yes"]].map(([value, label]) => (
                <button key={value} id={value === "NONE" ? "allergies" : undefined} type="button" aria-pressed={d.allergies === value} onClick={() => setAllergy(value)}
                  className={`min-h-11 min-w-24 rounded-xl px-4 text-sm font-bold ${d.allergies === value ? (value === "YES" ? "bg-amber-500 text-white" : "bg-emerald-600 text-white") : "bg-white text-slate-600 ring-1 ring-slate-300"}`}>{label}</button>))}
            </div>
            {shown.allergies && <p id="allergies-error" className="mt-1 text-sm font-medium text-red-600">{shown.allergies}</p>}
            {d.allergies === "YES" && <div className="mt-3"><FormField label="Allergic to what? *" name="allergy_details" error={shown.allergy_details}><Textarea rows={2} maxLength={500} placeholder="For example: penicillin (rash)" value={d.allergy_details} onChange={set("allergy_details")} /></FormField></div>}
          </fieldset>
          <FormField label="Family history" name="family_history"><Textarea maxLength={1000} placeholder="Father: diabetes ..." value={d.family_history} onChange={set("family_history")} /></FormField>
        </div>
      </Block>

      <Block title="Personal and social history">
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField label="Smoking / tobacco" name="smoking"><Select value={d.smoking} onChange={set("smoking")}><option value="">Not asked</option><option value="NONE">None</option><option value="SMOKER">Smoker</option><option value="CHEWER">Chews tobacco</option><option value="FORMER">Stopped</option></Select></FormField>
          <FormField label="Alcohol" name="alcohol"><Select value={d.alcohol} onChange={set("alcohol")}><option value="">Not asked</option><option value="NONE">None</option><option value="OCCASIONAL">Occasional</option><option value="REGULAR">Regular</option><option value="FORMER">Stopped</option></Select></FormField>
        </div>
        <div className="mt-4"><FormField label="Occupation, diet, sleep, other" name="personal_social"><Textarea maxLength={1000} value={d.personal_social} onChange={set("personal_social")} /></FormField></div>
        {female && <div className="mt-4"><FormField label="Menstrual and obstetric history (optional)" name="menstrual_obstetric"><Textarea maxLength={1000} placeholder="Last period, cycle, pregnancies" value={d.menstrual_obstetric} onChange={set("menstrual_obstetric")} /></FormField></div>}
      </Block>

      <Block title="Basic vitals" hint="Leave blank what was not measured.">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {VITAL_FIELDS.map(([key, label]) => (
            <FormField key={key} label={label} name={`vital_${key}`} error={vitalProblems[key]}><Input type="number" inputMode="decimal" step="any" value={d.vitals[key]} onChange={setVital(key)} /></FormField>))}
        </div>
      </Block>

      <div className="fixed inset-x-0 bottom-0 z-20 border-t border-slate-200 bg-white/95 px-4 py-3 backdrop-blur md:left-64">
        <div className="mx-auto flex max-w-4xl flex-wrap items-center justify-between gap-3">
          <div className="min-h-6"><SaveState state={invalid ? "invalid" : saveState} onRetry={save} />{problem && <p role="alert" className="text-sm font-medium text-red-600">{problem}</p>}</div>
          <Button type="button" disabled={busy} onClick={complete}>{busy ? "Completing..." : "Mark complete and choose doctor"}</Button>
        </div>
      </div>
    </div>
  );
}

export default function TakeHistory() {
  const { patientId } = useParams();
  return patientId ? <HistoryForm key={patientId} patientId={patientId} /> : <PatientPicker />;
}
