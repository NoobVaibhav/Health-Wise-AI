// "Points to check" for the doctor: what a doctor often reviews, given the history. Made by fixed rules, never a diagnosis.
import { AlertTriangle, Activity, CircleHelp, Cigarette, HeartPulse, Pill, Stethoscope } from "lucide-react";
import { Section } from "./HealthCard";

const STYLE = {
  safety: ["Safety first", "border-red-300 bg-red-50", "text-red-800", AlertTriangle],
  vitals: ["Recorded vitals", "border-amber-300 bg-amber-50", "text-amber-900", Activity],
  complaint: ["Because of today's problem", "border-sky-200 bg-sky-50", "text-sky-900", Stethoscope],
  medicine: ["Because of the medicines", "border-violet-200 bg-violet-50", "text-violet-900", Pill],
  condition: ["Because of the illnesses", "border-brand-200 bg-brand-50", "text-brand-900", HeartPulse],
  habit: ["Because of the habits", "border-slate-200 bg-slate-50", "text-slate-800", Cigarette],
  missing: ["Still missing", "border-amber-200 bg-white", "text-amber-900", CircleHelp],
};
const ORDER = ["safety", "vitals", "complaint", "medicine", "condition", "habit", "missing"];

export default function PointsToCheck({ points }) {
  if (!points?.length) return null;
  return (
    <Section title="Points to check">
      <p className="-mt-2 mb-4 text-sm text-slate-500">Worked out by the computer from the medicines, illnesses, habits and complaint in this history. They are things doctors often review. They are not a diagnosis, and you decide what is needed.</p>
      <div className="space-y-4">
        {ORDER.filter((c) => points.some((p) => p.category === c)).map((c) => {
          const [label, box, text, Icon] = STYLE[c];
          return (
            <div key={c}>
              <p className={`mb-2 flex items-center gap-2 text-sm font-extrabold ${text}`}><Icon size={16} />{label}</p>
              <ul className="space-y-2">
                {points.filter((p) => p.category === c).map((p, i) => (
                  <li key={i} className={`rounded-2xl border p-3 ${box}`}><p className={`font-bold ${text}`}>{p.title}</p><p className="text-[15px] text-slate-700">{p.detail}</p></li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>
    </Section>
  );
}
