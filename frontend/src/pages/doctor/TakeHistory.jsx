// The doctor's fast history form. Two parts, like the hospital sheet but much quicker to fill:
//   A. PERMANENT HISTORY (stays with the patient): illnesses, medicines, allergies, family and personal, usual values.
//   B. THIS VISIT (new each time): complaint, vitals, examination, diagnosis and plan.
// Almost everything is a tap: chips, Yes/No buttons, "normal" templates, pick-lists. On the right, "remember to ask"
// prompts and the live "points to check" follow what is typed. A draft is kept in this browser, so nothing is lost.
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { AlertTriangle, ArrowLeft, ArrowRight, CheckCircle2, ClipboardList, Lightbulb, Save } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import { addAssessment, getPatientHistoryForm, previewPoints, savePatientHistoryForm } from "../../services/historyApi";
import { getMedicineOptions, getTestOptions } from "../../services/catalogApi";
import { getErrorMessage } from "../../services/api";
import Autocomplete from "../../components/Autocomplete";
import { Block, Chips, NoneCheck, YesNo, addPhrase } from "../../components/historyKit";
import { RowList, UsualValues, toForm, toPayload } from "../../components/HistoryForm";
import { Button, Input, Textarea, fmtDate, inputClass } from "../../components/ui";
import { ErrorBox, Loading } from "../../components/Feedback";
import { useToast } from "../../components/Toast";

// ---------------------------------------------------------------- what the form offers
const STEPS = [
  { key: "past", part: "A", title: "Illnesses and operations", ask: [
    "Blood pressure, sugar, heart disease, thyroid, kidney, liver, asthma, TB, epilepsy, stroke, cancer?",
    "Since when, and is the patient on treatment for it?",
    "Any earlier hospital stay, operation or blood transfusion?",
    "Any recent change in treatment?"] },
  { key: "drugs", part: "A", title: "Medicines", ask: [
    "Ask the patient or family to show the tablet strips or the old prescription.",
    "Include injections, inhalers, drops, ayurvedic or herbal medicines and supplements.",
    "Which medicines were started or stopped recently? Are they taken regularly?",
    "Blood thinners, sugar tablets, water pills and heart tablets matter most."] },
  { key: "allergy", part: "A", title: "Allergies", ask: [
    "Any reaction to a medicine, injection, food, dust or contrast dye?",
    "What happened: rash, swelling, breathing trouble?"] },
  { key: "personal", part: "A", title: "Family and personal", ask: [
    "Tobacco and alcohol: how long and how much?",
    "Diet, appetite, sleep, bowel and bladder.",
    "Family: heart disease, diabetes, BP, cancer, sudden death.",
    "Who lives with the patient and can give the history? Occupation.",
    "Women: periods and pregnancies. Children: birth, vaccines, milestones."] },
  { key: "usual", part: "A", title: "Usual values", ask: [
    "What is the patient's usual pulse and BP when well? Ask for the last check-up slip.",
    "Usual sugar (fasting and after meals) and HbA1c.",
    "Last haemoglobin and creatinine, and any other important blood test (the latest ones from reports are listed here)."] },
  { key: "visit", part: "B", title: "Today's complaint", ask: [
    "What is the main problem, in the patient's own words, and since when?",
    "Sudden or slow? Getting better, worse or the same? How many episodes and how long did each last?",
    "What brings it on, and what relieves it? Anything with it: sweating, chest pain, palpitations, vomiting?",
    "Fever, cough, weight loss, change in urine or stool? Any fall or injury?"] },
  { key: "exam", part: "B", title: "Vitals and examination", ask: [
    "Pulse, BP, temperature, breathing rate and SpO2. Repeat if abnormal.",
    "Look for pallor, jaundice, cyanosis, clubbing, swelling and lymph nodes.",
    "Chest, heart, abdomen and nervous system. Orientation to time, place and person."] },
  { key: "plan", part: "B", title: "Diagnosis and plan", ask: [
    "Write the provisional diagnosis in your own words. The computer never suggests one.",
    "Pick the tests. The suggestions on the right come from the history.",
    "Medical or surgical plan. Cross-consultation if needed.",
    "Your name and the time are saved with this assessment automatically."] },
];
const CONDITION_PICKS = ["High blood pressure", "Diabetes", "Heart disease", "Heart failure", "Asthma / COPD", "Thyroid problem", "Kidney disease", "Liver disease", "Epilepsy / fits", "Tuberculosis", "Stroke", "Cancer", "Anaemia", "Arthritis", "Enlarged prostate", "Memory loss / Alzheimer's"];
const SINCE = ["< 1 year", "1 year", "5 years", "10 years", "20+ years"];
const FAMILY_PICKS = ["Heart disease", "Diabetes", "High blood pressure", "Cancer", "Stroke", "Asthma", "Kidney disease", "Thyroid problem"];
const ALLERGY_PICKS = ["Penicillin", "Sulfa drugs", "Aspirin / NSAIDs", "Cephalosporins", "Iodine contrast", "Latex", "Peanuts", "Eggs", "Shellfish", "Dust"];
const REACTIONS = ["Rash", "Itching", "Swelling", "Breathing difficulty", "Vomiting", "Anaphylaxis"];
const FREQUENCIES = [["OD", "Once daily"], ["BD", "Twice daily"], ["TDS", "Three times daily"], ["HS", "At night"], ["SOS", "If needed"], ["Weekly", "Once a week"]];
const COMPLAINTS = ["Fever", "Chest pain", "Giddiness", "Loss of consciousness", "Breathlessness", "Palpitations", "Headache", "Cough", "Vomiting", "Pain in abdomen", "Weakness", "Swelling of feet", "Weight loss", "Burning urine", "Joint pain"];
const DURATIONS = ["Today", "1 day", "2-3 days", "1 week", "2 weeks", "1 month", "More than 1 month"];
const SYMPTOMS = ["Fever", "Chest pain", "Palpitations", "Giddiness", "Fainting / loss of consciousness", "Breathlessness", "Headache", "Weakness", "Tremors", "Involuntary movements", "Vomiting", "Cough", "Swelling of feet", "Sweating"];
const STORY = [["Sudden onset", "It started suddenly."], ["Gradual onset", "It started slowly."], ["One episode", "There was one episode."], ["2-3 episodes", "There were 2-3 episodes."],
  ["Lasted under 1 min", "Each episode lasted less than a minute."], ["Lasted 10-15 min", "Each episode lasted 10-15 minutes."], ["With sweating", "It came with sweating."],
  ["Relieved by rest", "It was relieved by rest."], ["Getting worse", "It is getting worse."], ["No injury or fall", "There was no injury or fall."]];
const SIGNS = ["Pallor", "Icterus", "Cyanosis", "Clubbing", "Oedema", "Lymphadenopathy"];
const EXAM = [
  ["consciousness", "Consciousness and orientation", "Conscious, well oriented to time, place and person", []],
  ["respiratory", "Respiratory system", "B/L air entry present, no added sounds, chest movements equal", ["Crepts present", "Wheeze present", "Reduced air entry"]],
  ["cardiovascular", "Cardiovascular system", "S1 S2 heard, no added sounds, no murmur", ["Murmur heard", "Irregular rhythm", "Raised JVP"]],
  ["abdomen", "Abdomen", "Soft, non-tender, no organomegaly, bowel sounds present", ["Tenderness present", "Hepatomegaly", "Splenomegaly", "Ascites"]],
  ["nervous_system", "Nervous system", "Higher functions normal, power and tone normal, reflexes normal", ["Neck rigidity", "Weakness of a limb", "Slurred speech"]],
];
const QUICK_TESTS = ["ECG", "Complete Blood Count (CBC)", "Kidney function test (KFT)", "Liver function test (LFT)", "Urine routine and microscopy", "2D echo", "Lipid profile", "Chest X-ray", "Random blood sugar", "Troponin / CPK-MB", "Thyroid profile (T3, T4, TSH)"];

// vitals outside the limits commonly used for adults (the same limits the points-to-check use)
const VITAL_FLAG = {
  pulse: (v) => (v < 50 ? "Slow" : v > 120 ? "Fast" : ""), bp_systolic: (v) => (v >= 180 ? "Very high" : v < 90 ? "Low" : ""),
  bp_diastolic: (v) => (v >= 110 ? "Very high" : ""), spo2: (v) => (v < 92 ? "Low" : ""), temperature_f: (v) => (v >= 100.4 ? "Fever" : ""), resp_rate: (v) => (v > 24 ? "Fast" : ""),
};

const emptyVisit = () => ({ complaint: "", duration: "", story: "", vitals: {}, signs: {}, exam: {}, dx: "", tests: [], plan: "", planDetails: "", note: "" });
const lower = (s) => s.toLowerCase();

function composeGeneral(signs) {
  const absent = SIGNS.filter((s) => signs[s] === "no").map(lower);
  const present = SIGNS.filter((s) => signs[s] === "yes").map(lower);
  const parts = [];
  if (absent.length) parts.push(`No ${absent.join(", ")}`);
  if (present.length) parts.push(`Present: ${present.join(", ")}`);
  return parts.join(". ") || null;
}

export default function TakeHistory() {
  const { id } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const { data, loading, error, reload } = useFetch(() => getPatientHistoryForm(id), [id]);
  const [medicines, setMedicines] = useState([]);
  const [tests, setTests] = useState([]);
  const [f, setF] = useState(null);                // the permanent history (same shape as the patient's form)
  const [v, setV] = useState(emptyVisit());        // this visit
  const [step, setStep] = useState(0);
  const [live, setLive] = useState({ points_to_check: [], suggested_tests: [] });
  const [saving, setSaving] = useState(false);
  const [restored, setRestored] = useState(false);
  const [testText, setTestText] = useState("");
  const draftKey = `hw_history_draft_${id}`;
  const ready = useRef(false);

  useEffect(() => {
    getMedicineOptions().then((l) => setMedicines(l.map((m) => ({ name: m.name, hint: m.in_stock ? "In stock" : undefined })))).catch(() => {});
    getTestOptions().then((l) => setTests(l.map((t) => ({ name: t.name, hint: t.group })))).catch(() => {});
  }, []);

  // start from what is already saved; a draft kept in this browser wins
  useEffect(() => {
    if (!data || ready.current) return;
    ready.current = true;
    const base = toForm(data.history);
    base.current_problem = { ...base.current_problem, symptoms: [], denies: [] };
    try {
      const draft = JSON.parse(localStorage.getItem(draftKey) || "null");
      if (draft?.f && draft?.v) { setF(draft.f); setV(draft.v); setRestored(true); return; }
    } catch { /* no draft */ }
    setF(base);
  }, [data, draftKey]);

  useEffect(() => {
    if (!f) return undefined;
    const t = setTimeout(() => { try { localStorage.setItem(draftKey, JSON.stringify({ f, v })); } catch { /* storage full or blocked */ } }, 700);
    return () => clearTimeout(t);
  }, [f, v, draftKey]);

  // live points to check (the server works them out; nothing is saved)
  useEffect(() => {
    if (!f) return undefined;
    const t = setTimeout(() => {
      const vit = v.vitals;
      previewPoints(id, {
        history: { ...toPayload(f), current_problem: { ...toPayload(f).current_problem, complaint: v.complaint || null, details: v.story || null } },
        vitals: { pulse: num(vit.pulse), bp_systolic: num(vit.sys), bp_diastolic: num(vit.dia), spo2: num(vit.spo2), temperature_f: num(vit.temp), resp_rate: num(vit.rr) },
      }).then(setLive).catch(() => {});
    }, 700);
    return () => clearTimeout(t);
  }, [f, v, id]);

  const card = data?.card;
  const done = useMemo(() => {
    if (!f) return {};
    const b = f.baseline;
    return {
      past: f.conditions.length > 0 || f.no_known_conditions, drugs: f.medications.length > 0 || f.no_regular_medicines, allergy: f.allergies.length > 0 || f.no_known_allergies,
      personal: !!(f.habits.tobacco || f.habits.alcohol), usual: !!(b.pulse || b.bp_systolic || b.sugar_fasting || b.hba1c || (b.others || []).length),
      visit: !!(v.complaint || f.current_problem.symptoms.length), exam: !!(v.vitals.pulse || v.vitals.sys), plan: !!(v.dx || v.tests.length),
    };
  }, [f, v]);

  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (!f) return <Loading />;

  const up = (patch) => setF((o) => ({ ...o, ...patch }));
  const vis = (patch) => setV((o) => ({ ...o, ...patch }));
  const problem = (k, val) => up({ current_problem: { ...f.current_problem, [k]: val } });
  const habit = (k, val) => up({ habits: { ...f.habits, [k]: val } });
  const toggleIn = (list, item) => (list.includes(item) ? list.filter((x) => x !== item) : [...list, item]);
  const hasName = (list, name, key = "name") => list.some((x) => x[key] === name);
  const current = STEPS[step];
  const age = card.age;
  const usual = f.baseline;

  const setSymptom = (name, state) => {
    setF((o) => {
      const sy = o.current_problem.symptoms.filter((x) => x !== name);
      const de = o.current_problem.denies.filter((x) => x !== name);
      return { ...o, current_problem: { ...o.current_problem, symptoms: state === "yes" ? [...sy, name] : sy, denies: state === "no" ? [...de, name] : de } };
    });
  };

  const save = async () => {
    setSaving(true);
    try {
      const payload = toPayload(f);
      payload.current_problem = { ...payload.current_problem, complaint: v.complaint || null, duration: v.duration || null, details: v.story || null };
      await savePatientHistoryForm(id, payload);
      const visitFilled = v.complaint || v.story || Object.values(v.vitals).some(Boolean) || v.dx || v.tests.length || Object.values(v.exam).some(Boolean) || Object.keys(v.signs).length || v.note;
      if (visitFilled) {
        const vit = v.vitals;
        await addAssessment(id, {
          chief_complaint: v.complaint ? `${v.complaint}${v.duration ? ` (${v.duration})` : ""}` : null, history_of_present_illness: v.story || null,
          vitals: { pulse: num(vit.pulse), bp_systolic: num(vit.sys), bp_diastolic: num(vit.dia), temperature_f: num(vit.temp), resp_rate: num(vit.rr), spo2: num(vit.spo2), weight_kg: num(vit.weight), height_cm: num(vit.height) },
          examination: { consciousness: v.exam.consciousness || null, general: [composeGeneral(v.signs), v.exam.general].filter(Boolean).join(". ") || null, respiratory: v.exam.respiratory || null, cardiovascular: v.exam.cardiovascular || null, abdomen: v.exam.abdomen || null, nervous_system: v.exam.nervous_system || null },
          provisional_diagnosis: v.dx || null, investigations_advised: v.tests.join(", ") || null, plan_type: v.plan || null, plan_details: v.planDetails || null, special_note: v.note || null,
        });
      }
      try { localStorage.removeItem(draftKey); } catch { /* ignore */ }
      toast("History saved");
      navigate(`/doctor/patients/${id}`);
    } catch (e) { toast(getErrorMessage(e), "error"); } finally { setSaving(false); }
  };

  const addTest = (name) => { const t = name.trim(); if (t && !v.tests.includes(t)) vis({ tests: [...v.tests, t] }); setTestText(""); };

  // ---------------------------------------------------------------- the steps
  const pages = {
    past: (
      <>
        <Block title="Illnesses" done={done.past} hint="Tap what applies. Then tap how long, and whether the patient is on treatment.">
          <Chips items={CONDITION_PICKS} selected={f.conditions.map((c) => c.name)} onToggle={(c) => up({ no_known_conditions: false, conditions: hasName(f.conditions, c) ? f.conditions.filter((x) => x.name !== c) : [...f.conditions, { name: c, on_treatment: true }] })} />
          <div className="mt-4 space-y-2">
            {f.conditions.map((c, i) => (
              <div key={i} className="flex flex-wrap items-center gap-2 rounded-2xl bg-slate-50 p-3">
                <b className="min-w-40 text-slate-800">{c.name}</b>
                <span className="text-xs font-bold text-slate-400">SINCE</span>
                {SINCE.map((s) => <button type="button" key={s} onClick={() => up({ conditions: f.conditions.map((x, k) => (k === i ? { ...x, since: s } : x)) })} className={`rounded-full px-2.5 py-1 text-xs font-bold ${c.since === s ? "bg-brand-700 text-white" : "bg-white text-slate-500 ring-1 ring-slate-200"}`}>{s}</button>)}
                <Input className={`${inputClass} !w-28 !py-1`} placeholder="or type" value={SINCE.includes(c.since) ? "" : c.since ?? ""} onChange={(e) => up({ conditions: f.conditions.map((x, k) => (k === i ? { ...x, since: e.target.value } : x)) })} />
                <label className="ml-auto flex items-center gap-1.5 text-sm font-semibold text-slate-700"><input type="checkbox" checked={!!c.on_treatment} onChange={(e) => up({ conditions: f.conditions.map((x, k) => (k === i ? { ...x, on_treatment: e.target.checked } : x)) })} />On treatment</label>
              </div>
            ))}
          </div>
          <OtherIllness onAdd={(name) => up({ no_known_conditions: false, conditions: [...f.conditions, { name, on_treatment: true }] })} />
          <NoneCheck checked={f.no_known_conditions} disabled={f.conditions.length > 0} onChange={(x) => up({ no_known_conditions: x })}>No known illnesses</NoneCheck>
        </Block>
        <Block title="Operations and hospital stays" done={f.surgeries.length > 0 || f.no_past_surgery}>
          <RowList rows={f.surgeries} setRows={(surgeries) => up({ surgeries, no_past_surgery: false })} addLabel="Add an operation or hospital stay"
            fields={[{ key: "what", label: "What was done", placeholder: "e.g. angioplasty", flex: 2 }, { key: "year", label: "Year", placeholder: "e.g. 2018" }, { key: "hospital", label: "Hospital", placeholder: "optional", flex: 2 }]} />
          <NoneCheck checked={f.no_past_surgery} disabled={f.surgeries.length > 0} onChange={(x) => up({ no_past_surgery: x })}>No operations or hospital stays</NoneCheck>
        </Block>
      </>
    ),
    drugs: (
      <Block title="Medicines taken regularly" done={done.drugs} hint="Type a few letters and pick. Tap how often. The strength is part of the name; use the box only to change it.">
        <div className="space-y-3">
          {f.medications.map((m, i) => {
            const set = (patch) => up({ no_regular_medicines: false, medications: f.medications.map((x, k) => (k === i ? { ...x, ...patch } : x)) });
            return (
              <div key={i} className="rounded-2xl bg-slate-50 p-3">
                <div className="flex gap-2">
                  <div className="flex-1"><Autocomplete options={medicines} value={m.name || ""} onChange={(name) => set({ name })} placeholder="Medicine, e.g. aspirin" /></div>
                  <button type="button" onClick={() => up({ medications: f.medications.filter((_, k) => k !== i) })} className="rounded-xl px-3 text-sm font-bold text-slate-400 hover:bg-red-50 hover:text-red-600">Remove</button>
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  {FREQUENCIES.map(([short, long]) => <button type="button" key={short} title={long} onClick={() => set({ frequency: m.frequency === long ? "" : long })} className={`rounded-full px-3 py-1 text-xs font-bold ${m.frequency === long ? "bg-brand-700 text-white" : "bg-white text-slate-600 ring-1 ring-slate-200"}`}>{short}</button>)}
                  <Input className={`${inputClass} !w-36 !py-1`} placeholder="For what?" value={m.reason ?? ""} onChange={(e) => set({ reason: e.target.value })} />
                  <Input className={`${inputClass} !w-28 !py-1`} placeholder="Since" value={m.since ?? ""} onChange={(e) => set({ since: e.target.value })} />
                  <Input className={`${inputClass} !w-28 !py-1`} placeholder="Strength" value={m.dose ?? ""} onChange={(e) => set({ dose: e.target.value })} />
                </div>
              </div>
            );
          })}
        </div>
        <Button type="button" variant="soft" className="mt-3" onClick={() => up({ no_regular_medicines: false, medications: [...f.medications, { name: "", is_current: true }] })}>+ Add a medicine</Button>
        <NoneCheck checked={f.no_regular_medicines} disabled={f.medications.length > 0} onChange={(x) => up({ no_regular_medicines: x })}>No regular medicines</NoneCheck>
      </Block>
    ),
    allergy: (
      <Block title="Allergies" done={done.allergy} hint="Tap the allergy, then tap what happened.">
        <Chips items={ALLERGY_PICKS} selected={f.allergies.map((a) => a.name)} tone="red" onToggle={(a) => up({ no_known_allergies: false, allergies: hasName(f.allergies, a) ? f.allergies.filter((x) => x.name !== a) : [...f.allergies, { name: a, kind: ["Peanuts", "Eggs", "Shellfish"].includes(a) ? "FOOD" : ["Dust", "Latex"].includes(a) ? "OTHER" : "DRUG" }] })} />
        <div className="mt-4 space-y-2">
          {f.allergies.map((a, i) => (
            <div key={i} className="flex flex-wrap items-center gap-2 rounded-2xl bg-red-50/60 p-3">
              <b className="min-w-36 text-red-900">{a.name}</b>
              {REACTIONS.map((r) => <button type="button" key={r} onClick={() => up({ allergies: f.allergies.map((x, k) => (k === i ? { ...x, reaction: x.reaction === r ? "" : r } : x)) })} className={`rounded-full px-2.5 py-1 text-xs font-bold ${a.reaction === r ? "bg-red-600 text-white" : "bg-white text-slate-600 ring-1 ring-slate-200"}`}>{r}</button>)}
            </div>
          ))}
        </div>
        <OtherIllness label="Another allergy" onAdd={(name) => up({ no_known_allergies: false, allergies: [...f.allergies, { name, kind: "DRUG" }] })} />
        <NoneCheck checked={f.no_known_allergies} disabled={f.allergies.length > 0} onChange={(x) => up({ no_known_allergies: x })}>No known allergies</NoneCheck>
      </Block>
    ),
    personal: (
      <>
        <Block title="Habits and daily life" done={done.personal}>
          <div className="space-y-4">
            <PickRow label="Tobacco" value={f.habits.tobacco} onPick={(x) => habit("tobacco", x)} options={[["NONE", "None"], ["SMOKER", "Smoker"], ["CHEWER", "Chews tobacco"], ["FORMER", "Stopped"]]} years={f.habits.tobacco_years} onYears={(x) => habit("tobacco_years", x)} showYears={["SMOKER", "CHEWER", "FORMER"].includes(f.habits.tobacco)} />
            <PickRow label="Alcohol" value={f.habits.alcohol} onPick={(x) => habit("alcohol", x)} options={[["NONE", "None"], ["OCCASIONAL", "Occasionally"], ["REGULAR", "Regularly"], ["FORMER", "Stopped"]]} years={f.habits.alcohol_years} onYears={(x) => habit("alcohol_years", x)} showYears={["OCCASIONAL", "REGULAR", "FORMER"].includes(f.habits.alcohol)} />
            <PickRow label="Diet" value={f.habits.diet} onPick={(x) => habit("diet", x)} options={[["VEG", "Vegetarian"], ["NONVEG", "Non-vegetarian"], ["MIXED", "Mixed"]]} />
            <PickRow label="Appetite" value={f.habits.appetite} onPick={(x) => habit("appetite", x)} options={[["ADEQUATE", "Adequate"], ["POOR", "Poor"], ["INCREASED", "Increased"]]} />
            <PickRow label="Sleep" value={f.habits.sleep} onPick={(x) => habit("sleep", x)} options={[["ADEQUATE", "Adequate"], ["POOR", "Poor"], ["EXCESS", "Too much"]]} />
            <PickRow label="Bowel and bladder" value={f.habits.bowel_bladder} onPick={(x) => habit("bowel_bladder", x)} options={[["REGULAR", "Regular"], ["IRREGULAR", "Irregular"]]} />
          </div>
        </Block>
        <Block title="Family history" done={f.family.length > 0 || f.no_family_history}>
          <Chips items={FAMILY_PICKS} selected={f.family.map((x) => x.condition)} onToggle={(c) => up({ no_family_history: false, family: hasName(f.family, c, "condition") ? f.family.filter((x) => x.condition !== c) : [...f.family, { relation: "", condition: c }] })} />
          <div className="mt-3 space-y-2">{f.family.map((x, i) => (
            <div key={i} className="flex flex-wrap items-center gap-2 rounded-2xl bg-slate-50 p-2.5"><b className="min-w-36">{x.condition}</b>
              {["Father", "Mother", "Brother", "Sister", "Child"].map((r) => <button type="button" key={r} onClick={() => up({ family: f.family.map((y, k) => (k === i ? { ...y, relation: r } : y)) })} className={`rounded-full px-2.5 py-1 text-xs font-bold ${x.relation === r ? "bg-brand-700 text-white" : "bg-white text-slate-600 ring-1 ring-slate-200"}`}>{r}</button>)}</div>
          ))}</div>
          <NoneCheck checked={f.no_family_history} disabled={f.family.length > 0} onChange={(x) => up({ no_family_history: x })}>Nothing important in the family</NoneCheck>
        </Block>
        <Block title="Social and other" hint="Short notes. The last two are only needed for children and for women.">
          <div className="grid gap-3">
            <label className="text-xs font-bold text-slate-500">Work and home<Chips items={["Lives with family", "Lives alone", "Retired", "Farmer", "Housewife", "Office work", "Manual work"]} selected={[]} onToggle={(p) => up({ socioeconomic: addPhrase(f.socioeconomic, p, ", ") })} /><Textarea rows={2} value={f.socioeconomic} onChange={(e) => up({ socioeconomic: e.target.value })} /></label>
            <label className="text-xs font-bold text-slate-500">Vaccinations<Textarea rows={2} value={f.immunization} onChange={(e) => up({ immunization: e.target.value })} /></label>
            {(age ?? 99) < 18 && <><label className="text-xs font-bold text-slate-500">Birth history<Textarea rows={2} value={f.birth_history} onChange={(e) => up({ birth_history: e.target.value })} /></label>
              <label className="text-xs font-bold text-slate-500">Development: gross motor, fine motor, social, language<Textarea rows={2} value={f.developmental_history} onChange={(e) => up({ developmental_history: e.target.value })} /></label></>}
            {card.gender?.toLowerCase().startsWith("f") && <label className="text-xs font-bold text-slate-500">Periods and pregnancies<Textarea rows={2} value={f.menstrual_obstetric} onChange={(e) => up({ menstrual_obstetric: e.target.value })} /></label>}
          </div>
        </Block>
      </>
    ),
    usual: (
      <>
        <Block title="Usual values when well" done={done.usual} hint="These stay with the patient. Today's pulse and BP are compared with them.">
          <UsualValues baseline={f.baseline} onChange={(baseline) => up({ baseline })} />
        </Block>
        <LatestLabs labs={data.latest_labs} usual={f.baseline} onUse={(patch) => up({ baseline: { ...f.baseline, ...patch } })} />
      </>
    ),
    visit: (
      <>
        <Block title="Main complaint" done={!!v.complaint} hint="Tap the usual complaints, or type your own. Then tap how long.">
          <Chips items={COMPLAINTS} selected={[]} onToggle={(c) => vis({ complaint: addPhrase(v.complaint, c, ", ") })} />
          <Textarea className={`${inputClass} mt-3`} rows={2} placeholder="Main complaint, in the patient's words" value={v.complaint} onChange={(e) => vis({ complaint: e.target.value })} />
          <p className="mb-1 mt-3 text-xs font-bold uppercase text-slate-400">Since when</p>
          <Chips items={DURATIONS} selected={[v.duration]} onToggle={(d) => vis({ duration: v.duration === d ? "" : d })} />
        </Block>
        <Block title="Symptoms: tap Yes or No" hint="The 'No' answers matter too. Leave a symptom alone if you did not ask.">
          <div className="grid gap-2 sm:grid-cols-2">{SYMPTOMS.map((s) => (
            <YesNo key={s} label={s} yes="Has" no="No" value={f.current_problem.symptoms.includes(s) ? "yes" : f.current_problem.denies.includes(s) ? "no" : undefined} onChange={(state) => setSymptom(s, state)} />
          ))}</div>
        </Block>
        <Block title="Story of the illness" hint="Tap the parts that fit, then add your own words.">
          <Chips items={STORY.map(([l]) => l)} selected={[]} onToggle={(l) => vis({ story: addPhrase(v.story, STORY.find(([x]) => x === l)[1], " ") })} />
          <Textarea className={`${inputClass} mt-3`} rows={4} value={v.story} onChange={(e) => vis({ story: e.target.value })} />
        </Block>
      </>
    ),
    exam: (
      <>
        <Block title="Vitals" done={done.exam} hint="Anything outside the usual adult limits turns red. The patient's own usual value is shown under the box.">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[["pulse", "Pulse", "/min", "pulse"], ["sys", "BP top", "mmHg", "bp_systolic"], ["dia", "BP bottom", "mmHg", "bp_diastolic"], ["spo2", "SpO2", "%", "spo2"], ["temp", "Temp", "F", "temperature_f"], ["rr", "Resp. rate", "/min", "resp_rate"], ["weight", "Weight", "kg", null], ["height", "Height", "cm", null]].map(([key, label, unit, flagKey]) => {
              const val = v.vitals[key];
              const flag = flagKey && val !== undefined && val !== "" ? VITAL_FLAG[flagKey](Number(val)) : "";
              const usualValue = { pulse: usual.pulse, sys: usual.bp_systolic, dia: usual.bp_diastolic, spo2: usual.spo2 }[key];
              return (
                <label key={key} className="text-xs font-bold text-slate-500">{label} <span className="font-normal text-slate-400">{unit}</span>
                  <Input type="number" step={key === "temp" || key === "weight" ? 0.1 : 1} className={`${inputClass} ${flag ? "!border-red-400 !bg-red-50" : ""}`} value={val ?? ""} onChange={(e) => vis({ vitals: { ...v.vitals, [key]: e.target.value } })} />
                  {flag && <span className="text-red-700">{flag}</span>}{usualValue ? <span className="block font-normal text-slate-400">usual {usualValue}</span> : null}</label>
              );
            })}
          </div>
        </Block>
        <Block title="General examination" hint="Tap Present or Absent for each sign.">
          <div className="grid gap-2 sm:grid-cols-2">{SIGNS.map((s) => <YesNo key={s} label={s} yes="Present" no="Absent" value={v.signs[s]} onChange={(x) => vis({ signs: { ...v.signs, [s]: x } })} />)}</div>
          <Button type="button" variant="soft" className="mt-3" onClick={() => vis({ signs: Object.fromEntries(SIGNS.map((s) => [s, "no"])) })}>All absent</Button>
        </Block>
        <Block title="By system" hint="Tap Normal to fill the usual normal findings, then add what is different.">
          <div className="space-y-4">{EXAM.map(([key, label, normal, extras]) => (
            <div key={key}>
              <div className="mb-1 flex flex-wrap items-center gap-2"><span className="text-sm font-bold text-slate-700">{label}</span>
                <button type="button" onClick={() => vis({ exam: { ...v.exam, [key]: addPhrase(v.exam[key], normal, ". ") } })} className="rounded-full bg-emerald-100 px-3 py-0.5 text-xs font-bold text-emerald-800">Normal</button>
                {extras.map((x) => <button type="button" key={x} onClick={() => vis({ exam: { ...v.exam, [key]: addPhrase(v.exam[key], x, ". ") } })} className="rounded-full bg-amber-50 px-3 py-0.5 text-xs font-bold text-amber-800 ring-1 ring-amber-200">{x}</button>)}</div>
              <Textarea rows={2} value={v.exam[key] ?? ""} onChange={(e) => vis({ exam: { ...v.exam, [key]: e.target.value } })} />
            </div>
          ))}</div>
        </Block>
      </>
    ),
    plan: (
      <>
        <Block title="Provisional diagnosis" done={!!v.dx} hint="Written by you. The computer never suggests a diagnosis.">
          <Textarea rows={2} value={v.dx} onChange={(e) => vis({ dx: e.target.value })} />
        </Block>
        <Block title="Investigations advised" done={v.tests.length > 0} hint="Tap a test to add it. Suggestions from the history are marked with a bulb.">
          {live.suggested_tests.length > 0 && <div className="mb-3"><p className="mb-1.5 flex items-center gap-1.5 text-xs font-extrabold uppercase text-amber-700"><Lightbulb size={14} /> Worth considering, from the history</p>
            <Chips items={live.suggested_tests} selected={v.tests} onToggle={(t) => vis({ tests: toggleIn(v.tests, t) })} /></div>}
          <p className="mb-1.5 text-xs font-extrabold uppercase text-slate-400">Common tests</p>
          <Chips items={QUICK_TESTS} selected={v.tests} onToggle={(t) => vis({ tests: toggleIn(v.tests, t) })} />
          <div className="mt-3 max-w-md"><Autocomplete options={tests} value={testText} onChange={setTestText} onPick={addTest} onEnter={() => addTest(testText)} placeholder="Another test: type a few letters" /></div>
          {v.tests.length > 0 && <p className="mt-3 text-sm text-slate-700"><b>Selected:</b> {v.tests.join(", ")}</p>}
        </Block>
        <Block title="Plan of treatment">
          <Chips items={["Medical", "Surgical", "Medical and surgical"]} selected={[{ MEDICAL: "Medical", SURGICAL: "Surgical", BOTH: "Medical and surgical" }[v.plan]]} onToggle={(p) => vis({ plan: v.plan === ({ Medical: "MEDICAL", Surgical: "SURGICAL", "Medical and surgical": "BOTH" }[p]) ? "" : { Medical: "MEDICAL", Surgical: "SURGICAL", "Medical and surgical": "BOTH" }[p] })} />
          <Textarea className={`${inputClass} mt-3`} rows={2} placeholder="Plan details, cross-consultation if necessary" value={v.planDetails} onChange={(e) => vis({ planDetails: e.target.value })} />
          <Textarea className={`${inputClass} mt-3`} rows={2} placeholder="Any other special note" value={v.note} onChange={(e) => vis({ note: e.target.value })} />
        </Block>
      </>
    ),
  };

  const partA = STEPS.map((s, i) => [s, i]).filter(([s]) => s.part === "A");
  const partB = STEPS.map((s, i) => [s, i]).filter(([s]) => s.part === "B");
  const stepButton = ([s, i]) => (
    <button key={s.key} type="button" onClick={() => setStep(i)} className={`flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm font-bold ${i === step ? "bg-brand-700 text-white" : "text-slate-700 hover:bg-slate-100"}`}>
      {done[s.key] ? <CheckCircle2 size={16} className={i === step ? "text-white" : "text-emerald-600"} /> : <span className={`flex h-4 w-4 items-center justify-center rounded-full border text-[10px] ${i === step ? "border-white" : "border-slate-300"}`}>{i + 1}</span>}
      {s.title}
    </button>
  );

  const flagged = live.points_to_check.filter((p) => ["safety", "vitals"].includes(p.category));
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-3xl bg-gradient-to-r from-brand-700 to-brand-600 p-5 text-white">
        <div>
          <Link to={`/doctor/patients/${id}`} className="mb-1 flex items-center gap-1 text-sm font-semibold text-brand-100 hover:underline"><ArrowLeft size={14} /> Back to the patient</Link>
          <p className="text-2xl font-extrabold">Take history: {card.name}</p>
          <p className="text-brand-50">{card.age != null ? `${card.age} years` : ""}{card.gender ? ` - ${card.gender}` : ""} - {card.patient_code}{card.blood_group ? ` - ${card.blood_group}` : ""}</p>
        </div>
        <Button onClick={save} disabled={saving} className="!bg-white !text-brand-800 !bg-none"><Save size={16} className="mr-1.5 inline" />{saving ? "Saving..." : "Save everything"}</Button>
      </div>
      {restored && <p className="rounded-2xl bg-amber-50 p-3 text-sm font-semibold text-amber-900">An unsaved draft from this browser was restored. <button className="underline" onClick={() => { try { localStorage.removeItem(draftKey); } catch { /* ignore */ } ready.current = false; setRestored(false); setV(emptyVisit()); reload(); }}>Discard the draft</button></p>}
      {card.allergies.length > 0 && <p className="flex items-center gap-2 rounded-2xl border border-red-300 bg-red-50 p-3 text-sm font-bold text-red-800"><AlertTriangle size={16} /> Known allergy: {card.allergies.map((a) => a.name).join(", ")}</p>}

      <div className="grid gap-4 lg:grid-cols-[14rem_minmax(0,1fr)_20rem]">
        <nav className="space-y-1 rounded-3xl border border-slate-200/70 bg-white p-3 shadow-sm lg:sticky lg:top-4 lg:self-start">
          <p className="px-3 pb-1 pt-1 text-[11px] font-extrabold uppercase tracking-wide text-slate-400">A. Permanent history</p>
          {partA.map(stepButton)}
          <p className="px-3 pb-1 pt-3 text-[11px] font-extrabold uppercase tracking-wide text-slate-400">B. This visit</p>
          {partB.map(stepButton)}
        </nav>

        <div className="min-w-0 space-y-4">
          <p className="text-sm font-extrabold uppercase tracking-wide text-slate-400">{current.part === "A" ? "Part A: permanent history, stays with the patient" : "Part B: this visit, new every time"}</p>
          {pages[current.key]}
          <div className="flex justify-between gap-3">
            <Button variant="secondary" disabled={step === 0} onClick={() => { setStep(step - 1); window.scrollTo({ top: 0 }); }}><ArrowLeft size={15} className="mr-1 inline" />Back</Button>
            {step < STEPS.length - 1
              ? <Button onClick={() => { setStep(step + 1); window.scrollTo({ top: 0 }); }}>Next: {STEPS[step + 1].title}<ArrowRight size={15} className="ml-1 inline" /></Button>
              : <Button onClick={save} disabled={saving}><Save size={15} className="mr-1.5 inline" />{saving ? "Saving..." : "Save everything"}</Button>}
          </div>
        </div>

        <aside className="space-y-4 lg:sticky lg:top-4 lg:self-start">
          <div className="rounded-3xl border border-sky-200 bg-sky-50 p-4">
            <p className="mb-2 flex items-center gap-2 font-extrabold text-sky-900"><ClipboardList size={16} /> Remember to ask</p>
            <ul className="list-disc space-y-1.5 pl-5 text-sm text-sky-950">{current.ask.map((a) => <li key={a}>{a}</li>)}</ul>
          </div>
          <div className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="mb-2 flex items-center gap-2 font-extrabold text-slate-900"><Lightbulb size={16} className="text-amber-500" /> Points to check <span className="text-xs font-normal text-slate-400">(live)</span></p>
            {live.points_to_check.length === 0 ? <p className="text-sm text-slate-500">They appear here as you fill in the medicines, illnesses and complaint.</p> : (
              <ul className="space-y-2">{[...flagged, ...live.points_to_check.filter((p) => !flagged.includes(p) && p.category !== "missing")].slice(0, 7).map((p, i) => (
                <li key={i} className={`rounded-xl border p-2.5 text-sm ${["safety", "vitals"].includes(p.category) ? "border-red-200 bg-red-50" : "border-slate-200 bg-slate-50"}`}><p className="font-bold text-slate-900">{p.title}</p><p className="text-slate-600">{p.detail}</p></li>
              ))}</ul>
            )}
            <p className="mt-2 text-xs text-slate-400">Things doctors often review. Not a diagnosis; you decide.</p>
          </div>
          {data.latest_labs.length > 0 && current.part === "B" && (
            <div className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="mb-2 font-extrabold text-slate-900">Latest blood tests</p>
              <ul className="space-y-1 text-sm">{data.latest_labs.slice(0, 6).map((l) => <li key={l.name} className="flex justify-between gap-2"><span>{l.name}</span><b className={l.status === "ABOVE_RANGE" ? "text-amber-700" : l.status === "BELOW_RANGE" ? "text-sky-700" : "text-slate-800"}>{l.value} {l.unit}</b></li>)}</ul>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}

const num = (x) => (x === "" || x === undefined || x === null ? null : Number(x));

/** A text box that adds an item when Enter is pressed (for anything that is not in the tap lists). */
function OtherIllness({ onAdd, label = "Another illness" }) {
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
      <span className="w-32 text-sm font-bold text-slate-600">{label}</span>
      {options.map(([val, text]) => <button type="button" key={val} onClick={() => onPick(value === val ? "" : val)} className={`rounded-full border px-3.5 py-1.5 text-sm font-semibold ${value === val ? "border-brand-600 bg-brand-50 text-brand-900" : "border-slate-300 bg-white text-slate-600"}`}>{text}</button>)}
      {showYears && <span className="flex items-center gap-1 text-sm text-slate-500">for <Input type="number" min="0" className={`${inputClass} !w-20 !py-1`} value={years ?? ""} onChange={(e) => onYears(e.target.value)} /> years</span>}
    </div>
  );
}

/** The newest value of every test in the patient's reports, with one-tap "use as usual value" for the main ones. */
function LatestLabs({ labs, usual, onUse }) {
  if (!labs?.length) return <Block title="Latest blood tests from the reports"><p className="text-slate-500">No test results are in the reports of this patient yet.</p></Block>;
  const MAP = { HbA1c: "hba1c", Hemoglobin: "hemoglobin", Creatinine: "creatinine", "Fasting Glucose": "sugar_fasting" };
  return (
    <Block title="Latest blood tests from the reports" hint="Taken from the uploaded reports, never typed in. Values outside the printed range come first.">
      <table className="w-full text-sm">
        <thead><tr className="text-left text-xs text-slate-400"><th className="pb-1">Test</th><th>Latest</th><th>Normal range</th><th>Date</th><th /></tr></thead>
        <tbody>{labs.map((l) => (
          <tr key={l.name} className="border-t border-slate-100">
            <td className="py-1.5 font-semibold">{l.name}</td>
            <td className={`font-bold ${l.status === "ABOVE_RANGE" ? "text-amber-700" : l.status === "BELOW_RANGE" ? "text-sky-700" : "text-slate-800"}`}>{l.value} {l.unit}</td>
            <td className="text-slate-500">{l.range || "not printed"}</td><td className="text-slate-500">{fmtDate(l.date)}</td>
            <td className="text-right">{MAP[l.name] && usual[MAP[l.name]] === "" && <button type="button" className="rounded-full bg-brand-50 px-2.5 py-0.5 text-xs font-bold text-brand-800" onClick={() => onUse({ [MAP[l.name]]: l.value })}>Use as usual</button>}</td>
          </tr>
        ))}</tbody>
      </table>
    </Block>
  );
}
