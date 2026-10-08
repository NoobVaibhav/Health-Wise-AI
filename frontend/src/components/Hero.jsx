// Welcome banner and big "quick action" tiles used at the top of every dashboard.
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";

export function Hero({ title, subtitle, children }) {
  return (
    <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-brand-700 via-brand-600 to-sky-600 p-6 text-white shadow-lg md:p-8">
      <div className="pointer-events-none absolute -right-10 -top-10 h-48 w-48 rounded-full bg-white/10" />
      <div className="pointer-events-none absolute -bottom-16 right-24 h-40 w-40 rounded-full bg-white/10" />
      <div className="relative">
        <h1 className="text-2xl font-extrabold tracking-tight md:text-3xl">{title}</h1>
        {subtitle && <p className="mt-2 max-w-2xl text-base text-brand-50 md:text-lg">{subtitle}</p>}
        {children && <div className="mt-4 flex flex-wrap gap-3">{children}</div>}
      </div>
    </div>
  );
}

export const HeroButton = ({ to, children, primary }) => (
  <Link to={to} className={`inline-flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-bold ${primary ? "bg-white text-brand-800 hover:bg-brand-50" : "bg-white/15 text-white hover:bg-white/25"}`}>
    {children} <ArrowRight size={15} />
  </Link>
);

const TILE_TONES = ["from-brand-500 to-brand-700", "from-sky-400 to-blue-600", "from-emerald-400 to-emerald-600", "from-violet-400 to-violet-600", "from-amber-400 to-orange-500", "from-rose-400 to-rose-600"];

// items: [{ to, icon, label, hint }]
export function QuickActions({ items }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {items.map((item, i) => {
        const Icon = item.icon;
        return (
          <Link key={item.to + item.label} to={item.to} className="tile flex items-center gap-3 rounded-3xl border border-slate-200/70 bg-white p-4 shadow-sm">
            <span className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br text-white shadow ${TILE_TONES[i % TILE_TONES.length]}`}><Icon size={24} /></span>
            <span>
              <span className="block font-bold text-slate-900">{item.label}</span>
              {item.hint && <span className="block text-sm text-slate-500">{item.hint}</span>}
            </span>
          </Link>
        );
      })}
    </div>
  );
}
