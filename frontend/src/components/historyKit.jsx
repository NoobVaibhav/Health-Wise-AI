// Small building blocks for the doctor's fast history form: tap-to-pick chips, Yes/No buttons, a section card.
import { CheckCircle2 } from "lucide-react";

export const Chips = ({ items, selected = [], onToggle, tone = "brand", disabled }) => (
  <div className="flex flex-wrap gap-2">
    {items.map((item) => {
      const on = selected.includes(item);
      const colours = on ? (tone === "red" ? "border-red-400 bg-red-50 text-red-800" : "border-brand-600 bg-brand-50 text-brand-900") : "border-slate-300 bg-white text-slate-600 hover:border-brand-400 hover:bg-brand-50/40";
      return (
        <button key={item} type="button" disabled={disabled} onClick={() => onToggle(item)} className={`rounded-full border px-3.5 py-1.5 text-sm font-semibold transition ${colours}`}>{on ? "✓ " : ""}{item}</button>
      );
    })}
  </div>
);

/** Two big buttons, no typing: value is "yes", "no" or undefined. */
export const YesNo = ({ label, value, onChange, yes = "Yes", no = "No" }) => (
  <div className="flex items-center justify-between gap-3 rounded-2xl bg-slate-50 px-3 py-2">
    <span className="text-sm font-semibold text-slate-700">{label}</span>
    <span className="flex gap-1.5">
      <button type="button" onClick={() => onChange(value === "yes" ? undefined : "yes")} className={`min-w-14 rounded-xl px-3 py-1.5 text-sm font-bold ${value === "yes" ? "bg-amber-500 text-white" : "bg-white text-slate-500 ring-1 ring-slate-200"}`}>{yes}</button>
      <button type="button" onClick={() => onChange(value === "no" ? undefined : "no")} className={`min-w-14 rounded-xl px-3 py-1.5 text-sm font-bold ${value === "no" ? "bg-emerald-600 text-white" : "bg-white text-slate-500 ring-1 ring-slate-200"}`}>{no}</button>
    </span>
  </div>
);

export const Block = ({ title, hint, done, children, right }) => (
  <section className="rounded-3xl border border-slate-200/70 bg-white p-5 shadow-sm">
    <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
      <div>
        <h2 className="flex items-center gap-2 text-lg font-extrabold text-slate-900">{done && <CheckCircle2 size={18} className="text-emerald-600" />}{title}</h2>
        {hint && <p className="text-sm text-slate-500">{hint}</p>}
      </div>
      {right}
    </div>
    {children}
  </section>
);

export const NoneCheck = ({ checked, disabled, onChange, children }) => (
  <label className={`mt-3 flex items-center gap-2 text-sm font-semibold ${disabled ? "text-slate-300" : "text-slate-700"}`}>
    <input type="checkbox" className="h-4 w-4" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} /> {children}
  </label>
);

/** Add a phrase to a text box without retyping: appends with a separator. */
export const addPhrase = (text, phrase, sep = "; ") => {
  const current = (text || "").trim();
  if (!current) return phrase;
  if (current.toLowerCase().includes(phrase.toLowerCase())) return text;
  return `${current}${current.endsWith(".") || current.endsWith(";") ? " " : sep}${phrase}`;
};
