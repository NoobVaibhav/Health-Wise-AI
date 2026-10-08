// Suggestions for ANY kind of report. The doctor sees points to consider and can turn the draft patient tips into
// official advice; the patient sees general tips only after the doctor has reviewed the report.
import { useState } from "react";
import { AlertTriangle, Bot, CheckCircle2, Eye, Lightbulb, RefreshCw, Sparkles, Stethoscope } from "lucide-react";
import { Section } from "./HealthCard";
import { Hint } from "./Feedback";
import { Button } from "./ui";
import { refreshInsights } from "../services/reportApi";
import { getErrorMessage } from "../services/api";
import { useToast } from "./Toast";

const CONCERN = {
  attention: ["Worth a look", "bg-amber-100 text-amber-900", AlertTriangle],
  normal: ["Looks normal", "bg-emerald-100 text-emerald-800", CheckCircle2],
  neutral: ["For information", "bg-slate-100 text-slate-600", Eye],
};

const SourceNote = ({ source }) => (
  <p className="inline-flex items-center gap-1 rounded-full bg-violet-100 px-3 py-1 text-xs font-bold text-violet-800">
    {source === "llm" ? <Sparkles size={13} /> : <Bot size={13} />}
    {source === "llm" ? "Written with an AI model and checked by safety rules" : "Read by the computer with fixed rules (no AI model connected)"}
  </p>
);

/** The report's own sentences, each marked "looks normal" or "worth a look". */
export function KeyFindings({ findings, title = "What the report says" }) {
  if (!findings?.length) return null;
  return (
    <Section title={title}>
      <ul className="space-y-2">
        {findings.map((f, i) => {
          const [label, style, Icon] = CONCERN[f.concern] || CONCERN.neutral;
          return (
            <li key={i} className="flex items-start gap-3 rounded-2xl bg-slate-50 p-3">
              <span className={`mt-0.5 inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-bold ${style}`}><Icon size={13} />{label}</span>
              <span className="text-[15px] text-slate-700">{f.text}</span>
            </li>
          );
        })}
      </ul>
      <p className="mt-3 text-xs text-slate-400">The computer picked these sentences from the report and marked them by wording alone. It can be wrong, so please read the original.</p>
    </Section>
  );
}

/** For the doctor: red flags, points to consider, and draft tips that can become official advice in one click. */
export function DoctorInsights({ report, onUseAsAdvice, onChanged }) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const ins = report.insights;
  if (!ins) return null;

  const regenerate = async () => {
    setBusy(true);
    try { await refreshInsights(report.id); toast("Suggestions generated again"); onChanged?.(); } catch (e) { toast(getErrorMessage(e), "error"); } finally { setBusy(false); }
  };

  return (
    <div className="space-y-5">
      {ins.red_flags?.length > 0 && (
        <div className="rounded-3xl border-2 border-red-300 bg-red-50 p-5">
          <p className="mb-2 flex items-center gap-2 text-lg font-extrabold text-red-800"><AlertTriangle size={22} /> Flagged for prompt attention</p>
          <ul className="space-y-2 text-[15px] text-red-900">{ins.red_flags.map((r, i) => <li key={i}>{r}</li>)}</ul>
        </div>
      )}

      <Section title="Suggestions for the doctor" action={<SourceNote source={ins.source} />}>
        <p className="mb-3 flex items-center gap-2 text-sm text-slate-500"><Stethoscope size={16} /> Points to consider. They support your judgement and never replace it.</p>
        <ul className="space-y-2">
          {ins.doctor_suggestions.map((s, i) => (
            <li key={i} className="flex gap-3 rounded-2xl bg-violet-50 p-3 text-[15px] text-slate-800">
              <Lightbulb className="mt-0.5 shrink-0 text-violet-500" size={18} /> <span>{s}</span>
            </li>
          ))}
        </ul>
        <div className="mt-4 flex justify-end">
          <Button variant="secondary" disabled={busy} onClick={regenerate}><RefreshCw size={15} className={`mr-1.5 inline ${busy ? "animate-spin" : ""}`} />Generate again</Button>
        </div>
      </Section>

      <Section title="Draft tips for the patient">
        <p className="mb-3 text-sm text-slate-500">The patient sees these general tips after you review the report. Turn any of them into your own advice with one click, or leave them as they are.</p>
        <ul className="space-y-2">
          {ins.patient_recommendations.map((t, i) => (
            <li key={i} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-sky-50 p-3 text-[15px] text-slate-800">
              <span className="flex-1">{t}</span>
              {onUseAsAdvice && <Button variant="soft" onClick={() => onUseAsAdvice(t)}>Use as my advice</Button>}
            </li>
          ))}
        </ul>
      </Section>
    </div>
  );
}

/** For the patient (after review): friendly general tips. */
export function PatientTips({ insights }) {
  if (!insights?.patient_recommendations?.length) return null;
  return (
    <Section title="Helpful tips for you" action={<SourceNote source={insights.source} />}>
      <ul className="space-y-2">
        {insights.patient_recommendations.map((t, i) => (
          <li key={i} className="flex gap-3 rounded-2xl bg-sky-50 p-3 text-[15px] text-slate-800"><Lightbulb className="mt-0.5 shrink-0 text-sky-500" size={18} /> <span>{t}</span></li>
        ))}
      </ul>
      <div className="mt-4"><Hint title="Please remember">These are general tips written by a computer, not medical advice for you. Your doctor's own advice is shown separately under "Doctor's Advice". If something worries you, talk to your doctor.</Hint></div>
    </Section>
  );
}
