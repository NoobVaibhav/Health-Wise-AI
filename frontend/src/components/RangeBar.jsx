// A simple gauge: the green zone is the normal range printed on the lab report, the dot is the patient's result.
// It works for ranges like "4.0 - 5.6", "< 100" and "> 40". With no range, nothing is drawn (we never invent one).
// "4.0 - 5.6" -> "4.0 to 5.6", "< 200" -> "below 200", "> 40" -> "above 40"
export function humanRange(text) {
  if (!text) return text;
  return text.replace(/^\s*<\s*/, "below ").replace(/^\s*>\s*/, "above ").replace(/\s*-\s*/, " to ");
}

const COLORS = { WITHIN_RANGE: "#059669", ABOVE_RANGE: "#d97706", BELOW_RANGE: "#2563eb", UNKNOWN: "#64748b" };

export default function RangeBar({ value, low, high, status }) {
  const hasLow = low !== null && low !== undefined;
  const hasHigh = high !== null && high !== undefined;
  if (!hasLow && !hasHigh) return <p className="text-xs text-slate-400">No normal range was printed for this test.</p>;

  // Choose the visible scale so that both the normal range and the value fit with some margin.
  let min, max;
  if (hasLow && hasHigh) {
    const pad = (high - low) * 0.6 || 1;
    min = Math.min(low - pad, value - pad / 2);
    max = Math.max(high + pad, value + pad / 2);
  } else if (hasHigh) {
    min = Math.min(value, high) - Math.abs(high) * 0.5;
    max = Math.max(value, high) + Math.abs(high) * 0.3;
  } else {
    min = Math.min(value, low) - Math.abs(low) * 0.3;
    max = Math.max(value, low) + Math.abs(low) * 0.5;
  }
  const pct = (v) => Math.max(0, Math.min(100, ((v - min) / (max - min)) * 100));
  const zoneStart = hasLow ? pct(low) : 0;
  const zoneEnd = hasHigh ? pct(high) : 100;

  return (
    <div className="pt-4">
      <div className="relative h-3 rounded-full bg-slate-200">
        <div className="absolute inset-y-0 rounded-full bg-emerald-300/80" style={{ left: `${zoneStart}%`, width: `${zoneEnd - zoneStart}%` }} />
        <div className="absolute top-1/2 h-5 w-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-[3px] border-white shadow-md"
          style={{ left: `${pct(value)}%`, background: COLORS[status] || COLORS.UNKNOWN }} title={`Result: ${value}`} />
      </div>
      <div className="relative mt-1 h-4 text-[11px] text-slate-500">
        {hasLow && <span className="absolute -translate-x-1/2" style={{ left: `${zoneStart}%` }}>{low}</span>}
        {hasHigh && <span className="absolute -translate-x-1/2" style={{ left: `${zoneEnd}%` }}>{high}</span>}
      </div>
    </div>
  );
}
