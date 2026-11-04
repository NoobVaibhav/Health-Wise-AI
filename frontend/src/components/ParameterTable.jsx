// Test results of a report. Default view = one friendly card per test with a gauge and a plain sentence;
// a "Table" view is available for people who like rows and columns.
import { useState } from "react";
import { ChevronDown, ChevronUp, LayoutGrid, Table2 } from "lucide-react";
import StatusBadge from "./StatusBadge";
import RangeBar, { humanRange } from "./RangeBar";
import { TableNote } from "./ReportCoverage";

const FILTERS = [
  ["ALL", "All"], ["ABOVE_RANGE", "Too high"], ["BELOW_RANGE", "Too low"],
  ["WITHIN_RANGE", "Normal"], ["UNKNOWN", "No normal range"],
];

const BORDER = { WITHIN_RANGE: "border-emerald-200", ABOVE_RANGE: "border-amber-300", BELOW_RANGE: "border-sky-300", UNKNOWN: "border-slate-200" };

function sentence(p) {
  const unit = p.unit ? ` ${p.unit}` : "";
  const range = p.reference_text ? `The normal value is ${humanRange(p.reference_text)}${unit}. ` : "The lab did not give a normal range for this test. ";
  const verdict = {
    WITHIN_RANGE: "Your result is normal.",
    ABOVE_RANGE: "Your result is higher than normal.",
    BELOW_RANGE: "Your result is lower than normal.",
    UNKNOWN: "So the computer cannot tell if it is normal. Please ask the doctor.",
  }[p.status];
  return `${range}${verdict}`;
}

export default function ParameterTable({ parameters }) {
  const [filter, setFilter] = useState("ALL");
  const [view, setView] = useState("cards");
  const rows = parameters.filter((p) => filter === "ALL" || p.status === filter);
  const count = (key) => (key === "ALL" ? parameters.length : parameters.filter((p) => p.status === key).length);

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          {FILTERS.filter(([key]) => key === "ALL" || count(key) > 0).map(([key, label]) => (
            <button key={key} onClick={() => setFilter(key)}
              className={`min-h-10 rounded-full border-2 px-4 py-1.5 text-base font-bold ${filter === key ? "border-brand-800 bg-brand-700 text-white shadow-sm" : "border-slate-300 bg-white text-slate-700 hover:bg-slate-100"}`}>
              {label} ({count(key)})
            </button>
          ))}
        </div>
        <div className="flex gap-1 rounded-xl bg-slate-200 p-1">
          <button onClick={() => setView("cards")} className={`flex min-h-10 items-center gap-1.5 rounded-lg px-3 text-sm font-bold ${view === "cards" ? "bg-brand-700 text-white shadow-sm" : "text-slate-700"}`}><LayoutGrid size={17} /> Cards</button>
          <button onClick={() => setView("table")} className={`flex min-h-10 items-center gap-1.5 rounded-lg px-3 text-sm font-bold ${view === "table" ? "bg-brand-700 text-white shadow-sm" : "text-slate-700"}`}><Table2 size={17} /> Table</button>
        </div>
      </div>

      {rows.length === 0 && <p className="py-6 text-center text-slate-500">No test results match this filter.</p>}
      {view === "cards" ? (
        <div className="grid gap-4 md:grid-cols-2">{rows.map((p) => <ResultCard key={p.id} p={p} />)}</div>
      ) : (
        <TableView rows={rows} />
      )}
    </div>
  );
}

function ResultCard({ p }) {
  const [open, setOpen] = useState(false);
  const e = p.ai_explanation || {};
  return (
    <div className={`rounded-3xl border-2 bg-white p-5 ${BORDER[p.status]}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-lg font-extrabold text-slate-900">{p.normalized_name}</p>
          {p.test_name.toLowerCase() !== p.normalized_name.toLowerCase() && <p className="text-sm text-slate-500">Written on the report as: {p.test_name}</p>}
        </div>
        <StatusBadge status={p.status} />
      </div>
      <p className="mt-2 text-3xl font-extrabold text-slate-900">{p.value} <span className="text-base font-semibold text-slate-500">{p.unit}</span></p>
      <RangeBar value={p.value} low={p.reference_low} high={p.reference_high} status={p.status} />
      <p className="mt-2 text-base text-slate-700">{sentence(p)}</p>
      <TableNote text={e.table_note} />
      <p className="mt-2 rounded-xl bg-slate-50 p-3 text-base text-slate-700"><span className="font-semibold text-slate-700">What is this test? </span>{e.simple}</p>
      <button onClick={() => setOpen(!open)} className="mt-3 inline-flex min-h-10 items-center gap-1 rounded-xl border-2 border-brand-700 bg-white px-4 text-sm font-bold text-brand-800 hover:bg-brand-50">
        {open ? <>Show less <ChevronUp size={16} /></> : <>Tell me more <ChevronDown size={16} /></>}
      </button>
      {open && (
        <div className="mt-2 space-y-2 text-sm">
          <Info title="Why this test matters" text={e.why_it_matters} />
          <Info title="What to do next" text={e.follow_up} />
          <p className="text-xs text-slate-400">This explanation is computer-generated. Your doctor makes the medical decisions.</p>
        </div>
      )}
    </div>
  );
}

function TableView({ rows }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-left text-sm">
        <thead className="border-b text-slate-500"><tr><th className="py-2">Test</th><th>Your result</th><th>Normal value</th><th>Is it normal?</th></tr></thead>
        <tbody>
          {rows.map((p) => (
            <tr key={p.id} className="border-b">
              <td className="py-3 font-semibold text-slate-900">{p.normalized_name}{p.ai_explanation?.table_note && <span className="block text-xs font-normal text-indigo-800">Note: {p.ai_explanation.table_note}</span>}</td>
              <td className="font-bold">{p.value} {p.unit}</td>
              <td>{p.reference_text ? humanRange(p.reference_text) : <span className="text-slate-400">Not printed</span>}</td>
              <td><StatusBadge status={p.status} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const Info = ({ title, text }) =>
  text ? (
    <div className="rounded-xl bg-brand-50 p-3">
      <p className="font-semibold text-brand-800">{title}</p>
      <p className="text-slate-700">{text}</p>
    </div>
  ) : null;
