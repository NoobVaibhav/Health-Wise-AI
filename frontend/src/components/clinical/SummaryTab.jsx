// The first screen of the clinical summary: overview, then the evidence-linked sections, then the optional AI narrative.
import { useState } from "react";
import { AlertTriangle, Bot, Printer } from "lucide-react";
import { Section } from "../HealthCard";
import { printAs } from "../../utils/printTitle";
import { Button, fmtDate, fmtUtc } from "../ui";
import { generateAiNarrative } from "../../services/clinicalApi";
import { getErrorMessage } from "../../services/api";
import { useToast } from "../Toast";
import Statement, { LABEL_STYLE, LabelChip, SourceChip } from "./Statement";

const SECTIONS = [
  ["what_happened", "What has happened to this patient?", "Documented events in date order. Each line links to its record."],
  ["current_status", "Current clinical status", "The latest documented findings. This is not a diagnosis."],
  ["important_changes", "Important changes", "Calculated from the recorded values. A change is called better or worse only when the printed range supports it."],
  ["red_flags", "Red flags for the doctor to check", "Items to verify. The urgent-finding rules are simple checks that clinicians must validate."],
  ["missing", "Missing or conflicting information", "What the records do not show. Missing information is not proof that something did not happen."],
];

function Card({ title, children, tone = "" }) {
  return <div className={`rounded-2xl border border-slate-200 bg-white p-3.5 ${tone}`}><p className="mb-1 text-xs font-extrabold uppercase tracking-wide text-slate-400">{title}</p><div className="text-[15px] text-slate-800">{children}</div></div>;
}

export default function SummaryTab({ summary, patientId, patientName, onOpen, reload }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const o = summary.overview;
  const ai = summary.ai_summary;

  const writeAi = async () => {
    setBusy(true);
    try { await generateAiNarrative(patientId); toast("AI narrative written"); reload(); } catch (e) { toast(getErrorMessage(e), "error"); } finally { setBusy(false); }
  };

  return (
    <div className="space-y-5">
      {summary.urgent_notice && (
        <p className="flex items-start gap-3 rounded-2xl border-2 border-red-400 bg-red-50 p-4 font-semibold text-red-900"><AlertTriangle className="mt-0.5 shrink-0" size={20} />{summary.urgent_notice}</p>
      )}

      <div className="flex flex-wrap items-center justify-between gap-3 print:hidden">
        <div className="flex flex-wrap gap-1.5 text-xs">{Object.entries(summary.labels).filter(([k]) => k !== "AI_GENERATED" || ai).map(([k, v]) => <span key={k} className={`rounded-full px-2.5 py-0.5 font-bold ${LABEL_STYLE[k]}`}>{v}</span>)}</div>
        <Button variant="secondary" onClick={() => printAs(patientName, "Clinical summary")}><Printer size={15} className="mr-1.5 inline" />Print or save as PDF</Button>
      </div>

      <Section title="Patient overview">
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <Card title="Patient"><b>{o.patient_code}</b>{o.age != null ? `, ${o.age} years` : ""}{o.gender ? `, ${o.gender}` : ""}</Card>
          <Card title="Allergies" tone={o.allergies.length ? "!border-red-300 !bg-red-50" : ""}>{o.allergies.length ? o.allergies.map((a) => a.name + (a.reaction ? ` (${a.reaction})` : "")).join(", ") : <span className="italic text-slate-500">{o.allergies_status === "none known" ? "None known" : "Not recorded"}</span>}</Card>
          <Card title="Documented conditions">{o.conditions.length ? o.conditions.map((c) => c.name).join(", ") : <span className="italic text-slate-500">None documented</span>}</Card>
          <Card title="Medicines on record">{[...o.current_medicines.prescribed_open.map((m) => m.name), ...o.current_medicines.reported_in_history].join(", ") || <span className="italic text-slate-500">None documented</span>}
            <p className="mt-1 text-xs text-slate-500">{o.current_medicines.note}</p></Card>
          <Card title="Latest report">{o.latest_report ? <><SourceChip source={o.latest_report.source} onOpen={onOpen} /><p className="mt-1 text-sm text-slate-600">{o.latest_report.date_known ? fmtDate(o.latest_report.date) : "Test date not printed"} - {o.latest_report.review_status === "REVIEWED" ? "reviewed by a doctor" : "waiting for a doctor's review"}</p></> : <span className="italic text-slate-500">No reports</span>}</Card>
          <Card title="Most recent encounter">{o.latest_encounter ? <>{o.latest_encounter.text}<p className="text-sm text-slate-500">{fmtDate(o.latest_encounter.date)} - {o.latest_encounter.doctor}</p></> : <span className="italic text-slate-500">No assessment recorded</span>}</Card>
          <Card title="Pending follow-ups">{o.pending_follow_ups.count ? <b>{o.pending_follow_ups.count} pending{o.pending_follow_ups.overdue ? `, ${o.pending_follow_ups.overdue} overdue` : ""}</b> : <span className="italic text-slate-500">None pending</span>}</Card>
          <Card title="Unresolved findings" tone={o.unresolved_findings.length ? "!border-amber-300 !bg-amber-50" : ""}>{o.unresolved_findings.length ? o.unresolved_findings.map((u) => `${u.parameter} ${u.value} ${u.unit || ""}`).join("; ") : <span className="italic text-slate-500">None outside a printed range</span>}</Card>
        </div>
      </Section>

      {SECTIONS.map(([key, title, hint]) => (
        <Section key={key} title={title}>
          <p className="-mt-2 mb-3 text-sm text-slate-500">{hint}</p>
          <ul className="space-y-2.5">{summary[key].map((st) => <Statement key={st.key} st={st} labels={summary.labels} patientId={patientId} onOpen={onOpen} onChanged={reload} tone={key === "red_flags" ? "red" : ""} />)}</ul>
        </Section>
      ))}

      <Section title="AI-written narrative (optional)">
        {ai ? (
          <div className="rounded-2xl border border-violet-200 bg-violet-50/60 p-4">
            <p className="mb-2 flex flex-wrap items-center gap-2"><LabelChip label="AI_GENERATED" labels={summary.labels} /><LabelChip label="REQUIRES_CLINICIAN_VERIFICATION" labels={summary.labels} /><span className="text-xs text-slate-500">{fmtUtc(ai.generated_at)} by {ai.generated_by}{ai.model ? ` - ${ai.model}` : ""}</span></p>
            {ai.paragraphs.map((p, i) => <p key={i} className="mb-2 text-[15px] text-slate-800">{p.text} <span className="text-xs text-slate-400">[{p.cites.join(", ")}]</span></p>)}
            {ai.questions?.length > 0 && <><p className="mt-2 text-sm font-bold text-slate-700">Questions you may want to consider</p><ul className="list-disc pl-5 text-[15px] text-slate-800">{ai.questions.map((q) => <li key={q}>{q}</li>)}</ul></>}
            <p className="mt-2 text-xs text-slate-500">Written by the AI model from the verified statements above. It is kept apart from the doctors' own notes.</p>
          </div>
        ) : <p className="text-slate-500">{summary.ai_available ? "No AI narrative has been written yet." : "No AI model is connected. The summary above was made by the system's own rules and does not need one."}</p>}
        {summary.ai_available && <div className="mt-3 print:hidden"><Button variant="secondary" disabled={busy} onClick={writeAi}><Bot size={15} className="mr-1.5 inline" />{busy ? "Writing..." : ai ? "Write it again" : "Write an AI narrative"}</Button></div>}
      </Section>

      <p className="rounded-2xl bg-slate-100 p-4 text-sm text-slate-600">{summary.disclaimer}</p>
    </div>
  );
}
