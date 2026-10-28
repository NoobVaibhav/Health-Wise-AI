import { useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import Navbar from "./Navbar";
import Sidebar from "./Sidebar";
import DisclaimerBanner from "./DisclaimerBanner";
import ErrorBoundary from "./ErrorBoundary";

// Frame for every logged-in page: sidebar, top bar, and the medical disclaimer.
export default function Layout() {
  const [menuOpen, setMenuOpen] = useState(false);
  const location = useLocation();
  return (
    <div className="min-h-screen">
      <Sidebar open={menuOpen} onClose={() => setMenuOpen(false)} />
      <div className="md:pl-64">
        <Navbar onMenu={() => setMenuOpen(true)} />
        <main className="mx-auto max-w-6xl p-4 md:p-8">
          <DisclaimerBanner />
          {/* key = path, so every page fades in when you move to it */}
          <ErrorBoundary key={location.pathname} inFrame><div className="page-enter"><Outlet /></div></ErrorBoundary>
        </main>
      </div>
    </div>
  );
}
