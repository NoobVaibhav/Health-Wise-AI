// Views that work for ONE patient: report comparison and parameter trend chart.
// Used by the doctor (patient details) and by the patient (My Timeline).
import { useEffect, useState } from "react";
import { ArrowRight, MoveDown, MoveUp } from "lucide-react";
import { getComparison, getTrend, getTrendList } from "../services/patientApi";
import { getErrorMessage } from "../services/api";
import { EmptyState, ErrorBox, Hint, Loading } from "./Feedback";
import StatusBadge, { TrendBadge } from "./StatusBadge";
import TrendChart from "./TrendChart";
import { fmtDate } from "./ui";
import { humanRange } from "./RangeBar";

// One test, before and after: "7.2 -> 6.8" with the change in words.
function ChangeCard({ r }) {
  const up = r.change > 0;
  const same = r.change === 0;
  const Arrow = up ? MoveUp : MoveDown;
  return (
    <div className="rounded-3xl border border-slate-200/70 bg-white p-5 shadow-sm">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <p className="text-lg font-extrabold text-slate-900">{r.parameter}</p>
          {r.reference_text && <p className="text-sm text-slate-500">Normal range: {humanRange(r.reference_text)} {r.unit || ""}</p>}
        </div>
        <TrendBadge trend={r.trend} />
      </div>

      <div className="flex items-center gap-3">
        <div className="flex-1 rounded-2xl bg-slate-50 p-3 text-center">
          <p className="text-sm font-bold text-slate-500">BEFORE</p>
          <p className="text-2xl font-extrabold text-slate-700">{r.previous}</p>
        </div>
        <ArrowRight className="shrink-0 text-slate-300" size={22} />
        <div className="flex-1 rounded-2xl bg-brand-50 p-3 text-center">
          <p className="text-sm font-bold text-brand-700">NOW</p>
          <p className="text-2xl font-extrabold text-slate-900">{r.latest}</p>
        </div>
      </div>
      <p className="mt-1 text-center text-xs text-slate-400">{r.unit}</p>

      <p className="mt-3 flex items-center gap-2 text-sm font-semibold text-slate-700">
        {same ? "No change" : <><Arrow size={16} className="text-slate-500" /> {up ? "Went up" : "Went down"} by {Math.abs(r.change)} {r.unit}{r.change_percent != null && ` (${Math.abs(r.change_percent)}%)`}</>}
        <span className="ml-auto"><StatusBadge status={r.latest_status} /></span>
      </p>
      <p className="mt-1 text-sm text-slate-500">{r.note}</p>
    </div>
  );
}

export function ComparisonView({ patientId }) {
  const [previousId, setPreviousId] = useState("");
  const [latestId, setLatestId] = useState("");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    setError("");
    getComparison(patientId, previousId, latestId)
      .then((data) => {
        setResult(data);
        if (data.available && !previousId) { setPreviousId(String(data.previous.id)); setLatestId(String(data.latest.id)); }
      })
      .catch((e) => setError(getErrorMessage(e)));
  }, [patientId, previousId, latestId]);

  if (error) return <ErrorBox message={error} />;
  if (!result) return <Loading />;
  if (!result.available) return <EmptyState message="You need at least two reports to compare" hint="Once a second checked report is added, you will see here how each test changed." />;

  const label = (r) => `${r.filename} (${fmtDate(r.report_date || r.uploaded_at)})`;
  return (
    <div className="space-y-4">
      <Hint title="How to read this">Each box shows the same test from two different dates. "BEFORE" is the older report and "NOW" is the newer one. A number that changed is not always good or bad. Please ask the doctor what it means for you.</Hint>
      <div className="flex flex-wrap items-center gap-3 text-sm font-semibold text-slate-600">
        <label className="block max-w-full sm:inline">Older report: <select className="ml-1 max-w-full rounded-xl border border-slate-300 bg-white px-3 py-2" value={previousId} onChange={(e) => setPreviousId(e.target.value)}>
          {result.reports.map((r) => <option key={r.id} value={r.id}>{label(r)}</option>)}</select></label>
        <label className="block max-w-full sm:inline">Newer report: <select className="ml-1 max-w-full rounded-xl border border-slate-300 bg-white px-3 py-2" value={latestId} onChange={(e) => setLatestId(e.target.value)}>
          {result.reports.map((r) => <option key={r.id} value={r.id}>{label(r)}</option>)}</select></label>
      </div>
      {result.rows.length === 0 ? <p className="text-slate-500">These two reports have no tests in common.</p> : (
        <div className="grid gap-4 md:grid-cols-2">{result.rows.map((r) => <ChangeCard key={r.parameter} r={r} />)}</div>
      )}
    </div>
  );
}

export function TrendsView({ patientId }) {
  const [names, setNames] = useState(null);
  const [selected, setSelected] = useState("");
  const [trend, setTrend] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    getTrendList(patientId)
      .then((list) => { setNames(list); if (list.length) setSelected(list[0].name); })
      .catch((e) => { setError(getErrorMessage(e)); setNames([]); });
  }, [patientId]);
  useEffect(() => {
    if (selected) getTrend(patientId, selected).then(setTrend).catch((e) => setError(getErrorMessage(e)));
  }, [patientId, selected]);

  if (names === null) return <Loading />;
  if (error) return <ErrorBox message={error} />;
  if (names.length === 0) return <EmptyState message="No checked reports yet" hint="Once reports are checked by a doctor, you can pick a test here and see how it changed over time." />;
  return (
    <div>
      <p className="mb-2 text-sm font-semibold text-slate-500">Pick a test to see how it changed over time:</p>
      <div className="mb-4 flex flex-wrap gap-2">
        {names.map((n) => (
          <button key={n.name} onClick={() => setSelected(n.name)}
            className={`rounded-full px-3.5 py-1.5 text-sm font-semibold ${selected === n.name ? "bg-brand-600 text-white shadow-sm" : "bg-slate-100 text-slate-600 hover:bg-slate-200"}`}>{n.name}</button>
        ))}
      </div>
      {trend && trend.points.length < 2 && <p className="mb-2 text-sm text-slate-500">Only one result so far. A line appears once there are two or more reports.</p>}
      {trend && <TrendChart points={trend.points} unit={trend.unit} name={trend.parameter} />}
      <p className="mt-2 text-xs text-slate-400">The green band is the normal range printed on the lab report.</p>
    </div>
  );
}
