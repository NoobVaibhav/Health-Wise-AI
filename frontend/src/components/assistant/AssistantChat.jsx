// The patient's chat and voice assistant. It answers only from the signed-in patient's own records (the server decides which),
// shows where every answer came from, and works by typing alone when voice is not available.
// Voice: press the orb for a hands-free conversation (listen, answer aloud, listen again), or say "Hey HealthWise" (optional), or use the
// small microphone to dictate one question. All of it uses the browser's own free speech features: no outside voice service or key.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { AlertTriangle, Check, Copy, Loader2, Mic, Pause, Play, RotateCcw, Send, ShieldCheck, Square, Trash2, Volume2 } from "lucide-react";
import { deleteConversation, getAssistantInfo, getSuggestions, sendChat } from "../../services/assistantApi";
import { getErrorMessage } from "../../services/api";
import {
  LANG_NAMES, VOICE_NOTICE, createListener, createSpeaker, createWakeListener, cue, matchVoiceCommand, speechInputSupported, speechOutputSupported,
  voiceErrorMessage, voicesFor,
} from "../../utils/voice";
import VoicePanel from "./VoicePanel";

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

export default function AssistantChat() {
  const navigate = useNavigate();
  const [language, setLanguage] = useState(() => store.get("hw_assistant_lang", "en"));
  const [rate, setRate] = useState(() => Number(store.get("hw_assistant_rate", "1")));
  const [voiceName, setVoiceName] = useState(() => store.get("hw_assistant_voice", ""));
  const [autoRead, setAutoRead] = useState(() => store.get("hw_assistant_autoread", "no") === "yes");
  const [sounds, setSounds] = useState(() => store.get("hw_assistant_sounds", "yes") === "yes");
  const [aiConsent, setAiConsent] = useState(() => store.get("hw_assistant_ai", "no") === "yes");
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
  const listener = useRef(null);
  const bottom = useRef(null);
  const lastAnswer = useRef(null);
  const inputRef = useRef(null);
  const speakingId = useRef(null);
  const handsFreeRef = useRef(false);
  const silent = useRef(0);                               // listening rounds in a row in which nothing was said
  const messagesRef = useRef([]);
  const api = useRef({});                                 // the latest functions, for timers and callbacks that outlive a render
  const timers = useRef(new Set());
  /** A delayed call that is cancelled when the person leaves the page, so the microphone never starts on a page that is gone. */
  const later = useCallback((fn, ms) => {
    const id = setTimeout(() => { timers.current.delete(id); fn(); }, ms);
    timers.current.add(id);
  }, []);

  const inputOk = speechInputSupported();
  const outputOk = speechOutputSupported();
  const speaker = useMemo(() => createSpeaker({
    onState: (state) => setSpeaking((s) => ({ id: state === "idle" ? null : speakingId.current, state })),
    onProblem: setSpeakNote,
  }), []);

  useEffect(() => { getAssistantInfo(language).then(setInfo).catch(() => {}); }, [language]);
  useEffect(() => { getSuggestions(language).then(setSuggestions).catch(() => setSuggestions([])); }, [language]);
  useEffect(() => { messagesRef.current = messages; }, [messages]);
  // a new answer is shown from the question that led to it, so a long answer is read from its first line; the waiting note goes to the bottom
  useEffect(() => {
    const last = messages[messages.length - 1];
    const answered = last?.role === "ASSISTANT" && !busy && !failed;
    (answered ? lastAnswer.current : bottom.current)?.scrollIntoView?.({ behavior: "smooth", block: answered ? "start" : "end" });
  }, [messages, busy, failed]);
  useEffect(() => () => {
    handsFreeRef.current = false;
    timers.current.forEach(clearTimeout);
    timers.current.clear();
    speaker.stop();
    listener.current?.abort();
  }, [speaker]);
  useEffect(() => {                                       // the list of installed voices arrives a moment after the page opens
    if (!outputOk) return undefined;
    const load = () => setVoices(voicesFor(language));
    load();
    window.speechSynthesis.addEventListener?.("voiceschanged", load);
    return () => window.speechSynthesis.removeEventListener?.("voiceschanged", load);
  }, [outputOk, language]);

  const changeLanguage = (code) => { setLanguage(code); store.set("hw_assistant_lang", code); speaker.stop(); };
  const changeRate = (value) => { setRate(value); store.set("hw_assistant_rate", String(value)); };
  const changeVoice = (name) => { setVoiceName(name); store.set("hw_assistant_voice", name); };
  const changeAutoRead = (on) => { setAutoRead(on); store.set("hw_assistant_autoread", on ? "yes" : "no"); };
  const changeSounds = (on) => { setSounds(on); store.set("hw_assistant_sounds", on ? "yes" : "no"); };
  const changeConsent = (on) => { setAiConsent(on); store.set("hw_assistant_ai", on ? "yes" : "no"); };

  const speak = useCallback((message, { then, speed } = {}) => {
    speakingId.current = message.id;
    setSpeakNote("");
    return speaker.speak(message.text, { lang: language, rate: speed ?? rate, voiceName, onEnd: then });
  }, [speaker, language, rate, voiceName]);

  // ------------------------------------------------------------------ the conversation
  const endHandsFree = useCallback((message = "") => {
    handsFreeRef.current = false;
    setHandsFree(false);
    silent.current = 0;
    listener.current?.abort();
    setListening(false);
    setHeard("");
    if (message) setVoiceMessage(message);
  }, []);

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
    setBusy(true);
    setFailed(null);
    setInput("");
    setHeard("");
    setMessages((m) => [...m, { id: `local-${Date.now()}`, role: "PATIENT", text }]);
    try {
      const data = await sendChat({ message: text, conversation_id: conversationId, language, ai_consent: aiConsent });
      setConversationId(data.conversation_id);
      setMessages((m) => [...m.filter((x) => !String(x.id).startsWith("local-")), data.message, data.reply]);
      setBusy(false);
      if (sounds && viaVoice) cue("done");
      finishReply(data.reply, viaVoice);
    } catch (e) {
      endHandsFree();
      if (sounds && viaVoice) cue("error");
      setMessages((m) => m.filter((x) => !String(x.id).startsWith("local-")));
      setFailed({ text, viaVoice, message: e.response?.status === 401 ? "Your session has ended. Please log in again." : getErrorMessage(e) });
      setInput(text);                                 // the typed question is never lost
      setBusy(false);
    }
  }, [busy, conversationId, language, aiConsent, sounds, speaker, finishReply, endHandsFree]);

  const clearChat = useCallback(async () => {
    speaker.stop();
    if (conversationId) { try { await deleteConversation(conversationId); } catch { /* the chat on screen is cleared anyway */ } }
    setMessages([]); setConversationId(null); setFailed(null); setInput("");
  }, [conversationId, speaker]);

  /** A spoken sentence: a command for the voice itself ("stop", "repeat", "speak slower", "switch to Hindi"), or a question. */
  const onSpoken = useCallback((text) => {
    const command = matchVoiceCommand(text);
    if (!command) { send(text, true); return; }
    setInput(""); setHeard("");
    const lastReply = [...messagesRef.current].reverse().find((m) => m.role === "ASSISTANT");
    const keepListening = () => { if (handsFreeRef.current) later(() => api.current.listen({ auto: true }), 300); };
    if (command.type === "stop" || command.type === "exit") { speaker.stop(); endHandsFree(); return; }
    if (command.type === "clear") { clearChat().then(keepListening); return; }
    if (command.type === "language") { changeLanguage(command.value); keepListening(); return; }
    if (command.type === "repeat" && lastReply) { if (!speak(lastReply, { then: keepListening })) keepListening(); return; }
    if (command.type === "slower" || command.type === "faster") {
      const index = Math.max(0, Math.min(RATES.length - 1, RATES.indexOf(rate) + (command.type === "slower" ? -1 : 1)));
      changeRate(RATES[index]);
      if (lastReply) { if (!speak(lastReply, { then: keepListening, speed: RATES[index] })) keepListening(); } else keepListening();
      return;
    }
    keepListening();
  }, [send, speaker, endHandsFree, clearChat, speak, rate, later]);

  // ------------------------------------------------------------------ voice input
  /** One round of listening. auto: send what is heard at once and go on (hands-free, or after "Hey HealthWise"); otherwise the words are put in the box to be checked. */
  const listen = useCallback(({ auto = false } = {}) => {
    setVoiceMessage("");
    setHeard("");
    speaker.stop();
    let handled = false;
    let failedKind = null;
    const l = createListener({
      lang: language,
      onStart: () => { if (sounds) cue("start"); },
      onText: (text, final) => {
        setHeard(text);
        setInput(text);                               // shown in the box so the person can correct it before sending
        if (final && auto && !handled) { handled = true; silent.current = 0; l?.stop(); setInput(""); api.current.onSpoken(text); }
      },
      onError: (kind) => {
        failedKind = kind;
        if (kind === "no-speech" && auto) return;      // handled when this round ends
        if (kind !== "no-speech" && kind !== "aborted") { handled = true; if (sounds) cue("error"); }
        setVoiceMessage(voiceErrorMessage(kind));
        setListening(false);
        if (auto || handsFreeRef.current) endHandsFree(voiceErrorMessage(kind));
        inputRef.current?.focus();
      },
      onEnd: () => {
        setListening(false);
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
  }, [language, sounds, speaker, endHandsFree, later]);

  const startHandsFree = () => {
    silent.current = 0;
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

  api.current = { listen, onSpoken };

  const onKey = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); } };
  const lastMessage = messages[messages.length - 1];
  const followUps = lastMessage?.role === "ASSISTANT" ? lastMessage.follow_ups || [] : [];
  const chips = followUps.length ? followUps : suggestions;                   // after an answer: what people usually ask next about it
  const showChips = !busy && chips.length > 0;
  const orbState = listening ? "listening" : busy ? "thinking" : speaking.state !== "idle" ? "speaking" : "idle";

  return (
    <section className="flex h-[calc(100vh-19rem)] min-h-[34rem] flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm" aria-label="Ask HealthWise assistant">
      <header className="flex flex-wrap items-center gap-3 border-b border-slate-100 bg-slate-50 px-4 py-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-emerald-800" title="Answers use only your own medical records.">
          <ShieldCheck size={18} /> <span>Answers use your own medical records. Nobody else can see this chat.</span>
        </div>
        <div className="ml-auto flex flex-wrap items-center gap-2 text-sm">
          <label className="flex items-center gap-1.5 font-semibold text-slate-600">Language
            <select value={language} onChange={(e) => changeLanguage(e.target.value)} className="rounded-xl border border-slate-300 bg-white px-2 py-1.5 text-base">
              {Object.entries(LANG_NAMES).map(([code, name]) => <option key={code} value={code}>{name}</option>)}
            </select>
          </label>
          <button type="button" onClick={clearChat} className="flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-3 py-1.5 font-semibold text-slate-700 hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500">
            <Trash2 size={16} /> Clear chat
          </button>
        </div>
      </header>

      <VoicePanel state={orbState} heard={heard} onOrb={onOrb} inputOk={inputOk} outputOk={outputOk} handsFree={handsFree} wakeOn={wakeOn} onWake={changeWake} wakeSupported={inputOk}
        voices={voices} voiceName={voiceName} onVoice={changeVoice} autoRead={autoRead} onAutoRead={changeAutoRead} sounds={sounds} onSounds={changeSounds} rate={rate} onRate={changeRate} />

      <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4" role="log" aria-live="polite" aria-label="Conversation">
        {messages.length === 0 && (
          <div className="mx-auto max-w-xl rounded-2xl bg-brand-50/60 p-5 text-center text-slate-700">
            <p className="text-lg font-bold text-slate-900">Hello! Ask me about your own health records.</p>
            <p className="mt-1">I can explain your last checkup, reports, medicines and appointments in simple words. You can type, or press the round button and just talk to me.</p>
          </div>
        )}
        {messages.map((m, index) => {
          const mine = m.role === "PATIENT";
          const emergency = m.safety === "EMERGENCY";
          return (
            <div key={m.id} ref={index === messages.length - (messages[messages.length - 1]?.role === "ASSISTANT" ? 2 : 1) ? lastAnswer : null} className={`flex scroll-mt-2 ${mine ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[92%] rounded-3xl px-4 py-3 text-base leading-relaxed sm:max-w-[80%] ${mine ? "rounded-br-lg bg-brand-600 text-white" : emergency ? "rounded-bl-lg border-2 border-red-400 bg-red-50 text-red-900" : "rounded-bl-lg bg-slate-100 text-slate-900"}`}>
                {emergency && <p className="mb-1 flex items-center gap-1.5 font-extrabold"><AlertTriangle size={18} /> Urgent</p>}
                {mine ? <p className="whitespace-pre-line">{m.text}</p> : <AnswerText text={m.text} />}
                {!mine && <Sources sources={m.sources} />}
                {!mine && m.ai_used && <p className="mt-1 text-xs text-slate-500">Wording simplified by an AI service from the facts above.</p>}
                {!mine && (
                  <div className="mt-2 flex flex-wrap items-center gap-1.5">
                    <CopyAnswer text={m.text} />
                    {outputOk && (speaking.id === m.id && speaking.state !== "idle" ? (
                      <>
                        {speaking.state === "speaking"
                          ? <button type="button" aria-label="Pause reading" onClick={() => speaker.pause()} className="rounded-full bg-white p-2 text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50"><Pause size={16} /></button>
                          : <button type="button" aria-label="Resume reading" onClick={() => speaker.resume()} className="rounded-full bg-white p-2 text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50"><Play size={16} /></button>}
                        <button type="button" aria-label="Stop speaking" onClick={() => speaker.stop()} className="rounded-full bg-red-600 p-2 text-white hover:bg-red-700"><Square size={16} /></button>
                      </>
                    ) : (
                      <button type="button" aria-label="Read this answer aloud" onClick={() => speak(m)} className="flex items-center gap-1.5 rounded-full bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"><Volume2 size={16} /> Listen</button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          );
        })}
        {busy && (
          <div className="flex justify-start" role="status">
            <div className="flex items-center gap-2 rounded-3xl rounded-bl-lg bg-slate-100 px-4 py-3 text-slate-600"><Loader2 className="animate-spin" size={18} /> Looking through your records...</div>
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

      <footer className="space-y-2 border-t border-slate-100 bg-white px-4 py-3">
        {showChips && (
          <div className="flex items-center gap-2 overflow-x-auto pb-1" aria-label="Suggested questions">
            {followUps.length > 0 && <span className="shrink-0 text-sm font-bold text-slate-500">Ask next:</span>}
            {chips.map((s) => (
              <button key={s.key} type="button" onClick={() => send(s.text)} className="shrink-0 whitespace-nowrap rounded-full bg-brand-50 px-3.5 py-1.5 text-sm font-semibold text-brand-700 ring-1 ring-brand-100 hover:bg-brand-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500">{s.text}</button>
            ))}
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
        {listening && !handsFree && <p className="flex items-center gap-2 text-sm font-semibold text-red-600" role="status"><span className="h-2.5 w-2.5 animate-pulse rounded-full bg-red-600" /> Listening... speak now. You can edit the text before sending.</p>}
        <div className="flex items-end gap-2">
          <textarea ref={inputRef} value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={onKey} rows={1} maxLength={1000}
            aria-label="Type your question" placeholder="Type your question, or press the microphone..."
            className="max-h-32 min-h-[3rem] flex-1 resize-none rounded-2xl border border-slate-300 px-4 py-3 text-base focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200" />
          <button type="button" onClick={toggleMic} aria-pressed={listening && !handsFree} aria-label={listening && !handsFree ? "Stop listening" : "Speak your question"}
            className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 ${listening && !handsFree ? "animate-pulse bg-red-600 focus-visible:ring-red-500" : "bg-slate-700 hover:bg-slate-800 focus-visible:ring-slate-500"}`}>
            {listening && !handsFree ? <Square size={18} /> : <Mic size={20} />}
          </button>
          <button type="button" onClick={() => send(input, false)} disabled={busy || !input.trim()} aria-label="Send question"
            className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-brand-600 text-white hover:bg-brand-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-40">
            <Send size={20} />
          </button>
        </div>
        {info?.ai_wording_available && (
          <label className="flex items-start gap-2 text-sm text-slate-600">
            <input type="checkbox" checked={aiConsent} onChange={(e) => changeConsent(e.target.checked)} className="mt-1 h-4 w-4" />
            <span>Let an outside AI service make answers simpler. It sees only the answer text, without your name, phone or email, and can never change a number or date.</span>
          </label>
        )}
        <p className="text-xs text-slate-500">{info?.disclaimer || "This assistant gives information from your own records. It is not a doctor. Medical decisions should be made with qualified healthcare professionals."}</p>
      </footer>
    </section>
  );
}
