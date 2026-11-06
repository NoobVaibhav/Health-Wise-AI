// Small pieces shared by the sign-in pages: motion preferences, the logo, the heartbeat line and the compact header of a phone or tablet.
// The big decorative brand panel of a desktop lives in BrandPanel.jsx and is loaded only when it is shown. All of it is decoration (aria-hidden) and CSS or SVG only.
import { useEffect, useRef, useState } from "react";
import { ShieldCheck } from "lucide-react";
import { BrandMark } from "../BrandLogo";

export const TRUST = ["Private by design: only you and your doctors see your records.", "Every AI explanation is checked by a doctor first.", "Reports, medicines and history in one safe place."];

function useQuery(query, fallback) {
  const [matches, setMatches] = useState(() => (typeof window !== "undefined" && window.matchMedia ? window.matchMedia(query).matches : fallback));
  useEffect(() => {
    if (!window.matchMedia) return undefined;
    const mq = window.matchMedia(query);
    const on = () => setMatches(mq.matches);
    on();
    mq.addEventListener?.("change", on);
    return () => mq.removeEventListener?.("change", on);
  }, [query]);
  return matches;
}

export const useReducedMotion = () => useQuery("(prefers-reduced-motion: reduce)", false);
/** True on a desktop-sized screen (the brand panel is only built there, so a phone never downloads it). */
export const useDesktop = () => useQuery("(min-width: 1024px)", false);

export function Trust({ reduced }) {
  const [i, setI] = useState(0);
  useEffect(() => {
    if (reduced) return undefined;
    const t = setInterval(() => setI((n) => (n + 1) % TRUST.length), 4500);
    return () => clearInterval(t);
  }, [reduced]);
  return <p key={i} className="hw-fade flex min-h-12 items-start gap-2 text-sm text-brand-100"><ShieldCheck size={16} className="mt-0.5 shrink-0" aria-hidden="true" />{TRUST[i]}</p>;
}

// The heartbeat (viewBox 640 x 160): two beats. The delays of the two rings match the moment the line reaches each spike (the line is drawn between 8% and 55% of 6 s).
const ECG = "M0 80 L120 80 L145 80 L165 28 L190 132 L212 56 L232 80 L330 80 L430 80 L452 80 L472 20 L498 140 L520 60 L542 80 L640 80";
const BEATS = [[178, 1.27], [485, 2.62]];

export function Heartbeat({ reduced, paused = false, className = "", id = "hb" }) {
  const svg = useRef(null);
  useEffect(() => {                                           // the travelling dot is SMIL, which CSS cannot pause
    const el = svg.current;
    if (el?.pauseAnimations) { if (paused) el.pauseAnimations(); else el.unpauseAnimations(); }
  }, [paused]);
  return (
    <svg ref={svg} viewBox="0 0 640 160" className={className} aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id={`${id}-grad`} x1="0" x2="1"><stop offset="0" stopColor="#67e8f9" stopOpacity="0" /><stop offset="0.3" stopColor="#67e8f9" /><stop offset="0.7" stopColor="#ffffff" /><stop offset="1" stopColor="#a5f3fc" /></linearGradient>
        <filter id={`${id}-glow`} x="-20%" y="-60%" width="140%" height="220%"><feGaussianBlur stdDeviation="3.5" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
      </defs>
      <line x1="0" y1="80" x2="640" y2="80" stroke="#ffffff" strokeOpacity="0.12" strokeDasharray="2 8" strokeLinecap="round" />
      <path id={`${id}-path`} d={ECG} pathLength="1" fill="none" stroke={`url(#${id}-grad)`} strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" filter={`url(#${id}-glow)`} className={reduced ? "" : "hw-ecg-line hw-loop"} />
      {!reduced && BEATS.map(([x, delay]) => <circle key={x} cx={x} cy="80" r="9" fill="none" stroke="#a5f3fc" strokeWidth="2" className="hw-beat-ring hw-loop" style={{ animationDelay: `${delay}s` }} />)}
      {!reduced && (
        <circle r="5.5" fill="#ffffff" filter={`url(#${id}-glow)`}>
          <animateMotion dur="6s" repeatCount="indefinite" keyPoints="0;0;1;1" keyTimes="0;0.08;0.55;1" calcMode="linear"><mpath href={`#${id}-path`} /></animateMotion>
          <animate attributeName="opacity" values="0;1;1;0;0" keyTimes="0;0.08;0.85;0.95;1" dur="6s" repeatCount="indefinite" />
        </circle>)}
    </svg>
  );
}

export function LogoMark({ reduced, size = 34, box = "h-16 w-16" }) {
  return (
    <span className={`relative inline-flex ${box} items-center justify-center rounded-3xl bg-white/15 text-white ring-1 ring-white/30 ${reduced ? "" : "hw-logo-in"}`}>
      {!reduced && <span className="hw-logo-ring hw-loop absolute inset-0 rounded-3xl ring-2 ring-white/50" aria-hidden="true" />}
      <BrandMark size={size} variant="white" decorative />
    </span>
  );
}

/** The header of a phone or tablet: a small aurora, the logo, the name and a short heartbeat. */
export function CompactBrand({ reduced, paused }) {
  return (
    <header className="relative overflow-hidden bg-gradient-to-br from-brand-900 via-brand-700 to-sky-700 px-5 pb-5 pt-6 text-center text-white lg:hidden">
      <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
        <div className={`absolute -left-16 -top-20 h-56 w-56 rounded-full bg-cyan-300/30 blur-3xl ${reduced ? "" : "hw-orb-a hw-loop"}`} />
        <div className={`absolute -bottom-24 -right-10 h-56 w-56 rounded-full bg-indigo-400/25 blur-3xl ${reduced ? "" : "hw-orb-b hw-loop"}`} />
      </div>
      <div className="relative">
        <LogoMark reduced={reduced} size={26} box="h-12 w-12" />
        <h1 className="mt-2 text-2xl font-extrabold tracking-tight">HealthWise AI</h1>
        <p className="text-sm text-brand-100">Your health reports, explained simply.</p>
        <Heartbeat reduced={reduced} paused={paused} id="hbc" className="mx-auto mt-1 h-12 w-full max-w-xs" />
      </div>
    </header>
  );
}

/** Soft light on the form side: a dotted grid and two pale colour pools (still, so only the card moves). */
export function Backdrop() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      <div className="absolute -right-24 -top-24 h-96 w-96 rounded-full bg-cyan-200/40 blur-3xl" />
      <div className="absolute -bottom-32 -left-20 h-96 w-96 rounded-full bg-sky-200/40 blur-3xl" />
      <div className="absolute inset-0 opacity-[0.35] [background-image:radial-gradient(circle,rgba(14,116,144,0.18)_1px,transparent_1.2px)] [background-size:26px_26px]" />
    </div>
  );
}
