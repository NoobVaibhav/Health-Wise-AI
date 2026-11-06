import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { afterWakePhrase, createListener, createSpeaker, createWakeListener, detectLanguage, isNoise, matchVoiceCommand, startLevelMeter, supportsPauseControl, voiceErrorMessage, voicePlan } from "./voice";

beforeEach(() => { vi.useFakeTimers(); });
afterEach(() => { vi.useRealTimers(); });

const results = (text, final, confidence, alternatives = []) => ({ results: [Object.assign([{ transcript: text, confidence }, ...alternatives.map((t) => ({ transcript: t }))], { isFinal: final })] });
class Rec {
  static made = [];
  constructor() { Rec.made.push(this); }
  start() { this.onstart?.(); }
  stop() { this.onend?.(); }
  abort() { this.onend?.(); }
}
const win = (extra = {}) => ({ SpeechRecognition: Rec, navigator: { userAgent: "Mozilla/5.0 (Windows NT 10.0) Chrome/120" }, ...extra });
beforeEach(() => { Rec.made = []; });

describe("the listener", () => {
  it("passes the recogniser's confidence and alternative readings on with the text", () => {
    const onText = vi.fn();
    const l = createListener({ lang: "en", onText }, win());
    l.start();
    Rec.made[0].onresult(results("take two tablets", true, 0.62, ["take 2 tablets", "take to tablets"]));
    expect(onText).toHaveBeenCalledWith("take two tablets", true, { confidence: 0.62, alternatives: ["take two tablets", "take 2 tablets", "take to tablets"] });
    expect(Rec.made[0].lang).toBe("en-IN");
    expect(Rec.made[0].maxAlternatives).toBe(3);
  });

  it("a recogniser that freezes right after start is ended by the watchdog, once, and reported as stuck", () => {
    const onError = vi.fn(); const onEnd = vi.fn();
    class Silent { constructor() { Rec.made.push(this); } start() {} stop() {} abort() { this.onend?.(); } }
    createListener({ onText() {}, onError, onEnd }, { SpeechRecognition: Silent, navigator: { userAgent: "x" } }).start();
    vi.advanceTimersByTime(8100);
    expect(onError).toHaveBeenCalledWith("stuck");
    expect(onEnd).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(60000);
    expect(onEnd).toHaveBeenCalledTimes(1);
  });

  it("one that starts but never says anything or ends is ended after a long quiet, but speaking resets the clock", () => {
    const onError = vi.fn();
    createListener({ onText() {}, onError }, win()).start();
    vi.advanceTimersByTime(15000);
    Rec.made[0].onresult(results("hello", false));
    vi.advanceTimersByTime(15000);
    expect(onError).not.toHaveBeenCalled();                                                   // 15 s after the last words: still fine
    vi.advanceTimersByTime(6000);
    expect(onError).toHaveBeenCalledWith("stuck");
  });

  it("a normal ending, an error and an abort all switch the watchdog off", () => {
    const onError = vi.fn();
    const l = createListener({ onText() {}, onError }, win());
    l.start();
    Rec.made[0].onend();
    vi.advanceTimersByTime(60000);
    expect(onError).not.toHaveBeenCalled();
    l.start();
    l.abort();
    vi.advanceTimersByTime(60000);
    expect(onError).not.toHaveBeenCalled();
  });

  it("a long-running (wake phrase) listener has no watchdog: waiting quietly is its job", () => {
    const onError = vi.fn();
    createListener({ continuous: true, onText() {}, onError }, win()).start();
    vi.advanceTimersByTime(120000);
    expect(onError).not.toHaveBeenCalled();
  });

  it("with a pause time, a sentence ends only after that long without new words, and a slow speaker is not cut off", () => {
    const onText = vi.fn();
    createListener({ pauseMs: 1800, onText }, win()).start();
    const rec = Rec.made[0];
    expect(rec.continuous).toBe(true);
    rec.onresult(results("what is my", false));
    vi.advanceTimersByTime(1500);
    rec.onresult(results("what is my hemoglobin", false));                                    // still talking: the wait starts again
    vi.advanceTimersByTime(1500);
    expect(onText.mock.calls.every(([, final]) => final === false)).toBe(true);
    vi.advanceTimersByTime(400);
    expect(onText).toHaveBeenLastCalledWith("what is my hemoglobin", true, { confidence: null, alternatives: ["what is my hemoglobin"] });
  });

  it("without a pause time the recogniser's own end of speech is used, and on Android the pause time is never applied", () => {
    createListener({ pauseMs: 2000, onText() {} }, win({ navigator: { userAgent: "Mozilla/5.0 (Linux; Android 14) Chrome" } })).start();
    expect(Rec.made[0].continuous).toBe(false);
    createListener({ onText() {} }, win()).start();
    expect(Rec.made[1].continuous).toBe(false);
    expect(supportsPauseControl({ navigator: { userAgent: "Android" } })).toBe(false);
    expect(supportsPauseControl({ navigator: { userAgent: "Windows" }, Capacitor: { isNativePlatform: () => true } })).toBe(false);
    expect(supportsPauseControl({ navigator: { userAgent: "Windows" } })).toBe(true);
  });
  it("has a message for a stuck microphone", () => expect(voiceErrorMessage("stuck")).toMatch(/stopped responding/));
});

describe("noise, language and commands", () => {
  it("a cough, a bleep or 'umm' is not a sentence", () => {
    for (const t of ["", " ", "a", "umm", "Hmmm.", "uh", "अं", "हम्म", "...", "12"]) if (t !== "12") expect(isNoise(t)).toBe(true);
    for (const t of ["stop", "what is my sugar", "12", "मेरी दवा"]) expect(isNoise(t)).toBe(false);
  });
  it("tells English, Hindi, Marathi and Hinglish apart", () => {
    expect(detectLanguage("what is my hba1c")).toBe("en");
    expect(detectLanguage("मेरा क्रिएटिनिन कितना है")).toBe("hi");
    expect(detectLanguage("माझा हिमोग्लोबिन किती आहे")).toBe("mr");
    expect(detectLanguage("mera hba1c kitna hai")).toBe("hi");                                // Hinglish is answered in Hindi
    expect(detectLanguage("", "mr")).toBe("mr");
    expect(detectLanguage("12 34", "hi")).toBe("hi");
  });
  it("understands a command with filler words around it, in three languages, and never takes a question for one", () => {
    const yes = [["umm stop please", "stop"], ["okay can you stop", "stop"], ["please speak a bit slower", "slower"], ["repeat that please", "repeat"], ["can you say that again", "repeat"], ["dheere bolo", "slower"],
      ["tell me more", "more"], ["more details please", "more"], ["बस करो", "stop"], ["फिर से बोलो", "repeat"], ["thoda slow bolo", "slower"], ["तेज़ बोलो", "faster"], ["go a little faster", "faster"],
      ["switch to Hindi", "language"], ["marathi please", "language"], ["clear the chat", "clear"], ["that's all", "exit"], ["aur batao", "more"]];
    for (const [said, type] of yes) expect(matchVoiceCommand(said)?.type, said).toBe(type);
    for (const q of ["stop taking my medicine", "can I stop my tablets", "repeat my last blood test result", "clear my doubt about the report", "tell me slowly what the doctor said", "what is my hba1c"]) expect(matchVoiceCommand(q), q).toBeNull();
  });
  it("the wake phrase has to start the sentence, so a television or another person in the middle of a sentence does not count", () => {
    expect(afterWakePhrase("hey healthwise what medicines am i taking")).toBe("what medicines am i taking");
    expect(afterWakePhrase("ok hey health wise open my reports")).toBe("open my reports");
    expect(afterWakePhrase("and then the presenter said hey healthwise buy this now")).toBeNull();
    expect(afterWakePhrase("being health wise is important")).toBeNull();
  });
});

describe("the wake-phrase listener", () => {
  it("gives up with a message after a few errors in a row instead of retrying for ever", () => {
    class Failing { constructor() { Rec.made.push(this); } start() { setTimeout(() => { this.onerror?.({ error: "network" }); this.onend?.(); }, 0); } abort() {} stop() {} }
    const onError = vi.fn();
    createWakeListener({ onWake() {}, onError }, { SpeechRecognition: Failing }).start();
    vi.advanceTimersByTime(60000);
    expect(Rec.made.length).toBe(4);
    expect(onError).toHaveBeenCalledTimes(1);
    expect(onError).toHaveBeenCalledWith("network");
  });
  it("hearing words in between starts the count again (a flaky network is not a dead one)", () => {
    let n = 0;
    class Flaky { constructor() { Rec.made.push(this); } start() { n += 1; setTimeout(() => { if (n % 3 === 0) this.onresult?.(results("music playing", false)); else this.onerror?.({ error: "network" }); this.onend?.(); }, 0); } abort() {} stop() {} }
    const onError = vi.fn();
    const wake = createWakeListener({ onWake() {}, onError }, { SpeechRecognition: Flaky });
    wake.start();
    vi.advanceTimersByTime(30000);
    wake.stop();
    expect(onError).not.toHaveBeenCalled();
  });
  it("does not listen while the page is in the background", () => {
    const hidden = vi.spyOn(document, "visibilityState", "get").mockReturnValue("hidden");
    createWakeListener({ onWake() {}, onError() {} }, win()).start();
    vi.advanceTimersByTime(3000);
    expect(Rec.made.length).toBe(0);
    hidden.mockReturnValue("visible");
    vi.advanceTimersByTime(1500);
    expect(Rec.made.length).toBe(1);
    hidden.mockRestore();
  });
});

describe("which voice reads, and what the person is told", () => {
  const voice = (name, lang, localService = true) => ({ name, lang, localService });
  const synth = (voices) => ({ speechSynthesis: { getVoices: () => voices } });
  it("uses the voice of the language when there is one", () => {
    expect(voicePlan("hi", synth([voice("Swara", "hi-IN")]))).toEqual({ voice: voice("Swara", "hi-IN"), lang: "hi", note: "" });
  });
  it("reads Marathi with a Hindi voice, and says so, when there is no Marathi voice", () => {
    const plan = voicePlan("mr", synth([voice("Swara", "hi-IN"), voice("Heera", "en-IN")]));
    expect(plan.voice.name).toBe("Swara");
    expect(plan.lang).toBe("hi");
    expect(plan.note).toMatch(/No Marathi voice is installed.*Hindi voice reads the answer/);
  });
  it("says there is no voice, with the way out, when neither is installed; English never needs a message", () => {
    expect(voicePlan("mr", synth([voice("Heera", "en-IN")])).note).toMatch(/No मराठी voice is installed/);
    expect(voicePlan("hi", synth([])).voice).toBeNull();
    expect(voicePlan("en", synth([])).note).toBe("");
  });
  it("the speaker uses the stand-in voice and its language, tells the person, and clamps speed and pitch", () => {
    const spoken = [];
    const problems = [];
    const w = { speechSynthesis: { speak: (u) => spoken.push(u), cancel() {}, getVoices: () => [voice("Swara", "hi-IN")] }, SpeechSynthesisUtterance: class { constructor(t) { this.text = t; } } };
    const speaker = createSpeaker({ onProblem: (m) => problems.push(m) }, w);
    speaker.speak("माझा हिमोग्लोबिन १२ आहे.", { lang: "mr", rate: 3, pitch: 9 });
    expect(spoken[0].voice.name).toBe("Swara");
    expect(spoken[0].lang).toBe("hi-IN");
    expect(spoken[0].rate).toBe(1.5);
    expect(spoken[0].pitch).toBe(1.5);
    expect(problems[0]).toMatch(/Hindi voice/);
  });
  it("a longer limit lets the whole answer be read for 'tell me more'", () => {
    const spoken = [];
    const w = { speechSynthesis: { speak: (u) => spoken.push(u), cancel() {}, getVoices: () => [] }, SpeechSynthesisUtterance: class { constructor(t) { this.text = t; } } };
    const text = "This is one sentence about your report. ".repeat(40);
    createSpeaker({}, w).speak(text, { limit: 900 });
    expect(spoken[0].text.length).toBeLessThan(200);
    const all = [];
    w.speechSynthesis.speak = (u) => { all.push(u); u.onend(); };
    createSpeaker({}, w).speak(text, { limit: 5000 });
    expect(all.map((u) => u.text).join(" ")).not.toMatch(/The rest is in the written answer/);
  });
});

describe("the microphone level meter", () => {
  it("reports a level from 0 to 1 using echo cancellation and noise suppression, and stops everything when stopped", async () => {
    const stops = [];
    const track = { stop: () => stops.push("track") };
    const constraints = [];
    const data = [128, 160, 100];
    class Ctx { createAnalyser() { return { fftSize: 0, frequencyBinCount: 3, getByteTimeDomainData: (a) => a.set(data) }; } createMediaStreamSource() { return { connect() {} }; } close() { stops.push("ctx"); return Promise.resolve(); } }
    const w = { AudioContext: Ctx, navigator: { mediaDevices: { getUserMedia: async (c) => { constraints.push(c); return { getTracks: () => [track] }; } } } };
    const onLevel = vi.fn();
    const meter = await startLevelMeter(onLevel, w);
    expect(constraints[0].audio).toEqual({ echoCancellation: true, noiseSuppression: true, autoGainControl: true });
    vi.advanceTimersByTime(200);
    expect(onLevel).toHaveBeenCalledWith(0.5);
    meter.stop();
    expect(stops).toEqual(["track", "ctx"]);
  });
  it("is simply absent when the browser has no microphone access or the person said no", async () => {
    expect(await startLevelMeter(() => {}, {})).toBeNull();
    expect(await startLevelMeter(() => {}, { AudioContext: class {}, navigator: { mediaDevices: { getUserMedia: async () => { throw new Error("denied"); } } } })).toBeNull();
  });
});
