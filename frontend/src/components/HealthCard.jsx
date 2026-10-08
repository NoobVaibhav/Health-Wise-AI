const TONES = {
  brand: "from-brand-500 to-brand-700",
  amber: "from-amber-400 to-orange-500",
  sky: "from-sky-400 to-blue-600",
  slate: "from-slate-400 to-slate-600",
  emerald: "from-emerald-400 to-emerald-600",
  rose: "from-rose-400 to-rose-600",
  violet: "from-violet-400 to-violet-600",
};

// Number card with a coloured icon. `value` can be text or a component.
export default function HealthCard({ title, value, sub, icon: Icon, tone = "brand" }) {
  return (
    <div className="rounded-3xl border border-slate-200/70 bg-white p-5 shadow-sm">
      <div className="flex items-center gap-3">
        {Icon && (
          <span className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br text-white shadow ${TONES[tone] || TONES.brand}`}>
            <Icon size={22} />
          </span>
        )}
        <p className="text-sm font-semibold text-slate-500">{title}</p>
      </div>
      <p className="mt-3 break-words text-2xl font-extrabold text-slate-900">{value}</p>
      {sub && <p className="mt-1 text-sm text-slate-500">{sub}</p>}
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
