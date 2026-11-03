// The voice part of Ask HealthWise: one big animated button (the orb) that starts a hands-free conversation, what is being heard or said,
// and the voice settings. All state lives in AssistantChat; this only shows it.
import { Ear, Mic, Settings2, Square, Volume2 } from "lucide-react";

const STATES = {
  idle: { label: "Tap and talk to me", hint: "Hands-free: I listen, answer aloud, and listen again.", color: "from-brand-500 to-brand-700" },
  listening: { label: "Listening...", hint: "Speak now. Say \"stop\" or tap to finish.", color: "from-rose-500 to-red-600" },
  thinking: { label: "Looking through your records...", hint: "", color: "from-amber-400 to-orange-500" },
  speaking: { label: "Speaking...", hint: "Tap to interrupt and ask something else.", color: "from-emerald-500 to-teal-600" },
};

function Orb({ state, onClick, disabled }) {
  const s = STATES[state];
  const Icon = state === "listening" ? Square : state === "speaking" ? Volume2 : Mic;
  const name = state === "idle" ? "Start talking with HealthWise" : state === "listening" ? "Stop listening" : state === "speaking" ? "Interrupt and ask something else" : "Thinking";
  return (
    <button type="button" onClick={onClick} disabled={disabled} aria-label={name} data-state={state}
      className={`voice-orb voice-orb-${state} relative flex h-16 w-16 shrink-0 sm:h-20 sm:w-20 items-center justify-center rounded-full bg-gradient-to-br text-white shadow-lg focus:outline-none focus-visible:ring-4 focus-visible:ring-brand-300 disabled:cursor-wait ${s.color}`}>
      <Icon size={30} />
      {(state === "listening" || state === "speaking") && <span className="voice-bars" aria-hidden="true"><i /><i /><i /><i /><i /></span>}
    </button>
  );
}

export default function VoicePanel({
  state, heard, onOrb, inputOk, outputOk, handsFree, wakeOn, onWake, wakeSupported,
  voices, voiceName, onVoice, autoRead, onAutoRead, sounds, onSounds, rate, onRate,
}) {
  const s = STATES[state];
  return (
    <div className="relative border-b border-slate-100 bg-gradient-to-b from-slate-50 to-white px-4 pb-3 pt-3 sm:px-5">
      {/* phone: the orb on top, its words under it, centred; from sm up: the orb and its words side by side */}
      <div className="flex flex-col items-center gap-2 text-center sm:flex-row sm:gap-4 sm:text-left">
        <Orb state={state} onClick={onOrb} disabled={state === "thinking"} />
        <div className="min-w-0 max-w-full flex-1" aria-live="polite">
          <p className="text-base font-extrabold leading-snug text-slate-900 sm:text-lg">{s.label}</p>
          <p className="line-clamp-2 text-sm leading-snug text-slate-600">
            {state === "listening" && heard ? <span className="font-semibold text-slate-800">&ldquo;{heard}&rdquo;</span> : (handsFree && state === "idle" ? "" : s.hint)}
            {!inputOk && state === "idle" && "Voice input is not available in this browser, but you can type and listen to answers."}
          </p>
          {handsFree && <p className="mt-1 inline-flex items-center gap-1 rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-bold text-emerald-800">Hands-free conversation is on</p>}
          {wakeOn && !handsFree && <p className="mt-1 inline-flex items-center gap-1 rounded-full bg-violet-100 px-2.5 py-0.5 text-xs font-bold text-violet-800"><Ear size={12} /> Waiting for &ldquo;Hey HealthWise&rdquo;</p>}
        </div>
        <details className="absolute right-3 top-3 sm:static sm:shrink-0">
          <summary aria-label="Voice settings" title="Voice settings" className="flex h-11 min-w-11 cursor-pointer list-none items-center justify-center gap-1.5 rounded-xl border border-slate-300 bg-white px-0 text-sm font-semibold text-slate-700 hover:bg-slate-50 focus-visible:outline focus-visible:outline-[3px] focus-visible:outline-brand-400 sm:px-3">
            <Settings2 size={18} aria-hidden="true" /><span className="hidden sm:inline">Voice settings</span>
          </summary>
          <div className="absolute right-0 z-20 mt-2 max-h-[70dvh] w-[min(20rem,calc(100vw-2rem))] space-y-3 overflow-y-auto rounded-2xl border border-slate-200 bg-white p-4 text-sm shadow-xl">
            {outputOk && (
              <>
                <label className="block font-semibold text-slate-700">Voice
                  <select value={voiceName} onChange={(e) => onVoice(e.target.value)} className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-2 py-1.5 text-base">
                    <option value="">Best available</option>
                    {voices.filter((v) => v.name).map((v) => <option key={v.name} value={v.name}>{v.name}</option>)}
                  </select>
                </label>
                <label className="block font-semibold text-slate-700">Speed
                  <select value={rate} onChange={(e) => onRate(Number(e.target.value))} className="mt-1 w-full rounded-xl border border-slate-300 bg-white px-2 py-1.5 text-base">
                    <option value={0.8}>Slow</option><option value={1}>Normal</option><option value={1.25}>Fast</option>
                  </select>
                </label>
                <label className="flex items-start gap-2 text-slate-700"><input type="checkbox" checked={autoRead} onChange={(e) => onAutoRead(e.target.checked)} className="mt-1 h-4 w-4" /> Read every answer aloud, also when I type</label>
              </>
            )}
            <label className="flex items-start gap-2 text-slate-700"><input type="checkbox" checked={sounds} onChange={(e) => onSounds(e.target.checked)} className="mt-1 h-4 w-4" /> Play a small sound when I can speak</label>
            {wakeSupported && (
              <label className="flex items-start gap-2 text-slate-700">
                <input type="checkbox" checked={wakeOn} onChange={(e) => onWake(e.target.checked)} className="mt-1 h-4 w-4" />
                <span>Say &ldquo;Hey HealthWise&rdquo; to start (beta). The microphone stays on while this page is open, and your browser may send the sound to its speech service.</span>
              </label>
            )}
            <p className="border-t border-slate-100 pt-2 text-xs text-slate-500">You can say: &ldquo;stop&rdquo;, &ldquo;repeat&rdquo;, &ldquo;speak slower&rdquo;, &ldquo;switch to Hindi&rdquo;, &ldquo;brief me&rdquo; or &ldquo;open my reports&rdquo;.</p>
          </div>
        </details>
      </div>
    </div>
  );
}
