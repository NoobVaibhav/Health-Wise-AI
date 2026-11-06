import { NavLink } from "react-router-dom";
import { Circle, Menu } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { ICONS, menuFor } from "./navigation";
import { BrandMark } from "./BrandLogo";

// Staff on a tablet: a slim icon rail that stays out of the way. Every icon has a name (tooltip and screen reader); the top button opens the full menu over the page.
export default function NavRail({ onExpand }) {
  const { user } = useAuth();
  const links = menuFor(user);
  const home = links[0]?.[0];
  return (
    <nav aria-label="Pages" data-rail className="fixed inset-y-0 left-0 z-30 flex w-[4.5rem] flex-col items-center gap-1 bg-gradient-to-b from-brand-900 to-brand-800 pb-[max(0.5rem,var(--safe-bottom))] pt-[calc(0.5rem+var(--safe-top))] text-white print:hidden">
      <button type="button" onClick={onExpand} aria-label="Open the full menu" title="Menu" className="grid h-12 w-12 shrink-0 place-items-center rounded-2xl bg-white/15 ring-1 ring-white/20 hover:bg-white/25">
        <Menu size={22} aria-hidden="true" />
      </button>
      <BrandMark size={26} variant="white" decorative className="my-1.5 shrink-0 opacity-90" />
      <ul className="flex min-h-0 w-full flex-1 flex-col items-center gap-1 overflow-y-auto overscroll-contain px-2 pb-2 [scrollbar-width:none]">
        {links.map(([to, label, icon]) => {
          const Icon = ICONS[icon] || Circle;
          return (
            <li key={to}>
              <NavLink to={to} end={to === home} aria-label={label} title={label}
                className={({ isActive }) => `grid h-12 w-12 place-items-center rounded-2xl transition-colors ${isActive ? "bg-white text-brand-800 shadow-sm" : "text-brand-100 hover:bg-white/10"}`}>
                <Icon size={21} aria-hidden="true" />
              </NavLink>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
