// One-page summary for a doctor who meets the patient for the first time (or in an emergency):
// who, allergies, medicines taken, illnesses, operations, habits, contact. Printable (A4).
import { AlertTriangle, Droplets, Phone, Pill } from "lucide-react";
import { fmtUtcDate } from "./ui";

const WORD = {
  tobacco: { NONE: "No tobacco", SMOKER: "Smoker", CHEWER: "Chews tobacco", FORMER: "Stopped tobacco" },
  alcohol: { NONE: "No alcohol", OCCASIONAL: "Alcohol occasionally", REGULAR: "Alcohol regularly", FORMER: "Stopped alcohol" },
  diet: { VEG: "Vegetarian", NONVEG: "Non-vegetarian", MIXED: "Mixed diet", VEGAN: "Vegan" },
};

export function habitLines(h = {}) {
  const lines = [];
  if (h.tobacco) lines.push(`${WORD.tobacco[h.tobacco]}${h.tobacco_years && h.tobacco !== "NONE" ? ` (${h.tobacco_years} years)` : ""}`);
  if (h.alcohol) lines.push(`${WORD.alcohol[h.alcohol]}${h.alcohol_years && h.alcohol !== "NONE" ? ` (${h.alcohol_years} years)` : ""}`);
  if (h.diet) lines.push(WORD.diet[h.diet]);
  return lines;
}

const Block = ({ title, children, className = "" }) => (
  <div className={`rounded-2xl border border-slate-200 bg-white p-4 ${className}`}>
    <p className="mb-2 text-xs font-extrabold uppercase tracking-wide text-slate-400">{title}</p>
    {children}
  </div>
);

export default function EmergencyCard({ card }) {
  const habits = habitLines(card.habits);
  return (
    <div className="space-y-3 text-slate-800">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-gradient-to-r from-brand-700 to-brand-600 p-5 text-white print:bg-brand-700">
        <div>
          <p className="text-2xl font-extrabold">{card.name}</p>
          <p className="text-brand-50">{card.age != null ? `${card.age} years` : "Age not set"}{card.gender ? ` - ${card.gender}` : ""} - {card.patient_code}</p>
        </div>
        <div className="flex gap-3">
          <span className="flex items-center gap-2 rounded-xl bg-white/15 px-3 py-2 font-bold"><Droplets size={18} /> Blood group: {card.blood_group || "not set"}</span>
          {card.bmi && <span className="rounded-xl bg-white/15 px-3 py-2 font-bold">BMI {card.bmi}</span>}
        </div>
      </div>

      <div className={`rounded-2xl border-2 p-4 ${card.allergies.length ? "border-red-300 bg-red-50" : "border-slate-200 bg-white"}`}>
        <p className="mb-1 flex items-center gap-2 font-extrabold text-red-800"><AlertTriangle size={18} /> Allergies</p>
        {card.allergies.length ? (
          <ul className="space-y-0.5">{card.allergies.map((a, i) => <li key={i} className="font-semibold text-red-900">{a.name}{a.reaction ? ` - ${a.reaction}` : ""} <span className="text-xs font-normal text-red-700">({{ DRUG: "medicine", FOOD: "food", OTHER: "other" }[a.kind]})</span></li>)}</ul>
        ) : <p className="text-slate-600">{card.no_known_allergies ? "No known allergies (as told by the patient)." : "Not recorded. Please ask the patient."}</p>}
      </div>

      <Block title="Medicines taken regularly">
        {card.medicines.length ? (
          <table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-slate-400"><th className="pb-1">Medicine</th><th>Strength</th><th>How often</th><th>For</th></tr></thead>
            <tbody>{card.medicines.map((m, i) => (
              <tr key={i} className="border-t border-slate-100"><td className="py-1.5 pr-2 font-bold"><Pill size={14} className="mr-1 inline text-brand-600" />{m.name}</td><td className="pr-2">{m.dose || "-"}</td><td className="pr-2">{m.frequency || "-"}</td><td>{m.reason || "-"}</td></tr>
            ))}</tbody>
          </table>
        ) : <p className="text-slate-600">{card.no_regular_medicines ? "No regular medicines (as told by the patient)." : "Not recorded. Please ask the patient or the family."}</p>}
      </Block>

      {(Object.values(card.usual_values || {}).some((x) => x && (!Array.isArray(x) || x.length)) || card.latest_labs?.length > 0) && (
        <Block title="Usual values and latest blood tests">
          <div className="flex flex-wrap gap-2 text-sm">
            {[["Pulse", card.usual_values?.pulse, "/min"], ["BP", card.usual_values?.bp_systolic ? `${card.usual_values.bp_systolic}/${card.usual_values.bp_diastolic ?? "?"}` : null, ""], ["Sugar (fasting)", card.usual_values?.sugar_fasting, "mg/dL"], ["HbA1c", card.usual_values?.hba1c, "%"],
              ["Haemoglobin", card.usual_values?.hemoglobin, "g/dL"], ["Creatinine", card.usual_values?.creatinine, "mg/dL"], ...(card.usual_values?.others || []).map((o) => [o.name, o.value, o.unit || ""])]
              .filter(([, value]) => value).map(([k, value, unit]) => <span key={k} className="rounded-lg bg-slate-100 px-2.5 py-1"><span className="text-slate-500">usual {k}: </span><b>{value} {unit}</b></span>)}
            {(card.latest_labs || []).map((l) => <span key={l.name} className="rounded-lg bg-brand-50 px-2.5 py-1"><span className="text-slate-500">{l.name}: </span><b>{l.value} {l.unit}</b></span>)}
          </div>
        </Block>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        <Block title="Illnesses">
          {card.conditions.length ? <ul className="space-y-0.5">{card.conditions.map((c, i) => <li key={i}><b>{c.name}</b>{c.since ? ` - since ${c.since}` : ""}{c.on_treatment ? " - on treatment" : ""}</li>)}</ul>
            : <p className="text-slate-600">{card.no_known_conditions ? "No known illnesses." : "Not recorded."}</p>}
        </Block>
        <Block title="Operations and hospital stays">
          {card.surgeries.length ? <ul className="space-y-0.5">{card.surgeries.map((s, i) => <li key={i}><b>{s.what}</b>{s.year ? ` (${s.year})` : ""}{s.hospital ? ` - ${s.hospital}` : ""}</li>)}</ul>
            : <p className="text-slate-600">None recorded.</p>}
        </Block>
        <Block title="Habits">{habits.length ? <ul className="space-y-0.5">{habits.map((l) => <li key={l}>{l}</li>)}</ul> : <p className="text-slate-600">Not recorded.</p>}</Block>
        <Block title="Emergency contact">
          <p className="flex items-center gap-2 font-bold"><Phone size={15} className="text-brand-600" />{card.emergency_contact || "Not recorded"}</p>
          {card.phone && <p className="text-sm text-slate-600">Patient's phone: {card.phone}</p>}
        </Block>
      </div>

      <p className="text-xs text-slate-400">
        Written by {card.updated_by_name || "the patient"}{card.updated_at ? ` on ${fmtUtcDate(card.updated_at)}` : ""}. This is the patient's own record on HealthWise AI. Please confirm the details with the patient or the family.
        It is a summary of the history and does not replace a doctor's examination.
      </p>
    </div>
  );
}
