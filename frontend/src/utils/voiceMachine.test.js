import { describe, expect, it } from "vitest";
import { PHASES, PHASE_TEXT, initialVoice, voiceReducer } from "./voiceMachine";

const run = (events, from = initialVoice) => events.reduce((state, e) => voiceReducer(state, typeof e === "string" ? { type: e } : e), from);

describe("the voice state machine", () => {
  it("goes through a whole spoken exchange", () => {
    let s = initialVoice;
    const seen = [];
    for (const e of ["LISTEN", "HEARD", "HEARD", "SEND", "REPLIED", "SPEAK_START", "SPEAK_END", "LISTEN"]) { s = voiceReducer(s, { type: e }); seen.push(s.phase); }
    expect(seen).toEqual(["listening", "hearing", "hearing", "thinking", "idle", "speaking", "idle", "listening"]);
  });
  it("can speak straight after the question is sent (the answer arrives while thinking)", () => {
    expect(run(["LISTEN", "HEARD", "SEND", "SPEAK_START"]).phase).toBe("speaking");
  });
  it("a tap while the assistant speaks interrupts it and listens", () => {
    expect(run(["SPEAK_START", "LISTEN"]).phase).toBe("listening");
  });
  it("a typed question goes straight to thinking, from idle or from an error", () => {
    expect(run(["SEND"]).phase).toBe("thinking");
    expect(run([{ type: "ERROR", kind: "network" }, "SEND"]).phase).toBe("thinking");
  });
  it("STOP from every state ends in idle with no error left (stop, background tab, incoming call, leaving the page)", () => {
    for (const phase of PHASES) expect(voiceReducer({ phase, error: phase === "error" ? "denied" : null }, { type: "STOP" })).toEqual(initialVoice);
  });
  it("an error is kept with its kind and left by trying again, resetting, or any new action", () => {
    const failed = run(["LISTEN", { type: "ERROR", kind: "denied" }]);
    expect(failed).toEqual({ phase: "error", error: "denied" });
    expect(voiceReducer(failed, { type: "RESET" })).toEqual(initialVoice);
    expect(voiceReducer(failed, { type: "LISTEN" })).toEqual({ phase: "listening", error: null });
    expect(voiceReducer(failed, { type: "ERROR", kind: "denied" })).toBe(failed);                       // the same error again changes nothing (no re-render storm)
  });
  it("ignores an event that makes no sense, so a late result can never leave the screen stuck", () => {
    expect(voiceReducer(initialVoice, { type: "HEARD" })).toBe(initialVoice);                            // a result arriving after "stop"
    expect(voiceReducer(initialVoice, { type: "LISTEN_END" })).toBe(initialVoice);
    expect(voiceReducer(initialVoice, { type: "SPEAK_END" })).toBe(initialVoice);
    expect(voiceReducer(initialVoice, { type: "REPLIED" })).toBe(initialVoice);
    expect(voiceReducer(initialVoice, { type: "NOT_AN_EVENT" })).toBe(initialVoice);
    expect(run(["SEND", "LISTEN"]).phase).toBe("thinking");                                                // cannot listen while waiting for an answer
    expect(run(["LISTEN", "HEARD", "SEND", "LISTEN_END"]).phase).toBe("thinking");                       // the recogniser ending after the question was sent does not undo it
  });
  it("the recogniser ending with nothing sent returns to idle", () => {
    expect(run(["LISTEN", "LISTEN_END"]).phase).toBe("idle");
    expect(run(["LISTEN", "HEARD", "LISTEN_END"]).phase).toBe("idle");
  });
  it("every phase has a label and a sentence for a screen reader", () => {
    for (const phase of PHASES) expect(PHASE_TEXT[phase].label && PHASE_TEXT[phase].announce).toBeTruthy();
  });
});
