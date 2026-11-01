// Structured lab values: value, unit, the range the hospital set, a flag in words (never colour alone) and the earlier value of the same test.
const FLAG = {
  NORMAL: "bg-emerald-100 text-emerald-900", LOW: "bg-amber-100 text-amber-900", HIGH: "bg-amber-100 text-amber-900",
  CRITICAL_LOW: "bg-red-600 text-white", CRITICAL_HIGH: "bg-red-600 text-white", UNRATED: "bg-slate-200 text-slate-700",
};
const range = (r) => (r.ref_low == null && r.ref_high == null ? "no range set" : `${r.ref_low ?? ""} - ${r.ref_high ?? ""}`);

export default function ResultTable({ results }) {
  if (!results || results.length === 0) return null;
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[34rem] text-left text-sm">
        <thead><tr className="border-b text-xs uppercase text-slate-500"><th className="py-1.5 pr-3">Test</th><th className="pr-3">Result</th><th className="pr-3">Range</th><th className="pr-3">Flag</th><th>Earlier</th></tr></thead>
        <tbody>{results.map((r) => (
          <tr key={r.id} className="border-b border-slate-100 align-top">
            <td className="py-2 pr-3 font-semibold text-slate-900">{r.name}{r.method && <span className="block text-xs font-normal text-slate-500">{r.method}</span>}</td>
            <td className="pr-3 font-bold">{r.value} <span className="font-normal text-slate-500">{r.unit}</span></td>
            <td className="pr-3 text-slate-600">{range(r)}</td>
            <td className="pr-3"><span className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${FLAG[r.flag]}`}>{r.flag_text}</span></td>
            <td className="text-slate-600">{r.previous ? <>{r.previous.value} {r.previous.unit} <span className="text-xs text-slate-500">({r.previous.date}{r.previous.change === "up" ? ", now higher" : r.previous.change === "down" ? ", now lower" : r.previous.change === "same" ? ", same" : ""})</span></> : <span className="text-slate-400">-</span>}</td>
          </tr>))}</tbody>
      </table>
    </div>
  );
}
