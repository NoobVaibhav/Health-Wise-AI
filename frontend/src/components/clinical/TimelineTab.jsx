// A searchable, chronological list of everything documented, each item linked to its record. Dates are never guessed.
import { useState } from "react";
import useFetch from "../../hooks/useFetch";
import { getTimeline } from "../../services/clinicalApi";
import { Section } from "../HealthCard";
import { fmtDate, inputClass } from "../ui";
import { ErrorBox, Loading } from "../Feedback";
import { SourceChip } from "./Statement";

const KIND = { REPORT: "Report", REPORT_UPLOADED: "Upload", REPORT_REVIEWED: "Review", NOTE: "Note", RECOMMENDATION: "Advice", PRESCRIPTION: "Prescription", DISPENSING: "Pharmacy", HISTORY: "History",
  ASSESSMENT: "Assessment", EMERGENCY: "Emergency", APPOINTMENT: "Appointment", FOLLOW_UP: "Follow-up" };
const TONE = { EMERGENCY: "bg-red-100 text-red-800", REPORT: "bg-sky-100 text-sky-800", PRESCRIPTION: "bg-violet-100 text-violet-800", ASSESSMENT: "bg-emerald-100 text-emerald-800", FOLLOW_UP: "bg-amber-100 text-amber-900" };

export default function TimelineTab({ patientId, onOpen }) {
  const [q, setQ] = useState("");
  const { data, loading, error, reload } = useFetch(() => getTimeline(patientId, q), [patientId, q]);
  return (
    <Section title="Medical timeline">
      <input className={`${inputClass} mb-4`} placeholder="Search the timeline (for example: report, prescription, HbA1c, emergency)" value={q} onChange={(e) => setQ(e.target.value)} />
      {loading && !data ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> : data.events.length === 0 ? <p className="text-slate-500">Nothing documented{q ? " matches the search" : " yet"}.</p> : (
        <ol className="space-y-2">{data.events.map((e) => (
          <li key={e.key} className="flex gap-3 rounded-2xl border border-slate-200 bg-white p-3">
            <div className="w-28 shrink-0 text-sm"><p className={e.date ? "font-bold text-slate-800" : "font-bold italic text-slate-500"}>{e.date ? fmtDate(e.date) : e.date_note}</p><p className="text-xs text-slate-400">{e.date_label}</p></div>
            <div className="min-w-0 flex-1"><div className="flex flex-wrap items-center gap-2"><span className={`rounded-full px-2 py-0.5 text-xs font-bold ${TONE[e.kind] || "bg-slate-100 text-slate-600"}`}>{KIND[e.kind] || e.kind}</span><b className="text-slate-900">{e.title}</b></div>
              {e.detail && <p className="mt-0.5 text-sm text-slate-600">{e.detail}</p>}
              <div className="mt-1.5"><SourceChip source={e.source} onOpen={onOpen} /></div></div>
          </li>))}</ol>
      )}
    </Section>
  );
}
