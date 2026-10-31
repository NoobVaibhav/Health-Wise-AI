// The brand side of the sign-in pages: drifting colour orbs, a faint grid that follows the pointer a little, the heartbeat line with a glowing dot, floating
// medical icons and rotating trust messages. All of it is decoration (aria-hidden), light (CSS and SVG only) and switched off by "reduce motion".
import { useEffect, useState } from "react";
import { HeartPulse, Pill, ShieldCheck, Stethoscope } from "lucide-react";

export const TRUST = ["Private by design: only you and your doctors see your records.", "Every AI explanation is checked by a doctor first.", "Reports, medicines and history in one safe place."];
const ECG = "M0 60 L90 60 L110 60 L125 22 L142 98 L158 40 L172 60 L260 60 L340 60 L358 60 L372 14 L392 104 L410 44 L426 60 L520 60";

export function useReducedMotion() {
  const [reduced, setReduced] = useState(() => (typeof window !== "undefined" && window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)").matches : false));
  useEffect(() => {
    if (!window.matchMedia) return undefined;
    const query = window.matchMedia("(prefers-reduced-motion: reduce)");
    const on = () => setReduced(query.matches);
    query.addEventListener?.("change", on);
    return () => query.removeEventListener?.("change", on);
  }, []);
  return reduced;
}

export function Trust({ reduced }) {
  const [i, setI] = useState(0);
  useEffect(() => {
    if (reduced) return undefined;
    const t = setInterval(() => setI((n) => (n + 1) % TRUST.length), 4500);
    return () => clearInterval(t);
  }, [reduced]);
  return <p key={i} className="hw-fade flex min-h-12 items-start gap-2 text-sm text-brand-100"><ShieldCheck size={16} className="mt-0.5 shrink-0" aria-hidden="true" />{TRUST[i]}</p>;
}

export function Heartbeat({ reduced, className = "" }) {
  return (
    <svg viewBox="0 0 520 120" className={className} aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id="hw-ecg-grad" x1="0" x2="1"><stop offset="0" stopColor="#a5f3fc" stopOpacity="0" /><stop offset="0.35" stopColor="#a5f3fc" /><stop offset="1" stopColor="#ffffff" /></linearGradient>
        <filter id="hw-glow" x="-20%" y="-50%" width="140%" height="200%"><feGaussianBlur stdDeviation="3" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
      </defs>
      <path id="hw-ecg-path" d={ECG} pathLength="1" fill="none" stroke="url(#hw-ecg-grad)" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" filter="url(#hw-glow)" className={reduced ? "" : "hw-ecg-line"} />
      {!reduced && (
        <circle r="5" fill="#fff" filter="url(#hw-glow)">
          <animateMotion dur="6s" repeatCount="indefinite" keyPoints="0;0.55;0.55;1" keyTimes="0;0.55;0.85;1" calcMode="linear"><mpath href="#hw-ecg-path" /></animateMotion>
        </circle>)}
    </svg>
  );
}

/** Soft colour orbs and a dotted grid behind the whole page. */
export function Backdrop({ reduced }) {
  const loop = (name) => (reduced ? "" : name);
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      <div className={`absolute -left-24 -top-24 h-96 w-96 rounded-full bg-cyan-300/30 blur-3xl ${loop("hw-orb-a")}`} />
      <div className={`absolute -bottom-32 right-0 h-[28rem] w-[28rem] rounded-full bg-sky-400/25 blur-3xl ${loop("hw-orb-b")}`} />
      <div className={`absolute left-1/3 top-1/2 h-72 w-72 rounded-full bg-teal-300/20 blur-3xl ${loop("hw-orb-c")}`} />
      <div className={`absolute inset-0 opacity-[0.35] [background-image:radial-gradient(circle,rgba(14,116,144,0.22)_1px,transparent_1.2px)] [background-size:26px_26px] ${reduced ? "" : "hw-parallax"}`} />
    </div>
  );
}

const FLOATERS = [[Stethoscope, "right-[6%] top-[8%]", "hw-float-a", "h-14 w-14"], [Pill, "right-[3%] top-[26%]", "hw-float-b", "h-12 w-12"], [HeartPulse, "right-[12%] bottom-[22%]", "hw-float-b", "h-12 w-12"], [ShieldCheck, "right-[5%] bottom-[6%]", "hw-float-a", "h-14 w-14"]];

export function Floaters({ reduced }) {
  return (
    <div className={`pointer-events-none absolute inset-0 ${reduced ? "" : "hw-parallax-deep"}`} aria-hidden="true">
      {FLOATERS.map(([Icon, place, motion, size], i) => (
        <span key={i} className={`absolute ${place} flex ${size} items-center justify-center rounded-2xl bg-white/10 text-white/50 ring-1 ring-white/15 ${reduced ? "" : motion}`}><Icon size={26} /></span>))}
    </div>
  );
}

export function LogoMark({ reduced, size = 34, box = "h-16 w-16" }) {
  return (
    <span className={`relative inline-flex ${box} items-center justify-center rounded-3xl bg-white/15 text-white ring-1 ring-white/30 ${reduced ? "" : "hw-logo-in"}`}>
      {!reduced && <span className="hw-ring absolute inset-0 rounded-3xl ring-2 ring-white/50" aria-hidden="true" />}
      <HeartPulse size={size} aria-hidden="true" />
    </span>
  );
}
