import { Menu } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { ROLE_LABEL } from "./navigation";

// Top bar: menu button on mobile, and who is logged in.
export default function Navbar({ onMenu }) {
  const { user } = useAuth();
  return (
    <header className="sticky top-0 z-20 flex items-center justify-between border-b border-slate-200/70 bg-white/85 px-4 py-3 backdrop-blur md:px-8">
      <button onClick={onMenu} className="rounded-xl p-2 text-slate-600 hover:bg-slate-100 md:hidden" aria-label="Open menu">
        <Menu size={24} />
      </button>
      <p className="hidden text-sm font-medium text-slate-500 md:block">Your health reports, explained simply</p>
      <div className="flex items-center gap-3">
        <div className="text-right leading-tight">
          <p className="text-base font-bold text-slate-900">{user.full_name}</p>
          <p className="mt-0.5 inline-block rounded-full bg-brand-100 px-2.5 py-0.5 text-sm font-bold text-brand-800">Logged in as: {ROLE_LABEL[user.role]}</p>
        </div>
        <span className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-brand-700 text-base font-extrabold text-white shadow">
          {user.full_name[0].toUpperCase()}
        </span>
      </div>
    </header>
  );
}
