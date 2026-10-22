// Voice for the patient assistant, using the browser's own speech recognition and text-to-speech.
// Nothing here records or stores audio. The browser may send the audio to its speech provider (see VOICE_NOTICE).
// Every function is written so the chat keeps working by typing when voice is not available.

export const LANG_TAGS = { en: "en-IN", hi: "hi-IN", mr: "mr-IN" };
export const LANG_NAMES = { en: "English", hi: "हिन्दी", mr: "मराठी" };

export const VOICE_NOTICE =
  "When you use the microphone, your browser may send what you say to its speech service (for example Google for Chrome or Microsoft for Edge) to turn it into text. HealthWise AI does not record or keep your voice. You can always type instead.";

const win = () => (typeof window === "undefined" ? {} : window);

export const speechInputSupported = (w = win()) => Boolean(w.SpeechRecognition || w.webkitSpeechRecognition);
export const speechOutputSupported = (w = win()) => Boolean(w.speechSynthesis && w.SpeechSynthesisUtterance);

const ERROR_KIND = {
  "not-allowed": "denied",
  "service-not-allowed": "denied",
  "no-speech": "no-speech",
  "audio-capture": "no-microphone",
  network: "network",
  "language-not-supported": "language",
  aborted: "aborted",
};

export function voiceErrorMessage(kind) {
  switch (kind) {
    case "unsupported": return "Voice input is not available in this browser. Please type your question instead.";
    case "denied": return "The microphone is blocked. Allow microphone access in your browser's address bar, or type your question instead.";
    case "no-microphone": return "No microphone was found. Please type your question instead.";
    case "no-speech": return "I did not hear anything. Press the microphone and try again, or type your question.";
    case "network": return "Voice recognition needs an internet connection. Please type your question instead.";
    case "language": return "This browser cannot recognise that language by voice. Please type your question.";
    case "aborted": return "";
    default: return "Voice input did not work. Please type your question instead.";
  }
}

/** Starts listening. Returns { start, stop } or null if the browser has no speech recognition (the caller then falls back to typing). */
export function createListener({ lang = "en", onText, onError, onEnd }, w = win()) {
  const Recognition = w.SpeechRecognition || w.webkitSpeechRecognition;
  if (!Recognition) return null;
  const rec = new Recognition();
  rec.lang = LANG_TAGS[lang] || LANG_TAGS.en;
  rec.interimResults = true;
  rec.continuous = false;
  rec.maxAlternatives = 1;
  rec.onresult = (event) => {
    let text = "";
    let final = false;
    for (let i = 0; i < event.results.length; i += 1) {
      text += event.results[i][0].transcript;
      final = final || event.results[i].isFinal;
    }
    onText?.(text.trim(), final);
  };
  rec.onerror = (event) => onError?.(ERROR_KIND[event.error] || "other");
  rec.onend = () => onEnd?.();
  return {
    start: () => {
      try { rec.start(); } catch { onError?.("other"); }
    },
    stop: () => {
      try { rec.stop(); } catch { /* already stopped */ }
    },
  };
}

// ------------------------------------------------------------------ speaking
const SAY = [
  [/HbA1c/gi, "H b A one C"], [/\bLDL\b/g, "L D L"], [/\bHDL\b/g, "H D L"], [/\bVLDL\b/g, "V L D L"], [/\bTSH\b/g, "T S H"], [/\bECG\b/g, "E C G"],
  [/\bALT\b/g, "A L T"], [/\bAST\b/g, "A S T"], [/\bBUN\b/g, "B U N"], [/\beGFR\b/g, "e G F R"],
  [/mg\/dL/gi, "milligrams per decilitre"], [/ng\/mL/gi, "nanograms per millilitre"], [/g\/dL/gi, "grams per decilitre"], [/mmol\/L/gi, "millimoles per litre"],
  [/µg|μg|mcg/gi, "micrograms"], [/\bmg\b/gi, "milligrams"], [/\bml\b/gi, "millilitres"],
];

/** Text for the voice: no bullet marks or brackets noise, medical abbreviations spelled out (English only), and not too long. */
export function speakableText(text, lang = "en", limit = 900) {
  let t = (text || "").replace(/[••*_#>]/g, " ").replace(/\s*\n+\s*/g, ". ").replace(/\.\s*\./g, ".").replace(/\s+/g, " ").trim();
  if (lang === "en") for (const [pattern, spoken] of SAY) t = t.replace(pattern, spoken);
  if (t.length > limit) {
    const cut = t.slice(0, limit);
    t = cut.slice(0, Math.max(cut.lastIndexOf(". "), 200)) + ". The rest is in the written answer.";
  }
  return t;
}

/** The installed voice for a language, or null (then the browser would read it with the wrong accent, so we tell the patient). */
export function pickVoice(lang, w = win()) {
  const tag = (LANG_TAGS[lang] || "en-IN").toLowerCase();
  const voices = w.speechSynthesis?.getVoices?.() || [];
  return voices.find((v) => v.lang.toLowerCase() === tag) || voices.find((v) => v.lang.toLowerCase().startsWith(tag.slice(0, 2))) || null;
}

/** play / pause / resume / stop. state: idle | speaking | paused. */
export function createSpeaker({ onState, onProblem } = {}, w = win()) {
  const synth = w.speechSynthesis;
  const supported = Boolean(synth && w.SpeechSynthesisUtterance);
  let state = "idle";
  const set = (s) => { state = s; onState?.(s); };
  return {
    supported,
    get state() { return state; },
    speak(text, { lang = "en", rate = 1 } = {}) {
      if (!supported) { onProblem?.("Reading aloud is not available in this browser."); return false; }
      synth.cancel();
      const said = speakableText(text, lang);
      if (!said) return false;
      const utterance = new w.SpeechSynthesisUtterance(said);
      utterance.lang = LANG_TAGS[lang] || LANG_TAGS.en;
      utterance.rate = Math.min(1.5, Math.max(0.6, rate));
      const voice = pickVoice(lang, w);
      if (voice) utterance.voice = voice;
      else if (lang !== "en") onProblem?.(`No ${LANG_NAMES[lang]} voice is installed on this device, so the answer may not be read correctly. You can read the text instead.`);
      utterance.onend = () => set("idle");
      utterance.onerror = () => set("idle");
      set("speaking");
      synth.speak(utterance);
      return true;
    },
    pause() { if (supported && state === "speaking") { synth.pause(); set("paused"); } },
    resume() { if (supported && state === "paused") { synth.resume(); set("speaking"); } },
    stop() { if (supported) { synth.cancel(); set("idle"); } },
  };
}
