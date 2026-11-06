// Voice for the patient assistant, using the browser's own speech recognition and text-to-speech. No paid service and no API key is used.
// Nothing here records or stores audio. The browser may send the audio to its speech provider (see VOICE_NOTICE).
// Every function is written so the chat keeps working by typing when voice is not available.
import { speechText } from "./voiceText";

export { CONFIRM_TEXT, applyUnits, correctMedicalTerms, isNo, needsConfirmation, normaliseSpoken, sensitiveTerms } from "./voiceText";

export const LANG_TAGS = { en: "en-IN", hi: "hi-IN", mr: "mr-IN" };
export const LANG_NAMES = { en: "English", hi: "हिन्दी", mr: "मराठी" };

export const VOICE_NOTICE =
  "When you use the microphone, your browser may send what you say to its speech service (for example Google for Chrome or Microsoft for Edge) to turn it into text. HealthWise AI does not record or keep your voice. You can always type instead.";

const win = () => (typeof window === "undefined" ? {} : window);

export const speechInputSupported = (w = win()) => Boolean(w.SpeechRecognition || w.webkitSpeechRecognition);
export const speechOutputSupported = (w = win()) => Boolean(w.speechSynthesis && w.SpeechSynthesisUtterance);
/** Android Chrome repeats the text in continuous mode, so there the browser's own end-of-speech is used and no pause time is applied. */
export const supportsPauseControl = (w = win()) => !/Android/i.test(w.navigator?.userAgent || "") && !w.Capacitor?.isNativePlatform?.();

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
    case "stuck": return "The microphone stopped responding. Please try again, or type your question.";
    case "aborted": return "";
    default: return "Voice input did not work. Please type your question instead.";
  }
}

// ------------------------------------------------------------------ listening
const START_WAIT_MS = 8000;       // started but the engine never says it is listening
const QUIET_WAIT_MS = 20000;      // listening, but nothing at all (no words, no end, no error): a frozen engine, not a quiet person

/** Starts listening. Returns { start, stop, abort } or null if the browser has no speech recognition (the caller then falls back to typing).
 *  onText(text, isFinal, { confidence, alternatives }) gets the words as they are recognised; the last call has isFinal = true.
 *  pauseMs (optional, desktop): how long a pause ends a sentence, so a slow speaker is not cut off and a fast one does not wait for the browser's own timeout.
 *  A watchdog ends a round in which the engine freezes (no event for a long time) and reports it as "stuck", so the screen never stays on "listening". */
export function createListener({ lang = "en", continuous = false, pauseMs = null, onText, onError, onEnd, onStart }, w = win()) {
  const Recognition = w.SpeechRecognition || w.webkitSpeechRecognition;
  if (!Recognition) return null;
  const rec = new Recognition();
  const usePause = Boolean(pauseMs) && supportsPauseControl(w) && !continuous;
  rec.lang = LANG_TAGS[lang] || LANG_TAGS.en;
  rec.interimResults = true;
  rec.continuous = continuous || usePause;
  rec.maxAlternatives = 3;
  const watch = !continuous;                                       // a wake-phrase listener may wait quietly for minutes: only a normal round has a watchdog
  let watchdog = null;
  let pauseTimer = null;
  let delivered = false;
  let ended = false;                                               // one end per round, whichever of the engine and the watchdog comes first
  let last = { text: "", meta: {} };
  const disarm = () => { clearTimeout(watchdog); clearTimeout(pauseTimer); };
  const finish = () => { if (ended) return; ended = true; disarm(); onEnd?.(); };
  const arm = (ms) => {
    if (!watch) return;
    clearTimeout(watchdog);
    watchdog = setTimeout(() => {
      if (ended) return;
      ended = true;
      disarm();
      onError?.("stuck");
      try { (rec.abort || rec.stop).call(rec); } catch { /* already stopped */ }
      onEnd?.();
    }, ms);
  };
  const deliver = () => {
    if (delivered || !last.text) return;
    delivered = true;
    clearTimeout(pauseTimer);
    onText?.(last.text, true, last.meta);
    try { rec.stop(); } catch { /* already stopped */ }
  };
  rec.onstart = () => { arm(QUIET_WAIT_MS); onStart?.(); };
  rec.onresult = (event) => {
    arm(QUIET_WAIT_MS);
    let text = "";
    let final = false;
    let confidence = null;
    let alternatives = [];
    for (let i = 0; i < event.results.length; i += 1) {
      const best = event.results[i][0];
      text += best.transcript;
      final = final || event.results[i].isFinal;
      if (event.results[i].isFinal && typeof best.confidence === "number" && best.confidence > 0) confidence = best.confidence;
      if (i === event.results.length - 1) alternatives = Array.from({ length: event.results[i].length || 0 }, (_, k) => event.results[i][k]?.transcript).filter(Boolean);
    }
    text = text.trim();
    last = { text, meta: { confidence, alternatives } };
    if (usePause) {
      onText?.(text, false, last.meta);
      clearTimeout(pauseTimer);
      if (text) pauseTimer = setTimeout(deliver, pauseMs);
      return;
    }
    onText?.(text, final, last.meta);
  };
  rec.onerror = (event) => { disarm(); onError?.(ERROR_KIND[event.error] || "other"); };
  rec.onend = () => { if (usePause && !delivered && last.text) deliver(); finish(); };
  return {
    start: () => {
      delivered = false;
      ended = false;
      last = { text: "", meta: {} };
      arm(START_WAIT_MS);
      try { rec.start(); } catch { disarm(); onError?.("other"); }
    },
    stop: () => {
      try { rec.stop(); } catch { /* already stopped */ }
    },
    abort: () => {
      disarm();
      try { (rec.abort || rec.stop).call(rec); } catch { /* already stopped */ }
    },
  };
}

// A short bleep or cough is not a question: the sentence must hold a word, and "umm" or "hmm" alone is nothing.
const FILLER_ONLY = /^(?:u+h+m*|u+m+|h+m+|a+h+|e+r+m*|o+h+|अं+|उम्म?|हम्म|हं+|अह)[\s.!?,]*$/i;
export const isNoise = (text) => { const t = String(text || "").trim(); return t.length < 2 || !/[\p{L}\p{N}]/u.test(t) || FILLER_ONLY.test(t); };

/** Which of English, Hindi and Marathi a sentence is in (Hinglish counts as Hindi, which answers in the script a Hindi speaker reads). */
export function detectLanguage(text, fallback = "en") {
  const t = String(text || "");
  const dev = (t.match(/[ऀ-ॿ]/g) || []).length;
  const latin = (t.match(/[A-Za-z]/g) || []).length;
  if (dev > latin) {
    const mr = (t.match(/(?:आहे|माझा|माझी|माझे|काय|किती|तुम्ही|मला|कोणती|कधी|आहेत|नाही)/g) || []).length;
    const hi = (t.match(/(?:है|हैं|मेरा|मेरी|मेरे|क्या|कितना|कितनी|मुझे|कौन|कब|नहीं)/g) || []).length;
    return mr > hi ? "mr" : hi > 0 ? "hi" : (fallback === "mr" ? "mr" : "hi");
  }
  if (/\b(?:kya|hai|hain|mera|meri|mere|kitna|kitni|batao|bataiye|dawai|kab|nahi|kaun|karo|kholo|dikhao)\b/i.test(t)) return "hi";
  return latin ? "en" : fallback;
}

// "Hey HealthWise": the name WITH a greeting before it (English, Hindi and Marathi spellings). The name alone is not enough: people say "health wise"
// in ordinary talk ("being health wise is important") and that must not switch the microphone on. The phrase must also START the sentence (at most two words
// before it), so a television or another person saying it in the middle of a sentence does not count.
const WAKE = /(?:^|\s)(?:hey|hi|hello|ok|okay|हे|हाय|हेलो|ओके)\s+(?:health\s?wise|हेल्थ\s?वाइज़?|हेल्थ\s?वाईज|हेल्थवाइज)/i;

/** Text after the wake phrase ("hey healthwise what medicines am I taking" gives "what medicines am I taking"), or null when it was not said. */
export function afterWakePhrase(text) {
  const m = WAKE.exec(text || "");
  if (!m) return null;
  if (text.slice(0, m.index).trim().split(/\s+/).filter(Boolean).length > 2) return null;
  return text.slice(m.index + m[0].length).replace(/^[\s,.:;!-]+/, "").trim();
}

const WAKE_GIVE_UP = 4;           // recogniser errors in a row (no words heard in between) before the wake phrase gives up and says why

/** Listens quietly for the wake phrase and calls onWake(restOfTheSentence). Chrome ends a long listening session by itself, so it restarts
 *  until stop() is called. It only runs on the page where the person switched it on, only while that page is visible, gives up with a message after
 *  repeated errors (no endless retrying on a broken connection) and never keeps what it hears. */
export function createWakeListener({ lang = "en", onWake, onError }, w = win()) {
  let active = false;
  let listener = null;
  let heard = false;
  let restarts = 0;
  let failures = 0;
  const hidden = () => typeof document !== "undefined" && document.visibilityState === "hidden";
  const begin = () => {
    if (!active) return;
    if (hidden()) { setTimeout(begin, 1000); return; }          // not listening while the page is in the background
    heard = false;
    listener = createListener({
      lang,
      continuous: true,
      onText: (text, final) => {
        failures = 0;
        const rest = afterWakePhrase(text);
        if (rest === null || heard) return;
        if (rest && !final) return;                 // wait until the sentence is finished, then use all of it
        heard = true;
        active = false;
        listener?.abort();
        onWake?.(rest);
      },
      onError: (kind) => {
        if (kind === "denied" || kind === "no-microphone" || kind === "language") { active = false; onError?.(kind); return; }
        if (kind === "aborted" || kind === "no-speech") return;
        failures += 1;
        if (failures >= WAKE_GIVE_UP) { active = false; onError?.(kind === "network" ? "network" : "other"); }
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
    start() { if (!active) { active = true; failures = 0; begin(); } },
    stop() { active = false; listener?.abort(); },
  };
}

// ------------------------------------------------------------------ spoken commands
// Fillers around a command ("umm stop please", "okay can you stop") are taken off first, so a command is understood the way a person says it.
const COMMAND_FILLER_BEFORE = /^(?:(?:umm+|uhh*|err+|hmm+|okay|ok|so|well|hey|please|pls|sir|yaar|can you|could you|will you|would you|zara|ज़रा|जरा|कृपया|प्लीज़?|अं+)[,\s]+)+/i;
const COMMAND_FILLER_AFTER = /(?:[,\s]+(?:please|pls|sir|yaar|now|for me|ok|okay|na|ना|कृपया|प्लीज़?|जी|karo|kijiye|बताइए))+$/i;
const COMMANDS = [
  ["stop", /^(?:stop|cancel|quiet|be quiet|stop talking|stop reading|stop speaking|shut up|enough|that is enough|that'?s enough|hold on|wait|रुको|रुकिए|रुकिये|चुप|चुप रहो|बंद करो|बंद कर दो|बस करो|बस|थांबा|थांब|गप्प|गप्प बसा|band karo|band kar do|ruko|ruk jao|bas karo|bas|chup|chup raho)$/i],
  ["repeat", /^(?:repeat(?:\s+that)?|repeat once more|say\s+(?:that\s+)?again|say it again|once more|what did you say|read\s+(?:that\s+)?again|come again|फिर से बोलो|दोबारा बोलो|फिर से सुनाओ|फिर से बताओ|दोबारा सुनाओ|पुन्हा सांग|परत सांग|पुन्हा वाचा|पुन्हा सांगा|dobara bolo|dobara sunao|phir se bolo|phir se sunao|phir se batao|ek baar aur)$/i],
  ["more", /^(?:tell me more|more details?|more (?:about (?:it|that))?|explain (?:it |that )?more|go on|continue|read (?:it )?all|read the whole (?:thing|answer)|details|aur batao|aur bolo|poora batao|विस्तार से बताओ|और बताओ|पूरा बताओ|आणखी सांगा|अजून सांगा|सविस्तर सांगा)$/i],
  ["slower", /^(?:speak\s+|talk\s+|read\s+|go\s+|be\s+)?(?:a bit |a little |little )?(?:slower|slowly|slow down|more slowly|धीरे बोलो|धीमे बोलो|धीरे|हळू बोला|हळू|dheere bolo|dheere|thoda slow bolo|slow bolo|thoda dheere)$/i],
  ["faster", /^(?:speak\s+|talk\s+|read\s+|go\s+|be\s+)?(?:a bit |a little |little )?(?:faster|quicker|speed up|more quickly|तेज़ बोलो|तेज बोलो|जल्दी बोलो|वेगाने बोला|जलद बोला|tez bolo|jaldi bolo|thoda fast bolo)$/i],
  ["clear", /^(?:clear(?:\s+the)?\s+chat|clear everything|start over|new chat|delete (?:the )?chat|चैट साफ़ करो|चैट साफ करो|चॅट साफ करा|चैट डिलीट करो)$/i],
  ["exit", /^(?:stop listening|that'?s all|that is all|i am done|i'm done|no more|nothing else|that will be all|बस इतना|बस इतना ही|मैं हो गया|एवढेच|एवढंच|bas itna|bas itna hi)$/i],
];
/** "yes" in English, Hindi and Marathi, for questions the assistant asks before it does something that cannot be undone. */
export const isYes = (text) => /^(?:yes|yeah|yep|yup|sure|ok|okay|confirm|correct|right|that is right|that's right|do it|haan|han|ha|bilkul|sahi|हाँ|हां|जी|जी हाँ|ठीक है|सही|बिलकुल|हो|होय|हा|बरोबर)[\s.!]*$/i.test(String(text || "").trim());

const LANGUAGE_WORDS = { english: "en", "अंग्रेज़ी": "en", "अंग्रेजी": "en", इंग्लिश: "en", angrezi: "en", hindi: "hi", "हिंदी": "hi", "हिन्दी": "hi", marathi: "mr", "मराठी": "mr" };
const LANGUAGE_COMMAND = /^(?:speak\s+(?:in\s+)?|talk\s+(?:in\s+)?|switch\s+to\s+|change\s+(?:the\s+)?language\s+to\s+|answer\s+in\s+|reply\s+in\s+|use\s+)?(english|hindi|marathi|angrezi|अंग्रेज़ी|अंग्रेजी|इंग्लिश|हिंदी|हिन्दी|मराठी)(?:\s+(?:me|mein|madhe|में|मध्ये)\s+(?:bolo|bola|बोलो|बोला))?$/i;

/** A whole spoken sentence that is a command for the voice itself ("stop", "repeat", "speak slower", "switch to Hindi"), or null for a question. */
export function matchVoiceCommand(text) {
  let t = String(text || "").trim().replace(/[.!?,।]+$/g, "").trim();
  if (!t) return null;
  t = t.replace(COMMAND_FILLER_BEFORE, "").replace(COMMAND_FILLER_AFTER, "").trim();
  if (!t || t.split(/\s+/).length > 7) return null;
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

/** A live sound level (0 to 1) for the waveform while listening. Asks the browser for echo cancellation, noise suppression and automatic gain, so the meter and
 *  the room noise do not fool each other. Returns { stop } or null when the browser cannot or the person said no: the recogniser itself is not affected. */
export async function startLevelMeter(onLevel, w = win()) {
  try {
    const md = w.navigator?.mediaDevices;
    const Ctx = w.AudioContext || w.webkitAudioContext;
    if (!md?.getUserMedia || !Ctx) return null;
    const stream = await md.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
    const ctx = new Ctx();
    const analyser = ctx.createAnalyser();
    analyser.fftSize = 256;
    ctx.createMediaStreamSource(stream).connect(analyser);
    const data = new Uint8Array(analyser.frequencyBinCount);
    const timer = setInterval(() => {
      analyser.getByteTimeDomainData(data);
      let peak = 0;
      for (const v of data) peak = Math.max(peak, Math.abs(v - 128));
      onLevel(Math.min(1, peak / 64));
    }, 90);
    return { stop() { clearInterval(timer); stream.getTracks().forEach((t) => t.stop()); ctx.close?.().catch?.(() => {}); } };
  } catch { return null; }
}

// ------------------------------------------------------------------ speaking
/** Text for the voice: no marks, medical abbreviations, units, dates and ranges said in words (see voiceText.speechText), and not too long. */
export function speakableText(text, lang = "en", limit = 900) {
  return speechText(text, lang, limit);
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

/** Which voice reads this language, and what the person should be told: the right voice; a Hindi voice for Marathi (same script, understood by Marathi speakers) with a
 *  clear message; or no voice at all with a message. `lang` is the language the voice should be set to when a stand-in is used. */
export function voicePlan(lang, w = win(), preferred = "") {
  const own = pickVoice(lang, w, preferred);
  if (own) return { voice: own, lang, note: "" };
  if (lang === "mr") {
    const hindi = pickVoice("hi", w);
    if (hindi) return { voice: hindi, lang: "hi", note: "No Marathi voice is installed on this device, so a Hindi voice reads the answer. You can read the text on the screen, or install a Marathi voice in your device's text-to-speech settings." };
  }
  if (lang !== "en") return { voice: null, lang, note: `No ${LANG_NAMES[lang]} voice is installed on this device, so the answer may not be read correctly. You can read the text instead.` };
  return { voice: null, lang, note: "" };
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
    speak(text, { lang = "en", rate = 1, pitch = 1, voiceName = "", limit = 900, onEnd } = {}) {
      if (!supported) { onProblem?.("Reading aloud is not available in this browser."); return false; }
      synth.cancel();
      const said = speakableText(text, lang, limit);
      if (!said) return false;
      const chunks = speechChunks(said);
      const plan = voicePlan(lang, w, voiceName);
      if (plan.note) onProblem?.(plan.note);
      const mine = (run += 1);
      const next = (i) => {
        if (mine !== run) return;
        if (i >= chunks.length) { set("idle"); onEnd?.(); return; }
        const utterance = new w.SpeechSynthesisUtterance(chunks[i]);
        utterance.lang = LANG_TAGS[plan.lang] || LANG_TAGS.en;
        utterance.rate = Math.min(1.5, Math.max(0.6, rate));
        utterance.pitch = Math.min(1.5, Math.max(0.5, pitch));
        if (plan.voice) utterance.voice = plan.voice;
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
