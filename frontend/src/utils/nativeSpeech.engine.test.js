import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const h = vi.hoisted(() => ({ community: null }));
vi.mock("@capacitor/core", () => ({ Capacitor: { isNativePlatform: () => true } }));
vi.mock("@capacitor-community/speech-recognition", () => {
  h.community = {
    checkPermissions: vi.fn(async () => ({ speechRecognition: "granted" })), requestPermissions: vi.fn(async () => ({ speechRecognition: "granted" })), available: vi.fn(async () => ({ available: true })),
    addListener: vi.fn(async () => ({ remove() {} })), start: vi.fn(async () => {}), stop: vi.fn(async () => {}), isListening: vi.fn(async () => ({ isListening: true })),
  };
  return { SpeechRecognition: h.community };
});
vi.mock("@capacitor-community/text-to-speech", () => ({ TextToSpeech: { getSupportedVoices: vi.fn(async () => ({ voices: [] })), speak: vi.fn(async () => {}), stop: vi.fn(async () => {}) } }));

const flush = async () => { for (let i = 0; i < 8; i += 1) await Promise.resolve(); };
beforeEach(() => { vi.useFakeTimers(); });
afterEach(() => { vi.useRealTimers(); });

describe("the engine behind the Android app's recogniser can be swapped", () => {
  it("uses the community plugin by default, and any plugin with the same calls once it is set", async () => {
    vi.resetModules();
    delete window.SpeechRecognition;
    const { setNativeSpeechEngine, communityEngine } = await import("./nativeSpeech");
    const first = new window.SpeechRecognition();
    first.lang = "hi-IN";
    first.start();
    await flush();
    expect(h.community.start).toHaveBeenCalledWith(expect.objectContaining({ language: "hi-IN", partialResults: true }));
    first.abort();

    const calls = [];
    const listeners = {};
    const engine = {
      checkPermissions: async () => ({ speechRecognition: "granted" }), requestPermissions: async () => ({ speechRecognition: "granted" }), available: async () => ({ available: true }),
      addListener: async (name, fn) => { listeners[name] = fn; return { remove() {} }; }, start: async (o) => { calls.push(["start", o.language]); }, stop: async () => { calls.push(["stop"]); }, isListening: async () => ({ isListening: true }),
    };
    setNativeSpeechEngine(engine);
    h.community.start.mockClear();
    const second = new window.SpeechRecognition();
    const got = [];
    second.lang = "mr-IN";
    second.onresult = (e) => got.push([e.results[0][0].transcript, e.results[0].isFinal]);
    second.start();
    await flush();
    expect(calls).toEqual([["start", "mr-IN"]]);
    expect(h.community.start).not.toHaveBeenCalled();                                          // the other plugin is never touched
    listeners.partialResults({ matches: ["माझा हिमोग्लोबिन"] });
    expect(got).toEqual([["माझा हिमोग्लोबिन", false]]);
    second.abort();
    setNativeSpeechEngine(null);                                                                // back to the default
    expect(typeof communityEngine.start).toBe("function");
  });
});
