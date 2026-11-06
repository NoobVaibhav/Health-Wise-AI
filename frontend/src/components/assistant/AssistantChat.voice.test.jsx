// The voice journeys of the assistant added in the voice-quality work: what is read aloud (the short version, the whole answer, the private note), "Did I hear you right?",
// repaired medical words, noise, checking before sending, answer language from what is said, talking over the assistant, replay.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

vi.mock("react-router-dom", async (orig) => ({ ...(await orig()), useNavigate: () => vi.fn() }));
vi.mock("../../services/assistantApi", () => ({
  getAssistantInfo: vi.fn(() => Promise.resolve({ disclaimer: "x", ai_wording_available: false, vocabulary: ["metformin", "atorvastatin"] })),
  getSuggestions: vi.fn(() => Promise.resolve([])),
  sendChat: vi.fn(),
  deleteConversation: vi.fn(() => Promise.resolve()),
}));
import { sendChat } from "../../services/assistantApi";
import AssistantChat from "./AssistantChat";

const WRITTEN = "Vitamin D: 18 ng/mL on 12 Sep 2026, printed range 30 - 100 ng/mL.\nHemoglobin: 12.1 g/dL on 12 Sep 2026.\nThis is what your records say.\nPlease talk to your doctor about what this means for you.";
const reply = (over = {}) => ({
  conversation_id: 7,
  message: { id: 1, role: "PATIENT", text: "q" },
  reply: { id: 2, role: "ASSISTANT", text: WRITTEN, spoken: "Vitamin D: 18 nanograms per millilitre. Please talk to your doctor about what this means for you.", more: true,
    spoken_private: "Your answer is on the screen. It is from your report.", sources: [{ type: "report", id: 4, label: "Report: sep", date: "2026-09-12" }], safety: null, ai_used: false, ...over },
});

let recs, said, cancel;
const fakeSpeech = () => {
  recs = []; said = []; cancel = vi.fn();
  window.SpeechRecognition = class { constructor() { recs.push(this); } start() { this.onstart?.(); } stop() { this.onend?.(); } abort() { this.onend?.(); } };
  window.speechSynthesis = { speak: (u) => said.push(u), cancel, pause: () => {}, resume: () => {}, getVoices: () => [] };
  window.SpeechSynthesisUtterance = class { constructor(t) { this.text = t; } };
  localStorage.setItem("hw_voice_notice", "yes");
  localStorage.setItem("hw_assistant_sounds", "no");
};
const hear = (rec, text, isFinal = true, confidence) => act(async () => { rec.onresult({ results: [Object.assign([{ transcript: text, confidence }], { isFinal })] }); });
const open = () => render(<MemoryRouter><AssistantChat /></MemoryRouter>);
const orb = () => screen.getByRole("button", { name: "Start talking with HealthWise" });

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  delete window.SpeechRecognition; delete window.webkitSpeechRecognition; delete window.speechSynthesis; delete window.SpeechSynthesisUtterance;
});

describe("what is read aloud", () => {
  it("reads the short spoken version, while the screen keeps the whole written answer", async () => {
    fakeSpeech();
    sendChat.mockResolvedValue(reply());
    open();
    await userEvent.click(orb());
    await hear(recs[0], "what is my vitamin d level");
    await waitFor(() => expect(said.length).toBe(1));
    expect(said[0].text).toMatch(/^Vitamin D: 18 nanograms per millilitre\./);
    expect(said[0].text).not.toMatch(/Hemoglobin/);                                           // the rest is not read
    expect(screen.getByText(/Hemoglobin:/)).toBeTruthy();                                    // but it is on the screen
  });

  it("'tell me more' (spoken or tapped) reads the whole written answer, with the units and the month in words", async () => {
    fakeSpeech();
    sendChat.mockResolvedValue(reply());
    open();
    await userEvent.click(orb());
    await hear(recs[0], "what is my vitamin d level");
    await waitFor(() => expect(said.length).toBe(1));
    act(() => said[0].onend());
    await waitFor(() => expect(recs.length).toBe(2), { timeout: 2000 });
    await hear(recs[1], "tell me more");
    await waitFor(() => expect(said.length).toBe(2));
    expect(said[1].text).toMatch(/Vitamin D: 18 nanograms per millilitre on 12 September 2026/);        // the whole written answer, sentence by sentence: units and the month in words
    expect(said[1].text).toMatch(/30 to 100 nanograms per millilitre/);                      // a range is said as a range, not as a dash
    expect(said[1].text).toMatch(/h(?:ee)?moglobin: 12\.1 grams per decilitre on 12 September 2026/i);   // (the pronunciation list respells the word for the voice)
    act(() => said[1].onend());
    await waitFor(() => expect(said.length).toBe(3));
    expect(said[2].text).toMatch(/^This is what your records say\. Please talk to your doctor/);        // and the rest, read on to the end
    expect(sendChat).toHaveBeenCalledTimes(1);                                                // "tell me more" is a command, not a question for the server
    act(() => said[2].onend());                                                              // the reading has finished: the button to hear it all again is back
    await waitFor(() => expect(recs.length).toBe(3), { timeout: 2000 });                     // (hands-free listens again)
    await userEvent.click(await screen.findByRole("button", { name: "Hear all the details of this answer" }));
    await waitFor(() => expect(said.length).toBe(4));
  });

  it("private mode reads only a short note, never the values, but an emergency is always read whole", async () => {
    fakeSpeech();
    localStorage.setItem("hw_assistant_private", "yes");
    sendChat.mockResolvedValueOnce(reply());
    open();
    await userEvent.click(orb());
    await hear(recs[0], "what is my vitamin d level");
    await waitFor(() => expect(said.length).toBe(1));
    expect(said[0].text).toBe("Your answer is on the screen. It is from your report.");
    expect(screen.getByText(/Hemoglobin:/)).toBeTruthy();
    act(() => said[0].onend());
    await waitFor(() => expect(recs.length).toBe(2), { timeout: 2000 });
    sendChat.mockResolvedValueOnce(reply({ text: "This may be an emergency. Please call 112.", spoken: "This may be an emergency. Please call 112.", spoken_private: "This may be an emergency. Please call 112.", safety: "EMERGENCY", sources: [] }));
    await hear(recs[1], "i have severe chest pain right now");
    await waitFor(() => expect(said.length).toBe(2));
    expect(said[1].text).toBe("This may be an emergency. Please call 112.");
  });

  it("the replay button reads the last answer again", async () => {
    fakeSpeech();
    sendChat.mockResolvedValue(reply());
    open();
    expect(screen.queryByRole("button", { name: "Hear the last answer again" })).toBeNull();
    await userEvent.type(screen.getByLabelText("Type your question"), "vitamin d{Enter}");
    await screen.findByText(/Hemoglobin:/);
    await userEvent.click(await screen.findByRole("button", { name: "Hear the last answer again" }));
    await waitFor(() => expect(said.length).toBe(1));
    expect(said[0].text).toMatch(/^Vitamin D/);
  });
});

describe("what was heard", () => {
  it("a number heard with low confidence is read back, and 'yes' sends exactly that", async () => {
    fakeSpeech();
    sendChat.mockResolvedValue(reply());
    open();
    await userEvent.click(orb());
    await hear(recs[0], "my hemoglobin was 11 point 2", true, 0.45);
    await waitFor(() => expect(said.length).toBe(1));
    expect(said[0].text).toMatch(/^Did I hear: my h(?:ee)?moglobin was 11 point 2\? Say yes or no\./);                  // (spoken with the pronunciation list)
    expect(sendChat).not.toHaveBeenCalled();                                                  // nothing is sent until it is confirmed
    act(() => said[0].onend());
    await waitFor(() => expect(recs.length).toBe(2), { timeout: 2000 });
    await hear(recs[1], "yes");
    await waitFor(() => expect(sendChat).toHaveBeenCalledWith(expect.objectContaining({ message: "my hemoglobin was 11 point 2" })));
  });

  it("'no' asks for it again and sends nothing; a confident number is not read back", async () => {
    fakeSpeech();
    sendChat.mockResolvedValue(reply());
    open();
    await userEvent.click(orb());
    await hear(recs[0], "take 2 tablets", true, 0.3);
    await waitFor(() => expect(said.length).toBe(1));
    act(() => said[0].onend());
    await waitFor(() => expect(recs.length).toBe(2), { timeout: 2000 });
    await hear(recs[1], "no");
    await waitFor(() => expect(said.length).toBe(2));
    expect(said[1].text).toMatch(/Please say it again/);
    expect(sendChat).not.toHaveBeenCalled();
    act(() => said[1].onend());
    await waitFor(() => expect(recs.length).toBe(3), { timeout: 2000 });
    await hear(recs[2], "my hba1c is 6.1", true, 0.95);                                       // sure of it: sent without a question
    await waitFor(() => expect(sendChat).toHaveBeenCalledTimes(1));
  });

  it("a split-up medicine name is put right, read back, and sent as the name in the record", async () => {
    fakeSpeech();
    sendChat.mockResolvedValue(reply());
    open();
    await userEvent.click(orb());
    await waitFor(() => expect(screen.queryByText(/Voice input is not available/)).toBeNull());
    await hear(recs[0], "do i take met for min");
    await waitFor(() => expect(said.length).toBe(1));
    expect(said[0].text).toMatch(/Did I hear: do i take met-?formin\?/);
    act(() => said[0].onend());
    await waitFor(() => expect(recs.length).toBe(2), { timeout: 2000 });
    await hear(recs[1], "yes");
    await waitFor(() => expect(sendChat).toHaveBeenCalledWith(expect.objectContaining({ message: "do i take metformin" })));
  });

  it("a cough or an 'umm' is not a question: nothing is sent", async () => {
    fakeSpeech();
    open();
    await userEvent.click(orb());
    await hear(recs[0], "umm", true);
    await new Promise((r) => setTimeout(r, 50));
    expect(sendChat).not.toHaveBeenCalled();
  });

  it("with 'show what I said first' the words go to the box to be checked, not to the server", async () => {
    fakeSpeech();
    localStorage.setItem("hw_assistant_check", "yes");
    open();
    await userEvent.click(orb());
    await hear(recs[0], "what is my hba1c");
    expect(await screen.findByDisplayValue("what is my HbA1c")).toBeTruthy();                // the test name is written the way the records write it
    expect(sendChat).not.toHaveBeenCalled();
    expect(screen.queryByText(/Hands-free conversation is on/)).toBeNull();
  });

  it("with the language chosen automatically, a Hindi sentence is answered in Hindi without touching the selector", async () => {
    fakeSpeech();
    localStorage.setItem("hw_assistant_autolang", "yes");
    sendChat.mockResolvedValue(reply());
    open();
    await userEvent.click(orb());
    await hear(recs[0], "मेरा क्रिएटिनिन कितना है");
    await waitFor(() => expect(sendChat).toHaveBeenCalledWith(expect.objectContaining({ language: "hi" })));
    expect(screen.getByLabelText("Language").value).toBe("en");
  });
});

describe("talking over the assistant", () => {
  it("with 'let me interrupt' on, the first words cut the speech short and the new question is answered", async () => {
    fakeSpeech();
    localStorage.setItem("hw_assistant_barge", "yes");
    sendChat.mockResolvedValue(reply());
    open();
    await userEvent.click(orb());
    await hear(recs[0], "what is my vitamin d level");
    await waitFor(() => expect(said.length).toBe(1));
    await waitFor(() => expect(recs.length).toBe(2));                                         // a recogniser waits while the answer is spoken
    cancel.mockClear();
    await hear(recs[1], "what about my", false);
    expect(cancel).toHaveBeenCalled();                                                        // the speech stops at the first words
    await hear(recs[1], "what about my medicines", true);
    await waitFor(() => expect(sendChat).toHaveBeenCalledTimes(2));
    expect(sendChat).toHaveBeenLastCalledWith(expect.objectContaining({ message: "what about my medicines" }));
  });

  it("without it, nothing listens while the assistant speaks (so it never hears itself)", async () => {
    fakeSpeech();
    sendChat.mockResolvedValue(reply());
    open();
    await userEvent.click(orb());
    await hear(recs[0], "what is my vitamin d level");
    await waitFor(() => expect(said.length).toBe(1));
    expect(recs.length).toBe(1);
  });
});
