import { describe, expect, it, vi } from "vitest";
import { createListener, createSpeaker, pickVoice, speakableText, speechInputSupported, speechOutputSupported, voiceErrorMessage } from "./voice";

function fakeSynth(voices = []) {
  const calls = [];
  const synth = {
    speak: vi.fn((u) => calls.push(["speak", u])), cancel: vi.fn(() => calls.push(["cancel"])), pause: vi.fn(() => calls.push(["pause"])), resume: vi.fn(() => calls.push(["resume"])),
    getVoices: () => voices,
  };
  class Utterance { constructor(text) { this.text = text; } }
  return { w: { speechSynthesis: synth, SpeechSynthesisUtterance: Utterance }, synth, calls };
}

describe("voice input", () => {
  it("reports that there is no speech recognition and returns no listener, so the page falls back to typing", () => {
    expect(speechInputSupported({})).toBe(false);
    expect(createListener({ lang: "en" }, {})).toBeNull();
    expect(voiceErrorMessage("unsupported")).toMatch(/type your question/i);
  });

  it("turns recognition errors into plain messages", () => {
    class Rec { start() { this.onerror({ error: "not-allowed" }); } stop() {} }
    const onError = vi.fn();
    createListener({ lang: "hi", onError }, { webkitSpeechRecognition: Rec }).start();
    expect(onError).toHaveBeenCalledWith("denied");
    expect(voiceErrorMessage("denied")).toMatch(/microphone is blocked/i);
    expect(voiceErrorMessage("no-speech")).toMatch(/did not hear/i);
    expect(voiceErrorMessage("network")).toMatch(/internet/i);
  });

  it("uses the selected language and passes the recognised text on for editing", () => {
    let instance;
    class Rec { constructor() { instance = this; } start() {} stop() {} }
    const onText = vi.fn();
    createListener({ lang: "mr", onText }, { SpeechRecognition: Rec }).start();
    expect(instance.lang).toBe("mr-IN");
    const results = [Object.assign([{ transcript: "माझी " }], { isFinal: false }), Object.assign([{ transcript: "रिपोर्ट" }], { isFinal: true })];
    instance.onresult({ results });
    expect(onText).toHaveBeenCalledWith("माझी रिपोर्ट", true);
  });

  it("reports a start failure instead of throwing", () => {
    class Rec { start() { throw new Error("already started"); } stop() {} }
    const onError = vi.fn();
    createListener({ onError }, { SpeechRecognition: Rec }).start();
    expect(onError).toHaveBeenCalledWith("other");
  });
});

describe("voice output", () => {
  it("is unsupported without speechSynthesis and says so", () => {
    expect(speechOutputSupported({})).toBe(false);
    const problem = vi.fn();
    expect(createSpeaker({ onProblem: problem }, {}).speak("hello")).toBe(false);
    expect(problem).toHaveBeenCalled();
  });

  it("plays, pauses, resumes and stops", () => {
    const { w, calls } = fakeSynth();
    const states = [];
    const speaker = createSpeaker({ onState: (s) => states.push(s) }, w);
    expect(speaker.speak("Your haemoglobin was 12.1 g/dL.", { lang: "en", rate: 1.25 })).toBe(true);
    const utterance = calls.find((c) => c[0] === "speak")[1];
    expect(utterance.rate).toBe(1.25);
    expect(utterance.lang).toBe("en-IN");
    speaker.pause(); speaker.resume(); speaker.stop();
    expect(states).toEqual(["speaking", "paused", "speaking", "idle"]);
    expect(calls.map((c) => c[0])).toEqual(["cancel", "speak", "pause", "resume", "cancel"]);
    utterance.onend();
    expect(speaker.state).toBe("idle");
  });

  it("limits the speed and warns when no voice is installed for Hindi or Marathi", () => {
    const { w, calls } = fakeSynth([{ lang: "en-US" }]);
    const problem = vi.fn();
    createSpeaker({ onProblem: problem }, w).speak("नमस्कार", { lang: "mr", rate: 9 });
    expect(calls.find((c) => c[0] === "speak")[1].rate).toBe(1.5);
    expect(problem.mock.calls[0][0]).toMatch(/No मराठी voice/);
  });

  it("chooses an installed voice for the language", () => {
    const voices = [{ lang: "en-US" }, { lang: "hi-IN", name: "Hindi" }];
    expect(pickVoice("hi", fakeSynth(voices).w).name).toBe("Hindi");
    expect(pickVoice("mr", fakeSynth(voices).w)).toBeNull();
  });

  it("spells out medical abbreviations and units, drops bullet marks and shortens very long text", () => {
    const text = speakableText("HbA1c: 6.8 %\n• LDL 148 mg/dL\nTSH 2.1 ng/mL");
    expect(text).toContain("H b A one C");
    expect(text).toContain("L D L 148 milligrams per decilitre");
    expect(text).toContain("T S H");
    expect(text).not.toContain("•");
    const long = speakableText("A sentence. ".repeat(200));
    expect(long.length).toBeLessThan(1000);
    expect(long).toMatch(/rest is in the written answer/);
    expect(speakableText("HbA1c 6.8", "hi")).toContain("HbA1c");        // pronunciation rules are English only
  });
});
