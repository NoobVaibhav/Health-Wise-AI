const TONES = {
  brand: "from-brand-500 to-brand-700",
  amber: "from-amber-400 to-orange-500",
  sky: "from-sky-400 to-blue-600",
  slate: "from-slate-400 to-slate-600",
  emerald: "from-emerald-400 to-emerald-600",
  rose: "from-rose-400 to-rose-600",
  violet: "from-violet-400 to-violet-600",
};

// Number card: coloured icon and the number on one line, then the name and a short note. Every card has the same height, so a row looks even
// whether or not a card has a note. `value` can be text or a component.
export default function HealthCard({ title, value, sub, icon: Icon, tone = "brand" }) {
  const big = typeof value === "number";
  return (
    <div className="flex h-full min-h-[8.5rem] flex-col rounded-3xl border border-slate-200/70 bg-white p-5 shadow-sm transition hover:shadow-md">
      <div className="flex items-start justify-between gap-3">
        {Icon && (
          <span className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br text-white shadow ${TONES[tone] || TONES.brand}`}>
            <Icon size={22} />
          </span>
        )}
        <div className={`min-w-0 break-words text-right font-extrabold leading-none text-slate-900 ${big ? "text-4xl" : "text-xl"}`}>{value}</div>
      </div>
      <p className="mt-4 text-[15px] font-bold leading-snug text-slate-800">{title}</p>
      <p className="mt-0.5 text-sm leading-snug text-slate-500">{sub || " "}</p>
    </div>
  );
}

export function Section({ title, children, className = "", action }) {
  return (
    <section className={`rounded-3xl border border-slate-200/70 bg-white p-5 shadow-sm md:p-6 ${className}`}>
      {(title || action) && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          {title && <h2 className="text-lg font-bold text-slate-900">{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </section>
  );
}
