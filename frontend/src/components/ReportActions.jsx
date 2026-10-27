// The buttons at the top of a report page, and the "at a glance" strip under its title.
import { useEffect, useRef, useState } from "react";
import { flushSync } from "react-dom";
import { Check, ChevronDown, Copy, Download, FileText, ListChecks } from "lucide-react";
import { Button } from "./ui";
import { printAs } from "../utils/printTitle";

/** One button, two kinds of PDF: the full analysis, or one page with only what matters. `setMode` tells the print sheet which one to draw. */
export function DownloadMenu({ report, setMode }) {
  const [open, setOpen] = useState(false);
  const box = useRef(null);
  useEffect(() => {
    const away = (e) => { if (box.current && !box.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, []);
  const go = (mode) => {
    setOpen(false);
    flushSync(() => setMode(mode));                                      // the sheet must show the chosen version before the print window opens
    printAs(report.patient_name, report.report_type_label, mode === "short" ? "Summary" : "Analysis");
  };
  return (
    <div className="relative" ref={box}>
      <Button onClick={() => setOpen(!open)} aria-haspopup="menu" aria-expanded={open}><Download size={18} /> Download PDF <ChevronDown size={16} /></Button>
      {open && (
        <div role="menu" className="absolute right-0 z-20 mt-2 w-72 rounded-2xl border border-slate-200 bg-white p-1.5 shadow-xl">
          <button role="menuitem" onClick={() => go("short")} className="flex w-full items-start gap-3 rounded-xl p-3 text-left hover:bg-slate-50">
            <ListChecks size={20} className="mt-0.5 shrink-0 text-brand-700" />
            <span><b className="block text-slate-900">One-page summary</b><span className="text-sm text-slate-500">Only what to look at first. Easy to show or send.</span></span>
          </button>
          <button role="menuitem" onClick={() => go("full")} className="flex w-full items-start gap-3 rounded-xl p-3 text-left hover:bg-slate-50">
            <FileText size={20} className="mt-0.5 shrink-0 text-brand-700" />
            <span><b className="block text-slate-900">Full analysis</b><span className="text-sm text-slate-500">Every result, the numbers and the tips.</span></span>
          </button>
        </div>
      )}
    </div>
  );
}

export function CopySummary({ text }) {
  const [done, setDone] = useState(false);
  if (!text) return null;
  const copy = async () => {
    try { await navigator.clipboard.writeText(text); setDone(true); setTimeout(() => setDone(false), 2000); } catch { /* the text can still be selected by hand */ }
  };
  return <Button variant="secondary" onClick={copy}>{done ? <><Check size={18} className="text-emerald-600" /> Copied</> : <><Copy size={18} /> Copy summary</>}</Button>;
}

/** What matters most, in one line under the title, with a link down to the details. Built only from what the report already holds. */
export function AtAGlance({ report }) {
  if (!report.analysis_visible) return null;
  const ins = report.insights || {};
  const c = ins.counts;
  let tone, head, detail;
  if (c) {
    const names = (ins.priority || []).slice(0, 3).map((e) => e.name).join(", ");
    if (c.important) { tone = "border-amber-300 bg-amber-50 text-amber-900"; head = `${c.important} result${c.important === 1 ? "" : "s"} to look at first`; detail = `${names}${c.important > 3 ? " and more" : ""}. ${c.slight ? `${c.slight} slightly outside, ` : ""}${c.normal} normal.`; }
    else { tone = "border-emerald-300 bg-emerald-50 text-emerald-900"; head = "No result is far outside its range"; detail = `${c.normal} normal${c.slight ? `, ${c.slight} slightly outside` : ""}.`; }
  } else if (ins.metrics?.length || ins.key_findings?.length) {
    const look = [...(ins.metrics || []), ...(ins.key_findings || [])].filter((x) => x.concern === "attention");
    if (look.length) { tone = "border-amber-300 bg-amber-50 text-amber-900"; head = `${look.length} point${look.length === 1 ? "" : "s"} worth a look`; detail = look.slice(0, 3).map((x) => x.label || x.text).join("; ").slice(0, 160); }
    else { tone = "border-emerald-300 bg-emerald-50 text-emerald-900"; head = "Nothing in the report was marked as worth a look"; detail = "Please still read the full report."; }
  } else return null;
  const jump = () => document.getElementById("report-results")?.scrollIntoView({ behavior: "smooth", block: "start" });
  return (
    <div className={`flex flex-wrap items-center justify-between gap-2 rounded-2xl border px-4 py-3 ${tone}`}>
      <p><b>{head}.</b> <span className="text-sm">{detail}</span></p>
      <button onClick={jump} className="text-sm font-bold underline">See details</button>
    </div>
  );
}
