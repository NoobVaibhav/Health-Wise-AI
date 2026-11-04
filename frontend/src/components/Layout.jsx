import { useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import Navbar from "./Navbar";
import Sidebar from "./Sidebar";
import BottomNav from "./BottomNav";
import DisclaimerBanner from "./DisclaimerBanner";
import ErrorBoundary from "./ErrorBoundary";
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
  return (
    <div className={fill ? "flex h-dvh flex-col overflow-hidden" : "min-h-dvh"}>
      <Sidebar open={menuOpen} onClose={() => setMenuOpen(false)} />
      <div className={`lg:pl-64 ${fill ? "flex min-h-0 flex-1 flex-col" : ""}`}>
        <div className={fill ? "contents [@media(max-height:32rem)]:hidden" : "contents"}><Navbar onMenu={() => setMenuOpen(true)} /></div>
        <main className={`mx-auto w-full max-w-6xl p-3 sm:p-4 lg:p-8 ${tabs && !fill ? "pb-tabbar lg:pb-8" : ""} ${fill ? `flex min-h-0 flex-1 flex-col ${tabs ? "!pb-[calc(var(--height-tabbar)+var(--safe-bottom)+0.5rem)] lg:!pb-8" : ""}` : ""}`}>
          <div className={fill ? "[@media(max-height:32rem)]:hidden" : ""}><DisclaimerBanner /></div>
          {/* key = path, so every page fades in when you move to it */}
          <ErrorBoundary key={location.pathname} inFrame><div className={`page-enter ${fill ? "flex min-h-0 flex-1 flex-col" : ""}`}><Outlet /></div></ErrorBoundary>
        </main>
      </div>
      {tabs && <BottomNav />}
    </div>
  );
}
