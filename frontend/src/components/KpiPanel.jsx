// "Key numbers at a glance": the values a doctor (and, after review, the patient) should look at first.
// Lab report: the results outside the printed normal range, biggest difference first.
// Any other report (Holter, ECG, scan ...): the numbers the computer found in the text, such as counts and measurements.
// It only compares a number with a range that the report itself prints, and never invents one.
import { ArrowDown, ArrowUp, CheckCircle2, Gauge, Hash, TriangleAlert } from "lucide-react";
import { Section } from "./HealthCard";
import RangeBar, { humanRange } from "./RangeBar";

const num = (v) => (typeof v === "number" ? v.toLocaleString(undefined, { maximumFractionDigits: 2 }) : v);

/** How far outside the printed range, as a percentage of the limit that was crossed. */
function spreadPct(p) {
  const limit = p.status === "ABOVE_RANGE" ? p.reference_high : p.reference_low;
  if (limit === null || limit === undefined || limit === 0) return 0;
  return Math.round((Math.abs(p.value - limit) / Math.abs(limit)) * 100);
}

function Tile({ label, value, tone, sub, icon: Icon }) {
  const tones = {
    green: "bg-emerald-50 text-emerald-700", amber: "bg-amber-50 text-amber-700", sky: "bg-sky-50 text-sky-700",
    slate: "bg-slate-50 text-slate-600", rose: "bg-rose-50 text-rose-700",
  };
  return (
    <div className={`rounded-2xl p-4 ${tones[tone]}`}>
      <p className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-wide opacity-80">{Icon && <Icon size={14} />}{label}</p>
      <p className="mt-1 text-3xl font-extrabold leading-none">{value}</p>
      {sub && <p className="mt-1 text-xs opacity-80">{sub}</p>}
    </div>
  );
}

// ---------------------------------------------------------------- laboratory report
function LabKpis({ report }) {
  const params = report.parameters || [];
  const c = report.counts;
  const outside = params.filter((p) => p.status === "ABOVE_RANGE" || p.status === "BELOW_RANGE")
    .sort((a, b) => spreadPct(b) - spreadPct(a));
  return (
    <>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Tile label="Tests read" value={params.length} tone="slate" icon={Hash} />
        <Tile label="In normal range" value={c.WITHIN_RANGE} tone="green" icon={CheckCircle2} />
        <Tile label="Outside the range" value={outside.length} tone={outside.length ? "amber" : "green"} icon={TriangleAlert} sub={outside.length ? "Look at these first" : "Nothing to look at"} />
        <Tile label="No range printed" value={c.UNKNOWN} tone="slate" icon={Gauge} sub={c.UNKNOWN ? "Cannot be judged here" : undefined} />
      </div>

      {outside.length === 0 ? (
        <p className="mt-4 flex items-center gap-2 rounded-2xl bg-emerald-50 p-4 font-semibold text-emerald-800"><CheckCircle2 size={20} /> Every value that has a printed range is inside it.</p>
      ) : (
        <div className="mt-5">
          <p className="mb-3 text-sm font-bold text-slate-700">Look at these first (largest difference from the normal range at the top)</p>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {outside.slice(0, 6).map((p) => {
              const high = p.status === "ABOVE_RANGE";
              const Arrow = high ? ArrowUp : ArrowDown;
              return (
                <div key={p.id} className={`rounded-2xl border-2 bg-white p-4 ${high ? "border-amber-300" : "border-sky-300"}`}>
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-bold text-slate-800">{p.normalized_name || p.test_name}</p>
                    <span className={`inline-flex items-center gap-0.5 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-bold ${high ? "bg-amber-100 text-amber-800" : "bg-sky-100 text-sky-800"}`}>
                      <Arrow size={12} />{high ? "Higher" : "Lower"}
                    </span>
                  </div>
                  <p className="mt-1 text-3xl font-extrabold text-slate-900">{num(p.value)} <span className="text-base font-semibold text-slate-500">{p.unit}</span></p>
                  <p className="text-xs text-slate-500">Normal: {humanRange(p.reference_text)} {p.unit} {spreadPct(p) > 0 && <b className={high ? "text-amber-700" : "text-sky-700"}>({spreadPct(p)}% {high ? "above the upper" : "below the lower"} limit)</b>}</p>
                  <RangeBar value={p.value} low={p.reference_low} high={p.reference_high} status={p.status} />
                </div>
              );
            })}
          </div>
          {outside.length > 6 && <p className="mt-3 text-sm text-slate-500">{outside.length - 6} more value(s) are outside the range. They are listed under "Test results" below.</p>}
        </div>
      )}
    </>
  );
}

// ---------------------------------------------------------------- Holter, ECG, scans and other reports
function plainWords(m) {
  // a count of events (episodes, ectopics, pauses ...) in everyday words
  if (m.concern === "attention" && !m.range) return "Found in the report";
  if (m.concern === "attention") return "Outside the printed range";
  if (m.concern === "normal" && m.range) return "Inside the printed range";
  if (m.concern === "normal") return "None found";
  return "Measured value";
}

function MetricTile({ m }) {
  const style = { attention: "border-amber-300 bg-amber-50/70", normal: "border-emerald-200 bg-white", neutral: "border-slate-200 bg-white" }[m.concern];
  const chip = { attention: "bg-amber-100 text-amber-800", normal: "bg-emerald-100 text-emerald-800", neutral: "bg-slate-100 text-slate-600" }[m.concern];
  return (
    <div className={`rounded-2xl border-2 p-4 ${style}`}>
      <p className="text-sm font-semibold leading-snug text-slate-600">{m.label}</p>
      <p className="mt-1 text-3xl font-extrabold text-slate-900">{num(m.value)} {m.unit && <span className="text-base font-semibold text-slate-500">{m.unit}</span>}</p>
      {m.range && <p className="text-xs text-slate-500">Printed normal range: {m.range} {m.unit}</p>}
      <span className={`mt-2 inline-block rounded-full px-2.5 py-0.5 text-xs font-bold ${chip}`}>{plainWords(m)}</span>
    </div>
  );
}

function NarrativeKpis({ metrics }) {
  const flagged = metrics.filter((m) => m.concern === "attention");
  return (
    <>
      <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Tile label="Numbers read" value={metrics.length} tone="slate" icon={Hash} />
        <Tile label="Worth a look" value={flagged.length} tone={flagged.length ? "amber" : "green"} icon={TriangleAlert} sub={flagged.length ? "Counts above zero or outside a printed range" : "No count above zero"} />
        <Tile label="Nothing found" value={metrics.filter((m) => m.concern === "normal").length} tone="green" icon={CheckCircle2} />
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{metrics.map((m, i) => <MetricTile key={i} m={m} />)}</div>
    </>
  );
}

export default function KeyNumbers({ report }) {
  const metrics = report.insights?.metrics || [];
  const isLab = !report.is_narrative && (report.parameters?.length || 0) > 0;
  if (!isLab && metrics.length === 0) return null;
  return (
    <Section title="Key numbers at a glance">
      {isLab ? <LabKpis report={report} /> : <NarrativeKpis metrics={metrics} />}
      <p className="mt-4 text-xs text-slate-400">The computer found these numbers in the report. A number is marked only when the report prints a range for it, or when it counts events (episodes, ectopics, pauses) and the count is above zero. Please check the original report.</p>
    </Section>
  );
}
