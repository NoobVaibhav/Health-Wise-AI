// Voice for the patient assistant, using the browser's own speech recognition and text-to-speech. No paid service and no API key is used.
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
    case "denied": return win().Capacitor?.isNativePlatform?.()
      ? "The microphone is blocked. Open your phone's Settings, then Apps, HealthWise AI, Permissions, and allow Microphone, or type your question instead."
      : "The microphone is blocked. Allow microphone access in your browser's address bar, or type your question instead.";
    case "no-microphone": return "No microphone was found. Please type your question instead.";
    case "no-speech": return "I did not hear anything. Press the microphone and try again, or type your question.";
    case "network": return "Voice recognition needs an internet connection. Please type your question instead.";
    case "language": return "This browser cannot recognise that language by voice. Please type your question.";
    case "aborted": return "";
    default: return "Voice input did not work. Please type your question instead.";
  }
}

// ------------------------------------------------------------------ listening
/** Starts listening. Returns { start, stop, abort } or null if the browser has no speech recognition (the caller then falls back to typing).
 *  onText(text, isFinal) gets the words as they are recognised; the last call has isFinal = true. */
export function createListener({ lang = "en", continuous = false, onText, onError, onEnd, onStart }, w = win()) {
  const Recognition = w.SpeechRecognition || w.webkitSpeechRecognition;
  if (!Recognition) return null;
  const rec = new Recognition();
  rec.lang = LANG_TAGS[lang] || LANG_TAGS.en;
  rec.interimResults = true;
  rec.continuous = continuous;
  rec.maxAlternatives = 1;
  rec.onstart = () => onStart?.();
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
    abort: () => {
      try { (rec.abort || rec.stop).call(rec); } catch { /* already stopped */ }
    },
  };
}

// "Hey HealthWise": the name WITH a greeting before it (English, Hindi and Marathi spellings). The name alone is not enough: people say "health wise"
// in ordinary talk ("being health wise is important") and that must not switch the microphone on.
const WAKE = /(?:^|\s)(?:hey|hi|hello|ok|okay|हे|हाय|हेलो|ओके)\s+(?:health\s?wise|हेल्थ\s?वाइज़?|हेल्थ\s?वाईज|हेल्थवाइज)/i;

/** Text after the wake phrase ("hey healthwise what medicines am I taking" gives "what medicines am I taking"), or null when it was not said. */
export function afterWakePhrase(text) {
  const m = WAKE.exec(text || "");
  return m ? text.slice(m.index + m[0].length).replace(/^[\s,.:;!-]+/, "").trim() : null;
}

/** Listens quietly for the wake phrase and calls onWake(restOfTheSentence). Chrome ends a long listening session by itself, so it restarts
 *  until stop() is called. It only runs on the page where the person switched it on, and never keeps what it hears. */
export function createWakeListener({ lang = "en", onWake, onError }, w = win()) {
  let active = false;
  let listener = null;
  let heard = false;
  let restarts = 0;
  const begin = () => {
    if (!active) return;
    heard = false;
    listener = createListener({
      lang,
      continuous: true,
      onText: (text, final) => {
        const rest = afterWakePhrase(text);
        if (rest === null || heard) return;
        if (rest && !final) return;                 // wait until the sentence is finished, then use all of it
        heard = true;
        active = false;
        listener?.abort();
        onWake?.(rest);
      },
      onError: (kind) => {
        if (kind === "denied" || kind === "no-microphone" || kind === "language") { active = false; onError?.(kind); }
      },
      onEnd: () => {
        if (!active || heard) return;
        restarts += 1;
        setTimeout(begin, Math.min(2000, 150 * restarts));      // a short pause that grows a little, so a failing microphone is not hammered
      },
      onStart: () => { restarts = 0; },
    }, w);
    if (!listener) { active = false; onError?.("unsupported"); return; }
    listener.start();
  };
  return {
    start() { if (!active) { active = true; begin(); } },
    stop() { active = false; listener?.abort(); },
  };
}

// ------------------------------------------------------------------ spoken commands
const COMMANDS = [
  ["stop", /^(?:ok(?:ay)?\s+)?(?:stop|cancel|quiet|be quiet|stop talking|stop reading|shut up|enough|रुको|रुकिए|चुप|बंद करो|बस करो|थांबा|गप्प|बस)(?:\s+please)?$/i],
  ["repeat", /^(?:please\s+)?(?:repeat(?:\s+that)?|say\s+(?:that\s+)?again|once more|what did you say|read\s+(?:that\s+)?again|फिर से बोलो|दोबारा बोलो|फिर से सुनाओ|पुन्हा सांग|परत सांग|पुन्हा वाचा)$/i],
  ["slower", /^(?:please\s+)?(?:speak\s+|talk\s+)?(?:slower|slowly|slow down|धीरे बोलो|धीमे बोलो|हळू बोला|हळू)(?:\s+please)?$/i],
  ["faster", /^(?:please\s+)?(?:speak\s+|talk\s+)?(?:faster|quicker|speed up|तेज़ बोलो|तेज बोलो|वेगाने बोला|जलद बोला)(?:\s+please)?$/i],
  ["clear", /^(?:please\s+)?(?:clear(?:\s+the)?\s+chat|start over|new chat|चैट साफ़ करो|चैट साफ करो|चॅट साफ करा)$/i],
  ["exit", /^(?:stop listening|that'?s all|that is all|i am done|no more|बस इतना|मैं हो गया|एवढेच)$/i],
];
/** "yes" in English, Hindi and Marathi, for questions the assistant asks before it does something that cannot be undone. */
export const isYes = (text) => /^(?:yes|yeah|yep|yup|sure|ok|okay|confirm|do it|haan|han|हाँ|हां|जी|जी हाँ|ठीक है|हो|होय|हा)[\s.!]*$/i.test(String(text || "").trim());

const LANGUAGE_WORDS = { english: "en", "अंग्रेज़ी": "en", "अंग्रेजी": "en", इंग्लिश: "en", hindi: "hi", "हिंदी": "hi", "हिन्दी": "hi", marathi: "mr", "मराठी": "mr" };
const LANGUAGE_COMMAND = /^(?:please\s+)?(?:speak\s+(?:in\s+)?|talk\s+(?:in\s+)?|switch\s+to\s+|change\s+(?:the\s+)?language\s+to\s+|answer\s+in\s+)?(english|hindi|marathi|अंग्रेज़ी|अंग्रेजी|इंग्लिश|हिंदी|हिन्दी|मराठी)(?:\s+please)?$/i;

/** A whole spoken sentence that is a command for the voice itself ("stop", "repeat", "speak slower", "switch to Hindi"), or null for a question. */
export function matchVoiceCommand(text) {
  const t = String(text || "").trim().replace(/[.!?,]+$/g, "").trim();
  if (!t || t.split(/\s+/).length > 6) return null;
  const lang = LANGUAGE_COMMAND.exec(t);
  if (lang) return { type: "language", value: LANGUAGE_WORDS[lang[1].toLowerCase()] || LANGUAGE_WORDS[lang[1]] };
  for (const [type, pattern] of COMMANDS) if (pattern.test(t)) return { type };
  return null;
}

// ------------------------------------------------------------------ small sounds (made by the browser, no files)
let audioContext = null;
/** A short tone: "start" when listening begins, "done" when it ends, "error" when something went wrong. Silent if the browser blocks sound. */
export function cue(kind, w = win()) {
  try {
    const Ctx = w.AudioContext || w.webkitAudioContext;
    if (!Ctx) return;
    audioContext = audioContext || new Ctx();
    const tone = { start: [660, 880], done: [880, 660], error: [300, 220] }[kind] || [660, 660];
    const now = audioContext.currentTime;
    const gain = audioContext.createGain();
    gain.gain.setValueAtTime(0.0001, now);
    gain.gain.exponentialRampToValueAtTime(0.08, now + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, now + 0.22);
    gain.connect(audioContext.destination);
    tone.forEach((freq, i) => {
      const osc = audioContext.createOscillator();
      osc.type = "sine";
      osc.frequency.setValueAtTime(freq, now + i * 0.09);
      osc.connect(gain);
      osc.start(now + i * 0.09);
      osc.stop(now + i * 0.09 + 0.1);
    });
  } catch { /* sound is only a hint: the screen shows the same state */ }
}

// ------------------------------------------------------------------ speaking
const SAY = [
  [/HbA1c/gi, "H b A one C"], [/\bLDL\b/g, "L D L"], [/\bHDL\b/g, "H D L"], [/\bVLDL\b/g, "V L D L"], [/\bTSH\b/g, "T S H"], [/\bECG\b/g, "E C G"],
  [/\bALT\b/g, "A L T"], [/\bAST\b/g, "A S T"], [/\bBUN\b/g, "B U N"], [/\beGFR\b/g, "e G F R"], [/\bLVEF\b/g, "L V E F"], [/\bTMT\b/g, "T M T"],
  [/\bCT\b/g, "C T"], [/\bMRI\b/g, "M R I"], [/\bRBC\b/g, "R B C"], [/\bWBC\b/g, "W B C"], [/\bPSA\b/g, "P S A"],
  [/mg\/dL/gi, "milligrams per decilitre"], [/ng\/mL/gi, "nanograms per millilitre"], [/g\/dL/gi, "grams per decilitre"], [/mmol\/L/gi, "millimoles per litre"],
  [/µg|μg|mcg/gi, "micrograms"], [/\bmg\b/gi, "milligrams"], [/\bml\b/gi, "millilitres"], [/\bbpm\b/gi, "beats per minute"], [/\bmmHg\b/g, "millimetres of mercury"],
  [/(\d)\s*%/g, "$1 percent"],
];

/** Text for the voice: no bullet marks, medical abbreviations spelled out (English only), and not too long. */
export function speakableText(text, lang = "en", limit = 900) {
  let t = (text || "").replace(/[••*_#>]/g, " ").replace(/:\s*\n+\s*/g, ": ").replace(/\s*\n+\s*/g, ". ").replace(/\.\s*\./g, ".").replace(/\s+/g, " ").trim();
  if (lang === "en") for (const [pattern, spoken] of SAY) t = t.replace(pattern, spoken);
  if (t.length > limit) {
    const cut = t.slice(0, limit);
    t = cut.slice(0, Math.max(cut.lastIndexOf(". "), 200)) + ". The rest is in the written answer.";
  }
  return t;
}

/** The text cut into short pieces at the ends of sentences. Long text in one piece is cut off by Chrome after about 15 seconds. */
export function speechChunks(text, max = 180) {
  const sentences = String(text).match(/[^.!?।]+[.!?।]*\s*/g) || [String(text)];
  const chunks = [];
  let current = "";
  for (const sentence of sentences) {
    if (current && (current + sentence).length > max) { chunks.push(current.trim()); current = ""; }
    if (sentence.length > max) {                                   // one very long sentence: cut at a comma or a space
      for (const part of sentence.match(new RegExp(`.{1,${max}}(?:[,;\\s]|$)`, "g")) || [sentence]) chunks.push(part.trim());
    } else current += sentence;
  }
  if (current.trim()) chunks.push(current.trim());
  return chunks.filter(Boolean);
}

const NATURAL = /natural|neural|online|premium|enhanced/i;
const rank = (v) => (NATURAL.test(v.name || "") ? 0 : /google/i.test(v.name || "") ? 1 : v.localService === false ? 2 : 3);

/** All installed voices for a language, the most natural sounding first (the "Natural" and "Online" voices of Edge, then Google's, then the rest). */
export function voicesFor(lang, w = win()) {
  const tag = (LANG_TAGS[lang] || "en-IN").toLowerCase();
  const all = w.speechSynthesis?.getVoices?.() || [];
  const exact = all.filter((v) => (v.lang || "").toLowerCase() === tag);
  const same = all.filter((v) => (v.lang || "").toLowerCase().startsWith(tag.slice(0, 2)) && !exact.includes(v));
  return [...exact.sort((a, b) => rank(a) - rank(b)), ...same.sort((a, b) => rank(a) - rank(b))];     // the right accent first, then the nicest voice of it
}

/** The chosen voice if it is still installed for this language, otherwise the most natural one, or null (the person is then told). */
export function pickVoice(lang, w = win(), preferred = "") {
  const list = voicesFor(lang, w);
  return list.find((v) => v.name && v.name === preferred) || list[0] || null;
}

/** play / pause / resume / stop. state: idle | speaking | paused. speak() reads the text sentence by sentence; onEnd runs when it has all been read
 *  (not when it was stopped). */
export function createSpeaker({ onState, onProblem } = {}, w = win()) {
  const synth = w.speechSynthesis;
  const supported = Boolean(synth && w.SpeechSynthesisUtterance);
  let state = "idle";
  let run = 0;                                         // a new speak() or a stop() ends the earlier reading
  const set = (s) => { state = s; onState?.(s); };
  return {
    supported,
    get state() { return state; },
    speak(text, { lang = "en", rate = 1, pitch = 1, voiceName = "", onEnd } = {}) {
      if (!supported) { onProblem?.("Reading aloud is not available in this browser."); return false; }
      synth.cancel();
      const said = speakableText(text, lang);
      if (!said) return false;
      const chunks = speechChunks(said);
      const voice = pickVoice(lang, w, voiceName);
      if (!voice && lang !== "en") onProblem?.(`No ${LANG_NAMES[lang]} voice is installed on this device, so the answer may not be read correctly. You can read the text instead.`);
      const mine = (run += 1);
      const next = (i) => {
        if (mine !== run) return;
        if (i >= chunks.length) { set("idle"); onEnd?.(); return; }
        const utterance = new w.SpeechSynthesisUtterance(chunks[i]);
        utterance.lang = LANG_TAGS[lang] || LANG_TAGS.en;
        utterance.rate = Math.min(1.5, Math.max(0.6, rate));
        utterance.pitch = pitch;
        if (voice) utterance.voice = voice;
        utterance.onend = () => next(i + 1);
        utterance.onerror = (e) => { if (mine === run && e?.error !== "canceled" && e?.error !== "interrupted") set("idle"); };
        synth.speak(utterance);
      };
      set("speaking");
      next(0);
      return true;
    },
    pause() { if (supported && state === "speaking") { synth.pause(); set("paused"); } },
    resume() { if (supported && state === "paused") { synth.resume(); set("speaking"); } },
    stop() { run += 1; if (supported) { synth.cancel(); set("idle"); } },
  };
}
