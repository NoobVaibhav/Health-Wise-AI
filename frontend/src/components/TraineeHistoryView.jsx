// A history taken by a trainee, read-only, with who took it and whether a doctor has verified it.
import { BadgeCheck, Clock } from "lucide-react";
import { fmtUtc } from "./ui";

const SMOKING = { NONE: "Does not smoke or chew tobacco", SMOKER: "Smoker", CHEWER: "Tobacco chewer", FORMER: "Former tobacco user" };
const ALCOHOL = { NONE: "No alcohol", OCCASIONAL: "Occasional alcohol", REGULAR: "Regular alcohol", FORMER: "Former alcohol use" };
const VITAL_LABELS = [["pulse", "Pulse", ""], ["bp_systolic", "BP upper", ""], ["bp_diastolic", "BP lower", ""], ["temperature_f", "Temperature", " °F"], ["resp_rate", "Breathing rate", ""], ["spo2", "Oxygen", " %"], ["weight_kg", "Weight", " kg"], ["height_cm", "Height", " cm"]];

export function Status({ history }) {
  return history.status === "VERIFIED"
    ? <span className="inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-1 text-xs font-bold text-emerald-800"><BadgeCheck size={14} /> Verified by {history.verified_by}</span>
    : <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2.5 py-1 text-xs font-bold text-amber-800"><Clock size={14} /> {history.status === "DRAFT" ? "Draft" : "Pending doctor review"}</span>;
}

const Row = ({ label, children }) => (children ? <div><dt className="text-xs font-bold uppercase tracking-wide text-slate-500">{label}</dt><dd className="whitespace-pre-line text-slate-800">{children}</dd></div> : null);

export default function TraineeHistoryView({ history }) {
  const d = history.data || {};
  const vitals = VITAL_LABELS.filter(([k]) => d.vitals?.[k] != null).map(([k, label, unit]) => `${label} ${d.vitals[k]}${unit}`).join(" · ");
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2 text-sm text-slate-600">
        <span>Taken by <b>{history.taken_by}</b></span><span>· {fmtUtc(history.completed_at || history.updated_at)}</span><Status history={history} />
      </div>
      <dl className="grid gap-3 sm:grid-cols-2">
        <Row label="Main complaint">{[d.chief_complaint, d.duration && `for ${d.duration}`].filter(Boolean).join(" ")}</Row>
        <Row label="Symptoms">{(d.symptoms || []).join(", ")}</Row>
        <Row label="History of present illness">{d.present_illness}</Row>
        <Row label="Past medical history">{d.past_medical}</Row>
        <Row label="Past surgical history">{d.past_surgical}</Row>
        <Row label="Medicines">{d.medications}</Row>
        <Row label="Allergies">{d.allergies === "NONE" ? "None" : d.allergies === "YES" ? d.allergy_details : null}</Row>
        <Row label="Family history">{d.family_history}</Row>
        <Row label="Habits">{[SMOKING[d.smoking], ALCOHOL[d.alcohol]].filter(Boolean).join(". ")}</Row>
        <Row label="Personal and social">{d.personal_social}</Row>
        <Row label="Menstrual and obstetric">{d.menstrual_obstetric}</Row>
        <Row label="Vitals">{vitals}</Row>
      </dl>
      {history.doctor_notes && <p className="rounded-2xl bg-sky-50 p-3 text-sm text-sky-900"><b>Doctor's note:</b> {history.doctor_notes}</p>}
    </div>
  );
}
