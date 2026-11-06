// Android's in-app WebView has neither the Web Speech API's recognition nor its speech synthesis, so inside the Android app we give `window` small
// stand-ins that use the phone's own speech recognition and text-to-speech (Capacitor plugins). voice.js then works unchanged.
// In a normal browser this file does nothing.
import { Capacitor } from "@capacitor/core";
import { SpeechRecognition as CommunityPlugin } from "@capacitor-community/speech-recognition";
import { TextToSpeech } from "@capacitor-community/text-to-speech";

// The recogniser behind the Android app is a swappable ENGINE: any object with these six calls. Today it is the free community plugin; a better one (an on-device
// Hindi/Marathi model, for example) plugs in with setNativeSpeechEngine(engine) and nothing else changes: the rest of the app only ever sees the browser's
// SpeechRecognition shape that this file builds. Engine calls (all async):
//   checkPermissions() / requestPermissions() -> { speechRecognition: "granted" | ... }      available() -> { available: boolean }
//   start({ language, maxResults, partialResults, popup })      stop()      isListening() -> { isListening: boolean }
//   addListener("partialResults", fn({ matches: [text] }))  and  addListener("listeningState", fn({ status: "started" | "stopped" }))  -> { remove() }
export const communityEngine = {
  checkPermissions: () => CommunityPlugin.checkPermissions(),
  requestPermissions: () => CommunityPlugin.requestPermissions(),
  available: () => CommunityPlugin.available(),
  start: (options) => CommunityPlugin.start(options),
  stop: () => CommunityPlugin.stop(),
  isListening: () => CommunityPlugin.isListening(),
  addListener: (name, fn) => CommunityPlugin.addListener(name, fn),
};
let Native = communityEngine;
export const setNativeSpeechEngine = (engine) => { Native = engine || communityEngine; };

const NO_SPEECH_MS = 9000;      // nothing heard at all: the plugin reports no error once partial results are on, so we end the round ourselves
const FINAL_WAIT_MS = 1500;     // after the phone says speech ended, its final text still arrives a moment later

class NativeSpeechRecognition {
  constructor() {
    this.lang = "en-IN";
    this.interimResults = true;
    this.continuous = false;
    this.maxAlternatives = 1;
    this.onstart = this.onresult = this.onerror = this.onend = null;
    this._text = "";
    this._active = false;
    this._ended = false;
    this._handles = [];
    this._timer = null;
    this._poll = null;
  }

  _emit(text, isFinal) {
    const alt = Object.assign([{ transcript: text }], { isFinal });
    this.onresult?.({ results: [alt] });
  }

  _cleanup() {
    clearTimeout(this._timer);
    clearInterval(this._poll);
    this._handles.forEach((h) => h.remove?.());
    this._handles = [];
  }

  _finish(error) {
    if (!this._active) return;
    this._active = false;
    this._cleanup();
    if (this._text) this._emit(this._text, true);
    else if (error) this.onerror?.({ error });
    this.onend?.();
  }

  async start() {
    if (this._active) return;
    this._active = true;
    this._ended = false;
    this._text = "";
    try {
      let perm = await Native.checkPermissions();
      if (perm.speechRecognition !== "granted") perm = await Native.requestPermissions();
      if (perm.speechRecognition !== "granted") throw Object.assign(new Error("denied"), { code: "not-allowed" });
      const avail = await Native.available();
      if (!avail.available) throw Object.assign(new Error("unavailable"), { code: "language-not-supported" });

      this._handles.push(await Native.addListener("partialResults", (d) => {
        const text = (d.matches && d.matches[0]) || "";
        if (!text || !this._active) return;
        this._text = text;
        if (this._ended) this._finish();                         // the final text came in after speech ended
        else this._emit(text, false);
      }));
      this._handles.push(await Native.addListener("listeningState", (d) => {
        if (d.status === "started") clearTimeout(this._timer);   // the person is speaking
        if (d.status === "stopped") {
          this._ended = true;
          clearTimeout(this._timer);
          this._timer = setTimeout(() => this._finish("no-speech"), FINAL_WAIT_MS);
        }
      }));

      await Native.start({ language: this.lang, maxResults: 1, partialResults: true, popup: false });
      this._timer = setTimeout(() => this._finish("no-speech"), NO_SPEECH_MS);
      // the plugin cannot report a recogniser error once partial results are on (for example "no match" or "network"), so watch whether it is still listening
      this._poll = setInterval(async () => {
        try {
          const { isListening } = await Native.isListening();
          if (!isListening && this._active && !this._ended) { this._ended = true; this._timer = setTimeout(() => this._finish("no-speech"), FINAL_WAIT_MS); }
        } catch { /* the timers above still end the round */ }
      }, 800);
      this.onstart?.();
    } catch (e) {
      this._active = false;
      this._cleanup();
      this.onerror?.({ error: e.code || (/permission|denied/i.test(String(e.message)) ? "not-allowed" : "audio-capture") });
      this.onend?.();
    }
  }

  stop() { Native.stop().catch(() => {}); clearTimeout(this._timer); this._ended = true; this._timer = setTimeout(() => this._finish(), 600); }
  abort() { this._text = ""; Native.stop().catch(() => {}); this._finish(); }
}

// ---------------------------------------------------------------- speaking
class NativeUtterance {
  constructor(text = "") {
    this.text = text;
    this.lang = "en-IN";
    this.rate = 1;
    this.pitch = 1;
    this.volume = 1;
    this.voice = null;
    this.onstart = this.onend = this.onerror = null;
  }
}

const nativeSynth = {
  _voices: [],
  _current: null,
  _paused: null,
  _token: 0,
  _listeners: new Set(),
  getVoices() { return this._voices; },
  addEventListener(name, fn) { if (name === "voiceschanged") this._listeners.add(fn); },
  removeEventListener(name, fn) { this._listeners.delete(fn); },
  async loadVoices() {
    try {
      const { voices } = await TextToSpeech.getSupportedVoices();
      this._voices = (voices || []).map((v, i) => ({ name: v.name || v.voiceURI, lang: v.lang, localService: true, default: Boolean(v.default), _index: i }));
      this._listeners.forEach((fn) => fn());
    } catch { /* the phone's default voice is still used */ }
  },
  async speak(utterance) {
    const mine = (this._token += 1);
    this._current = utterance;
    const finish = (kind, error) => {
      if (mine !== this._token) return;                          // cancelled or replaced: stay quiet, like the browser's own "canceled"
      this._current = null;
      if (kind === "end") utterance.onend?.({});
      else utterance.onerror?.({ error });
    };
    try {
      utterance.onstart?.({});
      await TextToSpeech.speak({
        text: utterance.text,
        lang: utterance.lang,
        rate: utterance.rate,
        pitch: utterance.pitch,
        volume: utterance.volume,
        category: "playback",
        queueStrategy: 1,
        ...(utterance.voice && Number.isInteger(utterance.voice._index) ? { voice: utterance.voice._index } : {}),
      });
      finish("end");
    } catch {
      finish("error", "synthesis-failed");
    }
  },
  cancel() { this._token += 1; this._current = null; this._paused = null; TextToSpeech.stop().catch(() => {}); },
  pause() { if (!this._current) return; this._paused = this._current; this._token += 1; TextToSpeech.stop().catch(() => {}); },     // Android cannot pause: resume starts the sentence again
  resume() { const u = this._paused; this._paused = null; if (u) this.speak(u); },
};

if (Capacitor.isNativePlatform()) {
  window.SpeechRecognition = NativeSpeechRecognition;
  window.SpeechSynthesisUtterance = NativeUtterance;
  Object.defineProperty(window, "speechSynthesis", { value: nativeSynth, configurable: true });
  nativeSynth.loadVoices();
}
