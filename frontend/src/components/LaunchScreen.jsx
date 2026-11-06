import { useCallback, useEffect, useId, useState } from "react";
import { createPortal } from "react-dom";
import { useAuth } from "../context/AuthContext";
import { MARK, WORDMARK } from "./brandPaths";
import "./launch.css";

// The launch screen: it covers the app only while it starts (the sign-in check, the first route), never longer, and never blocks.
//   first start of a session  the full sequence (about 1.4 s): the mark glows, the pulse traces, a ripple, then the name and the line of text
//   later in the same session a short fade of the logo (a reload, or coming back to the app)
//   reduced motion            the logo as a still picture with a 300 ms fade
//   always                    at least 1.2 s on the full sequence (so it never flashes), at most 4 s, a tap or key press skips it
// The first frame (brand colour and the mark in place) is also in index.html (#hw-launch), so nothing blank shows before this loads; it is removed here.
export const MIN_MS = 1200, CAP_MS = 4000, SEQUENCE_MS = 1500;
const MIN_BY_MODE = { full: MIN_MS, quick: 160, reduced: 300 };
const LEAVE_MS = { full: 360, quick: 200, reduced: 300 };
const SEEN = "hw_launch_seen";

const session = {
  seen: () => { try { return sessionStorage.getItem(SEEN) === "1"; } catch { return false; } },
  mark: () => { try { sessionStorage.setItem(SEEN, "1"); } catch { /* storage may be blocked: the full sequence then simply plays each start */ } },
};
const prefersReducedMotion = () => typeof window !== "undefined" && !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
const modeNow = () => (prefersReducedMotion() ? "reduced" : session.seen() ? "quick" : "full");

/** `ready` says the app has finished starting. Without it the screen leaves after the cap. */
export function LaunchScreen({ ready }) {
  const id = useId().replace(/:/g, "");
  const [mode] = useState(modeNow);
  const [phase, setPhase] = useState("intro");            // intro -> hold (waiting for the app) -> leaving -> gone
  const [start] = useState(() => (typeof performance !== "undefined" ? performance.now() : 0));

  const leave = useCallback(() => setPhase((p) => (p === "leaving" || p === "gone" ? p : "leaving")), []);

  // the static first frame from index.html hands over to this one (same colours, same mark size, same place); the app waits behind it
  useEffect(() => {
    document.documentElement.classList.add("hw-launching");
    const raf = requestAnimationFrame(() => requestAnimationFrame(() => document.getElementById("hw-launch")?.remove()));
    return () => cancelAnimationFrame(raf);
  }, []);

  // leave when the app is ready, but not before the minimum; and never later than the cap
  useEffect(() => {
    if (!ready) return undefined;
    const wait = Math.max(0, MIN_BY_MODE[mode] - (performance.now() - start));
    const t = setTimeout(leave, wait);
    return () => clearTimeout(t);
  }, [ready, mode, start, leave]);
  useEffect(() => { const t = setTimeout(leave, CAP_MS); return () => clearTimeout(t); }, [leave]);

  // after the sequence, if the app is still not ready: a calm breathing pulse, the sequence is never replayed
  useEffect(() => {
    if (mode !== "full") return undefined;
    const t = setTimeout(() => setPhase((p) => (p === "intro" ? "hold" : p)), SEQUENCE_MS);
    return () => clearTimeout(t);
  }, [mode]);

  // a tap or a key press skips it
  useEffect(() => {
    if (phase === "leaving" || phase === "gone") return undefined;
    const skip = () => leave();
    window.addEventListener("pointerdown", skip);
    window.addEventListener("keydown", skip);
    return () => { window.removeEventListener("pointerdown", skip); window.removeEventListener("keydown", skip); };
  }, [phase, leave]);

  // lifting: the app's own entrance animations are released, the flag is kept for the next start, and the screen is removed after its fade
  useEffect(() => {
    if (phase !== "leaving") return undefined;
    document.documentElement.classList.remove("hw-launching");
    session.mark();
    const t = setTimeout(() => setPhase("gone"), LEAVE_MS[mode] + 40);
    return () => clearTimeout(t);
  }, [phase, mode]);
  useEffect(() => () => document.documentElement.classList.remove("hw-launching"), []);

  if (phase === "gone" || typeof document === "undefined") return null;
  const ink = (n) => `${id}-${n}`;
  return createPortal(
    <div className="hw-launch" data-mode={mode} data-phase={phase} data-testid="launch-screen" {...(phase === "leaving" ? { "aria-hidden": "true" } : {})}>
      <div className="hw-l-aurora" aria-hidden="true"><i /><i /></div>
      <div className="hw-l-lines" aria-hidden="true" />
      <div className="hw-l-stage" aria-hidden="true">
        <span className="hw-l-glow" />
        <span className="hw-l-ring" />
        <svg className="hw-l-mark" viewBox="0 0 64 64" focusable="false">
          <defs>
            <mask id={ink("m")} maskUnits="userSpaceOnUse" x="0" y="0" width="64" height="64">
              <rect width="64" height="64" fill="#fff" />
              <path d={MARK.PULSE} fill="none" stroke="#000" strokeWidth="3.6" strokeLinecap="round" strokeLinejoin="round" />
              <circle cx="14.5" cy="32" r="3.1" fill="#000" />
              <circle cx="49.5" cy="32" r="3.1" fill="none" stroke="#000" strokeWidth="2.3" />
            </mask>
          </defs>
          <path d={MARK.HEART} fill="#fff" mask={`url(#${ink("m")})`} />
          <path className="hw-l-trace" d={MARK.PULSE} pathLength="1" strokeWidth="3.6" />
          <circle className="hw-l-nodeL" cx="14.5" cy="32" r="3.1" />
          <circle className="hw-l-nodeR" cx="49.5" cy="32" r="3.1" strokeWidth="2.3" />
        </svg>
        <svg className="hw-l-word" viewBox={`80 16 ${WORDMARK.width - 80} 36`} focusable="false">
          <path className="hw-l-w1" d={WORDMARK.parts[0]} fill="#fff" />
          <path className="hw-l-w2" d={WORDMARK.parts[1]} fill="#fff" />
          <path className="hw-l-w3" d={WORDMARK.parts[2]} fill="#fff" />
          <path className="hw-l-ai" d={WORDMARK.ai} fill="#22D3EE" />
          <g transform={`translate(${WORDMARK.width - 36} 32)`}>
            <path className="hw-l-spark" d="M0 -5.2C0.4 -1.4 1.4 -0.4 5.2 0C1.4 0.4 0.4 1.4 0 5.2C-0.4 1.4 -1.4 0.4 -5.2 0C-1.4 -0.4 -0.4 -1.4 0 -5.2Z" style={{ "--hw-sweep": "6px" }} />
          </g>
        </svg>
        <p className="hw-l-tag">Your health, clearly explained</p>
      </div>
      {phase !== "leaving" && <p role="status" className="sr-only">HealthWise AI, loading</p>}
    </div>,
    document.body,
  );
}

/** The screen wired to the app's start: it is ready when the sign-in check has finished. */
export default function LaunchGate() {
  const { loading } = useAuth();
  return <LaunchScreen ready={!loading} />;
}
