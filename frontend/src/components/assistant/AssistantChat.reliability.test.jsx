// Reliability scenarios for the voice assistant, run against the real chat component with a scripted fake recogniser (no real microphone).
// Each scenario ends with the question "is the screen back to a usable state, with no recogniser left running?". It SCORES (prints a table, writes a file
// when VOICE_BENCH_LABEL is set) and asserts only that the scenarios ran, so the same file is run before and after the voice work.
//   VOICE_BENCH_LABEL=baseline npx vitest run src/components/assistant/AssistantChat.reliability.test.jsx
// What a script cannot show: how often a real Chrome, Android Chrome, installed PWA or Android WebView stops by itself. That needs the real-device checklist.
import { describe, expect, it, vi, afterEach } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

vi.mock("react-router-dom", async (orig) => ({ ...(await orig()), useNavigate: () => vi.fn() }));
vi.mock("../../services/assistantApi", () => ({
  getAssistantInfo: vi.fn(() => Promise.resolve({ disclaimer: "x", ai_wording_available: false })),
  getSuggestions: vi.fn(() => Promise.resolve([])),
  sendChat: vi.fn(),
  deleteConversation: vi.fn(() => Promise.resolve()),
}));
import AssistantChat from "./AssistantChat";
import { createSpeaker, createWakeListener } from "../../utils/voice";

const here = path.dirname(fileURLToPath(import.meta.url));
const results = path.resolve(here, "../../../../backend/tests/voice_benchmark/results");
const label = process.env.VOICE_BENCH_LABEL || "";

class FakeRec {
  static instances = [];
  static throwOnStart = false;
  constructor() { this.lang = "en-IN"; this.active = false; this.aborted = 0; FakeRec.instances.push(this); }
  start() { if (FakeRec.throwOnStart) throw new Error("InvalidStateError"); this.active = true; this.onstart?.(); }
  stop() { this.active = false; this.onend?.(); }
  abort() { this.aborted += 1; this.active = false; this.onend?.(); }
  end() { this.active = false; this.onend?.(); }
  fail(error) { this.onerror?.({ error }); this.end(); }
}

const state = () => document.querySelector(".voice-orb")?.dataset.state;
const running = () => FakeRec.instances.filter((r) => r.active).length;
const settle = async (ms = 0) => { await act(async () => { await vi.advanceTimersByTimeAsync(ms); }); };

async function open() {
  FakeRec.instances = [];
  FakeRec.throwOnStart = false;
  localStorage.clear();
  localStorage.setItem("hw_voice_notice", "yes");
  delete window.speechSynthesis; delete window.SpeechSynthesisUtterance;
  window.SpeechRecognition = FakeRec;
  const view = render(<MemoryRouter><AssistantChat /></MemoryRouter>);
  await settle(0);
  return view;
}
const tapOrb = async () => { await act(async () => { fireEvent.click(document.querySelector(".voice-orb")); }); };
const fire = async (fn) => { await act(async () => { fn(); }); };
const said = (re) => re.test(document.body.textContent);

const log = [];
async function scenario(id, name, run) {
  vi.useFakeTimers();
  let view;
  try {
    view = await open();
    const r = await run(view);
    log.push({ id, name, ok: Boolean(r.ok), note: r.note || "" });
  } catch (e) {
    log.push({ id, name, ok: false, note: `scenario failed to run: ${String(e.message).slice(0, 120)}` });
  } finally {
    try { view?.unmount(); } catch { /* already gone */ }
    vi.clearAllTimers();
    vi.useRealTimers();
    Object.defineProperty(document, "visibilityState", { value: "visible", configurable: true });
    delete window.SpeechRecognition;
  }
}

afterEach(() => { vi.useRealTimers(); });

describe("voice reliability scenarios", () => {
  it("runs every scenario and reports which ones leave the screen stuck", async () => {
    await scenario("R1", "nothing heard twice in hands-free: ends with a clear message, nothing left running", async () => {
      await tapOrb();
      await fire(() => FakeRec.instances[0].end()); await settle(300);
      await fire(() => FakeRec.instances[1]?.end()); await settle(300);
      return { ok: state() === "idle" && running() === 0 && FakeRec.instances.length === 2 && said(/did not hear anything/i), note: `state=${state()} recognisers=${FakeRec.instances.length}` };
    });
    await scenario("R2", "microphone permission denied: message shown, back to idle, typing works", async () => {
      await tapOrb();
      await fire(() => FakeRec.instances[0].fail("not-allowed")); await settle(0);
      return { ok: state() === "idle" && said(/microphone is blocked/i) && !screen.getByLabelText("Type your question").disabled, note: `state=${state()}` };
    });
    await scenario("R3", "network error while listening: one short retry, then one message, no restart loop", async () => {
      await tapOrb();
      await fire(() => FakeRec.instances[0].fail("network")); await settle(1000);
      const retried = FakeRec.instances.length === 2 && state() === "listening";                // the blip is retried quietly
      await fire(() => FakeRec.instances[1].fail("network")); await settle(5000);                 // the retry fails too
      return { ok: retried && state() === "idle" && FakeRec.instances.length === 2 && said(/internet connection/i), note: `recognisers started=${FakeRec.instances.length}, retried quietly=${retried}` };
    });
    await scenario("R4", "tab goes to the background while listening: listening stops", async () => {
      await tapOrb();
      Object.defineProperty(document, "visibilityState", { value: "hidden", configurable: true });
      await act(async () => { document.dispatchEvent(new Event("visibilitychange")); });
      return { ok: state() === "idle" && running() === 0, note: `state=${state()} running=${running()}` };
    });
    await scenario("R5", "leaving the page while listening: recogniser stopped, nothing restarts", async (view) => {
      await tapOrb();
      await fire(() => view.unmount()); await settle(5000);
      return { ok: running() === 0 && FakeRec.instances.length === 1, note: `running=${running()} started=${FakeRec.instances.length}` };
    });
    await scenario("R6", "language changed while listening: no second recogniser, and the running one follows the new language", async () => {
      await tapOrb();
      await act(async () => { fireEvent.change(screen.getByLabelText("Language"), { target: { value: "hi" } }); });
      await settle(500);
      const live = FakeRec.instances.filter((r) => r.active);
      return { ok: running() <= 1 && (live.length === 0 || live.every((r) => r.lang === "hi-IN")), note: `running=${running()} language=${live[0]?.lang || "none"}` };
    });
    await scenario("R7", "the recogniser refuses to start (already started elsewhere, or blocked): message, back to idle", async () => {
      FakeRec.throwOnStart = true;
      await tapOrb();
      return { ok: state() === "idle" && said(/did not work|type your question/i), note: `state=${state()}` };
    });
    await scenario("R8", "the engine freezes after start (no result, no end, no error) for 60 seconds: a watchdog ends the round", async () => {
      await tapOrb();
      await settle(60000);
      return { ok: state() !== "listening", note: `state after 60 s of silence from the engine = ${state()}` };
    });
    await scenario("R9", "tapping the round button while listening stops it at once", async () => {
      await tapOrb();
      await tapOrb();
      return { ok: state() === "idle" && running() === 0, note: `state=${state()}` };
    });
    await scenario("R10", "a final result arriving after the person tapped stop is not lost and not sent twice", async () => {
      const { sendChat } = await import("../../services/assistantApi");
      sendChat.mockResolvedValue({ conversation_id: 1, message: { id: 1, role: "PATIENT", text: "x" }, reply: { id: 2, role: "ASSISTANT", text: "ok", sources: [], safety: null } });
      sendChat.mockClear();
      await tapOrb();
      const rec = FakeRec.instances[0];
      await act(async () => { rec.onresult({ results: [Object.assign([{ transcript: "what is my hba1c" }], { isFinal: true })] }); rec.onresult({ results: [Object.assign([{ transcript: "what is my hba1c" }], { isFinal: true })] }); });
      await settle(50);
      return { ok: sendChat.mock.calls.length === 1, note: `sent ${sendChat.mock.calls.length} time(s) for one spoken question that the engine reported twice` };
    });

    // pieces of voice.js on their own
    vi.useFakeTimers();
    try {
      const made = [];
      class Failing { constructor() { made.push(this); } start() { setTimeout(() => { this.onerror?.({ error: "network" }); this.onend?.(); }, 0); } abort() {} stop() {} }
      const w = { SpeechRecognition: Failing };
      const wake = createWakeListener({ lang: "en", onWake: () => {}, onError: () => {} }, w);
      wake.start();
      await vi.advanceTimersByTimeAsync(60000);
      wake.stop();
      log.push({ id: "R11", name: "wake phrase with a failing network: gives up with a message after a few tries instead of retrying for ever", ok: made.length <= 6, note: `recogniser started ${made.length} times in 60 s` });

      const active = new Set();
      const synth = {
        speak: (u) => { active.add(u); },
        cancel: () => { active.clear(); },
        getVoices: () => [], pause() {}, resume() {},
      };
      const speaker = createSpeaker({}, { speechSynthesis: synth, SpeechSynthesisUtterance: class { constructor(t) { this.text = t; } } });
      speaker.speak("First answer. Second sentence.");
      speaker.speak("A different answer.");
      log.push({ id: "R12", name: "two answers started close together: only the newest is spoken (no overlapping speech)", ok: active.size <= 1, note: `utterances queued at once=${active.size}` });
    } finally { vi.useRealTimers(); }

    const failedIds = log.filter((l) => !l.ok).map((l) => l.id);
    console.log("\n== Reliability scenarios\n" + log.map((l) => `  ${l.id.padEnd(4)} ${l.ok ? "ok   " : "STUCK"} ${l.name}  [${l.note}]`).join("\n") + `\n  ${log.length - failedIds.length}/${log.length} ok; not ok: ${failedIds.join(", ") || "none"}`);
    if (label) { fs.mkdirSync(results, { recursive: true }); fs.writeFileSync(path.join(results, `frontend-reliability-${label}.json`), JSON.stringify({ scenarios: log, ok: log.length - failedIds.length, total: log.length, not_ok: failedIds }, null, 1), "utf8"); }
    expect(log.length).toBe(12);
  }, 120000);
});
