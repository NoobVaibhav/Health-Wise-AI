import { Link } from "react-router-dom";
import { Menu } from "lucide-react";
import { Avatar } from "./DataViews";
import { ROLE_HOME, useAuth } from "../context/AuthContext";
import { ROLE_LABEL } from "./navigation";

// Top bar: menu button on mobile, and who is logged in. Compact on a phone, and it scrolls away in a short landscape screen so the page gets the room.
export default function Navbar({ onMenu }) {
  const { user } = useAuth();
  return (
    <header className="sticky top-0 z-20 flex min-h-14 shrink-0 items-center justify-between border-b border-slate-200/70 bg-white/90 px-3 pb-1.5 pt-[calc(0.375rem+var(--safe-top))] backdrop-blur-sm [@media(max-height:32rem)]:static lg:px-8 lg:py-3">
      <button type="button" onClick={onMenu} className="grid h-11 w-11 place-items-center rounded-xl text-slate-700 hover:bg-slate-100 lg:hidden" aria-label="Open menu">
        <Menu size={24} aria-hidden="true" />
      </button>
      <p className="hidden text-sm font-medium text-slate-600 lg:block">Your health reports, explained simply</p>
      <Link to={`${ROLE_HOME[user.role]}/profile`} title="Open my profile" className="flex min-w-0 items-center gap-2 rounded-2xl p-1 hover:bg-slate-100 focus:outline-none focus-visible:ring-4 focus-visible:ring-brand-200 lg:gap-3 lg:p-1.5">
        <div className="min-w-0 text-right leading-tight">
          <p className="truncate text-sm font-bold text-slate-900 lg:text-base">{user.full_name}</p>
          <p className="mt-0.5 inline-block max-w-full truncate rounded-full bg-brand-100 px-2 py-0.5 text-xs font-bold text-brand-800 lg:px-2.5 lg:text-sm"><span className="hidden sm:inline">Logged in as: </span>{ROLE_LABEL[user.role]}</p>
        </div>
        <Avatar name={user.full_name} size={36} userId={user.id} version={user.avatar_version} round />
      </Link>
    </header>
  );
}
