import { useEffect, useRef } from "react";
import { NavLink } from "react-router-dom";
import { Circle, HeartPulse, LogOut } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import useMediaQuery from "../hooks/useMediaQuery";
import useBackClose from "../hooks/useBackClose";
import { ICONS, ROLE_LABEL, menuFor } from "./navigation";

const FOCUSABLE = "a[href],button:not([disabled])";

// The side menu: always open from 1024 px up; on a phone it is a drawer. An open drawer is a dialog: it takes focus, keeps it inside (Tab wraps),
// closes with Escape or a tap outside, locks the page behind it, and hands focus back to the button that opened it.
// `staff` menus stay a drawer up to 1279 px (a tablet has the icon rail instead) and are a fixed sidebar from 1280 px; the patient's menu is fixed from 1024 px.
export default function Sidebar({ open, onClose, staff = false }) {
  const { user, logout } = useAuth();
  const links = menuFor(user);
  const home = links[0]?.[0];
  const drawer = useMediaQuery(staff ? "(max-width: 1279px)" : "(max-width: 1023px)");
  const ref = useRef(null);
  const opener = useRef(null);
  const modal = drawer && open;
  const close = useRef(onClose);
  close.current = onClose;
  useBackClose(modal, onClose);

  useEffect(() => {
    if (!modal) return undefined;
    opener.current = document.activeElement;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    ref.current?.querySelector(FOCUSABLE)?.focus();
    const key = (e) => {
      if (e.key === "Escape") { close.current(); return; }
      if (e.key !== "Tab") return;
      const items = [...ref.current.querySelectorAll(FOCUSABLE)];
      if (!items.length) return;
      const first = items[0], last = items[items.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("keydown", key);
      document.body.style.overflow = previous;
      opener.current?.focus?.();
    };
  }, [modal]);

  return (
    <>
      {open && <div className={`fade-in fixed inset-0 z-[35] bg-slate-900/50 ${staff ? "xl:hidden" : "lg:hidden"}`} onClick={onClose} aria-hidden="true" />}
      <aside ref={ref} aria-label="Menu" {...(modal ? { role: "dialog", "aria-modal": "true" } : {})} {...(drawer && !open ? { inert: "", "aria-hidden": "true" } : {})}
        className={`fixed inset-y-0 left-0 z-40 flex w-72 max-w-[85vw] flex-col bg-gradient-to-b from-brand-900 via-brand-800 to-brand-900 pt-[var(--safe-top)] text-white transition-transform duration-[var(--duration-base)] ease-[var(--ease-soft)] ${staff ? "xl:w-64 xl:translate-x-0" : "lg:w-64 lg:translate-x-0"} ${open ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="flex items-center gap-3 px-5 py-5 lg:py-6">
          <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white/15 text-white ring-1 ring-white/20"><HeartPulse size={24} aria-hidden="true" /></span>
          <div>
            <p className="text-lg font-extrabold leading-tight">HealthWise AI</p>
            <p className="text-xs leading-tight text-brand-100">{ROLE_LABEL[user.role]} portal</p>
          </div>
        </div>
        <nav className="flex-1 space-y-1 overflow-y-auto overscroll-contain px-3 pb-3" aria-label="Pages">
          {links.map(([to, label, icon]) => {
            const Icon = ICONS[icon] || Circle;
            return (
              <NavLink key={to} to={to} end={to === home} onClick={onClose}
                className={({ isActive }) => `flex min-h-11 items-center gap-3 rounded-2xl px-3.5 py-2.5 text-base font-bold transition ${isActive ? "bg-white text-brand-800 shadow-sm" : "text-brand-100 hover:bg-white/10"}`}>
                <Icon size={19} aria-hidden="true" /> {label}
              </NavLink>
            );
          })}
        </nav>
        <button type="button" onClick={logout} className="mx-3 mb-[calc(0.75rem+var(--safe-bottom))] mt-2 flex items-center justify-center gap-3 rounded-2xl border-2 border-white/70 bg-white/10 px-3.5 py-3 text-base font-bold text-white hover:bg-white/25">
          <LogOut size={20} aria-hidden="true" /> Log out
        </button>
      </aside>
    </>
  );
}
