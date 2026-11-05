import { Suspense, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import Navbar from "./Navbar";
import Sidebar from "./Sidebar";
import BottomNav from "./BottomNav";
import NavRail from "./NavRail";
import useLayoutMode from "../hooks/useLayoutMode";
import DisclaimerBanner from "./DisclaimerBanner";
import ErrorBoundary from "./ErrorBoundary";
import { Loading } from "./Feedback";
import { useAuth } from "../context/AuthContext";

// Pages that fill the screen exactly (no page scroll): the page inside owns its own scrolling region, like a chat with its input bar pinned at the bottom.
const FILL_PAGES = ["/patient/assistant"];

// Frame for every logged-in page: sidebar, top bar, the medical disclaimer, and (for a patient on a phone) the tab bar.
export default function Layout() {
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  const { user } = useAuth();
  const fill = FILL_PAGES.includes(location.pathname);
  const tabs = user?.role === "PATIENT";
  const staff = !tabs;                     // staff: icon rail on a tablet, full sidebar from 1280 px. The patient frame is unchanged.
  const { rail } = useLayoutMode();
  return (
    <div className={fill ? "flex h-dvh flex-col overflow-hidden" : "min-h-dvh"}>
      {staff && rail && <NavRail onExpand={() => setMenuOpen(true)} />}
      <Sidebar open={menuOpen} onClose={() => setMenuOpen(false)} staff={staff} />
      <div className={`${staff ? "shell-staff" : "lg:pl-64"} ${fill ? "flex min-h-0 flex-1 flex-col" : ""}`}>
        <div className={fill ? "contents [@media(max-height:32rem)]:hidden" : "contents"}><Navbar onMenu={() => setMenuOpen(true)} staff={staff} /></div>
        <main className={`mx-auto w-full ${staff ? "max-w-[88rem] lg:p-6 xl:p-8" : "max-w-6xl lg:p-8"} p-3 sm:p-4 ${tabs && !fill ? "pb-tabbar lg:pb-8" : ""} ${fill ? `flex min-h-0 flex-1 flex-col ${tabs ? "!pb-[calc(var(--height-tabbar)+var(--safe-bottom)+0.5rem)] lg:!pb-8" : ""}` : ""}`}>
          <div className={fill ? "[@media(max-height:32rem)]:hidden" : ""}><DisclaimerBanner /></div>
          {/* key = path, so every page fades in when you move to it */}
          <ErrorBoundary key={location.pathname} inFrame><div className={`page-enter ${fill ? "flex min-h-0 flex-1 flex-col" : ""}`}><Suspense fallback={<Loading />}><Outlet /></Suspense></div></ErrorBoundary>
        </main>
      </div>
      {tabs && <BottomNav />}
    </div>
  );
}
