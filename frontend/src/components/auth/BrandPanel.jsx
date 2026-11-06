// The brand side of the sign-in pages on a desktop: aurora, film grain, a light that follows the pointer, the heartbeat, a word-by-word headline with a rotating word,
// feature cards, a marquee of departments and floating glass tiles. Everything here is decoration or marketing copy; it is loaded only on a desktop-sized screen.
// Text sits on flat translucent surfaces (no backdrop blur) so it stays sharp, and only transform and opacity move.
import { useRef } from "react";
import { Activity, FileSearch, Mic, Pill, ShieldCheck, Stethoscope, Syringe } from "lucide-react";
import { Heartbeat, LogoMark, Trust } from "./AuthArt";

const LEAD = ["Understand", "your"];
const ROT = ["history", "reports", "medicines", "health"];
const MODULES = ["OPD", "Inpatient", "Emergency", "Laboratory", "Radiology", "Pharmacy", "Operation theatre", "Blood bank", "Billing", "Insurance"];
const FEATURES = [
  ["report", "AI report analysis", "Upload a report and see every value explained with a clear gauge."],
  ["voice", "Voice assistant", "Ask about your health in English, Hindi or Marathi."],
  ["secure", "Secure records", "Private, doctor-reviewed, and never a diagnosis on its own."],
];
// [icon, where, depth (how far it follows the pointer), float style, size]
const TILES = [[Stethoscope, "right-[7%] top-[9%]", 22, "hw-float-a", "h-16 w-16"], [Pill, "right-[3%] top-[34%]", 12, "hw-float-b", "h-14 w-14"], [Activity, "right-[14%] bottom-[24%]", 30, "hw-float-c", "h-16 w-16"],
  [Syringe, "left-[46%] top-[6%]", 8, "hw-float-b", "h-12 w-12"], [ShieldCheck, "right-[6%] bottom-[7%]", 16, "hw-float-a", "h-14 w-14"]];

function FeatureIcon({ kind }) {
  const Icon = { report: FileSearch, voice: Mic, secure: ShieldCheck }[kind];
  return (
    <span className="hw-icon-box flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-white/15 ring-1 ring-white/25">
      <Icon size={22} aria-hidden="true" />
      {kind === "voice" && <span className="hw-bars" aria-hidden="true"><i /><i /><i /></span>}
      {kind === "secure" && <span className="hw-shine" aria-hidden="true" />}
      {kind === "report" && <span className="hw-scanline" aria-hidden="true" />}
    </span>
  );
}

export default function BrandPanel({ reduced, paused }) {
  const root = useRef(null);
  const frame = useRef(0);
  const move = (e) => {                                         // the light and the depth follow the pointer (a mouse only, one update per frame)
    if (reduced || e.pointerType === "touch" || !root.current) return;
    cancelAnimationFrame(frame.current);
    frame.current = requestAnimationFrame(() => {
      const el = root.current;
      if (!el) return;
      const r = el.getBoundingClientRect();
      const x = e.clientX - r.left - r.width / 2, y = e.clientY - r.top - r.height / 2;
      el.style.setProperty("--sx", x.toFixed(0));
      el.style.setProperty("--sy", y.toFixed(0));
      el.style.setProperty("--px", (x / r.width).toFixed(3));
      el.style.setProperty("--py", (y / r.height).toFixed(3));
    });
  };
  const rise = (n) => (reduced ? "" : `hw-rise hw-d${n}`);

  return (
    <aside ref={root} onPointerMove={move} aria-label="About HealthWise AI" className="relative flex h-full flex-col justify-center overflow-hidden bg-gradient-to-br from-brand-900 via-brand-800 to-sky-800 p-12 text-white">
      <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
        <div className={`absolute -left-[15%] -top-[10%] h-[28rem] w-[28rem] rounded-full bg-cyan-400/35 blur-3xl ${reduced ? "" : "hw-orb-a hw-loop"}`} />
        <div className={`absolute -bottom-[18%] -right-[12%] h-[32rem] w-[32rem] rounded-full bg-sky-500/35 blur-3xl ${reduced ? "" : "hw-orb-b hw-loop"}`} />
        <div className={`absolute left-[30%] top-[38%] h-[20rem] w-[20rem] rounded-full bg-teal-300/25 blur-3xl ${reduced ? "" : "hw-orb-c hw-loop"}`} />
        <div className={`absolute right-[22%] top-[8%] h-[16rem] w-[16rem] rounded-full bg-indigo-400/30 blur-3xl ${reduced ? "" : "hw-orb-d hw-loop"}`} />
        <div className="hw-grain absolute inset-0" />
        {!reduced && <div className="hw-spot absolute left-1/2 top-1/2 -ml-[19rem] -mt-[19rem] h-[38rem] w-[38rem] rounded-full" />}
        {TILES.map(([Icon, place, depth, motion, size], i) => (
          <span key={i} className={`absolute ${place} ${reduced ? "" : "hw-depth"}`} style={{ "--depth": depth }}>
            <span className={`hw-tile flex ${size} items-center justify-center rounded-3xl text-white/85 ${reduced ? "" : `${motion} hw-loop`}`} style={reduced ? undefined : { animationDelay: `${i * -2.1}s` }}><Icon size={26} /></span>
          </span>))}
      </div>

      <div className="relative z-10 max-w-xl">
        <LogoMark reduced={reduced} />
        <h1 className={`mt-6 text-5xl font-extrabold tracking-tight ${rise(1)}`}>HealthWise AI</h1>
        <p className="mt-5">
          <span className="sr-only">Understand your health reports, without the confusing medical language.</span>
          <span aria-hidden="true" className="block text-3xl font-bold leading-tight text-white xl:text-4xl">
            {LEAD.map((w, i) => <span key={w} className={reduced ? "mr-3 inline-block" : "hw-word mr-3"} style={{ "--i": i }}>{w}</span>)}
            <span className="hw-rot font-extrabold" data-static={reduced ? "true" : "false"}>
              {ROT.map((w, i) => <span key={w} style={{ "--i": i }} className="bg-gradient-to-r from-cyan-200 via-white to-sky-200 bg-clip-text text-transparent">{w}</span>)}
            </span>
          </span>
          <span aria-hidden="true" className={`mt-2 block text-lg text-brand-100 ${reduced ? "" : "hw-word"}`} style={{ "--i": 5 }}>without the confusing medical language.</span>
        </p>
        <Heartbeat reduced={reduced} paused={paused} className="my-5 h-32 w-full max-w-xl" />
        <ul className="space-y-3">
          {FEATURES.map(([kind, head, text], i) => (
            <li key={head} className={`hw-feature flex gap-4 rounded-2xl p-3.5 ${reduced ? "" : "hw-slide-in-left hw-stagger"}`} style={{ "--i": i + 2 }}>
              <FeatureIcon kind={kind} />
              <span><span className="block text-lg font-bold">{head}</span><span className="text-brand-100">{text}</span></span>
            </li>))}
        </ul>
        <div className={`hw-marquee-mask mt-6 ${rise(6)}`} role="group" aria-label="What the hospital system covers">
          <ul className={`hw-marquee ${reduced ? "" : "hw-loop"}`} data-static={reduced ? "true" : "false"}>
            {(reduced ? MODULES : [...MODULES, ...MODULES]).map((m, i) => <li key={m + i} aria-hidden={i >= MODULES.length ? "true" : undefined} className="hw-chip shrink-0 rounded-full bg-white/10 px-3.5 py-1.5 text-xs font-bold text-white ring-1 ring-white/20">{m}</li>)}
          </ul>
        </div>
        <div className="mt-6"><Trust reduced={reduced} /></div>
      </div>
    </aside>
  );
}
