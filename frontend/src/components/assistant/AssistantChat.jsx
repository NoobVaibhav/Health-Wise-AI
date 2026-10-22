// The patient's chat and voice assistant. It answers only from the signed-in patient's own records (the server decides which),
// shows where every answer came from, and works by typing alone when voice is not available.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, Loader2, Mic, Pause, Play, RotateCcw, Send, ShieldCheck, Square, Trash2, Volume2 } from "lucide-react";
import { deleteConversation, getAssistantInfo, getSuggestions, sendChat } from "../../services/assistantApi";
import { getErrorMessage } from "../../services/api";
import { LANG_NAMES, VOICE_NOTICE, createListener, createSpeaker, speechInputSupported, speechOutputSupported, voiceErrorMessage } from "../../utils/voice";

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

function Sources({ sources }) {
  if (!sources?.length) return null;
  return (
    <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs">
      <span className="font-semibold text-slate-500">Source:</span>
      {sources.map((s) => (
        <Link key={`${s.type}-${s.id}`} to={(SOURCE_ROUTE[s.type] || (() => "/patient"))(s)}
          className="rounded-full bg-brand-50 px-2.5 py-1 font-semibold text-brand-700 ring-1 ring-brand-100 hover:bg-brand-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500">
          {s.label}{s.date ? ` · ${when(s.date)}` : ""}
        </Link>
      ))}
    </div>
  );
}

export default function AssistantChat() {
  const [language, setLanguage] = useState(() => store.get("hw_assistant_lang", "en"));
  const [rate, setRate] = useState(() => Number(store.get("hw_assistant_rate", "1")));
  const [aiConsent, setAiConsent] = useState(() => store.get("hw_assistant_ai", "no") === "yes");
  const [info, setInfo] = useState(null);
  const [suggestions, setSuggestions] = useState([]);
  const [messages, setMessages] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState(null);            // { text, viaVoice, message } of the question that did not get an answer
  const [listening, setListening] = useState(false);
  const [voiceNotice, setVoiceNotice] = useState(false);
  const [voiceMessage, setVoiceMessage] = useState("");
  const [speaking, setSpeaking] = useState({ id: null, state: "idle" });
  const [speakNote, setSpeakNote] = useState("");
  const listener = useRef(null);
  const bottom = useRef(null);
  const inputRef = useRef(null);
  const speakingId = useRef(null);

  const inputOk = speechInputSupported();
  const outputOk = speechOutputSupported();
  const speaker = useMemo(() => createSpeaker({
    onState: (state) => setSpeaking((s) => ({ id: state === "idle" ? null : speakingId.current, state })),
    onProblem: setSpeakNote,
  }), []);

  useEffect(() => { getAssistantInfo(language).then(setInfo).catch(() => {}); }, [language]);
  useEffect(() => { getSuggestions(language).then(setSuggestions).catch(() => setSuggestions([])); }, [language]);
  useEffect(() => { bottom.current?.scrollIntoView?.({ behavior: "smooth", block: "end" }); }, [messages, busy, failed]);
  useEffect(() => () => { speaker.stop(); listener.current?.stop(); }, [speaker]);

  const changeLanguage = (code) => { setLanguage(code); store.set("hw_assistant_lang", code); speaker.stop(); };
  const changeRate = (value) => { setRate(value); store.set("hw_assistant_rate", String(value)); };
  const changeConsent = (on) => { setAiConsent(on); store.set("hw_assistant_ai", on ? "yes" : "no"); };

  const speak = useCallback((message) => {
    speakingId.current = message.id;
    setSpeakNote("");
    speaker.speak(message.text, { lang: language, rate });
  }, [speaker, language, rate]);

  const send = useCallback(async (raw, viaVoice = false) => {
    const text = raw.trim();
    if (!text || busy) return;
    if (typeof navigator !== "undefined" && navigator.onLine === false) {
      setFailed({ text, viaVoice, message: "You seem to be offline. Your question is kept; send it again when the connection is back." });
      return;
    }
    speaker.stop();
    setBusy(true);
    setFailed(null);
    setInput("");
    setMessages((m) => [...m, { id: `local-${Date.now()}`, role: "PATIENT", text }]);
    try {
      const data = await sendChat({ message: text, conversation_id: conversationId, language, ai_consent: aiConsent });
      setConversationId(data.conversation_id);
      setMessages((m) => [...m.filter((x) => !String(x.id).startsWith("local-")), data.message, data.reply]);
      if ((viaVoice || data.reply.safety === "EMERGENCY") && outputOk) speak(data.reply);
    } catch (e) {
      setMessages((m) => m.filter((x) => !String(x.id).startsWith("local-")));
      setFailed({ text, viaVoice, message: e.response?.status === 401 ? "Your session has ended. Please log in again." : getErrorMessage(e) });
      setInput(text);                                 // the typed question is never lost
    } finally {
      setBusy(false);
    }
  }, [busy, conversationId, language, aiConsent, outputOk, speak, speaker]);

  // ------------------------------------------------------------------ voice input
  const beginListening = () => {
    setVoiceMessage("");
    const l = createListener({
      lang: language,
      onText: (text) => setInput(text),                // shown in the box so the patient can correct it before sending
      onError: (kind) => { setVoiceMessage(voiceErrorMessage(kind)); setListening(false); inputRef.current?.focus(); },
      onEnd: () => { setListening(false); inputRef.current?.focus(); },
    });
    if (!l) { setVoiceMessage(voiceErrorMessage("unsupported")); inputRef.current?.focus(); return; }
    listener.current = l;
    setListening(true);
    l.start();
  };
  const toggleMic = () => {
    if (listening) { listener.current?.stop(); return; }
    speaker.stop();
    if (!inputOk) { setVoiceMessage(voiceErrorMessage("unsupported")); inputRef.current?.focus(); return; }
    if (store.get("hw_voice_notice", "no") !== "yes") { setVoiceNotice(true); return; }
    beginListening();
  };
  const acceptVoiceNotice = () => { store.set("hw_voice_notice", "yes"); setVoiceNotice(false); beginListening(); };

  const clearChat = async () => {
    speaker.stop();
    if (conversationId) { try { await deleteConversation(conversationId); } catch { /* the chat on screen is cleared anyway */ } }
    setMessages([]); setConversationId(null); setFailed(null); setInput("");
  };

  const onKey = (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); } };
  const showChips = !busy && suggestions.length > 0;

  return (
    <section className="flex h-[calc(100vh-19rem)] min-h-[30rem] flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm" aria-label="Ask HealthWise assistant">
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
          {outputOk && (
            <label className="flex items-center gap-1.5 font-semibold text-slate-600">Voice speed
              <select value={rate} onChange={(e) => changeRate(Number(e.target.value))} className="rounded-xl border border-slate-300 bg-white px-2 py-1.5 text-base">
                <option value={0.8}>Slow</option><option value={1}>Normal</option><option value={1.25}>Fast</option>
              </select>
            </label>
          )}
          <button type="button" onClick={clearChat} className="flex items-center gap-1.5 rounded-xl border border-slate-300 bg-white px-3 py-1.5 font-semibold text-slate-700 hover:bg-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500">
            <Trash2 size={16} /> Clear chat
          </button>
        </div>
      </header>

      <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4" role="log" aria-live="polite" aria-label="Conversation">
        {messages.length === 0 && (
          <div className="mx-auto max-w-xl rounded-2xl bg-brand-50/60 p-5 text-center text-slate-700">
            <p className="text-lg font-bold text-slate-900">Hello! Ask me about your own health records.</p>
            <p className="mt-1">I can explain your last checkup, reports, medicines and appointments in simple words. You can type, or press the microphone and speak.</p>
          </div>
        )}
        {messages.map((m) => {
          const mine = m.role === "PATIENT";
          const emergency = m.safety === "EMERGENCY";
          return (
            <div key={m.id} className={`flex ${mine ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[92%] rounded-3xl px-4 py-3 text-base leading-relaxed sm:max-w-[80%] ${mine ? "rounded-br-lg bg-brand-600 text-white" : emergency ? "rounded-bl-lg border-2 border-red-400 bg-red-50 text-red-900" : "rounded-bl-lg bg-slate-100 text-slate-900"}`}>
                {emergency && <p className="mb-1 flex items-center gap-1.5 font-extrabold"><AlertTriangle size={18} /> Urgent</p>}
                <p className="whitespace-pre-line">{m.text}</p>
                {!mine && <Sources sources={m.sources} />}
                {!mine && m.ai_used && <p className="mt-1 text-xs text-slate-500">Wording simplified by an AI service from the facts above.</p>}
                {!mine && outputOk && (
                  <div className="mt-2 flex items-center gap-1.5">
                    {speaking.id === m.id && speaking.state !== "idle" ? (
                      <>
                        {speaking.state === "speaking"
                          ? <button type="button" aria-label="Pause reading" onClick={() => speaker.pause()} className="rounded-full bg-white p-2 text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50"><Pause size={16} /></button>
                          : <button type="button" aria-label="Resume reading" onClick={() => speaker.resume()} className="rounded-full bg-white p-2 text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50"><Play size={16} /></button>}
                        <button type="button" aria-label="Stop speaking" onClick={() => speaker.stop()} className="rounded-full bg-red-600 p-2 text-white hover:bg-red-700"><Square size={16} /></button>
                      </>
                    ) : (
                      <button type="button" aria-label="Read this answer aloud" onClick={() => speak(m)} className="flex items-center gap-1.5 rounded-full bg-white px-3 py-1.5 text-sm font-semibold text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"><Volume2 size={16} /> Listen</button>
                    )}
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
          <div className="flex gap-2 overflow-x-auto pb-1" aria-label="Suggested questions">
            {suggestions.map((s) => (
              <button key={s.key} type="button" onClick={() => send(s.text)} className="shrink-0 whitespace-nowrap rounded-full bg-brand-50 px-3.5 py-1.5 text-sm font-semibold text-brand-700 ring-1 ring-brand-100 hover:bg-brand-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500">{s.text}</button>
            ))}
          </div>
        )}
        {voiceNotice && (
          <div className="rounded-2xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900" role="dialog" aria-label="Voice privacy">
            <p>{VOICE_NOTICE}</p>
            <div className="mt-2 flex gap-2">
              <button type="button" onClick={acceptVoiceNotice} className="rounded-xl bg-amber-600 px-3 py-1.5 font-semibold text-white hover:bg-amber-700">I understand, start listening</button>
              <button type="button" onClick={() => { setVoiceNotice(false); inputRef.current?.focus(); }} className="rounded-xl bg-white px-3 py-1.5 font-semibold text-slate-700 ring-1 ring-slate-200">I will type instead</button>
            </div>
          </div>
        )}
        {voiceMessage && <p className="rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-900" role="status">{voiceMessage}</p>}
        {speakNote && <p className="rounded-xl bg-amber-50 px-3 py-2 text-sm text-amber-900" role="status">{speakNote}</p>}
        {listening && <p className="flex items-center gap-2 text-sm font-semibold text-red-600" role="status"><span className="h-2.5 w-2.5 animate-pulse rounded-full bg-red-600" /> Listening... speak now. You can edit the text before sending.</p>}
        <div className="flex items-end gap-2">
          <textarea ref={inputRef} value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={onKey} rows={1} maxLength={1000}
            aria-label="Type your question" placeholder="Type your question, or press the microphone..."
            className="max-h-32 min-h-[3rem] flex-1 resize-none rounded-2xl border border-slate-300 px-4 py-3 text-base focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200" />
          <button type="button" onClick={toggleMic} aria-pressed={listening} aria-label={listening ? "Stop listening" : "Speak your question"}
            className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-full text-white focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 ${listening ? "animate-pulse bg-red-600 focus-visible:ring-red-500" : "bg-slate-700 hover:bg-slate-800 focus-visible:ring-slate-500"}`}>
            {listening ? <Square size={18} /> : <Mic size={20} />}
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
