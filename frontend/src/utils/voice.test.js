import { describe, expect, it, vi } from "vitest";
import { afterWakePhrase, createSpeaker, createWakeListener, matchVoiceCommand, pickVoice, speakableText, speechChunks, voicesFor } from "./voice";

describe("spoken commands", () => {
  it("knows a whole sentence that is a command for the voice", () => {
    expect(matchVoiceCommand("stop")).toEqual({ type: "stop" });
    expect(matchVoiceCommand("OK stop.")).toEqual({ type: "stop" });
    expect(matchVoiceCommand("say that again")).toEqual({ type: "repeat" });
    expect(matchVoiceCommand("speak slower please")).toEqual({ type: "slower" });
    expect(matchVoiceCommand("faster")).toEqual({ type: "faster" });
    expect(matchVoiceCommand("clear the chat")).toEqual({ type: "clear" });
    expect(matchVoiceCommand("that's all")).toEqual({ type: "exit" });
    expect(matchVoiceCommand("switch to Hindi")).toEqual({ type: "language", value: "hi" });
    expect(matchVoiceCommand("मराठी")).toEqual({ type: "language", value: "mr" });
    expect(matchVoiceCommand("रुको")).toEqual({ type: "stop" });
    expect(matchVoiceCommand("धीरे बोलो")).toEqual({ type: "slower" });
  });
  it("leaves real questions alone, also when they contain a command word", () => {
    for (const q of ["what is my stop smoking advice", "explain my report again please and the results", "which medicines am I taking", "repeat my last blood test result", ""]) {
      expect(matchVoiceCommand(q)).toBeNull();
    }
  });
});

describe("Hey HealthWise", () => {
  it("finds the wake phrase and gives back the rest of the sentence", () => {
    expect(afterWakePhrase("hey healthwise what medicines am I taking")).toBe("what medicines am I taking");
    expect(afterWakePhrase("Hey Health Wise, brief me")).toBe("brief me");
    expect(afterWakePhrase("ok healthwise")).toBe("");
    expect(afterWakePhrase("हे हेल्थवाइज मेरी दवाइयाँ")).toBe("मेरी दवाइयाँ");
    expect(afterWakePhrase("what is the weather")).toBeNull();
  });
  it("listens, waits for the finished sentence, calls onWake once and stops listening", () => {
    vi.useFakeTimers();
    const made = [];
    class Rec { constructor() { made.push(this); } start() { this.onstart?.(); } stop() { this.onend?.(); } abort() { this.stopped = true; } }
    const w = { webkitSpeechRecognition: Rec };
    const onWake = vi.fn();
    const wake = createWakeListener({ onWake }, w);
    wake.start();
    const say = (text, isFinal) => made[made.length - 1].onresult({ results: [Object.assign([{ transcript: text }], { isFinal })] });
    say("good morning everyone", true);
    expect(onWake).not.toHaveBeenCalled();
    say("hey healthwise what", false);
    expect(onWake).not.toHaveBeenCalled();                 // the sentence is not finished
    say("hey healthwise what is my next appointment", true);
    say("hey healthwise what is my next appointment", true);
    expect(onWake).toHaveBeenCalledTimes(1);
    expect(onWake).toHaveBeenCalledWith("what is my next appointment");
    vi.useRealTimers();
  });
  it("starts listening again when the browser ends a long listening session, until it is stopped", () => {
    vi.useFakeTimers();
    const made = [];
    class Rec { constructor() { made.push(this); } start() { this.onstart?.(); } stop() {} abort() {} }
    const wake = createWakeListener({ onWake() {} }, { SpeechRecognition: Rec });
    wake.start();
    made[0].onend();
    vi.advanceTimersByTime(500);
    expect(made.length).toBe(2);
    wake.stop();
    made[1].onend();
    vi.advanceTimersByTime(3000);
    expect(made.length).toBe(2);
    vi.useRealTimers();
  });
  it("gives up and says why when the microphone is blocked", () => {
    const onError = vi.fn();
    class Rec { start() { this.onerror({ error: "not-allowed" }); } stop() {} abort() {} }
    createWakeListener({ onWake() {}, onError }, { SpeechRecognition: Rec }).start();
    expect(onError).toHaveBeenCalledWith("denied");
  });
});

describe("reading aloud", () => {
  it("cuts the text into sentences so a long answer is not cut off", () => {
    const text = "Your most recent visit was on 15 Oct 2026. Reason for the visit: cough. " + "Take rest and drink fluids. ".repeat(12);
    const chunks = speechChunks(text, 100);
    expect(chunks.length).toBeGreaterThan(3);
    expect(chunks.every((c) => c.length <= 110)).toBe(true);
    expect(chunks.join(" ").replace(/\s+/g, " ")).toBe(text.trim().replace(/\s+/g, " "));
    expect(speechChunks("A single very long sentence without any stop " + "word ".repeat(80), 100).every((c) => c.length <= 110)).toBe(true);
  });
  it("does not read a stray full stop after a colon", () => {
    expect(speakableText("Here is your update:\nNo appointment is recorded.\nAll good.")).toBe("Here is your update: No appointment is recorded. All good.");
  });
  it("says units and abbreviations the way a person would", () => {
    expect(speakableText("HbA1c 7.1 %, LVEF 35 %, heart rate 62 bpm, glucose 141 mg/dL")).toBe("H b A one C 7.1 percent, L V E F 35 percent, heart rate 62 beats per minute, glucose 141 milligrams per decilitre");
  });
  const voice = (name, lang, localService = true) => ({ name, lang, localService });
  it("puts the most natural voice first, and keeps the voice the person chose", () => {
    const voices = [voice("Microsoft Heera", "en-IN"), voice("Google US English", "en-US", false), voice("Microsoft Neerja Online (Natural)", "en-IN", false), voice("Microsoft Ravi", "en-IN"), voice("Microsoft Swara Online (Natural)", "hi-IN", false)];
    const w = { speechSynthesis: { getVoices: () => voices } };
    expect(voicesFor("en", w).map((v) => v.name)).toEqual(["Microsoft Neerja Online (Natural)", "Microsoft Heera", "Microsoft Ravi", "Google US English"]);
    expect(pickVoice("en", w).name).toBe("Microsoft Neerja Online (Natural)");
    expect(pickVoice("en", w, "Microsoft Ravi").name).toBe("Microsoft Ravi");
    expect(pickVoice("hi", w).name).toBe("Microsoft Swara Online (Natural)");
    expect(pickVoice("mr", w)).toBeNull();
  });
  it("reads one sentence after another, calls onEnd only when everything was read, and a stop ends it", () => {
    const spoken = [];
    const w = { speechSynthesis: { speak: (u) => spoken.push(u), cancel: vi.fn(), getVoices: () => [] }, SpeechSynthesisUtterance: class { constructor(t) { this.text = t; } } };
    const onEnd = vi.fn();
    const states = [];
    const speaker = createSpeaker({ onState: (s) => states.push(s) }, w);
    const long = (word) => `${word} sentence ` + "is quite long and has many words in it so that it fills a whole piece of speech. ".repeat(2);
    speaker.speak(`${long("First")} ${long("Second")} ${long("Third")}`, { onEnd });
    expect(spoken.length).toBe(1);
    spoken[0].onend();
    expect(spoken.length).toBe(2);
    expect(onEnd).not.toHaveBeenCalled();
    spoken[1].onend();
    spoken[2].onend();
    expect(onEnd).toHaveBeenCalledTimes(1);
    expect(states.at(-1)).toBe("idle");
    const again = [];
    w.speechSynthesis.speak = (u) => again.push(u);
    speaker.speak(`${long("One")} ${long("Another")}`, { onEnd });
    speaker.stop();
    again[0].onend();                                      // an old sentence ending after stop() must not go on
    expect(again.length).toBe(1);
    expect(onEnd).toHaveBeenCalledTimes(1);
  });
});
