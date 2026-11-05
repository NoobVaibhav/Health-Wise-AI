import { Share2 } from "lucide-react";

// "Share" through the phone's own share sheet (Android, iPad). It shows only where the browser has one, and it shares only the short text the screen passes in;
// nothing is sent anywhere by the app itself. Printing or "Save as PDF" stays the way to get the full document.
export const canShare = () => typeof navigator !== "undefined" && typeof navigator.share === "function";

export default function ShareButton({ title, text, label = "Share" }) {
  if (!canShare()) return null;
  const share = async () => {
    try { await navigator.share({ title, text }); } catch { /* the person closed the share sheet */ }
  };
  return <button type="button" onClick={share} className="inline-flex min-h-11 items-center gap-2 rounded-xl border-2 border-brand-700 bg-white px-5 text-base font-bold text-brand-800"><Share2 size={18} aria-hidden="true" /> {label}</button>;
}
