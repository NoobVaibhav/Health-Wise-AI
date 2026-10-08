import { Bot, CalendarClock, ClipboardCheck, FileText, Pill, Stethoscope, StickyNote } from "lucide-react";
import { fmtDate } from "./ui";

// The timeline comes from the database. `source` shows WHO produced each item, so computer-generated
// information is never confused with the doctor's own words.
const ICONS = {
  APPOINTMENT: CalendarClock, REPORT_UPLOADED: FileText, AI_ANALYSIS: Bot, DOCTOR_REVIEW: ClipboardCheck,
  DOCTOR_NOTE: StickyNote, RECOMMENDATION: Stethoscope, PRESCRIPTION: Pill, DISPENSING: Pill, HISTORY_ENTRY: Stethoscope,
};
const SOURCE_STYLE = {
  AI: ["bg-violet-500", "bg-violet-100 text-violet-800", "Computer-generated"],
  DOCTOR: ["bg-emerald-500", "bg-emerald-100 text-emerald-800", "Doctor"],
  PHARMACY: ["bg-amber-500", "bg-amber-100 text-amber-900", "Pharmacy"],
  HOSPITAL: ["bg-sky-500", "bg-sky-100 text-sky-800", "Hospital"],
};

export default function Timeline({ events }) {
  if (!events || events.length === 0) return <p className="py-4 text-center text-slate-500">Nothing here yet. Your reports, doctor notes and medicines will appear in this timeline, newest first.</p>;
  const groups = [];
  for (const e of events) {
    const last = groups[groups.length - 1];
    if (last && last.date === e.date) last.items.push(e);
    else groups.push({ date: e.date, items: [e] });
  }
  return (
    <div className="space-y-7">
      {groups.map((g) => (
        <div key={g.date}>
          <p className="mb-3 inline-block rounded-full bg-brand-100 px-3 py-1 text-sm font-extrabold text-brand-800">{fmtDate(g.date)}</p>
          <ol className="space-y-4 border-l-2 border-slate-200 pl-6">
            {g.items.map((e, i) => {
              const Icon = ICONS[e.type] || FileText;
              const [dot, badge, label] = SOURCE_STYLE[e.source] || SOURCE_STYLE.HOSPITAL;
              return (
                <li key={`${e.type}-${e.entity_id}-${i}`} className="relative">
                  <span className={`absolute -left-[39px] top-0 flex h-8 w-8 items-center justify-center rounded-full text-white ring-4 ring-white ${dot}`}><Icon size={16} /></span>
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-bold text-slate-900">{e.title}</p>
                    <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-bold ${badge}`}>{label}</span>
                  </div>
                  {e.detail && <p className="text-sm text-slate-600">{e.detail}</p>}
                </li>
              );
            })}
          </ol>
        </div>
      ))}
    </div>
  );
}
