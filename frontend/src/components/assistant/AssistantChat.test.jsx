import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

const navigateMock = vi.hoisted(() => vi.fn());
vi.mock("react-router-dom", async (orig) => ({ ...(await orig()), useNavigate: () => navigateMock }));
vi.mock("../../services/assistantApi", () => ({
  getAssistantInfo: vi.fn(() => Promise.resolve({ disclaimer: "This assistant gives information from your own records.", ai_wording_available: false })),
  getSuggestions: vi.fn(() => Promise.resolve([{ key: "checkup", text: "My last checkup" }])),
  sendChat: vi.fn(),
  deleteConversation: vi.fn(() => Promise.resolve()),
}));
import { sendChat, deleteConversation } from "../../services/assistantApi";
import AssistantChat from "./AssistantChat";

const reply = (over = {}) => ({
  conversation_id: 7,
  message: { id: 1, role: "PATIENT", text: "My last checkup" },
  reply: { id: 2, role: "ASSISTANT", text: "Your most recent visit on record was on 22 Oct 2026.", sources: [{ type: "appointment", id: 4, label: "Appointment", date: "2026-10-22" }], safety: null, ai_used: false, ...over },
});
const open = () => render(<MemoryRouter><AssistantChat /></MemoryRouter>);

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  delete window.SpeechRecognition; delete window.webkitSpeechRecognition; delete window.speechSynthesis; delete window.SpeechSynthesisUtterance;
});

describe("AssistantChat", () => {
  it("shows the privacy statement, the disclaimer and suggested questions that send a question", async () => {
    sendChat.mockResolvedValue(reply());
    open();
    expect(screen.getByText(/Answers use your own medical records/)).toBeTruthy();
    expect(await screen.findByText(/information from your own records/)).toBeTruthy();
    await userEvent.click(await screen.findByRole("button", { name: "My last checkup" }));
    expect(sendChat).toHaveBeenCalledWith(expect.objectContaining({ message: "My last checkup", language: "en", conversation_id: null }));
    expect(await screen.findByText(/Your most recent visit on record/)).toBeTruthy();
  });

  it("links every source to the original record", async () => {
    sendChat.mockResolvedValue(reply());
    open();
    await userEvent.type(screen.getByLabelText("Type your question"), "hello{Enter}");
    const link = await screen.findByRole("link", { name: /Appointment/ });
    expect(link.getAttribute("href")).toBe("/patient/appointments");
  });

  it("falls back to typing when the browser has no voice input", async () => {
    open();
    await userEvent.click(screen.getByRole("button", { name: "Speak your question" }));
    expect(screen.getByRole("status").textContent).toMatch(/Voice input is not available.*type your question/i);
    expect(document.activeElement).toBe(screen.getByLabelText("Type your question"));
    sendChat.mockResolvedValue(reply());
    await userEvent.keyboard("My last checkup{Enter}");
    await waitFor(() => expect(sendChat).toHaveBeenCalled());
  });

  it("shows a message when the microphone is blocked and keeps typing available", async () => {
    class Rec { start() { this.onerror({ error: "not-allowed" }); } stop() {} }
    window.webkitSpeechRecognition = Rec;
    localStorage.setItem("hw_voice_notice", "yes");
    open();
    await userEvent.click(screen.getByRole("button", { name: "Speak your question" }));
    expect(await screen.findByText(/microphone is blocked/i)).toBeTruthy();
    expect(screen.getByLabelText("Type your question")).toBeTruthy();
  });

  it("explains where the voice goes before the first use, and the recognised text can be edited before sending", async () => {
    let rec;
    class Rec { constructor() { rec = this; } start() {} stop() { this.onend(); } }
    window.SpeechRecognition = Rec;
    open();
    await userEvent.click(screen.getByRole("button", { name: "Speak your question" }));
    expect(screen.getByRole("dialog", { name: "Voice privacy" }).textContent).toMatch(/does not record or keep your voice/);
    await userEvent.click(screen.getByRole("button", { name: /I understand/ }));
    rec.onresult({ results: [Object.assign([{ transcript: "explain my blood report" }], { isFinal: true })] });
    const box = await screen.findByDisplayValue("explain my blood report");
    await userEvent.type(box, " please");
    sendChat.mockResolvedValue(reply());
    await userEvent.click(screen.getByRole("button", { name: "Send question" }));
    expect(sendChat).toHaveBeenCalledWith(expect.objectContaining({ message: "explain my blood report please" }));
  });

  it("keeps the typed question and offers to try again when sending fails", async () => {
    sendChat.mockRejectedValueOnce({ response: { status: 503, data: { detail: "The service is busy." } } }).mockResolvedValueOnce(reply());
    open();
    const box = screen.getByLabelText("Type your question");
    await userEvent.type(box, "My last checkup");
    await userEvent.click(screen.getByRole("button", { name: "Send question" }));
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(box.value).toBe("My last checkup");
    await userEvent.click(screen.getByRole("button", { name: /Try again/ }));
    expect(await screen.findByText(/Your most recent visit/)).toBeTruthy();
    expect(sendChat).toHaveBeenCalledTimes(2);
  });

  it("reads an answer aloud with pause, resume and stop buttons", async () => {
    const calls = [];
    window.speechSynthesis = { speak: (u) => calls.push(["speak", u]), cancel: () => calls.push(["cancel"]), pause: () => calls.push(["pause"]), resume: () => calls.push(["resume"]), getVoices: () => [{ lang: "en-IN" }] };
    window.SpeechSynthesisUtterance = class { constructor(t) { this.text = t; } };
    sendChat.mockResolvedValue(reply());
    open();
    await userEvent.type(screen.getByLabelText("Type your question"), "hi{Enter}");
    await userEvent.click(await screen.findByRole("button", { name: "Read this answer aloud" }));
    expect(calls.some((c) => c[0] === "speak")).toBe(true);
    await userEvent.click(screen.getByRole("button", { name: "Pause reading" }));
    await userEvent.click(screen.getByRole("button", { name: "Resume reading" }));
    await userEvent.click(screen.getByRole("button", { name: "Stop speaking" }));
    expect(calls.map((c) => c[0]).slice(-4)).toEqual(["speak", "pause", "resume", "cancel"]);
    expect(screen.getByRole("button", { name: "Read this answer aloud" })).toBeTruthy();
  });

  it("styles an emergency answer and clears the chat", async () => {
    sendChat.mockResolvedValue(reply({ text: "This may be an emergency. Please call 112.", safety: "EMERGENCY", sources: [] }));
    open();
    await userEvent.type(screen.getByLabelText("Type your question"), "I have chest pain now{Enter}");
    expect(await screen.findByText("Urgent")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: /Clear chat/ }));
    await userEvent.click(screen.getByRole("button", { name: /Yes, clear chat/ }));   // the icon-only button now asks first
    expect(deleteConversation).toHaveBeenCalledWith(7);
    expect(screen.queryByText("Urgent")).toBeNull();
  });

  it("sends the chosen language", async () => {
    sendChat.mockResolvedValue(reply());
    open();
    fireEvent.change(screen.getByLabelText("Language"), { target: { value: "hi" } });
    await userEvent.type(screen.getByLabelText("Type your question"), "mera report{Enter}");
    expect(sendChat).toHaveBeenCalledWith(expect.objectContaining({ language: "hi" }));
  });
  it("offers the next questions that fit the answer, shows repeated sources once and keeps the label of each line in bold", async () => {
    sendChat.mockResolvedValue(reply({
      text: "Advice and instructions your doctor has recorded:\nFollow-up date given: 27 Oct 2026\nThis is what your records say. I have not added anything of my own.",
      sources: [{ type: "recommendation", id: 1, label: "Doctor's advice", date: "2026-10-27" }, { type: "recommendation", id: 2, label: "Doctor's advice", date: "2026-10-27" }],
      follow_ups: [{ key: "meds", text: "My medicines" }, { key: "appointments", text: "My appointments" }],
    }));
    open();
    await userEvent.click(await screen.findByRole("button", { name: "My last checkup" }));
    expect(await screen.findByText(/Ask next/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "My medicines" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "My last checkup" })).toBeNull();                 // the follow-ups replace the first suggestions
    expect(screen.getAllByText(/Doctor's advice/).length).toBe(1);                                 // two sources with the same label and day: one chip
    expect(screen.getByText(/\(2\)/)).toBeTruthy();
    expect(screen.getByText("Follow-up date given:").tagName).toBe("B");
    expect(screen.getByRole("button", { name: "Copy this answer" })).toBeTruthy();
  });
});

describe("AssistantChat hands-free voice conversation", () => {
  let recs, said;
  const fakeSpeech = () => {
    recs = []; said = [];
    window.SpeechRecognition = class { constructor() { recs.push(this); } start() { this.onstart?.(); } stop() { this.onend?.(); } abort() { this.onend?.(); } };
    window.speechSynthesis = { speak: (u) => said.push(u), cancel: () => {}, pause: () => {}, resume: () => {}, getVoices: () => [] };
    window.SpeechSynthesisUtterance = class { constructor(t) { this.text = t; } };
    localStorage.setItem("hw_voice_notice", "yes");
    localStorage.setItem("hw_assistant_sounds", "no");
  };
  const hear = (rec, text, isFinal = true) => rec.onresult({ results: [Object.assign([{ transcript: text }], { isFinal })] });
  const orb = () => screen.getByRole("button", { name: "Start talking with HealthWise" });

  it("listens, sends what was said, reads the answer aloud and listens again; 'stop' ends it", async () => {
    fakeSpeech();
    sendChat.mockResolvedValue(reply({ text: "Your next appointment is on 3 Nov 2026." }));
    open();
    await userEvent.click(orb());
    expect(recs.length).toBe(1);
    expect(screen.getByText(/Hands-free conversation is on/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Stop listening" }).getAttribute("data-state")).toBe("listening");
    hear(recs[0], "when is my", false);
    await waitFor(() => expect(screen.getAllByText(/when is my/).length).toBeGreaterThan(0));                       // what is heard is shown as it comes
    hear(recs[0], "when is my next appointment", true);
    await waitFor(() => expect(sendChat).toHaveBeenCalledWith(expect.objectContaining({ message: "when is my next appointment" })));
    await waitFor(() => expect(said.length).toBe(1));                                   // the answer is read without pressing anything
    expect(said[0].text).toMatch(/next appointment is on 3 November 2026/);                  // the month is said in full, not as "Nov"
    said[0].onend();
    await waitFor(() => expect(recs.length).toBe(2), { timeout: 2000 });                // and it listens again
    sendChat.mockClear();
    hear(recs[1], "stop", true);
    await waitFor(() => expect(screen.queryByText(/Hands-free conversation is on/)).toBeNull());
    expect(sendChat).not.toHaveBeenCalled();                                            // "stop" is a command, not a question
  });

  it("repeats the last answer and slows down when asked", async () => {
    fakeSpeech();
    sendChat.mockResolvedValue(reply({ text: "Your next appointment is on 3 Nov 2026." }));
    open();
    await userEvent.click(orb());
    hear(recs[0], "next appointment", true);
    await waitFor(() => expect(said.length).toBe(1));
    said[0].onend();
    await waitFor(() => expect(recs.length).toBe(2), { timeout: 2000 });
    hear(recs[1], "speak slower", true);
    await waitFor(() => expect(said.length).toBe(2));
    expect(said[1].rate).toBe(0.8);
    expect(said[1].text).toMatch(/next appointment/);
    expect(localStorage.getItem("hw_assistant_rate")).toBe("0.8");
    expect(sendChat).toHaveBeenCalledTimes(1);
  });

  it("opens the page the server names, and a goodbye ends the conversation after it is spoken", async () => {
    fakeSpeech();
    navigateMock.mockClear();
    sendChat.mockResolvedValueOnce(reply({ text: "Opening your reports.", action: { type: "navigate", to: "/patient/reports", label: "your reports" } }));
    open();
    await userEvent.type(screen.getByLabelText("Type your question"), "open my reports{Enter}");
    await waitFor(() => expect(navigateMock).toHaveBeenCalledWith("/patient/reports"), { timeout: 2000 });
    sendChat.mockResolvedValueOnce(reply({ text: "Goodbye. Take care!", action: { type: "end_conversation" } }));
    await userEvent.click(orb());
    hear(recs[0], "goodbye", true);
    await waitFor(() => expect(said.length).toBe(1));
    said[0].onend();
    await new Promise((r) => setTimeout(r, 600));
    expect(recs.length).toBe(1);                                                       // it did not listen again
    expect(screen.queryByText(/Hands-free conversation is on/)).toBeNull();
  });

  it("stops by itself, and says so, when nothing is heard twice in a row", async () => {
    fakeSpeech();
    open();
    await userEvent.click(orb());
    recs[0].onerror({ error: "no-speech" }); recs[0].onend();
    await waitFor(() => expect(recs.length).toBe(2), { timeout: 2000 });
    recs[1].onerror({ error: "no-speech" }); recs[1].onend();
    expect(await screen.findByText(/I stopped listening because I did not hear anything/)).toBeTruthy();
    expect(screen.queryByText(/Hands-free conversation is on/)).toBeNull();
    expect(recs.length).toBe(2);
  });

  it("tapping the orb while it speaks interrupts and listens at once", async () => {
    fakeSpeech();
    sendChat.mockResolvedValue(reply({ text: "Your next appointment is on 3 Nov 2026." }));
    open();
    await userEvent.click(orb());
    hear(recs[0], "next appointment", true);
    await waitFor(() => expect(said.length).toBe(1));
    await userEvent.click(await screen.findByRole("button", { name: "Interrupt and ask something else" }));
    await waitFor(() => expect(recs.length).toBe(2));
    expect(screen.getByRole("button", { name: "Stop listening" })).toBeTruthy();
  });
});
