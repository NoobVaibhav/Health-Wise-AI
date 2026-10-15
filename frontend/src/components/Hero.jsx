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
  <Link to={to} className={`inline-flex min-h-12 items-center gap-2 rounded-xl border-2 px-5 py-2.5 text-base font-bold shadow-md ${primary ? "border-white bg-white text-brand-900 hover:bg-brand-50" : "border-white bg-brand-900/50 text-white hover:bg-brand-900/70"}`}>
    {children} <ArrowRight size={18} />
  </Link>
);

const TILE_TONES = ["from-brand-500 to-brand-700", "from-sky-400 to-blue-600", "from-emerald-400 to-emerald-600", "from-violet-400 to-violet-600", "from-amber-400 to-orange-500", "from-rose-400 to-rose-600"];

// items: [{ to, icon, label, hint }]
export function QuickActions({ items }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-4">
      {items.map((item, i) => {
        const Icon = item.icon;
        return (
          <Link key={item.to + item.label} to={item.to} className="tile flex min-h-24 items-center gap-4 rounded-3xl border-2 border-brand-200 bg-white p-5 shadow-sm hover:border-brand-600">
            <span className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br text-white shadow ${TILE_TONES[i % TILE_TONES.length]}`}><Icon size={24} /></span>
            <span className="min-w-0 flex-1">
              <span className="block text-lg font-extrabold text-slate-900">{item.label}</span>
              {item.hint && <span className="block text-base text-slate-600">{item.hint}</span>}
            </span>
            <ArrowRight size={20} className="shrink-0 text-brand-700" />
          </Link>
        );
      })}
    </div>
  );
}
