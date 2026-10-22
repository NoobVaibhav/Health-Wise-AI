// One statement of the clinical summary: its text, HOW it is known (label), WHERE it comes from (source chips that open the
// original record), and the doctor's own reviews, shown apart from the computer's words.
import { useState } from "react";
import { BadgeCheck, FileText, MessageSquarePlus } from "lucide-react";
import { Button, Textarea, fmtUtc } from "../ui";
import { reviewSummaryItem } from "../../services/clinicalApi";
import { getErrorMessage } from "../../services/api";
import { useToast } from "../Toast";

export const LABEL_STYLE = {
  DIRECTLY_DOCUMENTED: "bg-emerald-100 text-emerald-800", CALCULATED: "bg-sky-100 text-sky-800", AI_GENERATED: "bg-violet-100 text-violet-800",
  REQUIRES_CLINICIAN_VERIFICATION: "bg-amber-100 text-amber-900", INSUFFICIENT_INFORMATION: "bg-slate-200 text-slate-700",
};
const ACTIONS = { INTERPRETATION: "Add my interpretation", CORRECTION: "Correct an extraction error", MISSING_FLAG: "Flag missing information" };
const ACTION_WORD = { REVIEWED: "Reviewed", INTERPRETATION: "Interpretation", CORRECTION: "Correction", MISSING_FLAG: "Missing information flagged" };

export const LabelChip = ({ label, labels }) => <span className={`inline-block whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-bold ${LABEL_STYLE[label] || LABEL_STYLE.INSUFFICIENT_INFORMATION}`}>{labels?.[label] || label}</span>;

export const SourceChip = ({ source, onOpen }) => (
  <button type="button" onClick={() => onOpen?.(source)} className="inline-flex items-center gap-1 rounded-full border border-slate-300 bg-white px-2.5 py-0.5 text-xs font-semibold text-slate-600 hover:border-brand-500 hover:text-brand-800" title="Open the original record">
    <FileText size={12} />{source.label}{source.date ? ` (${source.date})` : ""}
  </button>
);

export default function Statement({ st, labels, patientId, onOpen, onChanged, tone }) {
  const toast = useToast();
  const [adding, setAdding] = useState(null);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);

  const send = async (action, body) => {
    setBusy(true);
    try { await reviewSummaryItem(patientId, { item_key: st.key, action, text: body || null }); toast(action === "REVIEWED" ? "Marked as reviewed" : "Saved"); setAdding(null); setText(""); onChanged?.(); }
    catch (e) { toast(getErrorMessage(e), "error"); } finally { setBusy(false); }
  };
  const reviewed = st.reviews?.some((r) => r.action === "REVIEWED");
  const box = tone === "red" ? "border-red-200 bg-red-50/60" : "border-slate-200 bg-white";

  return (
    <li className={`rounded-2xl border p-3.5 ${box}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="min-w-0 flex-1 text-[15px] leading-snug text-slate-800">{st.headline && <b className="mr-1">{st.headline}.</b>}{st.text}</p>
        <LabelChip label={st.label} labels={labels} />
      </div>
      {st.warnings?.length > 0 && <ul className="mt-1.5 space-y-0.5 text-xs text-amber-800">{st.warnings.map((w) => <li key={w}>Note: {w}</li>)}</ul>}
      {st.sources?.length > 0 && <div className="mt-2 flex flex-wrap gap-1.5">{st.sources.map((s) => <SourceChip key={`${s.type}${s.id}${s.date}`} source={s} onOpen={onOpen} />)}</div>}
      {st.reviews?.map((r) => (
        <p key={r.id} className="mt-2 rounded-xl border-l-4 border-brand-600 bg-brand-50 px-3 py-1.5 text-sm text-slate-800">
          <b className="text-brand-800">{ACTION_WORD[r.action]}</b> by {r.doctor}, {fmtUtc(r.at)}{r.text ? <>: {r.text}</> : null}
        </p>
      ))}
      {patientId && (
        <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs print:hidden">
          {!reviewed && <button type="button" disabled={busy} onClick={() => send("REVIEWED")} className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2.5 py-1 font-bold text-emerald-800 hover:bg-emerald-100"><BadgeCheck size={13} />Mark reviewed</button>}
          {Object.entries(ACTIONS).map(([k, label]) => <button key={k} type="button" onClick={() => setAdding(adding === k ? null : k)} className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 font-bold text-slate-600 hover:bg-slate-200"><MessageSquarePlus size={13} />{label}</button>)}
        </div>
      )}
      {adding && (
        <div className="mt-2 space-y-2 print:hidden">
          <Textarea rows={2} autoFocus value={text} placeholder="Your words. The original record and the computer's statement stay unchanged." onChange={(e) => setText(e.target.value)} />
          <div className="flex gap-2"><Button disabled={busy || !text.trim()} onClick={() => send(adding, text)}>Save</Button><Button variant="secondary" onClick={() => setAdding(null)}>Cancel</Button></div>
        </div>
      )}
    </li>
  );
}
