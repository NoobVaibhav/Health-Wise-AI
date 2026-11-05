import { Minus, Plus } from "lucide-react";

// A number with big minus and plus buttons (for a quantity at the counter or a vital at the bedside). The number can still be typed.
export default function Stepper({ value, onChange, min = 0, max = 9999, step = 1, label, disabled = false }) {
  const n = Number(value);
  const set = (v) => onChange(String(Math.min(max, Math.max(min, Number.isFinite(v) ? v : min))));
  return (
    <div className="inline-flex items-stretch rounded-xl border-2 border-slate-300 bg-white" role="group" aria-label={label}>
      <button type="button" disabled={disabled || n <= min} onClick={() => set((Number.isFinite(n) ? n : min) - step)} aria-label={`Less: ${label}`} className="grid h-12 w-12 place-items-center rounded-l-lg text-slate-700 hover:bg-slate-100 disabled:opacity-40"><Minus size={20} aria-hidden="true" /></button>
      <input type="text" inputMode="numeric" enterKeyHint="done" aria-label={label} disabled={disabled} value={value} onChange={(e) => onChange(e.target.value.replace(/[^0-9.]/g, ""))} onBlur={() => set(n)}
        className="num h-12 w-16 border-x-2 border-slate-200 bg-white text-center text-lg font-bold focus:outline-none focus-visible:bg-brand-50" />
      <button type="button" disabled={disabled || n >= max} onClick={() => set((Number.isFinite(n) ? n : min) + step)} aria-label={`More: ${label}`} className="grid h-12 w-12 place-items-center rounded-r-lg text-slate-700 hover:bg-slate-100 disabled:opacity-40"><Plus size={20} aria-hidden="true" /></button>
    </div>
  );
}
