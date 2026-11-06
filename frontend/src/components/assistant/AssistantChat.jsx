// The patient's chat and voice assistant. It answers only from the signed-in patient's own records (the server decides which),
// shows where every answer came from, and works by typing alone when voice is not available.
// Voice: press the orb for a hands-free conversation (listen, answer aloud, listen again), or say "Hey HealthWise" (optional), or use the
// small microphone to dictate one question. All of it uses the browser's own free speech features: no outside voice service or key.
import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { AlertTriangle, ArrowDown, Check, Copy, Mic, Pause, Play, RotateCcw, Send, ShieldCheck, Square, Trash2, Volume2 } from "lucide-react";
import { deleteConversation, getAssistantInfo, getSuggestions, sendChat } from "../../services/assistantApi";
import { getErrorMessage } from "../../services/api";
import {
  CONFIRM_TEXT, LANG_NAMES, VOICE_NOTICE, correctMedicalTerms, createListener, createSpeaker, createWakeListener, cue, detectLanguage, isNo, isNoise, isYes, matchVoiceCommand,
  needsConfirmation, speechInputSupported, speechOutputSupported, startLevelMeter, supportsPauseControl, voiceErrorMessage, voicesFor,
} from "../../utils/voice";
import { initialVoice, voiceReducer } from "../../utils/voiceMachine";
import VoicePanel from "./VoicePanel";
import MicInfo, { MicInfoButton } from "./MicInfo";

const SOURCE_ROUTE = {
  report: (s) => `/patient/reports/${s.id}`,
  prescription: () => "/patient/prescriptions",
  appointment: () => "/patient/appointments",
  note: () => "/patient/notes",
  recommendation: () => "/patient/recommendations",
  history: () => "/patient/health-history",
};
const store = {
  get: (k, d) => { try { return localStorage.getItem(k) ?? d; } catch { return d; } },
  set: (k, v) => { try { localStorage.setItem(k, v); } catch { /* storage may be blocked: the setting just is not remembered */ } },
};
const when = (iso) => (iso ? new Date(iso).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" }) : "");
const RATES = [0.8, 1, 1.25];
const SAY_AGAIN = { en: "Okay. Please say it again.", hi: "ठीक है। कृपया फिर से बोलिए।", mr: "ठीक आहे. कृपया पुन्हा बोला." };
/** The clock time of a message ("10:42 am"). The server sends UTC without a zone mark, so one is added. */
const clock = (iso) => (iso ? new Date(/[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`).toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }) : "");

/** The same label and date twice (two pieces of advice from one day) is shown once with a count. */
function groupSources(sources) {
  const groups = new Map();
  for (const s of sources) {
    const key = `${s.type}|${s.label}|${s.date || ""}`;
    groups.has(key) ? groups.get(key).count++ : groups.set(key, { ...s, count: 1 });
  }
  return [...groups.values()];
}

function Sources({ sources }) {
  if (!sources?.length) return null;
  return (
    <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs">
      <span className="font-semibold text-slate-500">Source:</span>
      {groupSources(sources).map((s) => (
        <Link key={`${s.type}-${s.id}`} to={(SOURCE_ROUTE[s.type] || (() => "/patient"))(s)}
          className="rounded-full bg-brand-50 px-2.5 py-1 font-semibold text-brand-700 ring-1 ring-brand-100 hover:bg-brand-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500">
          {s.label}{s.date ? ` · ${when(s.date)}` : ""}{s.count > 1 ? ` (${s.count})` : ""}
        </Link>
      ))}
    </div>
  );
}

// "Medicine: Tab. X, 5 mg" -> the label in bold; each line is its own short paragraph, and the closing reminder is set apart in smaller print.
const LABELLED = /^([^:.\n]{3,40}):\s+(.+)$/;
const FOOTNOTE = /^(This is what your records say|Please talk to your doctor|Only what is written|यह आपके रिकॉर्ड|कृपया अपने डॉक्टर|हे तुमच्या नोंदी|कृपया तुमच्या डॉक्टर)/i;
function AnswerText({ text }) {
  const lines = String(text).split("\n").filter((l) => l.trim());
  return lines.map((line, i) => {
    const m = LABELLED.exec(line);
    if (FOOTNOTE.test(line)) return <p key={i} className="mt-2 border-t border-slate-200 pt-2 text-sm text-slate-500">{line}</p>;
    return <p key={i} className={i ? "mt-1.5" : "font-semibold text-slate-900"}>{m ? <><b>{m[1]}:</b> {m[2]}</> : line}</p>;
  });
}

function CopyAnswer({ text }) {
  const [done, setDone] = useState(false);
  const copy = async () => {
    try { await navigator.clipboard.writeText(text); setDone(true); setTimeout(() => setDone(false), 2000); } catch { /* the text can still be selected by hand */ }
  };
  return (
    <button type="button" onClick={copy} aria-label="Copy this answer" className="flex items-center gap-1.5 rounded-full bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500">
      {done ? <><Check size={16} className="text-emerald-600" /> Copied</> : <><Copy size={16} /> Copy</>}
    </button>
  );
}

// One line on a phone (the whole text stays in the page); a tap opens the rest.
function Disclaimer({ text }) {
  const [more, setMore] = useState(false);
  return (
    <p className="flex items-start gap-1 text-xs text-slate-600 [@media(max-height:32rem)]:hidden">
      <span className={`min-w-0 flex-1 ${more ? "" : "line-clamp-1 sm:line-clamp-none"}`}>{text}</span>
      <button type="button" onClick={() => setMore((m) => !m)} aria-expanded={more} className="-my-3 min-w-11 shrink-0 px-1 font-bold underline sm:hidden">{more ? "Less" : "More"}</button>
    </p>
  );
}

export default function AssistantChat() {
  const navigate = useNavigate();
  const [language, setLanguage] = useState(() => store.get("hw_assistant_lang", "en"));
  const [rate, setRate] = useState(() => Number(store.get("hw_assistant_rate", "1")));
  const [voiceName, setVoiceName] = useState(() => store.get("hw_assistant_voice", ""));
  const [autoRead, setAutoRead] = useState(() => store.get("hw_assistant_autoread", "no") === "yes");
  const [sounds, setSounds] = useState(() => store.get("hw_assistant_sounds", "yes") === "yes");
  const [aiConsent, setAiConsent] = useState(() => store.get("hw_assistant_ai", "no") === "yes");
  const [pitch, setPitch] = useState(() => Number(store.get("hw_assistant_pitch", "1")) || 1);
  const [pauseMs, setPauseMs] = useState(() => Number(store.get("hw_assistant_pause", "0")) || 0);     // 0: the browser decides when a sentence ends; else how long a pause ends it (desktop)
  const [confirmBeforeSend, setConfirmBeforeSend] = useState(() => store.get("hw_assistant_check", "no") === "yes");   // spoken words go to the box to be checked, not straight to the server
  const [privateMode, setPrivateMode] = useState(() => store.get("hw_assistant_private", "no") === "yes");           // read only a short note aloud: the answer stays on the screen
  const [bargeIn, setBargeIn] = useState(() => store.get("hw_assistant_barge", "no") === "yes");                     // talking over the assistant stops it (needs headphones)
  const [autoLang, setAutoLang] = useState(() => store.get("hw_assistant_autolang", "no") === "yes");                // the answer language follows what was said
  const [level, setLevel] = useState(null);                  // live microphone level 0..1 while listening, when the browser allows it
  const [info, setInfo] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [messages, setMessages] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(null);            // { text, viaVoice, message } of the question that did not get an answer
  const [listening, setListening] = useState(false);
  const [heard, setHeard] = useState("");                 // the words recognised so far
  const [handsFree, setHandsFree] = useState(false);
  const [wakeOn, setWakeOn] = useState(false);
  const [voiceNotice, setVoiceNotice] = useState(null);   // null, or what to start once the privacy note is accepted: "hands" | "dictate" | "wake"
  const [voiceMessage, setVoiceMessage] = useState("");
  const [speaking, setSpeaking] = useState({ id: null, state: "idle" });
  const [speakNote, setSpeakNote] = useState("");
  const [voices, setVoices] = useState([]);
  const [micInfo, setMicInfo] = useState(false);          // the (i) sheet "How the microphone works"
  const [confirmClear, setConfirmClear] = useState(false);
  const [showJump, setShowJump] = useState(false);        // "Jump to latest" while the person has scrolled up
  const stick = useRef(true);                             // true while the view is at the bottom: new messages then scroll into view
  const listener = useRef(null);
  const bottom = useRef(null);
  const lastAnswer = useRef(null);
  const inputRef = useRef(null);
  const speakingId = useRef(null);
  const handsFreeRef = useRef(false);
  const pendingClear = useRef(false);                     // the assistant asked "clear this chat?" and waits for yes or no
  const silent = useRef(0);                               // listening rounds in a row in which nothing was said
  const retries = useRef(0);                              // short retries after a network blip while listening (one, then the message)
  const messagesRef = useRef([]);
  const api = useRef({});                                 // the latest functions, for timers and callbacks that outlive a render
  const timers = useRef(new Set());
  const pendingConfirm = useRef(null);                    // "Did I hear ...? Say yes or no": what was heard, waiting for the answer
  const barge = useRef(null);                             // { listener, cut }: the recogniser that waits for the person to talk over the assistant
  const vocabRef = useRef([]);                            // this patient's own medicine names, for putting misheard words back
  const lastLang = useRef(null);                          // the language of the last question when it is chosen automatically
  /** A delayed call that is cancelled when the person leaves the page, so the microphone never starts on a page that is gone. */
  const later = useCallback((fn, ms) => {
    const id = setTimeout(() => { timers.current.delete(id); fn(); }, ms);
    timers.current.add(id);
  }, []);

  const inputOk = speechInputSupported();
  const outputOk = speechOutputSupported();
  const [voice, dispatchVoice] = useReducer(voiceReducer, initialVoice);     // idle, listening, hearing, thinking, speaking or error (utils/voiceMachine.js)
  const speaker = useMemo(() => createSpeaker({
    onState: (state) => {
      setSpeaking((s) => ({ id: state === "idle" ? null : speakingId.current, state }));
      dispatchVoice({ type: state === "idle" ? "SPEAK_END" : "SPEAK_START" });
      const b = barge.current;
      if (state === "idle" && b && !b.cut) { barge.current = null; b.listener?.abort(); }     // the speech ended: nobody is talking over it any more
    },
    onProblem: setSpeakNote,
  }), []);

  useEffect(() => { getAssistantInfo(language).then(setInfo).catch(() => {}); }, [language]);
  useEffect(() => { vocabRef.current = info?.vocabulary || []; }, [info]);
  useEffect(() => { getSuggestions(language).then(setSuggestions).catch(() => setSuggestions([])); }, [language]);
  useEffect(() => { messagesRef.current = messages; }, [messages]);
  // a new answer is shown from the question that led to it, so a long answer is read from its first line; the waiting note goes to the bottom
  useEffect(() => {
    const last = messages[messages.length - 1];
    const answered = last?.role === "ASSISTANT" && !busy && !failed;
    if (!stick.current && last?.role !== "PATIENT") return;      // someone reading older messages is not pulled away; the jump button is there
    (answered ? lastAnswer.current : bottom.current)?.scrollIntoView?.({ behavior: "smooth", block: answered ? "start" : "end" });
  }, [messages, busy, failed]);
  useEffect(() => () => {
    handsFreeRef.current = false;
    timers.current.forEach(clearTimeout);
    timers.current.clear();
    speaker.stop();
    listener.current?.abort();
    const b = barge.current;
    barge.current = null;
    b?.listener?.abort();
  }, [speaker]);
  useEffect(() => {                                       // the sound level for the meter: only while listening, only where the browser lets a second microphone use run beside the recogniser
    if (!listening || !supportsPauseControl()) return undefined;
    let alive = true;
    let meter = null;
    startLevelMeter(setLevel).then((m) => { if (alive) meter = m; else m?.stop(); });
    return () => { alive = false; meter?.stop(); setLevel(null); };
  }, [listening]);
  useEffect(() => {                                       // the list of installed voices arrives a moment after the page opens
    if (!outputOk) return undefined;
    const load = () => setVoices(voicesFor(language));
    load();
    window.speechSynthesis.addEventListener?.("voiceschanged", load);
    return () => window.speechSynthesis.removeEventListener?.("voiceschanged", load);
  }, [outputOk, language]);

  const changeLanguage = (code) => {
    setLanguage(code); lastLang.current = code; store.set("hw_assistant_lang", code); speaker.stop();
    if (listener.current) {                              // changed while listening: the running recogniser is set to the old language, so start again in the new one
      const again = handsFreeRef.current;
      listener.current.abort();
      if (again) later(() => { if (!listener.current) api.current.listen({ auto: true }); }, 300);
    }
  };
  const changePitch = (v) => { setPitch(v); store.set("hw_assistant_pitch", String(v)); };
  const changePause = (v) => { setPauseMs(v); store.set("hw_assistant_pause", String(v)); };
  const changeCheck = (on) => { setConfirmBeforeSend(on); store.set("hw_assistant_check", on ? "yes" : "no"); };
  const changePrivate = (on) => { setPrivateMode(on); store.set("hw_assistant_private", on ? "yes" : "no"); };
  const changeBarge = (on) => { setBargeIn(on); store.set("hw_assistant_barge", on ? "yes" : "no"); };
  const changeAutoLang = (on) => { setAutoLang(on); store.set("hw_assistant_autolang", on ? "yes" : "no"); };
  const changeRate = (value) => { setRate(value); store.set("hw_assistant_rate", String(value)); };
  const changeVoice = (name) => { setVoiceName(name); store.set("hw_assistant_voice", name); };
  const changeAutoRead = (on) => { setAutoRead(on); store.set("hw_assistant_autoread", on ? "yes" : "no"); };
  const changeSounds = (on) => { setSounds(on); store.set("hw_assistant_sounds", on ? "yes" : "no"); };
  const changeConsent = (on) => { setAiConsent(on); store.set("hw_assistant_ai", on ? "yes" : "no"); };

  const stopBarge = useCallback(() => { const b = barge.current; barge.current = null; b?.listener?.abort(); }, []);
  const answerLang = autoLang ? lastLang.current || language : language;

  /** Reads an answer aloud: the short spoken version the server made from the same written answer (private mode: only a short note), or with full = true the whole written
   *  answer ("tell me more"). With "interrupt by talking" on and a voice conversation going, a recogniser waits during the speech: the first words cut the speech short. */
  const speak = useCallback((message, { then, speed, full = false } = {}) => {
    speakingId.current = message.id;
    setSpeakNote("");
    const emergency = message.safety === "EMERGENCY";
    const text = privateMode && !emergency && message.spoken_private ? message.spoken_private : !full && message.spoken ? message.spoken : message.text;
    if (bargeIn && inputOk && handsFreeRef.current) {
      stopBarge();
      const state = { listener: null, cut: false };
      state.listener = createListener({
        lang: answerLang,
        onText: (heardText, final, meta) => {
          if (isNoise(heardText)) return;
          if (!state.cut) { state.cut = true; speaker.stop(); }
          if (final) { barge.current = null; api.current.onHeard(correctMedicalTerms(heardText, { lang: answerLang, vocabulary: vocabRef.current }), heardText, meta); }
        },
        onError: () => {},
        onEnd: () => { if (barge.current === state && !state.cut) barge.current = null; },
      });
      if (state.listener) { barge.current = state; state.listener.start(); }
    }
    return speaker.speak(text, { lang: answerLang, rate: speed ?? rate, pitch, voiceName, limit: full ? 3000 : 900, onEnd: () => { stopBarge(); then?.(); } });
  }, [speaker, answerLang, rate, pitch, voiceName, privateMode, bargeIn, inputOk, stopBarge]);

  // ------------------------------------------------------------------ the conversation
  const endHandsFree = useCallback((message = "") => {
    handsFreeRef.current = false;
    setHandsFree(false);
    silent.current = 0;
    pendingConfirm.current = null;
    listener.current?.abort();
    const b = barge.current;
    barge.current = null;
    b?.listener?.abort();
    setListening(false);
    setHeard("");
    dispatchVoice({ type: "STOP" });
    if (message) setVoiceMessage(message);
  }, []);

  // The phone goes to the background, the screen locks, a call comes in or the page is left: nothing keeps listening or talking, and the screen shows "ready" again.
  useEffect(() => {
    const stopAll = () => {
      timers.current.forEach(clearTimeout);
      timers.current.clear();
      endHandsFree();
      speaker.stop();
    };
    const onVisibility = () => { if (document.visibilityState === "hidden") stopAll(); };
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener("pagehide", stopAll);
    return () => { document.removeEventListener("visibilitychange", onVisibility); window.removeEventListener("pagehide", stopAll); };
  }, [endHandsFree, speaker]);

  /** After an answer: read it aloud when the question was spoken (or the person asked for every answer to be read), then listen again if hands-free. */
  const finishReply = useCallback((reply, viaVoice) => {
    const action = reply.action;
    if (action?.type === "navigate") {                    // "open my reports": show what was done, then go there
      endHandsFree();
      later(() => navigate(action.to), 700);
      return;
    }
    if (action?.type === "end_conversation") handsFreeRef.current = false;
    const again = () => { if (handsFreeRef.current) later(() => api.current.listen({ auto: true }), 350); else setHandsFree(false); };
    const read = outputOk && (reply.safety === "EMERGENCY" || viaVoice || handsFreeRef.current || autoRead || action?.type === "end_conversation");
    if (read) { if (!speak(reply, { then: again })) again(); } else again();
  }, [autoRead, endHandsFree, later, navigate, outputOk, speak]);

  const send = useCallback(async (raw, viaVoice = false) => {
    const text = raw.trim();
    if (!text || busy) return;
    if (typeof navigator !== "undefined" && navigator.onLine === false) {
      endHandsFree();
      setFailed({ text, viaVoice, message: "You seem to be offline. Your question is kept; send it again when the connection is back." });
      return;
    }
    speaker.stop();
    const lang = autoLang ? detectLanguage(text, language) : language;     // "Choose the answer language from what I say"
    lastLang.current = lang;
    dispatchVoice({ type: "SEND" });
    setBusy(true);
    setFailed(null);
    setVoiceMessage("");                              // an old "I stopped listening" note does not belong next to a new question
    setInput("");
    setHeard("");
    setMessages((m) => [...m, { id: `local-${Date.now()}`, role: "PATIENT", text }]);
    try {
      const data = await sendChat({ message: text, conversation_id: conversationId, language: lang, ai_consent: aiConsent });
      setConversationId(data.conversation_id);
      setMessages((m) => [...m.filter((x) => !String(x.id).startsWith("local-")), data.message, data.reply]);
      setBusy(false);
      dispatchVoice({ type: "REPLIED" });
      if (sounds && viaVoice) cue("done");
      finishReply(data.reply, viaVoice);
    } catch (e) {
      endHandsFree();
      if (sounds && viaVoice) cue("error");
      setMessages((m) => m.filter((x) => !String(x.id).startsWith("local-")));
      setFailed({ text, viaVoice, message: e.response?.status === 401 ? "Your session has ended. Please log in again." : getErrorMessage(e) });
      setInput(text);                                 // the typed question is never lost
      setBusy(false);
      dispatchVoice({ type: "ERROR", kind: "send" });
    }
  }, [busy, conversationId, language, autoLang, aiConsent, sounds, speaker, finishReply, endHandsFree]);

  const jumpToLatest = () => { stick.current = true; setShowJump(false); bottom.current?.scrollIntoView?.({ behavior: "smooth", block: "end" }); };
  const onLogScroll = (e) => {
    const el = e.currentTarget;
    const near = el.scrollHeight - el.scrollTop - el.clientHeight < 140;
    stick.current = near;
    setShowJump(!near && messagesRef.current.length > 0);
  };
  const clearChat = useCallback(async () => {
    speaker.stop();
    if (conversationId) { try { await deleteConversation(conversationId); } catch { /* the chat on screen is cleared anyway */ } }
    setMessages([]); setConversationId(null); setFailed(null); setInput("");
  }, [conversationId, speaker]);

  /** A spoken sentence: a command for the voice itself ("stop", "repeat", "speak slower", "switch to Hindi"), or a question. */
  const onSpoken = useCallback((text) => {
    const keepOn = () => { if (handsFreeRef.current) later(() => api.current.listen({ auto: true }), 300); };
    if (pendingConfirm.current) {                         // the answer to "Did I hear ...? Say yes or no."
      const phrase = pendingConfirm.current;
      pendingConfirm.current = null;
      setVoiceMessage("");
      if (isYes(text)) { send(phrase, true); return; }
      if (isNo(text)) {
        const again = SAY_AGAIN[answerLang] || SAY_AGAIN.en;
        setVoiceMessage(again);
        if (!outputOk || !speaker.speak(again, { lang: answerLang, rate, pitch, voiceName, onEnd: keepOn })) keepOn();
        return;
      }
      // anything else is a new sentence: it is taken as it was said
    }
    if (pendingClear.current) {                           // the answer to "Do you want to clear this chat?"
      pendingClear.current = false;
      setVoiceMessage("");
      if (isYes(text)) { setInput(""); setHeard(""); clearChat().then(() => { if (handsFreeRef.current) later(() => api.current.listen({ auto: true }), 300); }); return; }
      // anything else: the chat is kept and the sentence is taken as it was meant
    }
    const command = matchVoiceCommand(text);
    if (!command) { send(text, true); return; }
    setInput(""); setHeard("");
    const lastReply = [...messagesRef.current].reverse().find((m) => m.role === "ASSISTANT");
    const keepListening = () => { if (handsFreeRef.current) later(() => api.current.listen({ auto: true }), 300); };
    if (command.type === "stop" || command.type === "exit") { speaker.stop(); endHandsFree(); return; }
    if (command.type === "clear") {                       // deleting the chat cannot be undone and background speech can sound like the command: ask first
      pendingClear.current = true;
      const ask = "Do you want to clear this chat? Say yes or no.";
      setVoiceMessage(ask);
      if (!outputOk || !speaker.speak(ask, { lang: "en", rate, pitch, voiceName, onEnd: keepListening })) keepListening();
      return;
    }
    if (command.type === "language") { changeLanguage(command.value); keepListening(); return; }
    if (command.type === "repeat" && lastReply) { if (!speak(lastReply, { then: keepListening })) keepListening(); return; }
    if (command.type === "more" && lastReply) { if (!speak(lastReply, { then: keepListening, full: true })) keepListening(); return; }       // "tell me more": the whole written answer
    if (command.type === "slower" || command.type === "faster") {
      const index = Math.max(0, Math.min(RATES.length - 1, RATES.indexOf(rate) + (command.type === "slower" ? -1 : 1)));
      changeRate(RATES[index]);
      if (lastReply) { if (!speak(lastReply, { then: keepListening, speed: RATES[index] })) keepListening(); } else keepListening();
      return;
    }
    keepListening();
  }, [send, speaker, endHandsFree, clearChat, speak, rate, pitch, later, outputOk, language, answerLang, voiceName]);

  /** What the recogniser finished hearing. Put right (medical words, "h b a 1 c"), then: shown in the box first when the person asked to check it; read back ("Did I hear
   *  ...?") when it holds a number, date or medicine and the recogniser was not sure or had to be corrected; otherwise taken as the question. */
  const onHeard = useCallback((shown, raw, meta) => {
    if (confirmBeforeSend) { setInput(shown); endHandsFree(); inputRef.current?.focus(); return; }
    const ask = pendingConfirm.current ? null : needsConfirmation({ heard: raw, corrected: shown, confidence: meta?.confidence ?? null, vocabulary: vocabRef.current });
    if (ask && !matchVoiceCommand(shown)) {
      pendingConfirm.current = ask;
      const say = (CONFIRM_TEXT[answerLang] || CONFIRM_TEXT.en)(ask);
      setVoiceMessage(say);
      const keepOn = () => { if (handsFreeRef.current) later(() => api.current.listen({ auto: true }), 300); };
      if (!outputOk || !speaker.speak(say, { lang: answerLang, rate, pitch, voiceName, onEnd: keepOn })) keepOn();
      return;
    }
    api.current.onSpoken(shown);
  }, [confirmBeforeSend, endHandsFree, answerLang, outputOk, speaker, rate, pitch, voiceName, later]);

  // ------------------------------------------------------------------ voice input
  /** One round of listening. auto: send what is heard at once and go on (hands-free, or after "Hey HealthWise"); otherwise the words are put in the box to be checked. */
  const listen = useCallback(({ auto = false } = {}) => {
    setVoiceMessage("");
    setHeard("");
    speaker.stop();
    let handled = false;
    let failedKind = null;
    dispatchVoice({ type: "LISTEN" });
    const l = createListener({
      lang: language,
      pauseMs: supportsPauseControl() && pauseMs ? pauseMs : null,
      onStart: () => { if (sounds) cue("start"); },
      onText: (text, final, meta) => {
        if (final && isNoise(text)) return;            // a cough, a bleep or "umm" is not a question: the round counts as silence
        const shown = final ? correctMedicalTerms(text, { lang: language, vocabulary: vocabRef.current }) : text;
        setHeard(shown);
        setInput(shown);                               // shown in the box so the person can correct it before sending
        if (text) retries.current = 0;
        if (text && !final) dispatchVoice({ type: "HEARD" });
        if (final && auto && !handled) { handled = true; silent.current = 0; l?.stop(); setInput(""); api.current.onHeard(shown, text, meta); }
      },
      onError: (kind) => {
        failedKind = kind;
        if (kind === "no-speech" && auto) return;      // handled when this round ends
        if (auto && kind === "network" && retries.current < 1 && navigator.onLine !== false) {      // a network blip: one short retry before saying anything
          retries.current += 1;
          handled = true;
          setListening(false);
          later(() => api.current.listen({ auto: true }), 800);
          return;
        }
        if (kind !== "no-speech" && kind !== "aborted") { handled = true; if (sounds) cue("error"); }
        setVoiceMessage(voiceErrorMessage(kind));
        setListening(false);
        if (auto || handsFreeRef.current) endHandsFree(voiceErrorMessage(kind));
        if (kind !== "no-speech" && kind !== "aborted") dispatchVoice({ type: "ERROR", kind });
        inputRef.current?.focus();
      },
      onEnd: () => {
        setListening(false);
        dispatchVoice({ type: "LISTEN_END" });
        if (listener.current === l) listener.current = null;
        if (auto && !handled && handsFreeRef.current && failedKind !== "aborted") {
          silent.current += 1;                         // nothing was said this time
          if (silent.current >= 2) { endHandsFree("I stopped listening because I did not hear anything. Tap the round button to talk again."); return; }
          later(() => api.current.listen({ auto: true }), 200);
          return;
        }
        if (!auto) inputRef.current?.focus();
      },
    });
    if (!l) { setVoiceMessage(voiceErrorMessage("unsupported")); endHandsFree(); inputRef.current?.focus(); return; }
    listener.current = l;
    setListening(true);
    l.start();
  }, [language, sounds, pauseMs, speaker, endHandsFree, later]);

  const startHandsFree = () => {
    silent.current = 0;
    retries.current = 0;
    handsFreeRef.current = true;
    setHandsFree(true);
    listen({ auto: true });
  };
  const startVoice = (what) => {
    if (!inputOk) { setVoiceMessage(voiceErrorMessage("unsupported")); inputRef.current?.focus(); return; }
    if (store.get("hw_voice_notice", "no") !== "yes") { setVoiceNotice(what); return; }
    if (what === "hands") startHandsFree();
    else if (what === "wake") setWakeOn(true);
    else listen({ auto: false });
  };
  const acceptVoiceNotice = () => { store.set("hw_voice_notice", "yes"); const what = voiceNotice; setVoiceNotice(null); startVoice(what); };

  const onOrb = () => {
    if (listening) { endHandsFree(); return; }
    if (speaking.state !== "idle") { speaker.stop(); startVoice("hands"); return; }
    startVoice("hands");
  };
  const toggleMic = () => {
    if (listening) { if (handsFree) endHandsFree(); else listener.current?.stop(); return; }
    speaker.stop();
    startVoice("dictate");
  };
  const changeWake = (on) => { if (on) startVoice("wake"); else setWakeOn(false); };

  // "Hey HealthWise": listens for the name only while nothing else is going on, then hands over to the normal listening
  useEffect(() => {
    if (!wakeOn || listening || busy || handsFree || voiceNotice || speaking.state !== "idle") return undefined;
    const wake = createWakeListener({
      lang: language,
      onWake: (rest) => { if (sounds) cue("start"); if (rest) api.current.onSpoken(rest); else api.current.listen({ auto: true }); },
      onError: (kind) => { setWakeOn(false); setVoiceMessage(voiceErrorMessage(kind)); },
    });
    wake.start();
    return () => wake.stop();
  }, [wakeOn, listening, busy, handsFree, voiceNotice, speaking.state, language, sounds]);

  api.current = { listen, onSpoken, onHeard };

  const onKey = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); } };
  const lastMessage = messages[messages.length - 1];
  const followUps = lastMessage?.role === "ASSISTANT" ? lastMessage.follow_ups || [] : [];
  const chips = followUps.length ? followUps : suggestions;                   // after an answer: what people usually ask next about it
  const showChips = !busy && chips.length > 0;
  const orbState = voice.phase === "error" ? "idle" : voice.phase;          // after an error the round button is ready again; the message says what happened
  const lastAssistant = [...messages].reverse().find((m) => m.role === "ASSISTANT");

  return (
    <section className="relative flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-card sm:rounded-3xl" aria-label="Ask HealthWise assistant">
      <header className="flex items-center gap-1.5 border-b border-slate-100 bg-slate-50 px-3 py-1.5">
        <p className="flex min-w-0 flex-1 items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1.5 text-xs font-bold text-emerald-800 ring-1 ring-emerald-100" title="Answers use your own medical records. Nobody else can see this chat.">
          <ShieldCheck size={15} className="shrink-0" aria-hidden="true" />
          <span className="truncate" aria-hidden="true"><span className="sm:hidden">Private</span><span className="hidden sm:inline">Private: your own records only</span></span>
          <span className="sr-only">Answers use your own medical records. Nobody else can see this chat.</span>
        </p>
        <label className="flex shrink-0 items-center text-sm font-semibold text-slate-600"><span className="sr-only">Language</span>
          <select value={language} onChange={(e) => changeLanguage(e.target.value)} className="h-11 max-w-[8.5rem] rounded-xl border border-slate-300 bg-white px-2 text-base focus-visible:outline focus-visible:outline-[3px] focus-visible:outline-brand-400">
            {Object.entries(LANG_NAMES).map(([code, name]) => <option key={code} value={code}>{name}</option>)}
          </select>
        </label>
        <button type="button" onClick={() => setConfirmClear(true)} aria-label="Clear chat" title="Clear chat" aria-haspopup="dialog"
          className="grid h-11 w-11 shrink-0 place-items-center rounded-full text-slate-600 hover:bg-slate-100 focus-visible:outline focus-visible:outline-[3px] focus-visible:outline-brand-400"><Trash2 size={19} aria-hidden="true" /></button>
        <MicInfoButton open={micInfo} onClick={() => setMicInfo(true)} />
      </header>
      {confirmClear && (
        <div role="alertdialog" aria-label="Clear this chat?" className="sheet-in flex flex-wrap items-center justify-between gap-2 border-b border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
          <span className="font-semibold">Clear this chat? It cannot be brought back.</span>
          <span className="flex gap-2">
            <button type="button" onClick={() => { setConfirmClear(false); clearChat(); }} className="min-h-11 rounded-xl bg-red-600 px-4 font-semibold text-white hover:bg-red-700">Yes, clear chat</button>
            <button type="button" onClick={() => setConfirmClear(false)} className="min-h-11 rounded-xl bg-white px-4 font-semibold text-slate-700 ring-1 ring-slate-300">Keep it</button>
          </span>
        </div>)}

      <VoicePanel state={orbState} compact={messages.length > 0} heard={heard} level={level} onOrb={onOrb} inputOk={inputOk} outputOk={outputOk} handsFree={handsFree} wakeOn={wakeOn} onWake={changeWake} wakeSupported={inputOk}
        failed={voice.phase === "error"} canReplay={outputOk && Boolean(lastAssistant)} onReplay={() => lastAssistant && speak(lastAssistant)} errorText={voiceMessage}
        voices={voices} voiceName={voiceName} onVoice={changeVoice} autoRead={autoRead} onAutoRead={changeAutoRead} sounds={sounds} onSounds={changeSounds} rate={rate} onRate={changeRate}
        pitch={pitch} onPitch={changePitch} pauseMs={pauseMs} onPause={changePause} pauseSupported={supportsPauseControl()} confirmBeforeSend={confirmBeforeSend} onConfirmBeforeSend={changeCheck}
        privateMode={privateMode} onPrivateMode={changePrivate} bargeIn={bargeIn} onBargeIn={changeBarge} autoLang={autoLang} onAutoLang={changeAutoLang} />

      <div className="relative min-h-0 flex-1">
      <div className="h-full space-y-3 overflow-y-auto overscroll-contain px-3 py-3 sm:px-4" role="log" aria-live="polite" aria-label="Conversation" onScroll={onLogScroll}>
        {messages.length === 0 && (
          <div className="mx-auto max-w-xl py-1 text-center text-slate-700">
            <p className="text-base font-bold text-slate-900 sm:text-lg">Hello! Ask me about your own health records.</p>
            <p className="mt-1 text-sm sm:text-base">I can explain your last checkup, reports, medicines and appointments in simple words. Type, or tap the round button and talk to me.</p>
            {suggestions.length > 0 && (
              <div className="mt-3 grid gap-2 sm:grid-cols-2" aria-label="Suggested questions">
                {suggestions.slice(0, 4).map((q) => (
                  <button key={q.key} type="button" onClick={() => send(q.text)} className="min-h-11 rounded-2xl bg-brand-50 px-4 py-2 text-sm font-semibold text-brand-800 sm:text-base ring-1 ring-brand-100 hover:bg-brand-100 focus-visible:outline focus-visible:outline-[3px] focus-visible:outline-brand-400">{q.text}</button>
                ))}
              </div>)}
          </div>
        )}
        {messages.map((m, index) => {
          const mine = m.role === "PATIENT";
          const emergency = m.safety === "EMERGENCY";
          return (
            <div key={m.id} ref={index === messages.length - (messages[messages.length - 1]?.role === "ASSISTANT" ? 2 : 1) ? lastAnswer : null} className={`msg-in flex scroll-mt-2 ${mine ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[85%] rounded-3xl px-4 py-3 text-base leading-relaxed sm:max-w-[75%] ${mine ? "rounded-br-lg bg-brand-600 text-white" : emergency ? "rounded-bl-lg border-2 border-red-400 bg-red-50 text-red-900" : "rounded-bl-lg bg-slate-100 text-slate-900"}`}>
                {emergency && <p className="mb-1 flex items-center gap-1.5 font-extrabold"><AlertTriangle size={18} /> Urgent</p>}
                {mine ? <p className="whitespace-pre-line">{m.text}</p> : <AnswerText text={m.text} />}
                {!mine && <Sources sources={m.sources} />}
                {m.created_at && <p className={`mt-1 text-xs ${mine ? "text-right text-brand-100" : "text-slate-500"}`}><time dateTime={m.created_at}>{clock(m.created_at)}</time></p>}
                {!mine && m.ai_used && <p className="mt-1 text-xs text-slate-500">Wording simplified by an AI service from the facts above.</p>}
                {!mine && (
                  <div className="mt-2 flex flex-wrap items-center gap-1.5">
                    <CopyAnswer text={m.text} />
                    {outputOk && (speaking.id === m.id && speaking.state !== "idle" ? (
                      <>
                        {speaking.state === "speaking"
                          ? <button type="button" aria-label="Pause reading" onClick={() => speaker.pause()} className="grid h-11 w-11 place-items-center rounded-full bg-white text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50"><Pause size={18} /></button>
                          : <button type="button" aria-label="Resume reading" onClick={() => speaker.resume()} className="grid h-11 w-11 place-items-center rounded-full bg-white text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50"><Play size={18} /></button>}
                        <button type="button" aria-label="Stop speaking" onClick={() => speaker.stop()} className="grid h-11 w-11 place-items-center rounded-full bg-red-700 text-white hover:bg-red-800"><Square size={18} /></button>
                      </>
                    ) : (
                      <button type="button" aria-label="Read this answer aloud" onClick={() => speak(m)} className="flex items-center gap-1.5 rounded-full bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"><Volume2 size={16} /> Listen</button>
                    ))}
                    {outputOk && m.more && !privateMode && !(speaking.id === m.id && speaking.state !== "idle") && (
                      <button type="button" aria-label="Hear all the details of this answer" onClick={() => speak(m, { full: true })} className="flex items-center gap-1.5 rounded-full bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500">Tell me more</button>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}
        {busy && (
          <div className="flex justify-start" role="status">
            <div className="msg-in flex items-center gap-2 rounded-3xl rounded-bl-lg bg-slate-100 px-4 py-3 text-slate-700"><span className="flex gap-1" aria-hidden="true"><i className="typing-dot" /><i className="typing-dot" /><i className="typing-dot" /></span> Looking through your records...</div>
          </div>
        )}
        {failed && (
          <div className="rounded-2xl border border-red-200 bg-red-50 p-3 text-red-800" role="alert">
            <p>{failed.message}</p>
            <button type="button" onClick={() => send(failed.text, failed.viaVoice)} className="mt-1 flex items-center gap-1.5 font-semibold underline"><RotateCcw size={15} /> Try again</button>
          </div>
        )}
        <div ref={bottom} />
      </div>
      {showJump && (
        <button type="button" onClick={jumpToLatest} className="sheet-in absolute bottom-3 left-1/2 flex min-h-11 -translate-x-1/2 items-center gap-1.5 rounded-full bg-brand-700 px-4 text-sm font-bold text-white shadow-lg focus-visible:outline focus-visible:outline-[3px] focus-visible:outline-brand-300"><ArrowDown size={16} aria-hidden="true" /> Jump to latest</button>)}
      </div>

      <footer className="shrink-0 space-y-2 border-t border-slate-100 bg-white px-3 pb-[max(0.5rem,var(--safe-bottom))] pt-2 sm:px-4">
        {showChips && messages.length > 0 && (
          <div className="relative [@media(max-height:32rem)]:hidden">
          <div className="flex items-center gap-2 overflow-x-auto pb-1 pr-10 [scrollbar-width:none]" aria-label="Suggested questions">
            {followUps.length > 0 && <span className="shrink-0 text-sm font-bold text-slate-500">Ask next:</span>}
            {chips.map((s) => (
              <button key={s.key} type="button" onClick={() => send(s.text)} className="shrink-0 whitespace-nowrap rounded-full bg-brand-50 px-3.5 py-1.5 text-sm font-semibold text-brand-700 ring-1 ring-brand-100 hover:bg-brand-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500">{s.text}</button>
            ))}
          </div>
          <span className="pointer-events-none absolute inset-y-0 right-0 w-10 bg-gradient-to-l from-white to-transparent" aria-hidden="true" />
          </div>
        )}
        {voiceNotice && (
          <div className="rounded-2xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900" role="dialog" aria-label="Voice privacy">
            <p>{VOICE_NOTICE}</p>
            <div className="mt-2 flex gap-2">
              <button type="button" onClick={acceptVoiceNotice} className="rounded-xl bg-amber-600 px-3 py-1.5 font-semibold text-white hover:bg-amber-700">I understand, start listening</button>
              <button type="button" onClick={() => { setVoiceNotice(null); inputRef.current?.focus(); }} className="rounded-xl bg-white px-3 py-1.5 font-semibold text-slate-700 ring-1 ring-slate-200">I will type instead</button>
            </div>
          </div>
        )}
        {voiceMessage && <p className="rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-900" role="status">{voiceMessage}</p>}
        {speakNote && <p className="rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-900" role="status">{speakNote}</p>}
        {listening && !handsFree && <p className="flex items-center gap-2 text-sm font-semibold text-red-700" role="status"><span className="flex h-4 items-end gap-0.5" aria-hidden="true"><i className="wave-bar" /><i className="wave-bar" /><i className="wave-bar" /><i className="wave-bar" /></span> Listening... speak now. You can edit the text before sending.</p>}
        <div className="flex items-end gap-2">
          <textarea ref={inputRef} value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={onKey} rows={1} maxLength={1000}
            aria-label="Type your question" placeholder="Ask a question..."
            className="max-h-28 min-h-12 min-w-0 flex-1 resize-none rounded-2xl border border-slate-300 px-4 py-3 text-base focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200" />
          <button type="button" onClick={toggleMic} aria-pressed={listening && !handsFree} aria-label={listening && !handsFree ? "Stop listening" : "Speak your question"}
            className={`relative flex h-12 w-12 shrink-0 items-center justify-center rounded-full text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 ${listening && !handsFree ? "bg-red-700 focus-visible:ring-red-500" : "bg-slate-700 hover:bg-slate-800 focus-visible:ring-slate-500"}`}>
            {listening && !handsFree && <span className="orb-ring orb-ring-listening" aria-hidden="true" />}
            {listening && !handsFree ? <Square size={20} aria-hidden="true" className="relative" /> : <Mic size={22} aria-hidden="true" className="relative" />}
          </button>
          <button type="button" onClick={() => send(input, false)} disabled={busy || !input.trim()} aria-label="Send question"
            className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-brand-700 text-white hover:bg-brand-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-40">
            <Send size={20} />
          </button>
        </div>
        <Disclaimer text={info?.disclaimer || "This assistant gives information from your own records. It is not a doctor. Medical decisions should be made with qualified healthcare professionals."} />
      </footer>
      {micInfo && (
        <MicInfo onClose={() => setMicInfo(false)}>
          {info?.ai_wording_available && (
            <label className="flex items-start gap-2.5 rounded-2xl bg-slate-50 p-3 text-sm text-slate-700">
              <input type="checkbox" checked={aiConsent} onChange={(e) => changeConsent(e.target.checked)} className="mt-0.5 h-5 w-5 shrink-0" />
              <span>Let an outside AI service make answers simpler. It sees only the answer text, without your name, phone or email, and can never change a number or date.</span>
            </label>
          )}
        </MicInfo>
      )}
    </section>
  );
}
