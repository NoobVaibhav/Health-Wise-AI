// The voice part of Ask HealthWise: one round button (the orb) that starts a hands-free conversation, what is being heard or said,
// and the voice settings. One slim strip on every screen size, so the answers keep the room. All state lives in AssistantChat; this only shows it.
import { useEffect, useRef } from "react";
import { Ear, Mic, RotateCcw, Settings2, Square, Volume2 } from "lucide-react";

const STATES = {
  idle: { label: "Tap and talk to me", hint: "Hands-free: I listen, answer aloud, and listen again.", color: "from-brand-600 to-brand-800", tint: "" },
  listening: { label: "Listening...", hint: "Speak now. Say \"stop\" or tap to finish.", color: "from-rose-600 to-red-700", tint: "bg-rose-50" },
  hearing: { label: "I can hear you...", hint: "Keep going. I wait until you stop.", color: "from-rose-600 to-red-700", tint: "bg-rose-50" },
  thinking: { label: "Looking through your records...", hint: "", color: "from-amber-500 to-orange-600", tint: "bg-amber-50" },
  speaking: { label: "Speaking...", hint: "Tap to interrupt and ask something else.", color: "from-emerald-600 to-teal-700", tint: "bg-emerald-50" },
  error: { label: "That did not work", hint: "Tap to try again, or type your question.", color: "from-slate-600 to-slate-800", tint: "bg-slate-100" },
};
const LISTENING = ["listening", "hearing"];

function Orb({ state, onClick, disabled }) {
  const s = STATES[state];
  const Icon = LISTENING.includes(state) ? Square : state === "speaking" ? Volume2 : Mic;
  const name = state === "idle" ? "Start talking with HealthWise" : LISTENING.includes(state) ? "Stop listening" : state === "speaking" ? "Interrupt and ask something else" : state === "error" ? "Try talking again" : "Thinking";
  return (
    <span className="relative inline-flex h-12 w-12 shrink-0 sm:h-16 sm:w-16">
      {state !== "thinking" && <span className={`orb-ring orb-ring-${state}`} aria-hidden="true" />}
      <button type="button" onClick={onClick} disabled={disabled} aria-label={name} data-state={state}
        className={`voice-orb voice-orb-${state} relative flex h-full w-full items-center justify-center rounded-full bg-gradient-to-br text-white shadow-md focus:outline-none focus-visible:ring-4 focus-visible:ring-brand-300 disabled:cursor-wait ${s.color}`}>
        <Icon size={26} aria-hidden="true" />
        {(LISTENING.includes(state) || state === "speaking") && <span className="voice-bars" aria-hidden="true"><i /><i /><i /><i /><i /></span>}
      </button>
    </span>
  );
}

export default function VoicePanel({
  state, compact, failed, heard, level, onOrb, onReplay, canReplay, inputOk, outputOk, handsFree, wakeOn, onWake, wakeSupported,
  voices, voiceName, onVoice, autoRead, onAutoRead, sounds, onSounds, rate, onRate, pitch, onPitch, pauseMs, onPause, pauseSupported,
  confirmBeforeSend, onConfirmBeforeSend, privateMode, onPrivateMode, bargeIn, onBargeIn, autoLang, onAutoLang,
}) {
  const s = STATES[state];
  const menu = useRef(null);
  // the settings close when you tap anywhere else or press Escape, so they never stay open over the chat
  useEffect(() => {
    const close = (e) => {
      const d = menu.current;
      if (!d?.open) return;
      if (e.type === "keydown" ? e.key === "Escape" : !d.contains(e.target)) d.open = false;
    };
    document.addEventListener("pointerdown", close);
    document.addEventListener("keydown", close);
    return () => { document.removeEventListener("pointerdown", close); document.removeEventListener("keydown", close); };
  }, []);
  return (
    <div className={`relative shrink-0 border-b border-slate-100 px-3 py-1.5 transition-colors sm:px-5 sm:py-2 ${failed && state === "idle" ? "bg-slate-100" : s.tint || "bg-slate-50/60"}`}>
      <p className="sr-only" aria-live="polite">{failed && state === "idle" ? "Something went wrong. You can tap the round button to try again, or type." : ""}</p>
      <div className="flex items-center gap-3">
        <Orb state={state} onClick={onOrb} disabled={state === "thinking"} />
        <div className="min-w-0 flex-1" aria-live="polite">
          <p className="text-sm font-extrabold leading-snug text-slate-900 sm:text-lg">{s.label}</p>
          <p className={`line-clamp-2 text-sm leading-snug text-slate-600 [@media(max-height:32rem)]:hidden ${compact && state === "idle" ? "hidden sm:block" : ""}`}>
            {LISTENING.includes(state) && heard ? <span className="font-semibold text-slate-800">&ldquo;{heard}&rdquo;</span> : (handsFree && state === "idle" ? "" : s.hint)}
            {!inputOk && state === "idle" && "Voice input is not available in this browser, but you can type and listen to answers."}
          </p>
          {LISTENING.includes(state) && typeof level === "number" && (
            <span role="meter" aria-label="Microphone level" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(level * 100)} className="mt-1 block h-1.5 w-32 max-w-full overflow-hidden rounded-full bg-rose-100">
              <i className="block h-full rounded-full bg-rose-500 transition-[width] duration-100" style={{ width: `${Math.max(4, Math.round(level * 100))}%` }} />
            </span>)}
          {handsFree && <p className="mt-1 inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-bold text-emerald-900">Hands-free conversation is on</p>}
          {wakeOn && !handsFree && <p className="mt-1 inline-flex items-center gap-1 rounded-full bg-violet-100 px-2.5 py-0.5 text-xs font-bold text-violet-900"><Ear size={12} aria-hidden="true" /> Waiting for &ldquo;Hey HealthWise&rdquo;</p>}
        </div>
        {canReplay && state === "idle" && (
          <button type="button" onClick={onReplay} aria-label="Hear the last answer again" title="Hear the last answer again"
            className="grid h-11 w-11 shrink-0 place-items-center rounded-xl border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 focus-visible:outline focus-visible:outline-[3px] focus-visible:outline-brand-400"><RotateCcw size={18} aria-hidden="true" /></button>)}
        <details ref={menu} className="shrink-0 sm:static">
          <summary aria-label="Voice settings" title="Voice settings" className="flex h-11 min-w-11 cursor-pointer list-none items-center justify-center gap-1.5 rounded-xl border border-slate-300 bg-white px-0 text-sm font-semibold text-slate-700 hover:bg-slate-50 sm:px-3">
            <Settings2 size={18} aria-hidden="true" /><span className="hidden sm:inline">Voice settings</span>
          </summary>
          <div className="absolute right-3 top-full z-20 mt-1 max-h-[60dvh] w-[min(20rem,calc(100vw-2rem))] space-y-3 overflow-y-auto overscroll-contain rounded-2xl border border-slate-200 bg-white p-4 text-sm shadow-sheet">
            {outputOk && (
              <>
                <label className="block font-semibold text-slate-700">Voice
                  <select value={voiceName} onChange={(e) => onVoice(e.target.value)} className="mt-1 h-11 w-full rounded-xl border border-slate-300 bg-white px-2 text-base">
                    <option value="">Best available</option>
                    {voices.filter((v) => v.name).map((v) => <option key={v.name} value={v.name}>{v.name}</option>)}
                  </select>
                </label>
                <label className="block font-semibold text-slate-700">Speed
                  <select value={rate} onChange={(e) => onRate(Number(e.target.value))} className="mt-1 h-11 w-full rounded-xl border border-slate-300 bg-white px-2 text-base">
                    <option value={0.8}>Slow</option><option value={1}>Normal</option><option value={1.25}>Fast</option>
                  </select>
                </label>
                <label className="block font-semibold text-slate-700">Voice pitch
                  <select value={pitch} onChange={(e) => onPitch(Number(e.target.value))} className="mt-1 h-11 w-full rounded-xl border border-slate-300 bg-white px-2 text-base">
                    <option value={0.85}>Lower</option><option value={1}>Normal</option><option value={1.15}>Higher</option>
                  </select>
                </label>
                <label className="flex min-h-11 items-center gap-2.5 text-slate-700"><input type="checkbox" checked={autoRead} onChange={(e) => onAutoRead(e.target.checked)} className="h-5 w-5 shrink-0" /> Read every answer aloud, also when I type</label>
                <label className="flex min-h-11 items-start gap-2.5 text-slate-700"><input type="checkbox" checked={privateMode} onChange={(e) => onPrivateMode(e.target.checked)} className="mt-0.5 h-5 w-5 shrink-0" /> <span>Private mode: show the answer on the screen and read only a short note, so people nearby do not hear your health details</span></label>
              </>
            )}
            <label className="flex min-h-11 items-center gap-2.5 text-slate-700"><input type="checkbox" checked={sounds} onChange={(e) => onSounds(e.target.checked)} className="h-5 w-5 shrink-0" /> Play a small sound when I can speak</label>
            {inputOk && pauseSupported && (
              <label className="block font-semibold text-slate-700">Wait after I stop talking
                <select value={pauseMs} onChange={(e) => onPause(Number(e.target.value))} className="mt-1 h-11 w-full rounded-xl border border-slate-300 bg-white px-2 text-base">
                  <option value={0}>Normal (the browser decides)</option><option value={1800}>Wait a little longer</option><option value={3000}>Wait much longer (I speak slowly)</option>
                </select>
              </label>
            )}
            {inputOk && <label className="flex min-h-11 items-center gap-2.5 text-slate-700"><input type="checkbox" checked={confirmBeforeSend} onChange={(e) => onConfirmBeforeSend(e.target.checked)} className="h-5 w-5 shrink-0" /> Show what I said first, and let me check it before it is sent</label>}
            {inputOk && <label className="flex min-h-11 items-start gap-2.5 text-slate-700"><input type="checkbox" checked={autoLang} onChange={(e) => onAutoLang(e.target.checked)} className="mt-0.5 h-5 w-5 shrink-0" /> <span>Choose the answer language from what I say (Hindi and English mixed is understood)</span></label>}
            {inputOk && outputOk && <label className="flex min-h-11 items-start gap-2.5 text-slate-700"><input type="checkbox" checked={bargeIn} onChange={(e) => onBargeIn(e.target.checked)} className="mt-0.5 h-5 w-5 shrink-0" /> <span>Let me interrupt by talking. Use headphones: on a speaker the assistant would hear itself.</span></label>}
            {wakeSupported && (
              <label className="flex min-h-11 items-center gap-2.5 text-slate-700">
                <input type="checkbox" checked={wakeOn} onChange={(e) => onWake(e.target.checked)} className="h-5 w-5 shrink-0" />
                <span>Say &ldquo;Hey HealthWise&rdquo; to start (beta). The microphone stays on while this page is open, and your browser may send the sound to its speech service.</span>
              </label>
            )}
            <p className="border-t border-slate-100 pt-2 text-xs text-slate-600">You can say: &ldquo;stop&rdquo;, &ldquo;repeat&rdquo;, &ldquo;tell me more&rdquo;, &ldquo;speak slower&rdquo;, &ldquo;switch to Hindi&rdquo;, &ldquo;brief me&rdquo; or &ldquo;open my reports&rdquo;.</p>
          </div>
        </details>
      </div>
    </div>
  );
}
