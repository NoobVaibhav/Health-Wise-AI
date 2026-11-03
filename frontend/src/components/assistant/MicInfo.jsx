// "How the microphone works": the full privacy text of the voice features, one tap away behind a small (i) button. The text is the same one that is shown
// before the microphone is used for the first time (VOICE_NOTICE); here it can be read again at any time. A sheet that rises over the chat, closed with Escape or the button.
import { useEffect, useRef } from "react";
import { Info, X } from "lucide-react";
import { VOICE_NOTICE } from "../../utils/voice";

export function MicInfoButton({ onClick, open }) {
  return (
    <button type="button" onClick={onClick} aria-label="How the microphone works" aria-haspopup="dialog" aria-expanded={open} title="How the microphone works"
      className="grid h-11 w-11 shrink-0 place-items-center rounded-full text-slate-600 hover:bg-slate-100 focus-visible:outline focus-visible:outline-[3px] focus-visible:outline-brand-400">
      <Info size={20} aria-hidden="true" />
    </button>
  );
}

export default function MicInfo({ onClose }) {
  const close = useRef(null);
  useEffect(() => {
    close.current?.focus();
    const key = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", key);
    return () => document.removeEventListener("keydown", key);
  }, [onClose]);
  return (
    <div className="absolute inset-0 z-30 flex items-end bg-slate-900/30" onClick={onClose}>
      <div role="dialog" aria-label="How the microphone works" onClick={(e) => e.stopPropagation()} className="sheet-in max-h-[80%] w-full overflow-y-auto rounded-t-3xl bg-white p-5 shadow-2xl">
        <div className="flex items-start justify-between gap-3">
          <h3 className="text-lg font-extrabold text-slate-900">How the microphone works</h3>
          <button ref={close} type="button" onClick={onClose} aria-label="Close" className="grid h-11 w-11 shrink-0 place-items-center rounded-full text-slate-600 hover:bg-slate-100 focus-visible:outline focus-visible:outline-[3px] focus-visible:outline-brand-400"><X size={20} aria-hidden="true" /></button>
        </div>
        <p className="mt-2 text-base leading-relaxed text-slate-700">{VOICE_NOTICE}</p>
        <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-slate-600">
          <li>The round button starts a hands-free conversation: it listens, answers aloud and listens again.</li>
          <li>The small microphone next to the text box dictates one question.</li>
          <li>Typing always works, with or without a microphone.</li>
        </ul>
      </div>
    </div>
  );
}
