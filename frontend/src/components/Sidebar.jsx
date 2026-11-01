import { NavLink } from "react-router-dom";
import { Circle, HeartPulse, LogOut } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { ICONS, ROLE_LABEL, menuFor } from "./navigation";

export default function Sidebar({ open, onClose }) {
  const { user, logout } = useAuth();
  const links = menuFor(user);
  const home = links[0]?.[0];
  return (
    <>
      {open && <div className="fixed inset-0 z-30 bg-slate-900/50 md:hidden" onClick={onClose} />}
      <aside className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col bg-gradient-to-b from-brand-900 via-brand-800 to-brand-900 text-white transition-transform md:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="flex items-center gap-3 px-5 py-6">
          <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white/15 text-white ring-1 ring-white/20"><HeartPulse size={24} /></span>
          <div>
            <p className="text-lg font-extrabold leading-tight">HealthWise AI</p>
            <p className="text-xs leading-tight text-brand-200">{ROLE_LABEL[user.role]} portal</p>
          </div>
        </div>
        <nav className="flex-1 space-y-1 overflow-y-auto px-3 pb-3">
          {links.map(([to, label, icon]) => {
            const Icon = ICONS[icon] || Circle;
            return (
              <NavLink key={to} to={to} end={to === home} onClick={onClose}
                className={({ isActive }) => `flex items-center gap-3 rounded-2xl px-3.5 py-2.5 text-base font-bold transition ${isActive ? "bg-white text-brand-800 shadow" : "text-brand-100 hover:bg-white/10"}`}>
                <Icon size={19} /> {label}
              </NavLink>
            );
          })}
        </nav>
        <button onClick={logout} className="m-3 flex items-center justify-center gap-3 rounded-2xl border-2 border-white/70 bg-white/10 px-3.5 py-3 text-base font-bold text-white hover:bg-white/25">
          <LogOut size={20} /> Log out
        </button>
      </aside>
    </>
  );
}
