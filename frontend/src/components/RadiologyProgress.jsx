// A patient's scans: the doctor sees an approved report and marks it as seen; the patient sees it only after that.
import { useState } from "react";
import { ScanLine } from "lucide-react";
import useFetch from "../hooks/useFetch";
import useSave from "../hooks/useSave";
import { getMyStudies, getPatientStudies, markStudySeen, openStudyFile } from "../services/diagnosticsApi";
import { ErrorBox } from "./Feedback";
import { Section } from "./HealthCard";
import { Button } from "./ui";

export default function RadiologyProgress({ patientId }) {
  const doctor = patientId != null;
  const { data, reload } = useFetch(() => (doctor ? getPatientStudies(patientId) : getMyStudies()), [patientId]);
  const { problem, busy, run } = useSave();
  const [open, setOpen] = useState(null);
  if (!data || data.length === 0) return null;
  return (
    <Section title="Scans">
      <ul className="divide-y divide-slate-100">{data.map((s) => (
        <li key={s.id} className="space-y-1 py-2.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="flex items-center gap-2 font-bold text-slate-900"><ScanLine size={16} className="text-brand-600" />{s.study}</p>
            <span className="rounded-full bg-slate-100 px-3 py-1 text-sm font-bold text-slate-700">{!doctor && s.status === "APPROVED" && !s.report ? "Report ready: your doctor will review it" : s.status_label}</span>
          </div>
          <p className="text-xs text-slate-400">Ordered {s.ordered_on} by {s.doctor_name}</p>
          {s.report && (
            <div className="rounded-xl bg-slate-50 p-3 text-sm">
              <button type="button" className="font-bold text-brand-700 underline" onClick={() => setOpen(open === s.id ? null : s.id)}>{open === s.id ? "Hide the report" : "Read the report"}</button>
              {open === s.id && <div className="mt-2 space-y-1"><p className="whitespace-pre-wrap"><b>Findings:</b> {s.report.findings}</p><p className="whitespace-pre-wrap"><b>Impression:</b> {s.report.impression}</p>
                {s.previous_studies.length > 0 && <p className="text-slate-600"><b>Earlier:</b> {s.previous_studies.map((p) => `${p.date}: ${p.impression}`).join("; ")}</p>}
                <p className="flex flex-wrap gap-3">{s.files.map((f) => <button key={f.id} type="button" className="font-semibold text-brand-700 underline" onClick={() => openStudyFile(f.id)}>{f.filename}</button>)}</p></div>}
            </div>)}
          {doctor && s.status === "APPROVED" && !s.doctor_seen_at && <Button variant="secondary" disabled={busy} onClick={async () => { if (await run(() => markStudySeen(s.id), "Marked as seen: the patient can now see it")) reload(); }}>I have seen this report</Button>}
        </li>))}</ul>
      {problem && <ErrorBox message={problem} />}
    </Section>
  );
}
