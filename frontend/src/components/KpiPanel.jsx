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
      <p className="flex items-center gap-1.5 text-sm font-bold opacity-90">{Icon && <Icon size={14} />}{label}</p>
      <p className="mt-1 text-3xl font-extrabold leading-none">{value}</p>
      {sub && <p className="mt-1 text-sm opacity-90">{sub}</p>}
    </div>
  );
}

// ---------------------------------------------------------------- laboratory report
const SEVERITY = {
  MARKED: ["Far outside the range", "bg-red-100 text-red-900", "border-red-300"],
  MODERATE: ["Clearly outside the range", "bg-amber-100 text-amber-900", "border-amber-300"],
  MILD: ["Slightly outside the range", "bg-sky-100 text-sky-900", "border-sky-300"],
};

/** Ranked results: the few that matter first, each with how far it is from the printed range and what the test measures. */
function RankedLabKpis({ report }) {
  const ins = report.insights;
  const params = report.parameters || [];
  const c = ins.counts;
  const slight = ins.slightly_outside || [];
  return (
    <>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Tile label="Tests read" value={params.length} tone="slate" icon={Hash} />
        <Tile label="Normal" value={c.normal} tone="green" icon={CheckCircle2} />
        <Tile label="Look at first" value={c.important} tone={c.important ? "rose" : "green"} icon={TriangleAlert} sub={c.important ? "Listed below, most important first" : "Nothing stands out"} />
        <Tile label="Slightly outside" value={c.slight} tone={c.slight ? "amber" : "green"} icon={Gauge} sub={c.no_range ? `${c.no_range} more have no printed range` : undefined} />
      </div>

      {ins.priority.length === 0 ? (
        <p className="mt-4 flex items-center gap-2 rounded-2xl bg-emerald-50 p-4 font-semibold text-emerald-800"><CheckCircle2 size={20} /> No result is far outside its printed range.</p>
      ) : (
        <div className="mt-5">
          <p className="mb-3 text-sm font-bold text-slate-700">Look at these first (most important first)</p>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {ins.priority.map((e) => {
              const p = params.find((x) => (x.normalized_name || x.test_name) === e.name);
              const high = e.direction === "HIGH";
              const Arrow = high ? ArrowUp : ArrowDown;
              const [label, chip, border] = SEVERITY[e.severity];
              return (
                <div key={e.name} className={`rounded-2xl border-2 bg-white p-4 ${border}`}>
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-bold text-slate-800">{e.name}</p>
                    <span className={`inline-flex items-center gap-0.5 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-bold ${chip}`}><Arrow size={13} />{high ? "High" : "Low"}</span>
                  </div>
                  <p className="mt-1 text-3xl font-extrabold text-slate-900">{num(e.value)} <span className="text-base font-semibold text-slate-500">{e.unit}</span></p>
                  <p className="text-sm text-slate-600">Normal: {e.range} {e.unit}</p>
                  <p className="mt-1 text-sm font-semibold text-slate-700">{label}: {e.how_far}</p>
                  {p && <RangeBar value={p.value} low={p.reference_low} high={p.reference_high} status={p.status} />}
                  {e.meaning && <p className="mt-2 text-sm text-slate-500">{e.meaning}</p>}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {slight.length > 0 && (
        <details className="mt-4 rounded-2xl bg-slate-50 p-4">
          <summary className="cursor-pointer text-sm font-bold text-slate-700">{slight.length} other result{slight.length === 1 ? " is" : "s are"} only slightly outside the range, or minor tests</summary>
          <ul className="mt-3 grid gap-x-6 gap-y-1.5 text-sm text-slate-700 sm:grid-cols-2">
            {slight.map((e) => <li key={e.name} className="flex flex-wrap justify-between gap-2 border-b border-slate-200 py-1"><b>{e.name}</b><span>{num(e.value)} {e.unit} ({e.direction === "HIGH" ? "high" : "low"}, normal {e.range}) <span className="text-slate-400">{e.how_far}</span></span></li>)}
          </ul>
        </details>
      )}
    </>
  );
}

function LabKpis({ report }) {
  if (report.insights?.priority && report.insights?.counts) return <RankedLabKpis report={report} />;
  const params = report.parameters || [];
  const c = report.counts;
  const outside = params.filter((p) => p.status === "ABOVE_RANGE" || p.status === "BELOW_RANGE")
    .sort((a, b) => spreadPct(b) - spreadPct(a));
  return (
    <>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Tile label="Tests found" value={params.length} tone="slate" icon={Hash} />
        <Tile label="Normal" value={c.WITHIN_RANGE} tone="green" icon={CheckCircle2} />
        <Tile label="Not normal" value={outside.length} tone={outside.length ? "amber" : "green"} icon={TriangleAlert} sub={outside.length ? "See the list below" : "Nothing to worry about here"} />
        <Tile label="No normal range" value={c.UNKNOWN} tone="slate" icon={Gauge} sub={c.UNKNOWN ? "The lab gave no range. Ask the doctor." : undefined} />
      </div>
    </>
  );
}

// ---------------------------------------------------------------- Holter, ECG, scans and other reports
function plainWords(m) {
  // a count of events (episodes, ectopics, pauses ...) in everyday words
  if (m.concern === "attention" && !m.range) return "Worth a look";
  if (m.concern === "attention") return "Outside the normal range";
  if (m.concern === "normal" && m.range) return "Inside the normal range";
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
      {m.range && <p className="text-xs text-slate-500">Normal range: {m.range} {m.unit}</p>}
      {m.detail && <p className="text-xs text-slate-500">{m.detail}</p>}
      <span className={`mt-2 inline-block rounded-full px-2.5 py-0.5 text-xs font-bold ${chip}`}>{plainWords(m)}</span>
    </div>
  );
}

function NarrativeKpis({ metrics }) {
  const flagged = metrics.filter((m) => m.concern === "attention");
  return (
    <>
      <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Tile label="Numbers found" value={metrics.length} tone="slate" icon={Hash} />
        <Tile label="Needs a look" value={flagged.length} tone={flagged.length ? "amber" : "green"} icon={TriangleAlert} sub={flagged.length ? "Something was found, or a value is outside its range" : "No count above zero"} />
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
    <Section title="The most important results">
      {isLab ? <LabKpis report={report} /> : <NarrativeKpis metrics={metrics} />}
      <p className="mt-4 text-xs text-slate-400">The computer copied these numbers from the report. It marks a number only when the report itself gives a normal range. Please check the original report.</p>
    </Section>
  );
}
