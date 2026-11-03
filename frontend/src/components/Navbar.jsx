import { Link } from "react-router-dom";
import { Menu } from "lucide-react";
import { Avatar } from "./DataViews";
import { ROLE_HOME, useAuth } from "../context/AuthContext";
import { ROLE_LABEL } from "./navigation";

// Top bar: menu button on mobile, and who is logged in.
export default function Navbar({ onMenu }) {
  const { user } = useAuth();
  return (
    <header className="sticky top-0 z-20 flex items-center justify-between border-b border-slate-200/70 bg-white/85 px-3 py-2 backdrop-blur md:px-8 md:py-3">
      <button onClick={onMenu} className="grid h-11 w-11 place-items-center rounded-xl text-slate-600 hover:bg-slate-100 md:hidden" aria-label="Open menu">
        <Menu size={24} />
      </button>
      <p className="hidden text-sm font-medium text-slate-500 md:block">Your health reports, explained simply</p>
      <Link to={`${ROLE_HOME[user.role]}/profile`} title="Open my profile" className="flex min-w-0 items-center gap-2 rounded-2xl p-1 md:gap-3 md:p-1.5 hover:bg-slate-100 focus:outline-none focus-visible:ring-4 focus-visible:ring-brand-200">
        <div className="min-w-0 text-right leading-tight">
          <p className="truncate text-sm font-bold text-slate-900 md:text-base">{user.full_name}</p>
          <p className="mt-0.5 inline-block max-w-full truncate rounded-full bg-brand-100 px-2 py-0.5 text-xs md:px-2.5 md:text-sm font-bold text-brand-800">Logged in as: {ROLE_LABEL[user.role]}</p>
        </div>
        <Avatar name={user.full_name} size={40} userId={user.id} version={user.avatar_version} round />
      </Link>
    </header>
  );
}
