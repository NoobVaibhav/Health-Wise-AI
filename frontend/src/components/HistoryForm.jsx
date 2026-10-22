// The health-history form. Plain words, big targets, "none" answers that count as answered.
// Used by the patient (their own page) and by the doctor (inside the patient's record).
import { useMemo, useState } from "react";
import { CheckCircle2, Circle, Plus, Trash2 } from "lucide-react";
import { Button, Input, Select, Textarea } from "./ui";

const CONDITION_PICKS = ["High blood pressure", "Diabetes", "Heart disease", "Heart failure", "Asthma / COPD", "Thyroid problem", "Kidney disease",
  "Liver disease", "Epilepsy / fits", "Tuberculosis", "Stroke", "Cancer", "Anaemia", "Arthritis", "Enlarged prostate", "Memory loss / Alzheimer's"];
const FAMILY_PICKS = ["Heart disease", "Diabetes", "High blood pressure", "Cancer", "Stroke", "Asthma", "Kidney disease", "Thyroid problem"];
const SYMPTOMS = ["Fever", "Chest pain", "Giddiness", "Fainting / loss of consciousness", "Breathlessness", "Palpitations", "Headache", "Weakness",
  "Vomiting", "Cough", "Swelling of feet", "Pain in abdomen", "Sweating", "Tremors", "Involuntary movements"];

const clean = (v) => (v === "" || v === undefined ? null : v);
const num = (v) => (v === "" || v === null || v === undefined ? null : Number(v));

/** The data from the server -> what the inputs show. */
export const toForm = (h) => ({
  height_cm: h.height_cm ?? "", weight_kg: h.weight_kg ?? "",
  conditions: h.conditions || [], surgeries: h.surgeries || [], family: h.family || [], allergies: h.allergies || [],
  medications: (h.medications || []).map(({ id, ...m }) => m),
  habits: { tobacco: "", alcohol: "", diet: "", appetite: "", sleep: "", bowel_bladder: "", exercise: "", tobacco_years: "", alcohol_years: "", ...(h.habits || {}) },
  current_problem: { complaint: "", duration: "", symptoms: [], denies: [], details: "", ...(h.current_problem || {}) },
  no_known_conditions: !!h.no_known_conditions, no_known_allergies: !!h.no_known_allergies, no_regular_medicines: !!h.no_regular_medicines,
  no_past_surgery: !!h.no_past_surgery, no_family_history: !!h.no_family_history,
  baseline: { pulse: "", bp_systolic: "", bp_diastolic: "", spo2: "", sugar_fasting: "", sugar_post_meal: "", hba1c: "", hemoglobin: "", creatinine: "", noted_on: "", note: "", others: [], ...(h.baseline || {}) },
  immunization: h.immunization || "", birth_history: h.birth_history || "", developmental_history: h.developmental_history || "", socioeconomic: h.socioeconomic || "", menstrual_obstetric: h.menstrual_obstetric || "",
});

/** What the inputs show -> what the server expects (empty text becomes null, numbers become numbers). */
export const toPayload = (f) => ({
  height_cm: num(f.height_cm), weight_kg: num(f.weight_kg),
  conditions: f.conditions.filter((c) => c.name?.trim()).map((c) => ({ name: c.name.trim(), since: clean(c.since), on_treatment: !!c.on_treatment, notes: clean(c.notes) })),
  surgeries: f.surgeries.filter((s) => s.what?.trim()).map((s) => ({ what: s.what.trim(), year: clean(s.year), hospital: clean(s.hospital) })),
  family: f.family.filter((x) => x.condition?.trim()).map((x) => ({ relation: x.relation?.trim() || "Family member", condition: x.condition.trim() })),
  allergies: f.allergies.filter((a) => a.name?.trim()).map((a) => ({ name: a.name.trim(), kind: a.kind || "DRUG", reaction: clean(a.reaction) })),
  medications: f.medications.filter((m) => m.name?.trim()).map((m) => ({ name: m.name.trim(), dose: clean(m.dose), frequency: clean(m.frequency), reason: clean(m.reason), since: clean(m.since), notes: clean(m.notes), is_current: m.is_current !== false })),
  habits: { tobacco: clean(f.habits.tobacco), tobacco_years: num(f.habits.tobacco_years), alcohol: clean(f.habits.alcohol), alcohol_years: num(f.habits.alcohol_years),
    diet: clean(f.habits.diet), appetite: clean(f.habits.appetite), sleep: clean(f.habits.sleep), bowel_bladder: clean(f.habits.bowel_bladder), exercise: clean(f.habits.exercise) },
  current_problem: { complaint: clean(f.current_problem.complaint), duration: clean(f.current_problem.duration), symptoms: f.current_problem.symptoms, denies: f.current_problem.denies, details: clean(f.current_problem.details) },
  no_known_conditions: f.no_known_conditions && f.conditions.length === 0, no_known_allergies: f.no_known_allergies && f.allergies.length === 0,
  no_regular_medicines: f.no_regular_medicines && f.medications.length === 0, no_past_surgery: f.no_past_surgery && f.surgeries.length === 0,
  no_family_history: f.no_family_history && f.family.length === 0,
  baseline: {
    pulse: num(f.baseline.pulse), bp_systolic: num(f.baseline.bp_systolic), bp_diastolic: num(f.baseline.bp_diastolic), spo2: num(f.baseline.spo2),
    sugar_fasting: num(f.baseline.sugar_fasting), sugar_post_meal: num(f.baseline.sugar_post_meal), hba1c: num(f.baseline.hba1c), hemoglobin: num(f.baseline.hemoglobin), creatinine: num(f.baseline.creatinine),
    others: (f.baseline.others || []).filter((o) => o.name?.trim() && String(o.value ?? "").trim()).map((o) => ({ name: o.name.trim(), value: String(o.value).trim(), unit: clean(o.unit) })),
    noted_on: clean(f.baseline.noted_on), note: clean(f.baseline.note),
  },
  immunization: clean(f.immunization), birth_history: clean(f.birth_history), developmental_history: clean(f.developmental_history), socioeconomic: clean(f.socioeconomic), menstrual_obstetric: clean(f.menstrual_obstetric),
});

export function Card({ n, title, hint, done, children }) {
  return (
    <section className="rounded-3xl border border-slate-200/70 bg-white p-5 shadow-sm md:p-6">
      <div className="mb-4 flex items-start gap-3">
        <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-sm font-extrabold ${done ? "bg-emerald-100 text-emerald-700" : "bg-brand-100 text-brand-800"}`}>{done ? <CheckCircle2 size={20} /> : n}</span>
        <div>
          <h2 className="text-lg font-extrabold text-slate-900">{title}</h2>
          {hint && <p className="text-sm text-slate-500">{hint}</p>}
        </div>
      </div>
      {children}
    </section>
  );
}

const Chip = ({ on, onClick, children, tone = "brand" }) => (
  <button type="button" onClick={onClick}
    className={`rounded-full border px-3.5 py-1.5 text-sm font-semibold transition ${on ? (tone === "red" ? "border-red-400 bg-red-50 text-red-800" : "border-brand-500 bg-brand-50 text-brand-800") : "border-slate-300 bg-white text-slate-600 hover:bg-slate-50"}`}>
    {on ? "✓ " : ""}{children}
  </button>
);

const NoneBox = ({ checked, onChange, children, disabled }) => (
  <label className={`mt-3 flex items-center gap-2 text-sm font-semibold ${disabled ? "text-slate-300" : "text-slate-700"}`}>
    <input type="checkbox" className="h-4 w-4" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} /> {children}
  </label>
);

/** A list of small rows. fields: [{ key, label, placeholder, type, options, flex }] */
export function RowList({ rows, setRows, fields, addLabel, blank = {} }) {
  const set = (i, key, value) => setRows(rows.map((r, k) => (k === i ? { ...r, [key]: value } : r)));
  return (
    <div className="space-y-3">
      {rows.map((row, i) => (
        <div key={i} className="flex flex-wrap items-end gap-2 rounded-2xl bg-slate-50 p-3">
          {fields.map((f) => (
            <label key={f.key} className="min-w-[8rem] text-xs font-bold text-slate-500" style={{ flex: f.flex || 1 }}>
              {f.label}
              {f.options ? (
                <Select value={row[f.key] ?? ""} onChange={(e) => set(i, f.key, e.target.value)}>{f.options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</Select>
              ) : f.type === "check" ? (
                <span className="mt-2 flex items-center gap-2 text-sm font-semibold text-slate-700"><input type="checkbox" className="h-4 w-4" checked={!!row[f.key]} onChange={(e) => set(i, f.key, e.target.checked)} />{f.placeholder}</span>
              ) : (
                <Input value={row[f.key] ?? ""} placeholder={f.placeholder} onChange={(e) => set(i, f.key, e.target.value)} />
              )}
            </label>
          ))}
          <button type="button" onClick={() => setRows(rows.filter((_, k) => k !== i))} aria-label="Remove this row" className="mb-1 rounded-xl p-2 text-slate-400 hover:bg-red-50 hover:text-red-600"><Trash2 size={18} /></button>
        </div>
      ))}
      <Button type="button" variant="soft" onClick={() => setRows([...rows, { ...blank }])}><Plus size={15} className="mr-1 inline" />{addLabel}</Button>
    </div>
  );
}

/** The patient's usual pulse, blood pressure, sugar and key blood-test values (the permanent baseline). */
export function UsualValues({ baseline, onChange }) {
  const set = (k, v) => onChange({ ...baseline, [k]: v });
  const field = (label, key, unit, step = 1) => (
    <label className="text-xs font-bold text-slate-500">{label} <span className="font-normal text-slate-400">{unit}</span>
      <Input type="number" step={step} value={baseline[key] ?? ""} onChange={(e) => set(key, e.target.value)} /></label>
  );
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {field("Pulse", "pulse", "/min")}{field("BP top", "bp_systolic", "mmHg")}{field("BP bottom", "bp_diastolic", "mmHg")}{field("SpO2", "spo2", "%")}
        {field("Sugar, fasting", "sugar_fasting", "mg/dL")}{field("Sugar, after meal", "sugar_post_meal", "mg/dL")}{field("HbA1c", "hba1c", "%", 0.1)}{field("Haemoglobin", "hemoglobin", "g/dL", 0.1)}
        {field("Creatinine", "creatinine", "mg/dL", 0.1)}
        <label className="text-xs font-bold text-slate-500 sm:col-span-3">Measured when<Input value={baseline.noted_on ?? ""} placeholder="e.g. March 2026 check-up" onChange={(e) => set("noted_on", e.target.value)} /></label>
      </div>
      <div>
        <p className="mb-2 text-sm font-bold text-slate-700">Other important values</p>
        <RowList rows={baseline.others || []} setRows={(others) => set("others", others)} addLabel="Add a value"
          fields={[{ key: "name", label: "Test", placeholder: "e.g. Uric acid, TSH, Vitamin D", flex: 2 }, { key: "value", label: "Value", placeholder: "e.g. 5.1" }, { key: "unit", label: "Unit", placeholder: "e.g. mg/dL" }]} />
      </div>
    </div>
  );
}

export default function HistoryForm({ initial, onSave, saving, saveLabel = "Save", showChildren = false }) {
  const [f, setF] = useState(() => toForm(initial));
  const [error, setError] = useState("");
  const up = (patch) => setF((old) => ({ ...old, ...patch }));
  const habit = (k, v) => up({ habits: { ...f.habits, [k]: v } });
  const problem = (k, v) => up({ current_problem: { ...f.current_problem, [k]: v } });
  const toggle = (list, key, item) => problem(key, list.includes(item) ? list.filter((x) => x !== item) : [...list, item]);
  const bmi = f.height_cm && f.weight_kg ? (f.weight_kg / (f.height_cm / 100) ** 2).toFixed(1) : null;
  const has = (list, name) => list.some((x) => (x.name || x.condition) === name);

  const done = useMemo(() => ({
    body: !!(f.height_cm && f.weight_kg), meds: f.medications.length > 0 || f.no_regular_medicines, allergies: f.allergies.length > 0 || f.no_known_allergies,
    conditions: f.conditions.length > 0 || f.no_known_conditions, surgeries: f.surgeries.length > 0 || f.no_past_surgery,
    family: f.family.length > 0 || f.no_family_history, habits: !!(f.habits.tobacco || f.habits.alcohol),
    usual: !!(f.baseline.pulse || f.baseline.bp_systolic || f.baseline.sugar_fasting || f.baseline.hba1c || (f.baseline.others || []).length),
  }), [f]);

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    try { await onSave(toPayload(f)); } catch (err) { setError(err.message || "Could not save."); }
  };

  return (
    <form onSubmit={submit} className="space-y-5">
      <Card n="1" title="Current problem" hint="Why is the patient worried right now? Leave it empty if there is no new problem.">
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="text-xs font-bold text-slate-500 sm:col-span-2">Main complaint<Input value={f.current_problem.complaint ?? ""} placeholder="e.g. giddiness and fainting yesterday night" onChange={(e) => problem("complaint", e.target.value)} /></label>
          <label className="text-xs font-bold text-slate-500">Since when?<Input value={f.current_problem.duration ?? ""} placeholder="e.g. 1 day" onChange={(e) => problem("duration", e.target.value)} /></label>
        </div>
        <p className="mb-2 mt-4 text-sm font-bold text-slate-700">Which of these are there?</p>
        <div className="flex flex-wrap gap-2">{SYMPTOMS.map((s) => <Chip key={s} on={f.current_problem.symptoms.includes(s)} onClick={() => toggle(f.current_problem.symptoms, "symptoms", s)}>{s}</Chip>)}</div>
        <p className="mb-2 mt-4 text-sm font-bold text-slate-700">Which of these are NOT there? (helps the doctor)</p>
        <div className="flex flex-wrap gap-2">{SYMPTOMS.map((s) => <Chip key={s} tone="red" on={f.current_problem.denies.includes(s)} onClick={() => toggle(f.current_problem.denies, "denies", s)}>No {s.toLowerCase()}</Chip>)}</div>
        <label className="mt-4 block text-xs font-bold text-slate-500">Tell the story in your own words (what happened, how long it lasted, what made it better or worse)
          <Textarea rows={3} value={f.current_problem.details ?? ""} onChange={(e) => problem("details", e.target.value)} /></label>
      </Card>

      <Card n="2" title="Medicines taken regularly" done={done.meds} hint="This is the most useful part for a doctor who meets the patient for the first time. Include tablets, injections, inhalers, drops, ayurvedic and other medicines.">
        <RowList rows={f.medications} setRows={(medications) => up({ medications, no_regular_medicines: false })} addLabel="Add a medicine" blank={{ is_current: true }}
          fields={[
            { key: "name", label: "Medicine name", placeholder: "e.g. Tab. Aspirin", flex: 2 },
            { key: "dose", label: "Strength", placeholder: "e.g. 75 mg" },
            { key: "frequency", label: "How often", placeholder: "e.g. once a day at night" },
            { key: "reason", label: "What is it for?", placeholder: "e.g. heart" },
            { key: "since", label: "Since", placeholder: "e.g. 2 years" },
          ]} />
        <NoneBox checked={f.no_regular_medicines} disabled={f.medications.length > 0} onChange={(v) => up({ no_regular_medicines: v })}>No regular medicines</NoneBox>
      </Card>

      <Card n="3" title="Allergies" done={done.allergies} hint="Medicines, food or anything else that has ever caused a rash, swelling, breathing trouble or other reaction.">
        <RowList rows={f.allergies} setRows={(allergies) => up({ allergies, no_known_allergies: false })} addLabel="Add an allergy" blank={{ kind: "DRUG" }}
          fields={[
            { key: "name", label: "Allergic to", placeholder: "e.g. Penicillin", flex: 2 },
            { key: "kind", label: "Type", options: [["DRUG", "Medicine"], ["FOOD", "Food"], ["OTHER", "Other"]] },
            { key: "reaction", label: "What happened?", placeholder: "e.g. skin rash", flex: 2 },
          ]} />
        <NoneBox checked={f.no_known_allergies} disabled={f.allergies.length > 0} onChange={(v) => up({ no_known_allergies: v })}>No known allergies</NoneBox>
      </Card>

      <Card n="4" title="Illnesses" done={done.conditions} hint="Tap the ones that apply, then add since when and whether treatment is going on. Add any other illness below.">
        <div className="mb-3 flex flex-wrap gap-2">
          {CONDITION_PICKS.map((c) => (
            <Chip key={c} on={has(f.conditions, c)} onClick={() => up({ no_known_conditions: false, conditions: has(f.conditions, c) ? f.conditions.filter((x) => x.name !== c) : [...f.conditions, { name: c, on_treatment: true }] })}>{c}</Chip>
          ))}
        </div>
        <RowList rows={f.conditions} setRows={(conditions) => up({ conditions, no_known_conditions: false })} addLabel="Add another illness" blank={{ on_treatment: true }}
          fields={[
            { key: "name", label: "Illness", placeholder: "e.g. Hypertension", flex: 2 },
            { key: "since", label: "Since", placeholder: "e.g. 25 years or 2003" },
            { key: "on_treatment", label: "Treatment", type: "check", placeholder: "On treatment" },
            { key: "notes", label: "Notes", placeholder: "optional", flex: 2 },
          ]} />
        <NoneBox checked={f.no_known_conditions} disabled={f.conditions.length > 0} onChange={(v) => up({ no_known_conditions: v })}>No known illnesses</NoneBox>
      </Card>

      <Card n="5" title="Operations and hospital stays" done={done.surgeries}>
        <RowList rows={f.surgeries} setRows={(surgeries) => up({ surgeries, no_past_surgery: false })} addLabel="Add an operation or hospital stay"
          fields={[
            { key: "what", label: "What was done", placeholder: "e.g. appendix operation", flex: 2 },
            { key: "year", label: "Year", placeholder: "e.g. 2018" },
            { key: "hospital", label: "Hospital", placeholder: "optional", flex: 2 },
          ]} />
        <NoneBox checked={f.no_past_surgery} disabled={f.surgeries.length > 0} onChange={(v) => up({ no_past_surgery: v })}>No operations or hospital stays</NoneBox>
      </Card>

      <Card n="6" title="Family history" done={done.family} hint="Illnesses in parents, brothers, sisters or children.">
        <div className="mb-3 flex flex-wrap gap-2">
          {FAMILY_PICKS.map((c) => <Chip key={c} on={has(f.family, c)} onClick={() => up({ no_family_history: false, family: has(f.family, c) ? f.family.filter((x) => x.condition !== c) : [...f.family, { relation: "", condition: c }] })}>{c}</Chip>)}
        </div>
        <RowList rows={f.family} setRows={(family) => up({ family, no_family_history: false })} addLabel="Add a family member"
          fields={[{ key: "relation", label: "Who", placeholder: "e.g. Father" }, { key: "condition", label: "Illness", placeholder: "e.g. heart attack at 55", flex: 2 }]} />
        <NoneBox checked={f.no_family_history} disabled={f.family.length > 0} onChange={(v) => up({ no_family_history: v })}>Nothing important in the family</NoneBox>
      </Card>

      <Card n="7" title="Habits and daily life" done={done.habits}>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="flex gap-2"><label className="flex-1 text-xs font-bold text-slate-500">Tobacco
            <Select value={f.habits.tobacco ?? ""} onChange={(e) => habit("tobacco", e.target.value)}><option value="">Choose</option><option value="NONE">None</option><option value="SMOKER">Smoker</option><option value="CHEWER">Chews tobacco</option><option value="FORMER">Used to, stopped</option></Select></label>
            {["SMOKER", "CHEWER", "FORMER"].includes(f.habits.tobacco) && <label className="w-28 text-xs font-bold text-slate-500">For years<Input type="number" min="0" value={f.habits.tobacco_years ?? ""} onChange={(e) => habit("tobacco_years", e.target.value)} /></label>}</div>
          <div className="flex gap-2"><label className="flex-1 text-xs font-bold text-slate-500">Alcohol
            <Select value={f.habits.alcohol ?? ""} onChange={(e) => habit("alcohol", e.target.value)}><option value="">Choose</option><option value="NONE">None</option><option value="OCCASIONAL">Occasionally</option><option value="REGULAR">Regularly</option><option value="FORMER">Used to, stopped</option></Select></label>
            {["OCCASIONAL", "REGULAR", "FORMER"].includes(f.habits.alcohol) && <label className="w-28 text-xs font-bold text-slate-500">For years<Input type="number" min="0" value={f.habits.alcohol_years ?? ""} onChange={(e) => habit("alcohol_years", e.target.value)} /></label>}</div>
          <label className="text-xs font-bold text-slate-500">Diet<Select value={f.habits.diet ?? ""} onChange={(e) => habit("diet", e.target.value)}><option value="">Choose</option><option value="VEG">Vegetarian</option><option value="NONVEG">Non-vegetarian</option><option value="MIXED">Mixed</option><option value="VEGAN">Vegan</option></Select></label>
          <label className="text-xs font-bold text-slate-500">Appetite<Select value={f.habits.appetite ?? ""} onChange={(e) => habit("appetite", e.target.value)}><option value="">Choose</option><option value="ADEQUATE">Normal</option><option value="POOR">Poor</option><option value="INCREASED">Increased</option></Select></label>
          <label className="text-xs font-bold text-slate-500">Sleep<Select value={f.habits.sleep ?? ""} onChange={(e) => habit("sleep", e.target.value)}><option value="">Choose</option><option value="ADEQUATE">Normal</option><option value="POOR">Poor</option><option value="EXCESS">Too much</option></Select></label>
          <label className="text-xs font-bold text-slate-500">Bowel and bladder<Select value={f.habits.bowel_bladder ?? ""} onChange={(e) => habit("bowel_bladder", e.target.value)}><option value="">Choose</option><option value="REGULAR">Regular</option><option value="IRREGULAR">Irregular</option></Select></label>
          <label className="text-xs font-bold text-slate-500 sm:col-span-2">Exercise<Input value={f.habits.exercise ?? ""} placeholder="e.g. walks 30 minutes daily" onChange={(e) => habit("exercise", e.target.value)} /></label>
        </div>
      </Card>

      <Card n="8" title="Body measurements" done={done.body}>
        <div className="grid gap-3 sm:grid-cols-3">
          <label className="text-xs font-bold text-slate-500">Height (cm)<Input type="number" min="30" max="250" value={f.height_cm} onChange={(e) => up({ height_cm: e.target.value })} /></label>
          <label className="text-xs font-bold text-slate-500">Weight (kg)<Input type="number" min="1" max="400" value={f.weight_kg} onChange={(e) => up({ weight_kg: e.target.value })} /></label>
          <div className="rounded-2xl bg-slate-50 p-3 text-center"><p className="text-xs font-bold text-slate-500">BMI</p><p className="text-2xl font-extrabold text-slate-800">{bmi || "-"}</p></div>
        </div>
      </Card>

      <Card n="9" title="My usual values (optional)" done={done.usual} hint="What these are when you are well, for example from your last check-up. A doctor compares today's reading with them.">
        <UsualValues baseline={f.baseline} onChange={(baseline) => up({ baseline })} />
      </Card>

      <Card n="10" title="Other" hint="Short answers are fine.">
        <div className="grid gap-3">
          <label className="text-xs font-bold text-slate-500">Vaccinations taken<Textarea rows={2} value={f.immunization} placeholder="e.g. COVID-19 two doses, tetanus 2022" onChange={(e) => up({ immunization: e.target.value })} /></label>
          <label className="text-xs font-bold text-slate-500">Work and home<Textarea rows={2} value={f.socioeconomic} placeholder="e.g. retired teacher, lives with wife and son" onChange={(e) => up({ socioeconomic: e.target.value })} /></label>
          {showChildren && (
            <>
              <label className="text-xs font-bold text-slate-500">Birth history (for children)<Textarea rows={2} value={f.birth_history} onChange={(e) => up({ birth_history: e.target.value })} /></label>
              <label className="text-xs font-bold text-slate-500">Development: sitting, walking, talking (for children)<Textarea rows={2} value={f.developmental_history} onChange={(e) => up({ developmental_history: e.target.value })} /></label>
            </>
          )}
        </div>
      </Card>

      <div className="sticky bottom-3 z-10 flex flex-wrap items-center justify-between gap-3 rounded-3xl border border-slate-200 bg-white/95 p-4 shadow-lg backdrop-blur">
        <p className="flex items-center gap-2 text-sm text-slate-500">{Object.values(done).every(Boolean) ? <CheckCircle2 className="text-emerald-600" size={18} /> : <Circle size={18} />}
          {Object.values(done).filter(Boolean).length} of 8 important parts answered. You can save now and finish later.</p>
        <Button disabled={saving}>{saving ? "Saving..." : saveLabel}</Button>
      </div>
      {error && <p className="rounded-2xl bg-red-50 p-3 text-sm font-semibold text-red-700">{error}</p>}
    </form>
  );
}
