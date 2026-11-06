// The demo accounts of the sample hospital as a DROPDOWN list under the "Demo accounts" button (not a pop-up): a search box and every account, grouped by role.
// Shown only while running `npm run dev`. Click an account to fill the e-mail, the password and the mobile number. Keyboard: Enter or Space opens the list,
// the search box gets the focus, Escape or a click outside closes it and the focus returns to the button.
import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronDown, Search } from "lucide-react";
import { ALL_DEMO, DEMO_GROUPS } from "./demoAccounts";

const GROUP_TONE = ["from-cyan-500 to-sky-600", "from-amber-500 to-orange-500", "from-violet-500 to-fuchsia-500", "from-emerald-500 to-teal-600", "from-slate-600 to-slate-800", "from-rose-500 to-pink-600", "from-indigo-500 to-blue-600"];

export default function DemoDropdown({ open, onToggle, onClose, picked, onPick, reduced }) {
  const [filter, setFilter] = useState("");
  const root = useRef(null);
  const button = useRef(null);
  const search = useRef(null);
  const panel = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    search.current?.focus({ preventScroll: true });
    panel.current?.scrollIntoView({ block: "nearest", behavior: reduced ? "auto" : "smooth" });         // the whole list comes into view
    const key = (e) => { if (e.key === "Escape") { onClose(); button.current?.focus(); } };
    const outside = (e) => { if (root.current && !root.current.contains(e.target)) onClose(); };
    document.addEventListener("keydown", key);
    document.addEventListener("pointerdown", outside);
    return () => { document.removeEventListener("keydown", key); document.removeEventListener("pointerdown", outside); };
  }, [open, onClose, reduced]);

  const shown = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    return DEMO_GROUPS.map(([g, rows]) => [g, rows.filter(([role, name, email]) => !needle || `${role} ${name} ${email}`.toLowerCase().includes(needle))]).filter(([, rows]) => rows.length);
  }, [filter]);

  return (
    <div ref={root} className="relative">
      <button ref={button} type="button" className="hw-demo-toggle" aria-expanded={open} aria-controls="demo-sheet" aria-haspopup="listbox" onClick={onToggle}>
        <span>Demo accounts <span className="ml-1 rounded-full bg-cyan-100 px-2 py-0.5 text-xs text-cyan-900">{ALL_DEMO.length}</span></span>
        <ChevronDown size={18} aria-hidden="true" className={reduced ? "" : "transition-transform duration-300"} style={{ transform: open ? "rotate(180deg)" : "none" }} />
      </button>

      <section ref={panel} id="demo-sheet" className="hw-drop" data-open={open ? "true" : "false"} aria-label="Demo accounts" aria-hidden={open ? undefined : "true"} inert={open ? undefined : ""}>
        <div className="border-b border-slate-100 p-3">
          <label className="relative block"><span className="sr-only">Search the demo accounts</span><Search size={16} className="pointer-events-none absolute left-3.5 top-3.5 text-slate-500" aria-hidden="true" />
            <input ref={search} value={filter} onChange={(e) => setFilter(e.target.value)} placeholder="Search a role or name" className="h-11 w-full rounded-full border border-slate-300 bg-white pl-10 pr-4 text-sm outline-none focus:border-cyan-600 focus:ring-4 focus:ring-cyan-500/20" /></label>
          <p className="mt-2 text-xs text-slate-600">Click one to fill the e-mail, the password and the mobile number. The password is the same for all.</p>
        </div>
        <div className="hw-drop-list">
          {shown.length === 0 && <p className="py-4 text-center text-sm text-slate-600">No demo account matches.</p>}
          {shown.map(([g, rows]) => {
            const tone = GROUP_TONE[DEMO_GROUPS.findIndex(([name]) => name === g)] || GROUP_TONE[0];
            return (
              <div key={g}>
                <p className="sticky top-0 z-10 flex items-center gap-2 bg-white/95 px-3 py-2 text-[11px] font-extrabold uppercase tracking-wider text-slate-700"><span className={`h-2.5 w-2.5 rounded-full bg-gradient-to-br ${tone}`} aria-hidden="true" />{g}</p>
                <div className="grid grid-cols-1 gap-2 px-3 pb-3 min-[480px]:grid-cols-2">
                  {rows.map(([role, name, email, phone]) => (
                    <button key={email} type="button" className="hw-demo" data-picked={picked === email ? "true" : "false"} onClick={() => onPick({ role, name, email, phone })} aria-label={`Fill in ${role}: ${name}`}>
                      <span className={`hw-avatar grid h-9 w-9 shrink-0 place-items-center rounded-full bg-gradient-to-br ${tone} text-sm font-extrabold text-white shadow-sm`}>{name.replace(/^Dr\. /, "").slice(0, 1)}</span>
                      <span className="min-w-0"><span className="block truncate text-sm font-bold text-slate-900">{role}</span><span className="block truncate text-xs text-slate-600">{name}</span></span>
                    </button>))}
                </div>
              </div>);
          })}
        </div>
      </section>
    </div>
  );
}
