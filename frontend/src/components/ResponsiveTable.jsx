import { Fragment, useState } from "react";
import { ChevronDown, Inbox } from "lucide-react";
import useLayoutMode from "../hooks/useLayoutMode";

// One table for every staff screen. It adapts to the width it has, not to the device:
//   phone            each row is a card (label: value pairs)
//   tablet portrait  the columns of priority 1 and 2 are shown; the rest open under the row ("Details")
//   tablet landscape and desktop: every column, with a sticky header
// columns: [{ key, label, priority (1 always, 2 from tablet, 3 from landscape), render?(row), numeric?, className? }]
export default function ResponsiveTable({ columns, rows, rowKey = (r) => r.id, loading = false, empty = "Nothing to show.", caption, pageSize = 25, onRowClick, renderCard, maxHeight = "70dvh" }) {
  const { mode } = useLayoutMode();
  const [open, setOpen] = useState(() => new Set());
  const [shown, setShown] = useState(pageSize);
  const value = (c, row) => (c.render ? c.render(row) : row[c.key] ?? "-");
  const toggle = (k) => setOpen((s) => { const n = new Set(s); n.has(k) ? n.delete(k) : n.add(k); return n; });

  if (loading) {
    return (
      <div role="status" aria-live="polite" className="space-y-2">
        <span className="sr-only">Loading...</span>
        {[0, 1, 2, 3].map((i) => <div key={i} className="skeleton h-12 w-full" aria-hidden="true" />)}
      </div>
    );
  }
  if (!rows.length) {
    return (
      <div className="rounded-2xl border-2 border-dashed border-slate-200 bg-white/70 p-8 text-center text-slate-600">
        <Inbox className="mx-auto mb-2 text-brand-600" size={26} aria-hidden="true" />
        <p>{empty}</p>
      </div>
    );
  }
  const visible = rows.slice(0, shown);
  const more = rows.length > shown && (
    <div className="pt-3 text-center">
      <button type="button" onClick={() => setShown((n) => n + pageSize)} className="min-h-11 rounded-xl border-2 border-brand-700 bg-white px-5 font-bold text-brand-800">Show more ({rows.length - shown} left)</button>
    </div>
  );

  if (mode === "phone") {
    return (
      <div>
        <ul className="space-y-2" aria-label={caption}>
          {visible.map((row) => (
            <li key={rowKey(row)} data-row className="rounded-2xl border border-slate-200 bg-white p-3 shadow-card">
              {renderCard ? renderCard(row) : (
                <dl className="space-y-1.5">
                  {columns.map((c) => (
                    <div key={c.key} className="flex items-baseline justify-between gap-3">
                      <dt className="shrink-0 text-sm font-semibold text-slate-600">{c.label}</dt>
                      <dd className={`min-w-0 break-words text-right ${c.numeric ? "num" : ""}`}>{value(c, row)}</dd>
                    </div>
                  ))}
                </dl>
              )}
              {onRowClick && <button type="button" onClick={() => onRowClick(row)} className="mt-2 min-h-11 w-full rounded-xl bg-brand-50 font-bold text-brand-800">Open</button>}
            </li>
          ))}
        </ul>
        {more}
      </div>
    );
  }

  const maxPriority = mode === "tabletPortrait" ? 2 : 3;
  const shownCols = columns.filter((c) => (c.priority ?? 1) <= maxPriority);
  const hiddenCols = columns.filter((c) => (c.priority ?? 1) > maxPriority);
  const span = shownCols.length + (hiddenCols.length ? 1 : 0);
  return (
    <div>
      <div className="overflow-auto overscroll-contain rounded-2xl border border-slate-200 bg-white" style={{ maxHeight }}>
        <table className="w-full border-collapse text-left text-sm">
          {caption && <caption className="sr-only">{caption}</caption>}
          <thead>
            <tr>
              {shownCols.map((c) => <th key={c.key} scope="col" className={`sticky top-0 z-10 whitespace-nowrap border-b border-slate-200 bg-slate-50 px-3 py-2.5 font-bold text-slate-700 ${c.numeric ? "text-right" : ""}`}>{c.label}</th>)}
              {hiddenCols.length > 0 && <th scope="col" className="sticky top-0 z-10 w-12 border-b border-slate-200 bg-slate-50 px-3 py-2.5"><span className="sr-only">Details</span></th>}
            </tr>
          </thead>
          <tbody>
            {visible.map((row) => {
              const k = rowKey(row);
              const expanded = open.has(k);
              return (
                <Fragment key={k}>
                  <tr data-row className={`border-b border-slate-100 ${onRowClick ? "cursor-pointer hover:bg-brand-50" : ""}`} onClick={onRowClick ? () => onRowClick(row) : undefined}>
                    {shownCols.map((c) => <td key={c.key} className={`px-3 py-2.5 align-top ${c.numeric ? "num text-right" : ""} ${c.className || ""}`}>{value(c, row)}</td>)}
                    {hiddenCols.length > 0 && (
                      <td className="px-1 py-1 text-right">
                        <button type="button" onClick={(e) => { e.stopPropagation(); toggle(k); }} aria-expanded={expanded} aria-label={expanded ? "Hide details" : "Show details"} className="grid h-11 w-11 place-items-center rounded-xl text-slate-600 hover:bg-slate-100">
                          <ChevronDown size={18} aria-hidden="true" className={`transition-transform ${expanded ? "rotate-180" : ""}`} />
                        </button>
                      </td>
                    )}
                  </tr>
                  {expanded && hiddenCols.length > 0 && (
                    <tr data-details className="border-b border-slate-100 bg-slate-50/70">
                      <td colSpan={span} className="px-3 py-2.5">
                        <dl className="grid gap-x-6 gap-y-1.5 sm:grid-cols-2">
                          {hiddenCols.map((c) => <div key={c.key} className="flex gap-2"><dt className="font-semibold text-slate-600">{c.label}:</dt><dd className={`min-w-0 break-words ${c.numeric ? "num" : ""}`}>{value(c, row)}</dd></div>)}
                        </dl>
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
      {more}
    </div>
  );
}
