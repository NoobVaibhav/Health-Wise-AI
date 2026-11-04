// Small reusable UI pieces: Modal, form fields, Tabs, buttons, date helpers.
import { useEffect, useId, useRef, useState } from "react";
import { X } from "lucide-react";

export const inputClass =
  "w-full rounded-xl border border-slate-300 bg-white px-3.5 py-2.5 text-base focus:border-brand-500 focus:outline-none focus:ring-4 focus:ring-brand-100";

// A dialog. On a phone it is a bottom sheet (rises from the bottom edge, scrolls inside itself, keeps clear of the home indicator); from sm up it is centred.
// It closes with the X, Escape or a tap on the dim area, holds the page still behind it, and gives focus back to what opened it.
export function Modal({ title, onClose, children, wide }) {
  const titleId = useId();
  const sheet = useRef(null);
  const close = useRef(onClose);                       // the latest onClose, so a parent that re-renders (typing in the form) never re-runs the focus handling
  close.current = onClose;
  useEffect(() => {
    const opener = document.activeElement;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    sheet.current?.focus();
    const key = (e) => { if (e.key === "Escape") close.current(); };
    document.addEventListener("keydown", key);
    return () => { document.removeEventListener("keydown", key); document.body.style.overflow = previous; opener?.focus?.(); };
  }, []);
  return (
    <div className="fade-in fixed inset-0 z-50 flex items-end justify-center bg-slate-900/50 sm:items-start sm:overflow-y-auto sm:p-4 sm:pt-10" onClick={onClose}>
      <div ref={sheet} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1} onClick={(e) => e.stopPropagation()}
        className={`sheet-up flex max-h-[92dvh] w-full flex-col overflow-hidden rounded-t-3xl bg-white shadow-sheet focus:outline-none sm:max-h-none sm:rounded-3xl sm:shadow-2xl ${wide ? "sm:max-w-3xl" : "sm:max-w-lg"}`}>
        <div className="mx-auto mt-2 h-1.5 w-10 shrink-0 rounded-full bg-slate-300 sm:hidden" aria-hidden="true" />
        <div className="flex shrink-0 items-center justify-between gap-3 px-5 pb-3 pt-3 sm:px-6 sm:pt-6">
          <h3 id={titleId} className="min-w-0 break-words text-xl font-bold text-slate-900">{title}</h3>
          <button type="button" onClick={onClose} className="grid h-11 w-11 shrink-0 place-items-center rounded-xl text-slate-600 hover:bg-slate-100" aria-label="Close"><X size={20} aria-hidden="true" /></button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-5 pb-[max(1.25rem,var(--safe-bottom))] sm:px-6 sm:pb-6">{children}</div>
      </div>
    </div>
  );
}

// A labelled field. `error` shows a readable message under the field (announced to screen readers); the input itself carries aria-invalid.
export function Field({ label, hint, error, children }) {
  return (
    <label className="block text-sm font-semibold text-slate-700">
      {label}
      <div className="mt-1.5">{children}</div>
      {error && <span role="alert" className="mt-1 block text-sm font-semibold text-red-700">{error}</span>}
      {hint && !error && <span className="mt-1 block text-xs font-normal text-slate-600">{hint}</span>}
    </label>
  );
}

const withBase = (className) => (className ? `${inputClass} ${className}` : inputClass);       // a className passed in is added to the base look, not instead of it
export const Input = ({ className, ...props }) => <input className={`${withBase(className)} aria-[invalid=true]:border-red-500 aria-[invalid=true]:ring-4 aria-[invalid=true]:ring-red-100`} {...props} />;
export const Textarea = ({ className, ...props }) => <textarea className={`${withBase(className)} aria-[invalid=true]:border-red-500 aria-[invalid=true]:ring-4 aria-[invalid=true]:ring-red-100`} rows={3} {...props} />;
export const Select = ({ children, className, ...props }) => <select className={`${withBase(className)} aria-[invalid=true]:border-red-500`} {...props}>{children}</select>;

export function Button({ variant = "primary", className = "", ...props }) {
  const styles = {
    primary: "border-2 border-brand-800 bg-brand-700 text-white shadow-md hover:bg-brand-800",
    secondary: "border-2 border-brand-700 bg-white text-brand-800 shadow-sm hover:bg-brand-50",
    danger: "border-2 border-red-800 bg-red-600 text-white shadow-md hover:bg-red-700",
    soft: "border-2 border-brand-300 bg-brand-100 text-brand-900 hover:bg-brand-200",
  };
  return <button className={`inline-flex min-h-11 items-center justify-center gap-1.5 rounded-xl px-5 py-2.5 text-base font-bold transition focus:outline-none focus-visible:ring-4 focus-visible:ring-brand-200 disabled:cursor-not-allowed disabled:opacity-50 ${styles[variant]} ${className}`} {...props} />;
}

export function Tabs({ tabs, initial, value, onChange }) {
  const [inner, setInner] = useState(initial || tabs[0][0]);
  const active = value ?? inner;
  const setActive = (key) => { setInner(key); onChange?.(key); };
  const current = tabs.find(([key]) => key === active) || tabs[0];
  return (
    <div>
      <div className="mb-4 flex flex-wrap gap-2 rounded-2xl bg-slate-200 p-1.5">
        {tabs.map(([key, label]) => (
          <button key={key} onClick={() => setActive(key)}
            className={`min-h-11 rounded-xl px-4 py-2 text-base font-bold transition ${active === key ? "bg-brand-700 text-white shadow" : "text-slate-700 hover:bg-white"}`}>
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
