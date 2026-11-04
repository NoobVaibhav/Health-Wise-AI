// What the computer did NOT analyse, and the results it shows exactly as printed.
//  - CoverageNote: a warning under the summary whenever any printed row or section was left out. Never shown as "complete" unless it really is.
//  - OtherResults: rows of sections that are not blood panels (Widal, semen examination, Mantoux ...). Printed values only: no Normal/High/Low verdict.
//  - TableNotes: what the report's own interpretation table says. It is a separate note and never changes the status of a result.
import { Info, ScanSearch } from "lucide-react";
import { Section } from "./HealthCard";

/** Groups the printed rows by the test they belong to ("Widal Test", "Semen Examination") so they read like the original report. */
export function groupOtherResults(rows = []) {
  const groups = [];
  for (const r of rows) {
    const key = `${r.section}|${r.title}`;
    let g = groups.find((x) => x.key === key);
    if (!g) { g = { key, title: r.title || r.section, rows: [] }; groups.push(g); }
    g.rows.push(r);
  }
  return groups;
}

export function CoverageNote({ report }) {
  const c = report.insights?.coverage;
  if (!c || c.complete) return null;
  return (
    <div role="status" className="rounded-2xl border border-amber-300 bg-amber-50 p-4 text-amber-900">
      <p className="flex items-center gap-2 font-bold"><ScanSearch size={18} /> {c.headline || "Not the whole report was analysed"}</p>
      <p className="mt-1 text-sm">{c.message}</p>
      {c.unread_rows?.length > 0 && (
        <ul className="mt-2 list-disc pl-5 text-sm">{c.unread_rows.map((r, i) => <li key={i}>Could not be read: {r.text}</li>)}</ul>
      )}
    </div>
  );
}

export function OtherResults({ report }) {
  const groups = groupOtherResults(report.insights?.other_results);
  if (!groups.length) return null;
  return (
    <Section title="Other results (shown as printed)">
      <p className="mb-3 text-sm text-slate-600">
        These results are not part of a blood panel. They are copied from the report exactly as printed. The computer does not say whether they are normal or abnormal;
        only a doctor can read them.
      </p>
      <div className="space-y-4">
        {groups.map((g) => (
          <div key={g.key} className="overflow-x-auto rounded-2xl border border-slate-200">
            <p className="bg-slate-50 px-4 py-2 font-bold text-slate-800">{g.title}</p>
            <table className="w-full min-w-[480px] text-left text-sm">
              <thead className="border-b text-slate-500"><tr><th className="px-4 py-2">Test</th><th>Printed result</th><th>Unit</th><th>Printed range</th></tr></thead>
              <tbody>
                {g.rows.map((r, i) => (
                  <tr key={i} className="border-b last:border-0">
                    <td className="px-4 py-2 font-semibold text-slate-900">{r.name}{r.subgroup && <span className="block text-xs font-normal text-slate-500">{r.subgroup}</span>}</td>
                    <td className="font-bold">{r.value}{r.printed_flag && <span className="ml-2 rounded bg-slate-100 px-1.5 py-0.5 text-xs font-bold text-slate-700" title="Flag printed by the laboratory">{r.printed_flag}</span>}</td>
                    <td>{r.unit || ""}</td>
                    <td>{r.reference || <span className="text-slate-400">not printed</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </div>
    </Section>
  );
}

/** One line under a result: what the report's own interpretation table says (separate from the status). */
export function TableNote({ text }) {
  if (!text) return null;
  return <p className="mt-2 flex gap-2 rounded-xl bg-indigo-50 p-3 text-sm text-indigo-900"><Info size={16} className="mt-0.5 shrink-0" /><span><b>Note from the report's table: </b>{text}</span></p>;
}
