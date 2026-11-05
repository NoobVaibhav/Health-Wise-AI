// The doctor's history form, kept simple: four big steps, one column, the rare things folded away.
//   Steps 1-2 = PERMANENT history (stays with the patient). Steps 3-4 = THIS VISIT (new every time).
// Almost everything is a tap or a pick-list. A draft is kept in this browser so nothing is lost, and the "points to check"
// are shown once, at the end, before saving.
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { AlertTriangle, ArrowLeft, ArrowRight, CheckCircle2, Lightbulb, Save } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import { addAssessment, getPatientHistoryForm, previewPoints, savePatientHistoryForm } from "../../services/historyApi";
import { getMedicineOptions, getTestOptions } from "../../services/catalogApi";
import { getErrorMessage } from "../../services/api";
import Autocomplete from "../../components/Autocomplete";
import PastHistory from "../../components/history/PastHistory";
import { AskTips, Block, Chips, Fold, MoreChips, NoneCheck, addPhrase } from "../../components/historyKit";
import { RowList, UsualValues, toForm, toPayload } from "../../components/historyFormData";
import { Button, Input, Select, Textarea, fmtDate, inputClass } from "../../components/ui";
import ActionBar from "../../components/ActionBar";
import { ErrorBox, Loading } from "../../components/Feedback";
import { useToast } from "../../components/Toast";

// ---------------------------------------------------------------- what the form offers
const STEPS = [
  { title: "Past history", part: "Stays with the patient", ask: ["Blood pressure, sugar, heart, thyroid, kidney, liver, asthma, TB, epilepsy, stroke, cancer?", "Since when, and is the patient on treatment?", "Any reaction to a medicine, injection, food or dust?", "Earlier hospital stays or operations?"] },
  { title: "Medicines and usual values", part: "Stays with the patient", ask: ["Ask to see the tablet strips or the old prescription.", "Include injections, inhalers, drops, ayurvedic medicines and supplements.", "Blood thinners, sugar tablets, water pills and heart tablets matter most.", "What are the usual pulse, BP and sugar when the patient is well?"] },
  { title: "Today's problem", part: "This visit", ask: ["What is the main problem, in the patient's words, and since when?", "Sudden or slow? Better, worse or the same? How many episodes?", "Anything with it: sweating, chest pain, palpitations, vomiting?", "Fever, cough, weight loss, change in urine or stool? Any fall or injury?"] },
  { title: "Examination and plan", part: "This visit", ask: ["Pulse and BP: repeat if abnormal.", "Orientation to time, place and person.", "Chest, heart, abdomen and nervous system.", "Write the provisional diagnosis yourself. The computer never suggests one."] },
];
const CONDITIONS = ["High blood pressure", "Diabetes", "Heart disease", "Asthma / COPD", "Thyroid problem", "Kidney disease", "Liver disease", "Stroke", "Heart failure", "Epilepsy / fits", "Tuberculosis", "Cancer", "Anaemia", "Arthritis", "Enlarged prostate", "Memory loss / Alzheimer's"];
const SINCE = ["Less than 1 year", "1 year", "5 years", "10 years", "20+ years"];
const ALLERGIES = ["Penicillin", "Sulfa drugs", "Aspirin / NSAIDs", "Cephalosporins", "Peanuts", "Dust", "Iodine contrast", "Latex", "Eggs", "Shellfish"];
const REACTIONS = ["Rash", "Itching", "Swelling", "Breathing difficulty", "Vomiting", "Anaphylaxis"];
const FREQUENCIES = ["Once daily", "Twice daily", "Three times daily", "At night", "If needed", "Once a week"];
const FAMILY = ["Heart disease", "Diabetes", "High blood pressure", "Cancer", "Stroke", "Asthma"];
const COMPLAINTS = ["Fever", "Chest pain", "Giddiness", "Loss of consciousness", "Breathlessness", "Palpitations", "Headache", "Cough", "Vomiting", "Pain in abdomen", "Weakness", "Swelling of feet", "Weight loss", "Burning urine", "Joint pain"];
const DURATIONS = ["Today", "1 day", "2-3 days", "1 week", "2 weeks", "1 month", "More than 1 month"];
const SYMPTOMS = ["Fever", "Chest pain", "Palpitations", "Giddiness", "Fainting / loss of consciousness", "Breathlessness", "Sweating", "Headache", "Weakness", "Vomiting", "Cough", "Swelling of feet", "Tremors", "Involuntary movements"];
const STORY = [["Sudden onset", "It started suddenly."], ["Gradual onset", "It started slowly."], ["2-3 episodes", "There were 2-3 episodes."], ["Lasted 10-15 min", "Each episode lasted 10-15 minutes."], ["With sweating", "It came with sweating."], ["Relieved by rest", "It was relieved by rest."], ["Getting worse", "It is getting worse."], ["No injury or fall", "There was no injury or fall."]];
const SIGNS = ["Pallor", "Icterus (jaundice)", "Cyanosis", "Clubbing", "Oedema (swelling)", "Lymph nodes"];
const EXAM = [
  ["consciousness", "Consciousness", "Conscious, well oriented to time, place and person"],
  ["respiratory", "Chest (breathing)", "B/L air entry present, no added sounds, chest movements equal"],
  ["cardiovascular", "Heart", "S1 S2 heard, no added sounds, no murmur"],
  ["abdomen", "Abdomen", "Soft, non-tender, no organomegaly, bowel sounds present"],
  ["nervous_system", "Nervous system", "Higher functions normal, power and tone normal, reflexes normal"],
];
const QUICK_TESTS = ["ECG", "Complete Blood Count (CBC)", "Kidney function test (KFT)", "Liver function test (LFT)", "Urine routine and microscopy", "2D echo", "Lipid profile", "Chest X-ray", "Random blood sugar", "Troponin / CPK-MB", "Thyroid profile (T3, T4, TSH)"];
const PLANS = { Medical: "MEDICAL", Surgical: "SURGICAL", "Medical and surgical": "BOTH" };

// vitals outside the limits commonly used for adults (the same limits the server's points to check use)
const FLAG = { pulse: (x) => (x < 50 ? "Slow" : x > 120 ? "Fast" : ""), sys: (x) => (x >= 180 ? "Very high" : x < 90 ? "Low" : ""), dia: (x) => (x >= 110 ? "Very high" : ""), spo2: (x) => (x < 92 ? "Low" : ""), temp: (x) => (x >= 100.4 ? "Fever" : ""), rr: (x) => (x > 24 ? "Fast" : "") };
const num = (x) => (x === "" || x === undefined || x === null ? null : Number(x));
const emptyVisit = () => ({ complaint: "", duration: "", story: "", vitals: {}, present: [], allClear: false, exam: {}, dx: "", tests: [], plan: "", planDetails: "", note: "" });

// the detailed records in the shape the "points to check" preview expects (nothing is saved from this)
const fromPast = (p) => (p ? {
  conditions: [p.diabetes, p.hypertension, ...p.other_conditions].filter(Boolean).map((c) => ({ name: c.name, since: c.diagnosis_year ? String(c.diagnosis_year) : c.duration_text || null, on_treatment: !!c.on_treatment, notes: c.notes })),
  medications: p.medications.map((m) => ({ name: m.name, dose: m.dose, frequency: m.frequency, reason: m.reason, since: m.since, notes: m.notes, is_current: m.is_current })),
  surgeries: [...p.standalone_surgeries, ...p.admissions.flatMap((a) => a.surgeries)].map((x) => ({ what: x.procedure_name, year: x.operation_date ? x.operation_date.slice(0, 4) : x.operation_year ? String(x.operation_year) : null, hospital: x.hospital })),
} : {});

function composeGeneral(v) {
  const clear = v.allClear ? SIGNS.filter((s) => !v.present.includes(s)).map((s) => s.split(" (")[0].toLowerCase()) : [];
  return [clear.length ? `No ${clear.join(", ")}` : "", v.present.length ? `Present: ${v.present.map((s) => s.split(" (")[0].toLowerCase()).join(", ")}` : ""].filter(Boolean).join(". ") || null;
}

export default function TakeHistory() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const { data, loading, error, reload } = useFetch(() => getPatientHistoryForm(id), [id]);
  const [medicines, setMedicines] = useState([]);
  const [tests, setTests] = useState([]);
  const [f, setF] = useState(null);                // permanent history, same shape as the patient's own form
  const [v, setV] = useState(emptyVisit());        // this visit
  const [step, setStep] = useState(0);
  const [pastState, setPastState] = useState(null);   // the detailed past history; it saves itself, so the form never sends it again
  const [live, setLive] = useState({ points_to_check: [], suggested_tests: [] });
  const [saving, setSaving] = useState(false);
  const [restored, setRestored] = useState(false);
  const [fromAppointment, setFromAppointment] = useState(null);   // the day of the appointment whose problem was copied in
  const [testText, setTestText] = useState("");
  const draftKey = `hw_history_draft_${id}`;
  const ready = useRef(false);

  useEffect(() => {
    getMedicineOptions().then((l) => setMedicines(l.map((m) => ({ name: m.name, hint: m.in_stock ? "In stock" : undefined })))).catch(() => {});
    getTestOptions().then((l) => setTests(l.map((t) => ({ name: t.name, hint: t.group })))).catch(() => {});
  }, []);

  // start from what is already saved; an unsaved draft kept in this browser wins
  useEffect(() => {
    if (!data || ready.current) return;
    ready.current = true;
    setPastState(data.past);
    try {
      const draft = JSON.parse(localStorage.getItem(draftKey) || "null");
      if (draft?.f && draft?.v) { setF(draft.f); setV({ ...emptyVisit(), ...draft.v }); setRestored(true); return; }
    } catch { /* no draft */ }
    const base = toForm(data.history);
    base.current_problem = { ...base.current_problem, symptoms: [], denies: [] };
    // what the patient wrote when booking the appointment is the starting point for today's problem
    const told = data.appointment_problem;
    if (told) {
      const names = { Fainting: "Fainting / loss of consciousness" };
      base.current_problem.symptoms = (told.symptoms || []).map((s) => names[s] || s);
      setV((o) => ({ ...o, complaint: told.reason || "", duration: DURATIONS.includes(told.duration) ? told.duration : "", story: told.details || "" }));
      setFromAppointment(told.scheduled_at);
    }
    setF(base);
  }, [data, draftKey]);

  useEffect(() => {
    if (!f) return undefined;
    const t = setTimeout(() => { try { localStorage.setItem(draftKey, JSON.stringify({ f, v })); } catch { /* storage blocked */ } }, 700);
    return () => clearTimeout(t);
  }, [f, v, draftKey]);

  // the server works out the points to check as the form is filled in (nothing is saved)
  useEffect(() => {
    if (!f || !pastState) return undefined;
    const t = setTimeout(() => {
      const x = v.vitals;
      const body = { ...toPayload(f), ...fromPast(pastState) };
      previewPoints(id, {
        history: { ...body, current_problem: { ...body.current_problem, complaint: v.complaint || null, details: v.story || null } },
        vitals: { pulse: num(x.pulse), bp_systolic: num(x.sys), bp_diastolic: num(x.dia), spo2: num(x.spo2), temperature_f: num(x.temp), resp_rate: num(x.rr) },
      }).then(setLive).catch(() => {});
    }, 800);
    return () => clearTimeout(t);
  }, [f, v, id, pastState]);

  const done = useMemo(() => {
    if (!f || !pastState) return [false, false, false, false];
    const b = f.baseline;
    return [
      (pastState.counts.conditions > 0 || f.no_known_conditions) && (f.allergies.length > 0 || f.no_known_allergies),
      (pastState.counts.medications > 0 || f.no_regular_medicines) && !!(b.pulse || b.bp_systolic || b.sugar_fasting || b.hba1c),
      !!(v.complaint || f.current_problem.symptoms.length), !!(v.vitals.pulse || v.dx || v.tests.length)];
  }, [f, v, pastState]);

  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (!f || !pastState) return <Loading />;

  const card = data.card;
  const up = (patch) => setF((o) => ({ ...o, ...patch }));
  const vis = (patch) => setV((o) => ({ ...o, ...patch }));
  const habit = (k, val) => up({ habits: { ...f.habits, [k]: val } });
  const toggle = (list, item) => (list.includes(item) ? list.filter((x) => x !== item) : [...list, item]);
  const usual = f.baseline;
  const flagged = live.points_to_check.filter((p) => ["safety", "vitals"].includes(p.category));

  const setProblem = (patch) => up({ current_problem: { ...f.current_problem, ...patch } });

  const save = async () => {
    setSaving(true);
    try {
      const body = toPayload(f);
      body.current_problem = { ...body.current_problem, complaint: v.complaint || null, duration: v.duration || null, details: v.story || null };
      body.conditions = []; body.surgeries = []; body.medications = [];
      body.no_known_conditions = !!f.no_known_conditions && pastState.counts.conditions === 0;
      body.no_regular_medicines = !!f.no_regular_medicines && pastState.counts.medications === 0;
      body.no_past_surgery = !!f.no_past_surgery && pastState.counts.surgeries + pastState.counts.admissions === 0;
      await savePatientHistoryForm(id, body);
      const x = v.vitals;
      const filled = v.complaint || v.story || Object.values(x).some(Boolean) || v.dx || v.tests.length || Object.values(v.exam).some((t) => t && t.trim()) || v.present.length || v.allClear || v.note;
      if (filled) {
        const exam = (k) => (v.exam[k] && v.exam[k].trim()) || null;
        await addAssessment(id, {
          chief_complaint: v.complaint ? `${v.complaint}${v.duration ? ` (${v.duration})` : ""}` : null, history_of_present_illness: v.story || null,
          vitals: { pulse: num(x.pulse), bp_systolic: num(x.sys), bp_diastolic: num(x.dia), temperature_f: num(x.temp), resp_rate: num(x.rr), spo2: num(x.spo2), weight_kg: num(x.weight), height_cm: num(x.height) },
          examination: { consciousness: exam("consciousness"), general: composeGeneral(v), respiratory: exam("respiratory"), cardiovascular: exam("cardiovascular"), abdomen: exam("abdomen"), nervous_system: exam("nervous_system") },
          provisional_diagnosis: v.dx || null, investigations_advised: v.tests.join(", ") || null, plan_type: v.plan || null, plan_details: v.planDetails || null, special_note: v.note || null,
        });
      }
      try { localStorage.removeItem(draftKey); } catch { /* ignore */ }
      toast("Saved");
      navigate(`/doctor/patients/${id}`);
    } catch (e) { toast(getErrorMessage(e), "error"); } finally { setSaving(false); }
  };

  const normalAll = () => vis({ allClear: true, present: [], exam: Object.fromEntries(EXAM.map(([k, , text]) => [k, text])) });
  const addTest = (name) => { const t = name.trim(); if (t && !v.tests.includes(t)) vis({ tests: [...v.tests, t] }); setTestText(""); };
  const go = (n) => { setStep(n); window.scrollTo({ top: 0, behavior: "smooth" }); };

  // ---------------------------------------------------------------- the four steps
  const pages = [
    // 1 -------------------------------------------------------------- past history
    <div key="1" className="space-y-4">
      <Block title="Past medical history" done={pastState.counts.conditions > 0 || f.no_known_conditions} hint="Long-term illnesses, the medicines taken for them, earlier hospital stays and operations. Every entry is saved as soon as you add it.">
        <PastHistory patientId={id} past={pastState} labs={data.diabetes_labs} editable onChange={setPastState} />
        <div className="mt-4 space-y-0.5 border-t border-slate-200 pt-3">
          <p className="text-sm font-bold text-slate-600">If you asked and there is nothing to record:</p>
          <NoneCheck checked={f.no_known_conditions} disabled={pastState.counts.conditions > 0} onChange={(x) => up({ no_known_conditions: x })}>No known long-term illnesses</NoneCheck>
          <NoneCheck checked={f.no_regular_medicines} disabled={pastState.counts.medications > 0} onChange={(x) => up({ no_regular_medicines: x })}>No regular medicines</NoneCheck>
          <NoneCheck checked={f.no_past_surgery} disabled={pastState.counts.surgeries + pastState.counts.admissions > 0} onChange={(x) => up({ no_past_surgery: x })}>No operations or hospital stays</NoneCheck>
        </div>
      </Block>

      <Block title="Allergies" done={f.allergies.length > 0 || f.no_known_allergies} hint="Medicines, food or anything that caused a reaction.">
        <MoreChips items={ALLERGIES} show={6} tone="red" selected={f.allergies.map((a) => a.name)} onToggle={(a) => up({ no_known_allergies: false, allergies: f.allergies.some((x) => x.name === a) ? f.allergies.filter((x) => x.name !== a) : [...f.allergies, { name: a, kind: ["Peanuts", "Eggs", "Shellfish"].includes(a) ? "FOOD" : ["Dust", "Latex"].includes(a) ? "OTHER" : "DRUG" }] })} />
        {f.allergies.length > 0 && <div className="mt-4 space-y-2">{f.allergies.map((a, i) => (
          <div key={a.name} className="flex flex-wrap items-center gap-3 rounded-2xl bg-red-50/60 px-3 py-2"><b className="min-w-36 flex-1 text-red-900">{a.name}</b>
            <Select className={`${inputClass} !w-48 !py-1.5`} value={a.reaction ?? ""} onChange={(e) => up({ allergies: f.allergies.map((x, k) => (k === i ? { ...x, reaction: e.target.value } : x)) })}><option value="">What happened?</option>{REACTIONS.map((r) => <option key={r}>{r}</option>)}</Select></div>))}</div>}
        <OtherItem label="Another allergy" onAdd={(name) => up({ no_known_allergies: false, allergies: [...f.allergies, { name, kind: "DRUG" }] })} />
        <NoneCheck checked={f.no_known_allergies} disabled={f.allergies.length > 0} onChange={(x) => up({ no_known_allergies: x })}>No known allergies</NoneCheck>
      </Block>

      <Fold title="Habits, family and daily life" badge={f.habits.tobacco || f.habits.alcohol ? "filled" : ""}>
        <div className="space-y-4">
          <PickRow label="Tobacco" value={f.habits.tobacco} onPick={(x) => habit("tobacco", x)} options={[["NONE", "None"], ["SMOKER", "Smoker"], ["CHEWER", "Chews"], ["FORMER", "Stopped"]]} years={f.habits.tobacco_years} onYears={(x) => habit("tobacco_years", x)} showYears={["SMOKER", "CHEWER", "FORMER"].includes(f.habits.tobacco)} />
          <PickRow label="Alcohol" value={f.habits.alcohol} onPick={(x) => habit("alcohol", x)} options={[["NONE", "None"], ["OCCASIONAL", "Sometimes"], ["REGULAR", "Regular"], ["FORMER", "Stopped"]]} years={f.habits.alcohol_years} onYears={(x) => habit("alcohol_years", x)} showYears={["OCCASIONAL", "REGULAR", "FORMER"].includes(f.habits.alcohol)} />
          <PickRow label="Diet" value={f.habits.diet} onPick={(x) => habit("diet", x)} options={[["VEG", "Vegetarian"], ["NONVEG", "Non-veg"], ["MIXED", "Mixed"]]} />
          <PickRow label="Sleep" value={f.habits.sleep} onPick={(x) => habit("sleep", x)} options={[["ADEQUATE", "Normal"], ["POOR", "Poor"], ["EXCESS", "Too much"]]} />
          <div><p className="mb-2 text-sm font-bold text-slate-600">Family history</p>
            <MoreChips items={FAMILY} selected={f.family.map((x) => x.condition)} onToggle={(c) => up({ no_family_history: false, family: f.family.some((x) => x.condition === c) ? f.family.filter((x) => x.condition !== c) : [...f.family, { relation: "Family member", condition: c }] })} />
            <NoneCheck checked={f.no_family_history} disabled={f.family.length > 0} onChange={(x) => up({ no_family_history: x })}>Nothing important in the family</NoneCheck></div>
          <label className="block text-sm font-bold text-slate-600">Work and home<Textarea rows={2} value={f.socioeconomic} placeholder="e.g. retired, lives with family" onChange={(e) => up({ socioeconomic: e.target.value })} /></label>
          {card.gender?.toLowerCase().startsWith("f") && <label className="block text-sm font-bold text-slate-600">Periods and pregnancies<Textarea rows={2} value={f.menstrual_obstetric} onChange={(e) => up({ menstrual_obstetric: e.target.value })} /></label>}
          {(card.age ?? 99) < 18 && <label className="block text-sm font-bold text-slate-600">Birth, vaccines and development<Textarea rows={2} value={f.birth_history} onChange={(e) => up({ birth_history: e.target.value })} /></label>}
        </div>
      </Fold>
    </div>,

    // 2 -------------------------------------------------------------- medicines and usual values
    <div key="2" className="space-y-4">
      <p className="rounded-2xl bg-brand-50 p-3 text-sm text-brand-900">Medicines taken regularly are recorded in step 1, under "Past medical history", linked to the illness they are for.</p>

      <Block title="Usual values when well" done={!!(usual.pulse || usual.bp_systolic || usual.sugar_fasting || usual.hba1c)} hint="Today's pulse and BP are compared with these. Leave empty what you do not know.">
        <UsualValues baseline={f.baseline} onChange={(baseline) => up({ baseline })} />
      </Block>
      <LatestLabs labs={data.latest_labs} usual={f.baseline} onUse={(patch) => up({ baseline: { ...f.baseline, ...patch } })} />
    </div>,

    // 3 -------------------------------------------------------------- today's problem
    <div key="3" className="space-y-4">
      <Block title="What is the problem?" done={!!v.complaint} hint="Tap the usual complaints, or write your own. Then tap since when.">
        <MoreChips items={COMPLAINTS} onToggle={(c) => vis({ complaint: addPhrase(v.complaint, c, ", ") })} />
        <Textarea className={`${inputClass} mt-3`} rows={2} placeholder="Main complaint, in the patient's words" value={v.complaint} onChange={(e) => vis({ complaint: e.target.value })} />
        <p className="mb-1.5 mt-3 text-sm font-bold text-slate-600">Since when?</p>
        <Chips items={DURATIONS} selected={[v.duration]} onToggle={(d) => vis({ duration: v.duration === d ? "" : d })} />
      </Block>
      <Block title="Which of these does the patient have?" hint="Tap each one that is present.">
        <MoreChips items={SYMPTOMS} show={8} selected={f.current_problem.symptoms} onToggle={(s) => setProblem({ symptoms: toggle(f.current_problem.symptoms, s), denies: f.current_problem.denies.filter((x) => x !== s) })} />
        <div className="mt-3"><Fold title="Which are NOT there? (the 'no' answers help too)" badge={f.current_problem.denies.length || ""}>
          <Chips items={SYMPTOMS} tone="red" selected={f.current_problem.denies} onToggle={(s) => setProblem({ denies: toggle(f.current_problem.denies, s), symptoms: f.current_problem.symptoms.filter((x) => x !== s) })} />
        </Fold></div>
      </Block>
      <Fold title="Add the story of the illness" badge={v.story ? "added" : ""}>
        <Chips items={STORY.map(([l]) => l)} onToggle={(l) => vis({ story: addPhrase(v.story, STORY.find(([x]) => x === l)[1], " ") })} selected={[]} />
        <Textarea className={`${inputClass} mt-3`} rows={4} placeholder="What happened, how long, what made it better or worse" value={v.story} onChange={(e) => vis({ story: e.target.value })} />
      </Fold>
    </div>,

    // 4 -------------------------------------------------------------- examination and plan
    <div key="4" className="space-y-4">
      <Block title="Vitals" done={!!v.vitals.pulse} hint="A reading outside the usual adult limits turns red. The patient's own usual value is shown below each box.">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          {[["pulse", "Pulse", "/min", usual.pulse], ["sys", "BP top", "mmHg", usual.bp_systolic], ["dia", "BP bottom", "mmHg", usual.bp_diastolic], ["spo2", "SpO2", "%", usual.spo2], ["temp", "Temp", "F", null]].map(([k, label, unit, usualValue]) => {
            const flag = v.vitals[k] ? FLAG[k](Number(v.vitals[k])) : "";
            return (
              <label key={k} className="text-xs font-bold text-slate-500">{label} <span className="font-normal text-slate-400">{unit}</span>
                <Input type="number" inputMode="decimal" step={k === "temp" ? 0.1 : 1} className={`${inputClass} ${flag ? "!border-red-400 !bg-red-50" : ""}`} value={v.vitals[k] ?? ""} onChange={(e) => vis({ vitals: { ...v.vitals, [k]: e.target.value } })} />
                {flag && <span className="text-red-700">{flag}</span>}{usualValue ? <span className="block font-normal text-slate-400">usual {usualValue}</span> : null}</label>);
          })}
        </div>
        <div className="mt-3"><Fold title="More: breathing rate, weight, height">
          <div className="grid grid-cols-3 gap-3">{[["rr", "Resp. rate /min"], ["weight", "Weight kg"], ["height", "Height cm"]].map(([k, label]) => <label key={k} className="text-xs font-bold text-slate-500">{label}<Input type="number" inputMode="decimal" value={v.vitals[k] ?? ""} onChange={(e) => vis({ vitals: { ...v.vitals, [k]: e.target.value } })} /></label>)}</div>
        </Fold></div>
      </Block>

      <Block title="Examination" done={v.allClear || Object.values(v.exam).some((t) => t && t.trim())} hint="If everything is normal, one tap does it. Then change only what is different."
        right={<Button type="button" onClick={normalAll}><CheckCircle2 size={15} className="mr-1.5 inline" />Everything normal</Button>}>
        <div className="space-y-2">{EXAM.map(([k, label, normal]) => {
          const text = v.exam[k];
          const isNormal = text === normal;
          const abnormal = text !== undefined && text !== "" && !isNormal;       // a single space means "abnormal, text still to be written"
          return (
            <div key={k} className="rounded-2xl bg-slate-50 px-3 py-2.5">
              <div className="flex flex-wrap items-center gap-2"><b className="min-w-36 flex-1 text-slate-800">{label}</b>
                <button type="button" onClick={() => vis({ exam: { ...v.exam, [k]: isNormal ? "" : normal } })} className={`rounded-full px-3.5 py-1 text-sm font-bold ${isNormal ? "bg-emerald-600 text-white" : "bg-white text-emerald-700 ring-1 ring-emerald-300"}`}>Normal</button>
                <button type="button" onClick={() => vis({ exam: { ...v.exam, [k]: abnormal ? "" : " " } })} className={`rounded-full px-3.5 py-1 text-sm font-bold ${abnormal ? "bg-amber-500 text-white" : "bg-white text-amber-700 ring-1 ring-amber-300"}`}>Abnormal</button></div>
              {abnormal && <Textarea className={`${inputClass} mt-2`} rows={2} placeholder="Write what you found" value={text.trim() === "" ? "" : text} onChange={(e) => vis({ exam: { ...v.exam, [k]: e.target.value || " " } })} />}
              {isNormal && <p className="mt-1 text-sm text-slate-500">{normal}</p>}
            </div>);
        })}</div>
        <div className="mt-3"><Fold title="Signs: tap any that are PRESENT" badge={v.present.length || ""}>
          <Chips items={SIGNS} tone="red" selected={v.present} onToggle={(s) => vis({ present: toggle(v.present, s) })} />
          <p className="mt-2 text-xs text-slate-400">Tap "Everything normal" first to record the others as absent.</p>
        </Fold></div>
      </Block>

      <Block title="Diagnosis and tests" hint="The diagnosis is yours to write. The computer never suggests one.">
        <Textarea rows={2} placeholder="Provisional diagnosis" value={v.dx} onChange={(e) => vis({ dx: e.target.value })} />
        <p className="mb-1.5 mt-4 text-sm font-bold text-slate-600">Tests to advise</p>
        {live.suggested_tests.length > 0 && <div className="mb-3 rounded-2xl bg-amber-50 p-3"><p className="mb-1.5 flex items-center gap-1.5 text-xs font-extrabold uppercase text-amber-800"><Lightbulb size={14} /> Worth considering, from the history</p>
          <Chips items={live.suggested_tests} selected={v.tests} onToggle={(t) => vis({ tests: toggle(v.tests, t) })} /></div>}
        <MoreChips items={QUICK_TESTS.filter((t) => !live.suggested_tests.includes(t))} show={6} selected={v.tests} onToggle={(t) => vis({ tests: toggle(v.tests, t) })} />
        <div className="mt-3 max-w-md"><Autocomplete options={tests} value={testText} onChange={setTestText} onPick={addTest} onEnter={() => addTest(testText)} placeholder="Another test: type a few letters" /></div>
        {v.tests.length > 0 && <p className="mt-3 text-sm text-slate-700"><b>Selected:</b> {v.tests.join(", ")}</p>}
      </Block>

      <Fold title="Plan and notes" badge={v.plan ? Object.keys(PLANS).find((k) => PLANS[k] === v.plan) : ""}>
        <Chips items={Object.keys(PLANS)} selected={[Object.keys(PLANS).find((k) => PLANS[k] === v.plan)]} onToggle={(p) => vis({ plan: v.plan === PLANS[p] ? "" : PLANS[p] })} />
        <Textarea className={`${inputClass} mt-3`} rows={2} placeholder="Plan details, cross-consultation if necessary" value={v.planDetails} onChange={(e) => vis({ planDetails: e.target.value })} />
        <Textarea className={`${inputClass} mt-3`} rows={2} placeholder="Any other special note" value={v.note} onChange={(e) => vis({ note: e.target.value })} />
      </Fold>

      <Block title="Check before you save" hint="Things doctors often review, worked out from what you entered. Not a diagnosis.">
        {live.points_to_check.length === 0 ? <p className="text-slate-500">Nothing to flag so far.</p> : (
          <>
            {flagged.length > 0 && <ul className="mb-3 space-y-2">{flagged.map((p, i) => <li key={i} className="rounded-2xl border border-red-200 bg-red-50 p-3"><p className="font-bold text-red-900">{p.title}</p><p className="text-sm text-slate-700">{p.detail}</p></li>)}</ul>}
            {live.points_to_check.length > flagged.length && <Fold title="More points to check" badge={live.points_to_check.length - flagged.length}>
              <ul className="space-y-2">{live.points_to_check.filter((p) => !flagged.includes(p)).map((p, i) => <li key={i} className="rounded-2xl border border-slate-200 bg-slate-50 p-3"><p className="font-bold text-slate-900">{p.title}</p><p className="text-sm text-slate-600">{p.detail}</p></li>)}</ul>
            </Fold>}
          </>
        )}
      </Block>
    </div>,
  ];

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <div className="rounded-3xl bg-gradient-to-r from-brand-700 to-brand-600 p-5 text-white">
        <Link to={`/doctor/patients/${id}`} className="mb-1 inline-flex min-h-11 items-center gap-1 text-sm font-semibold text-brand-100 hover:underline"><ArrowLeft size={14} /> Back to the patient</Link>
        <h1 className="text-2xl font-extrabold">Take history: {card.name}</h1>
        <p className="text-brand-50">{card.age != null ? `${card.age} years` : ""}{card.gender ? ` - ${card.gender}` : ""} - {card.patient_code}{card.blood_group ? ` - ${card.blood_group}` : ""}</p>
      </div>

      {card.allergies.length > 0 && <p className="flex items-center gap-2 rounded-2xl border border-red-300 bg-red-50 p-3 text-sm font-bold text-red-800"><AlertTriangle size={16} /> Known allergy: {card.allergies.map((a) => a.name).join(", ")}</p>}
      {flagged.length > 0 && step < 3 && <button type="button" onClick={() => go(3)} className="flex w-full items-center gap-2 rounded-2xl border border-amber-300 bg-amber-50 p-3 text-left text-sm font-bold text-amber-900"><AlertTriangle size={16} /> {flagged.length} important point{flagged.length > 1 ? "s" : ""} to check. Tap to see them.</button>}
      {fromAppointment && !restored && <p className="rounded-2xl border border-sky-200 bg-sky-50 p-3 text-sm font-semibold text-sky-900">Today's problem was filled in from what the patient wrote when booking the appointment on {fmtDate(fromAppointment)}. Please check it with the patient.</p>}
      {restored && <p className="rounded-2xl bg-amber-50 p-3 text-sm font-semibold text-amber-900">An unsaved draft from this browser was restored. <button className="underline" onClick={() => { try { localStorage.removeItem(draftKey); } catch { /* ignore */ } ready.current = false; setRestored(false); setV(emptyVisit()); reload(); }}>Discard the draft</button></p>}

      <div className="grid grid-cols-4 gap-2">{STEPS.map((s, i) => (
        <button key={s.title} type="button" onClick={() => go(i)} className={`rounded-2xl px-2 py-2.5 text-center ${i === step ? "bg-brand-700 text-white shadow" : "bg-white text-slate-600 ring-1 ring-slate-200"}`}>
          <span className={`mx-auto mb-1 flex h-6 w-6 items-center justify-center rounded-full text-xs font-extrabold ${i === step ? "bg-white/20" : done[i] ? "bg-emerald-100 text-emerald-700" : "bg-slate-100"}`}>{done[i] && i !== step ? <CheckCircle2 size={14} /> : i + 1}</span>
          <span className="block text-xs font-bold leading-tight sm:text-sm">{s.title}</span></button>))}</div>
      <p className="text-center text-xs font-extrabold uppercase tracking-wide text-slate-600">{STEPS[step].part}</p>

      <AskTips items={STEPS[step].ask} />
      {pages[step]}

      <ActionBar status={<span className="num text-slate-700">Step {step + 1} of {STEPS.length}</span>}>
        <Button variant="secondary" disabled={step === 0} onClick={() => go(step - 1)}><ArrowLeft size={15} className="mr-1 inline" />Back</Button>
        {step < STEPS.length - 1 && <Button onClick={() => go(step + 1)}>Next<ArrowRight size={15} className="ml-1 inline" /></Button>}
        <Button variant={step < STEPS.length - 1 ? "secondary" : "primary"} onClick={save} disabled={saving}><Save size={15} className="mr-1.5 inline" />{saving ? "Saving..." : "Save"}</Button>
      </ActionBar>
    </div>
  );
}

/** A text box that adds an item when Enter is pressed (for anything that is not in the tap lists). */
function OtherItem({ onAdd, label }) {
  const [text, setText] = useState("");
  const add = () => { if (text.trim().length >= 2) { onAdd(text.trim()); setText(""); } };
  return (
    <div className="mt-3 flex max-w-md gap-2">
      <Input value={text} placeholder={`${label}: type, then press Enter`} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); add(); } }} />
      <Button type="button" variant="soft" onClick={add}>Add</Button>
    </div>
  );
}

function PickRow({ label, value, onPick, options, years, onYears, showYears }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="w-20 text-sm font-bold text-slate-600">{label}</span>
      {options.map(([val, text]) => <button type="button" key={val} onClick={() => onPick(value === val ? "" : val)} className={`rounded-full border px-3.5 py-1.5 text-sm font-semibold ${value === val ? "border-brand-600 bg-brand-50 text-brand-900" : "border-slate-300 bg-white text-slate-600"}`}>{text}</button>)}
      {showYears && <span className="flex items-center gap-1 text-sm text-slate-500">for <Input type="number" inputMode="decimal" min="0" className={`${inputClass} !w-20 !py-1`} value={years ?? ""} onChange={(e) => onYears(e.target.value)} /> years</span>}
    </div>
  );
}

/** The newest value of every test in the patient's reports, folded away, with one tap to use a value as the usual one. */
function LatestLabs({ labs, usual, onUse }) {
  if (!labs?.length) return null;
  const MAP = { HbA1c: "hba1c", Hemoglobin: "hemoglobin", Creatinine: "creatinine", "Fasting Glucose": "sugar_fasting" };
  return (
    <Fold title="Latest blood tests from the reports" badge={labs.length}>
      <table className="w-full text-sm">
        <thead><tr className="text-left text-xs text-slate-400"><th className="pb-1">Test</th><th>Latest</th><th>Normal range</th><th>Date</th><th /></tr></thead>
        <tbody>{labs.map((l) => (
          <tr key={l.name} className="border-t border-slate-100">
            <td className="py-1.5 font-semibold">{l.name}</td>
            <td className={`font-bold ${l.status === "ABOVE_RANGE" ? "text-amber-700" : l.status === "BELOW_RANGE" ? "text-sky-700" : "text-slate-800"}`}>{l.value} {l.unit}</td>
            <td className="text-slate-500">{l.range || "not printed"}</td><td className="text-slate-500">{fmtDate(l.date)}</td>
            <td className="text-right">{MAP[l.name] && usual[MAP[l.name]] === "" && <button type="button" className="rounded-full bg-brand-50 px-2.5 py-0.5 text-xs font-bold text-brand-800" onClick={() => onUse({ [MAP[l.name]]: l.value })}>Use as usual</button>}</td>
          </tr>))}</tbody>
      </table>
    </Fold>
  );
}
