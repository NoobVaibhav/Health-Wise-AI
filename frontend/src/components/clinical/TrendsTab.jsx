// Laboratory comparison: previous against latest for every parameter, with the printed reference range, and a chart over time.
import { useState } from "react";
import useFetch from "../../hooks/useFetch";
import { getReportTrends } from "../../services/clinicalApi";
import { Section } from "../HealthCard";
import TrendChart from "../TrendChart";
import { fmtDate } from "../ui";
import { ErrorBox, Loading } from "../Feedback";
import { SourceChip } from "./Statement";

const STATUS = { RETURNED_WITHIN_RANGE: "Returned within the reference range", NEWLY_OUTSIDE_RANGE: "Newly outside the reference range", STILL_OUTSIDE_RANGE: "Still outside the reference range", WITHIN_RANGE: "Within the reference range",
  NO_REFERENCE_RANGE: "Reference range not provided", NOT_COMPARABLE: "Not comparable", INSUFFICIENT_DATA: "Insufficient data" };
const ASSESS = { IMPROVED: ["Improved", "bg-emerald-100 text-emerald-800"], WORSENED: ["Worsened", "bg-red-100 text-red-800"], STABLE: ["Stable", "bg-slate-200 text-slate-700"], NEUTRAL: ["Needs clinical interpretation", "bg-amber-100 text-amber-900"],
  NOT_COMPARABLE: ["Not comparable", "bg-slate-200 text-slate-700"], INSUFFICIENT_DATA: ["Insufficient data", "bg-slate-100 text-slate-500"] };
const TREND = { INCREASED: "Increased", DECREASED: "Decreased", UNCHANGED: "Unchanged" };

const when = (p) => `${fmtDate(p.date)}${p.date_known ? "" : " (upload date)"}`;
const val = (p) => (p ? `${p.value} ${p.unit || ""}` : "-");

export default function TrendsTab({ patientId, onOpen }) {
  const { data, loading, error, reload } = useFetch(() => getReportTrends(patientId), [patientId]);
  const [open, setOpen] = useState(null);
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (data.parameters.length === 0) return <Section title="Report trends"><p className="text-slate-500">No laboratory results have been recorded for this patient yet.</p></Section>;
  const chosen = data.parameters.find((p) => p.name === open);
  const latestUnit = chosen?.points.at(-1)?.unit;
  const chartPoints = chosen?.points.filter((p) => (p.unit || "") === (latestUnit || "")).map((p) => ({ date: p.date, value: p.value, reference_low: p.reference_low, reference_high: p.reference_high }));

  return (
    <div className="space-y-4">
      <Section title="Previous result compared with the latest">
        <p className="-mt-2 mb-3 text-sm text-slate-500">Reference ranges are the ones printed on each laboratory report. A result is called improved or worsened only when that range supports it; otherwise the direction is shown without a judgement.</p>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[860px] text-sm">
            <thead><tr className="text-left text-xs uppercase tracking-wide text-slate-400"><th className="pb-2">Test</th><th>Previous</th><th>Latest</th><th>Change</th><th>Reference range</th><th>Result</th><th>Report status</th></tr></thead>
            <tbody>{data.parameters.map((p) => {
              const c = p.comparison;
              const [label, tone] = ASSESS[c.assessment] || ASSESS.NEUTRAL;
              return (
                <tr key={p.name} onClick={() => setOpen(open === p.name ? null : p.name)} className={`cursor-pointer border-t border-slate-100 align-top hover:bg-slate-50 ${open === p.name ? "bg-brand-50/50" : ""}`}>
                  <td className="py-2.5 pr-2 font-bold text-slate-900">{p.name}</td>
                  <td className="pr-2">{c.previous ? <><b>{val(c.previous)}</b><br /><span className="text-xs text-slate-500">{when(c.previous)}</span></> : <span className="text-slate-400">-</span>}</td>
                  <td className="pr-2"><b>{val(c.latest)}</b><br /><span className="text-xs text-slate-500">{when(c.latest)}</span></td>
                  <td className="pr-2">{c.change != null ? <>{c.change > 0 ? "+" : ""}{c.change}{c.change_percent != null ? ` (${c.change_percent > 0 ? "+" : ""}${c.change_percent}%)` : ""}<br /><span className="text-xs text-slate-500">{TREND[c.trend]}</span></> : "-"}</td>
                  <td className="pr-2">{c.reference_range}</td>
                  <td className="pr-2"><span className={`inline-block rounded-full px-2 py-0.5 text-xs font-bold ${tone}`}>{label}</span><p className="mt-0.5 text-xs text-slate-500">{STATUS[c.status]}</p></td>
                  <td className="text-xs text-slate-600">{c.latest.review_status === "REVIEWED" ? "Reviewed by a doctor" : "Waiting for review"}</td>
                </tr>);
            })}</tbody>
          </table>
        </div>
      </Section>

      {chosen && (
        <Section title={`${chosen.name} over time`}>
          <p className="-mt-2 mb-2 text-sm text-slate-700">{chosen.comparison.interpretation}</p>
          {chosen.comparison.warnings?.map((w) => <p key={w} className="text-xs text-amber-800">Note: {w}</p>)}
          {chosen.mixed_units && <p className="text-xs text-amber-800">Note: the units differ between reports. The chart shows only the results in {latestUnit || "the latest unit"}.</p>}
          {chosen.conflicts.map((c) => <p key={c} className="text-xs text-red-700">Conflict: {c}</p>)}
          {chosen.duplicates_removed > 0 && <p className="text-xs text-slate-500">{chosen.duplicates_removed} duplicate result(s) were counted once.</p>}
          <TrendChart points={chartPoints} unit={latestUnit} name={chosen.name} />
          <div className="mt-2 flex flex-wrap gap-1.5">{chosen.points.map((p) => <SourceChip key={p.report_id} source={{ type: "report", id: p.report_id, label: p.report_name, date: p.date }} onOpen={onOpen} />)}</div>
        </Section>
      )}
    </div>
  );
}
