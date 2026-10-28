// The printed analysis of one report (A4): patient, summary, what to look at first, the numbers, the doctor's words and the tips.
// It sits on the page all the time but only shows when printing (the app's print rule hides everything except "print-area").
// The same sheet serves the doctor (points to consider) and the patient (tips); the report data already holds only what that role may see.
import { fmtDate, fmtUtc } from "./ui";
import SummaryPoints from "./SummaryPoints";

const num = (v) => (typeof v === "number" ? v.toLocaleString(undefined, { maximumFractionDigits: 2 }) : v);
const CONCERN = { attention: "Worth a look", normal: "Looks normal", neutral: "Note" };
const STATUS = { WITHIN_RANGE: "Normal", ABOVE_RANGE: "High", BELOW_RANGE: "Low", UNKNOWN: "No range" };

const Block = ({ title, children }) => (
  <section className="mb-3.5">
    <h2 className="mb-1.5 border-b-2 border-slate-800 pb-0.5 text-[13px] font-extrabold uppercase tracking-wide text-slate-900" style={{ breakAfter: "avoid" }}>{title}</h2>
    {children}
  </section>
);

/** short: one page, only what to look at first (no full table, no tips). */
export default function ReportPrintSheet({ report, role, short = false }) {
  if (!report.analysis_visible) return null;
  const ins = report.insights || {};
  const params = report.parameters || [];
  const priority = ins.priority || [];
  const slight = ins.slightly_outside || [];
  const metrics = ins.metrics || [];
  const findings = ins.key_findings || [];
  const tips = role === "DOCTOR" ? ins.doctor_suggestions : ins.patient_recommendations;
  const c = report.counts || {};
  const lookAt = (x) => !short || x.concern === "attention";
  return (
    <div className="print-area hidden text-[12px] leading-snug text-slate-900 print:block" aria-hidden="true">
      <div className="mb-3 flex items-end justify-between border-b-4 border-slate-900 pb-2">
        <div>
          <p className="text-[11px] font-bold uppercase tracking-widest text-slate-500">HealthWise AI - Report analysis</p>
          <h1 className="text-xl font-extrabold">{report.patient_name} <span className="text-sm font-semibold text-slate-500">({report.patient_code})</span></h1>
        </div>
        <div className="text-right text-[11px] text-slate-600">
          <p><b>{report.report_type_label}</b> - {report.filename}</p>
          <p>Test date: {fmtDate(report.report_date)}</p>
          <p>Printed: {new Date().toLocaleDateString()}</p>
        </div>
      </div>

      <Block title="In short">
        <SummaryPoints report={report} print />
        {!report.is_narrative && !short && <p className="mt-1.5 font-semibold">Normal: {c.WITHIN_RANGE ?? 0} - Too high: {c.ABOVE_RANGE ?? 0} - Too low: {c.BELOW_RANGE ?? 0} - No normal range: {c.UNKNOWN ?? 0}</p>}
      </Block>

      {report.doctor_review_status === "REVIEWED" && (
        <Block title="Checked by the doctor">
          <p><b>{report.reviewed_by_name}</b> - {fmtUtc(report.reviewed_at)}</p>
          <p>{report.review_comment || "The doctor looked at the computer analysis and agreed with it."}</p>
        </Block>
      )}

      {priority.length > 0 && (
        <Block title="Look at these first (most important first)">
          <table className="w-full border-collapse text-left">
            <thead><tr className="bg-slate-100"><th className="p-1">Test</th><th className="p-1">Result</th><th className="p-1">Normal</th><th className="p-1">How far outside the range</th></tr></thead>
            <tbody>{priority.map((e) => (
              <tr key={e.name} className="border-b border-slate-300" style={{ breakInside: "avoid" }}>
                <td className="p-1 font-bold">{e.name}</td>
                <td className="p-1 font-bold">{num(e.value)} {e.unit} ({e.direction === "HIGH" ? "high" : "low"})</td>
                <td className="p-1">{e.range} {e.unit}</td>
                <td className="p-1">{e.how_far}</td>
              </tr>))}</tbody>
          </table>
          {!short && priority.some((e) => e.meaning) && (
            <ul className="mt-1.5 list-disc space-y-0.5 pl-4 text-[11px] text-slate-600">{priority.filter((e) => e.meaning).map((e) => <li key={e.name} style={{ breakInside: "avoid" }}><b>{e.name}:</b> {e.meaning}</li>)}</ul>
          )}
        </Block>
      )}
      {slight.length > 0 && (
        <Block title={`${slight.length} other result${slight.length === 1 ? " is" : "s are"} only slightly outside the range, or minor tests`}>
          <p>{slight.map((e) => `${e.name} ${num(e.value)} ${e.unit || ""} (${e.direction === "HIGH" ? "high" : "low"}, normal ${e.range})`).join("; ")}.</p>
        </Block>
      )}

      {metrics.filter(lookAt).length > 0 && (
        <Block title={short ? "Numbers worth a look" : "Key numbers read from the report"}>
          <table className="w-full border-collapse text-left">
            <tbody>{metrics.filter(lookAt).map((m, i) => (
              <tr key={i} className="border-b border-slate-200" style={{ breakInside: "avoid" }}>
                <td className="w-1/2 p-1">{m.label}</td>
                <td className="p-1 font-bold">{num(m.value)} {m.unit}</td>
                <td className="p-1 text-slate-600">{m.detail || (m.concern === "attention" ? "Worth a look" : "")}</td>
              </tr>))}</tbody>
          </table>
        </Block>
      )}

      {report.is_narrative && findings.filter(lookAt).length > 0 && (
        <Block title="What the report says">
          <ul className="space-y-0.5">{findings.filter(lookAt).map((f, i) => <li key={i} style={{ breakInside: "avoid" }}><b>[{CONCERN[f.concern] || "Note"}]</b> {f.text}</li>)}</ul>
        </Block>
      )}

      {!report.is_narrative && !short && params.length > 0 && (
        <Block title="All test results">
          <table className="w-full border-collapse text-left text-[11px]">
            <thead><tr className="bg-slate-100"><th className="p-1">Test</th><th className="p-1">Result</th><th className="p-1">Normal range</th><th className="p-1">Status</th></tr></thead>
            <tbody>{params.map((p) => (
              <tr key={p.id} className={`border-b border-slate-200 ${p.status === "ABOVE_RANGE" || p.status === "BELOW_RANGE" ? "font-bold" : ""}`} style={{ breakInside: "avoid" }}>
                <td className="p-1">{p.normalized_name || p.test_name}</td>
                <td className="p-1">{num(p.value)} {p.unit}</td>
                <td className="p-1">{p.reference_text || "not printed"}</td>
                <td className="p-1">{STATUS[p.status] || p.status_label}</td>
              </tr>))}</tbody>
          </table>
        </Block>
      )}

      {!short && tips?.length > 0 && (
        <Block title={role === "DOCTOR" ? "Points for the doctor to consider" : "General tips"}>
          <ul className="list-disc space-y-0.5 pl-4">{tips.map((t, i) => <li key={i} style={{ breakInside: "avoid" }}>{typeof t === "string" ? t : t.text}</li>)}</ul>
        </Block>
      )}

      <p className="mt-4 border-t border-slate-400 pt-1.5 text-[10px] text-slate-500">
        This analysis was written by the computer from the report using fixed rules. It is not a diagnosis and does not replace a doctor. A doctor must check it before any decision. Compare with the original report.
      </p>
    </div>
  );
}
