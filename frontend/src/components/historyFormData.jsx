// Data helpers and small pieces shared by the doctor's history form: turn the saved history into form state and back,
// a list of small rows, and the usual-values grid. (Only doctors fill the permanent history in.)
import { Plus, Trash2 } from "lucide-react";
import { Button, Input, Select } from "./ui";

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
