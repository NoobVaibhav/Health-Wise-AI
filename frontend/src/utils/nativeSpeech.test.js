import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const h = vi.hoisted(() => ({ native: true, handlers: {}, listening: true, tts: null }));

vi.mock("@capacitor/core", () => ({ Capacitor: { isNativePlatform: () => h.native } }));
vi.mock("@capacitor-community/speech-recognition", () => ({
  SpeechRecognition: {
    checkPermissions: vi.fn(async () => ({ speechRecognition: "granted" })),
    requestPermissions: vi.fn(async () => ({ speechRecognition: "granted" })),
    available: vi.fn(async () => ({ available: true })),
    addListener: vi.fn(async (name, fn) => { h.handlers[name] = fn; return { remove: () => { delete h.handlers[name]; } }; }),
    start: vi.fn(async () => {}),
    stop: vi.fn(async () => {}),
    isListening: vi.fn(async () => ({ isListening: h.listening })),
  },
}));
vi.mock("@capacitor-community/text-to-speech", () => ({
  TextToSpeech: {
    getSupportedVoices: vi.fn(async () => ({ voices: [{ name: "English India", voiceURI: "en-in", lang: "en-IN", default: true }] })),
    speak: vi.fn((opts) => h.tts(opts)),
    stop: vi.fn(async () => {}),
  },
}));

const load = async () => {
  vi.resetModules();
  delete window.SpeechRecognition;
  delete window.SpeechSynthesisUtterance;
  await import("./nativeSpeech");
};
const flush = async () => { for (let i = 0; i < 8; i += 1) await Promise.resolve(); };

beforeEach(() => { vi.useFakeTimers(); h.native = true; h.handlers = {}; h.listening = true; h.tts = async () => {}; });
afterEach(() => { vi.useRealTimers(); });

describe("not in the Android app", () => {
  it("leaves the browser's own speech alone", async () => {
    h.native = false;
    await load();
    expect(window.SpeechRecognition).toBeUndefined();
    expect(window.SpeechSynthesisUtterance).toBeUndefined();
  });
});

describe("listening on the phone", () => {
  const start = async () => {
    await load();
    const rec = new window.SpeechRecognition();
    const events = { results: [], errors: [], ended: 0 };
    rec.onresult = (e) => events.results.push([e.results[0][0].transcript, e.results[0].isFinal]);
    rec.onerror = (e) => events.errors.push(e.error);
    rec.onend = () => { events.ended += 1; };
    await rec.start();
    await flush();
    return { rec, events };
  };

  it("passes the words on while they are spoken, then the final text once the phone says speech ended", async () => {
    const { events } = await start();
    h.handlers.partialResults({ matches: ["what are"] });
    h.handlers.listeningState({ status: "stopped" });
    h.handlers.partialResults({ matches: ["what are my medicines"] });     // the final text arrives after "stopped"
    expect(events.results).toEqual([["what are", false], ["what are my medicines", true]]);
    expect(events.ended).toBe(1);
    expect(events.errors).toEqual([]);
  });

  it("uses the last words heard when the final text never comes", async () => {
    const { events } = await start();
    h.handlers.partialResults({ matches: ["my allergies"] });
    h.handlers.listeningState({ status: "stopped" });
    await vi.advanceTimersByTimeAsync(1600);
    expect(events.results.at(-1)).toEqual(["my allergies", true]);
    expect(events.ended).toBe(1);
  });

  it("says nothing was heard when the phone stops listening by itself (the plugin gives no error for this)", async () => {
    const { events } = await start();
    h.listening = false;
    await vi.advanceTimersByTimeAsync(800 + 1600);
    expect(events.errors).toEqual(["no-speech"]);
    expect(events.ended).toBe(1);
  });

  it("gives up after nine seconds of silence", async () => {
    const { events } = await start();
    await vi.advanceTimersByTimeAsync(9100);
    expect(events.errors).toEqual(["no-speech"]);
    expect(events.ended).toBe(1);
  });

  it("does not time out while the person is speaking", async () => {
    const { events } = await start();
    h.handlers.listeningState({ status: "started" });
    await vi.advanceTimersByTimeAsync(9500);
    expect(events.errors).toEqual([]);
    expect(events.ended).toBe(0);
  });

  it("reports a refused microphone permission", async () => {
    const { SpeechRecognition: Native } = await import("@capacitor-community/speech-recognition");
    Native.checkPermissions.mockResolvedValueOnce({ speechRecognition: "denied" });
    Native.requestPermissions.mockResolvedValueOnce({ speechRecognition: "denied" });
    await load();
    const rec = new window.SpeechRecognition();
    const errors = [];
    rec.onerror = (e) => errors.push(e.error);
    await rec.start();
    expect(errors).toEqual(["not-allowed"]);
  });

  it("abort ends the round at once and keeps nothing", async () => {
    const { rec, events } = await start();
    h.handlers.partialResults({ matches: ["half a sentence"] });
    rec.abort();
    expect(events.ended).toBe(1);
    expect(events.results.at(-1)).toEqual(["half a sentence", false]);
  });
});

describe("speaking on the phone", () => {
  it("gives the page a speech synthesis with the phone's voices", async () => {
    await load();
    await flush();
    expect(window.speechSynthesis.getVoices()).toMatchObject([{ name: "English India", lang: "en-IN" }]);
  });

  it("reads an utterance and reports its start and end", async () => {
    await load();
    const said = [];
    h.tts = async (o) => { said.push(o); };
    const u = new window.SpeechSynthesisUtterance("Hello");
    const log = [];
    u.onstart = () => log.push("start");
    u.onend = () => log.push("end");
    u.rate = 1.25;
    await window.speechSynthesis.speak(u);
    expect(log).toEqual(["start", "end"]);
    expect(said[0]).toMatchObject({ text: "Hello", rate: 1.25 });
  });

  it("stays quiet about an utterance that was cancelled", async () => {
    await load();
    let release;
    h.tts = () => new Promise((r) => { release = r; });
    const u = new window.SpeechSynthesisUtterance("Long text");
    const log = [];
    u.onend = () => log.push("end");
    u.onerror = () => log.push("error");
    const pending = window.speechSynthesis.speak(u);
    window.speechSynthesis.cancel();
    release();
    await pending;
    expect(log).toEqual([]);
  });

  it("reports an error when the phone cannot speak", async () => {
    await load();
    h.tts = async () => { throw new Error("no engine"); };
    const u = new window.SpeechSynthesisUtterance("Hello");
    const errors = [];
    u.onerror = (e) => errors.push(e.error);
    await window.speechSynthesis.speak(u);
    expect(errors).toEqual(["synthesis-failed"]);
  });
});
