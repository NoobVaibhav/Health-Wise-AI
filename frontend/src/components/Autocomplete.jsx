// A text box with a pick-list under it. The doctor types a few letters, the matching names appear, and one click (or
// Enter) fills the box. Anything typed that is not in the list is still accepted, so the list is a shortcut only.
import { useEffect, useMemo, useRef, useState } from "react";
import { inputClass } from "./ui";

/** options: array of strings or { name, hint }. onChange receives the text. */
export default function Autocomplete({ value, onChange, options = [], placeholder, required, maxShown = 8, id, onPick, onEnter }) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const box = useRef(null);

  const items = useMemo(() => options.map((o) => (typeof o === "string" ? { name: o } : o)), [options]);
  const matches = useMemo(() => {
    const words = value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    const found = items.filter((o) => words.every((w) => o.name.toLowerCase().includes(w)));
    // names that START with what was typed come first
    const first = value.trim().toLowerCase();
    found.sort((a, b) => Number(!a.name.toLowerCase().startsWith(first)) - Number(!b.name.toLowerCase().startsWith(first)));
    return found.slice(0, maxShown);
  }, [items, value, maxShown]);

  useEffect(() => setActive(0), [value]);
  useEffect(() => {
    const close = (e) => { if (box.current && !box.current.contains(e.target)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const pick = (name) => { (onPick || onChange)(name); setOpen(false); };
  const onKeyDown = (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setOpen(true); setActive((a) => Math.min(a + 1, matches.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
    else if (e.key === "Enter" && open && matches[active]) { e.preventDefault(); pick(matches[active].name); }
    else if (e.key === "Enter" && onEnter) { e.preventDefault(); onEnter(); }
    else if (e.key === "Escape") setOpen(false);
  };

  return (
    <div ref={box} className="relative">
      <input id={id} className={inputClass} value={value} required={required} placeholder={placeholder} autoComplete="off"
        role="combobox" aria-expanded={open} aria-autocomplete="list"
        onChange={(e) => { onChange(e.target.value); setOpen(true); }} onFocus={() => setOpen(true)} onKeyDown={onKeyDown} />
      {open && matches.length > 0 && (
        <ul role="listbox" className="absolute z-30 mt-1 max-h-64 w-full overflow-y-auto rounded-xl border-2 border-brand-700 bg-white shadow-xl">
          {matches.map((o, i) => (
            <li key={o.name} role="option" aria-selected={i === active}
              onMouseDown={(e) => { e.preventDefault(); pick(o.name); }} onMouseEnter={() => setActive(i)}
              className={`flex cursor-pointer items-center justify-between gap-2 px-3.5 py-2.5 text-base ${i === active ? "bg-brand-100 text-brand-900" : "text-slate-800"}`}>
              <span>{o.name}</span>
              {o.hint && <span className="shrink-0 rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-bold text-emerald-800">{o.hint}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
