import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

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
});
