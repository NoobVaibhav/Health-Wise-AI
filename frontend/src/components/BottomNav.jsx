import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { CalendarClock, CircleUser, FileText, House, MessageCircle } from "lucide-react";

// The patient's five most used pages as a tab bar at the bottom of a phone (hidden from 1024 px up, where the side menu is always open).
// It steps aside while a text box has the keyboard, so the keyboard never pushes a bar over the page.
export const PATIENT_TABS = [
  ["/patient", "Home", House, true],
  ["/patient/reports", "Reports", FileText],
  ["/patient/assistant", "Assistant", MessageCircle],
  ["/patient/appointments", "Visits", CalendarClock],
  ["/patient/profile", "Profile", CircleUser],
];

const typing = (el) => !!el && (el.tagName === "TEXTAREA" || el.tagName === "SELECT" || (el.tagName === "INPUT" && !["checkbox", "radio", "button", "submit", "file", "range"].includes(el.type)));

export default function BottomNav() {
  const [keyboard, setKeyboard] = useState(false);
  useEffect(() => {
    const on = () => setKeyboard(typing(document.activeElement));
    const out = () => setTimeout(on, 0);
    document.addEventListener("focusin", on);
    document.addEventListener("focusout", out);
    return () => { document.removeEventListener("focusin", on); document.removeEventListener("focusout", out); };
  }, []);
  if (keyboard) return null;
  return (
    <nav aria-label="Main" className="fixed inset-x-0 bottom-0 z-30 border-t border-slate-200 bg-white/95 pb-[var(--safe-bottom)] shadow-sheet backdrop-blur-sm lg:hidden print:hidden">
      <ul className="mx-auto flex h-[var(--height-tabbar)] max-w-xl items-stretch">
        {PATIENT_TABS.map(([to, label, Icon, end]) => (
          <li key={to} className="min-w-0 flex-1">
            <NavLink to={to} end={end} className={({ isActive }) => `flex h-full min-h-11 flex-col items-center justify-center gap-0.5 text-xs font-bold ${isActive ? "text-brand-800" : "text-slate-600"}`}>
              {({ isActive }) => (
                <>
                  <span className={`grid h-7 w-14 max-w-full place-items-center rounded-full transition-colors ${isActive ? "bg-brand-100" : ""}`}><Icon size={21} aria-hidden="true" /></span>
                  <span className="truncate">{label}</span>
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
