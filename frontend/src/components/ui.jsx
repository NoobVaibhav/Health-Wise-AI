// Small reusable UI pieces: Modal, form fields, Tabs, buttons, date helpers.
import { useState } from "react";
import { X } from "lucide-react";

export const inputClass =
  "w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-[15px] focus:border-brand-500 focus:outline-none focus:ring-4 focus:ring-brand-100";

export function Modal({ title, onClose, children, wide }) {
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-slate-900/50 p-4 pt-10 backdrop-blur-sm" onClick={onClose}>
      <div className={`page-enter w-full rounded-3xl bg-white p-6 shadow-2xl ${wide ? "max-w-3xl" : "max-w-lg"}`} onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-xl font-bold text-slate-900">{title}</h3>
          <button onClick={onClose} className="rounded-xl p-1.5 text-slate-400 hover:bg-slate-100" aria-label="Close"><X size={20} /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Field({ label, hint, children }) {
  return (
    <label className="block text-sm font-semibold text-slate-700">
      {label}
      <div className="mt-1.5">{children}</div>
      {hint && <span className="mt-1 block text-xs font-normal text-slate-500">{hint}</span>}
    </label>
  );
}

export const Input = (props) => <input className={inputClass} {...props} />;
export const Textarea = (props) => <textarea className={inputClass} rows={3} {...props} />;
export const Select = ({ children, ...props }) => <select className={inputClass} {...props}>{children}</select>;

export function Button({ variant = "primary", className = "", ...props }) {
  const styles = {
    primary: "bg-gradient-to-r from-brand-600 to-brand-700 text-white shadow-sm hover:from-brand-700 hover:to-brand-800",
    secondary: "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50",
    danger: "bg-red-600 text-white hover:bg-red-700",
    soft: "bg-brand-50 text-brand-700 hover:bg-brand-100",
  };
  return <button className={`rounded-xl px-4 py-2.5 text-sm font-bold transition disabled:cursor-not-allowed disabled:opacity-50 ${styles[variant]} ${className}`} {...props} />;
}

export function Tabs({ tabs, initial }) {
  const [active, setActive] = useState(initial || tabs[0][0]);
  const current = tabs.find(([key]) => key === active) || tabs[0];
  return (
    <div>
      <div className="mb-4 flex flex-wrap gap-2 rounded-2xl bg-slate-100 p-1.5">
        {tabs.map(([key, label]) => (
          <button key={key} onClick={() => setActive(key)}
            className={`rounded-xl px-4 py-2 text-sm font-semibold transition ${active === key ? "bg-white text-brand-700 shadow-sm" : "text-slate-500 hover:text-slate-800"}`}>
            {label}
          </button>
        ))}
      </div>
      {current[2]}
    </div>
  );
}

// ---- dates. The server stores created/uploaded/reviewed times in UTC ("fmtUtc*"), but appointment times are
// exactly what the user typed ("fmtDateTime"), so they must not be shifted.
const asUtc = (iso) => (iso && !/[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso + "Z" : iso);
const DATE = { day: "numeric", month: "short", year: "numeric" };
const DATETIME = { ...DATE, hour: "numeric", minute: "2-digit" };

export const fmtDate = (iso) => (iso ? new Date(iso).toLocaleDateString(undefined, DATE) : "-");
export const fmtDateTime = (iso) => (iso ? new Date(iso).toLocaleString(undefined, DATETIME) : "-");
export const fmtUtc = (iso) => (iso ? new Date(asUtc(iso)).toLocaleString(undefined, DATETIME) : "-");
export const fmtUtcDate = (iso) => (iso ? new Date(asUtc(iso)).toLocaleDateString(undefined, DATE) : "-");

export const greeting = () => {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
};
