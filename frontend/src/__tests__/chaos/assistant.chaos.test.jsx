import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

vi.mock("../../services/assistantApi", () => ({
  getAssistantInfo: vi.fn(() => Promise.resolve({})),
  getSuggestions: vi.fn(() => Promise.resolve([])),
  sendChat: vi.fn(),
  deleteConversation: vi.fn(() => Promise.resolve()),
}));
import { deleteConversation, sendChat } from "../../services/assistantApi";
import AssistantChat from "../../components/assistant/AssistantChat";

let recs;
beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();
  recs = [];
  window.SpeechRecognition = class { constructor() { recs.push(this); } start() { this.onstart?.(); } stop() { this.onend?.(); } abort() { this.onend?.(); } };
  window.speechSynthesis = { speak: () => {}, cancel: () => {}, pause: () => {}, resume: () => {}, getVoices: () => [] };
  window.SpeechSynthesisUtterance = class { constructor(t) { this.text = t; } };
  localStorage.setItem("hw_voice_notice", "yes");
  localStorage.setItem("hw_assistant_sounds", "no");
});
const hear = (rec, text) => rec.onresult({ results: [Object.assign([{ transcript: text }], { isFinal: true })] });

describe("voice assistant, spoken commands", () => {
  it.fails("V-01: the words 'start over' heard in the background do not delete the whole conversation from the server without asking", async () => {
    sendChat.mockResolvedValue({ conversation_id: 7, message: { id: 1, role: "PATIENT", text: "hi" }, reply: { id: 2, role: "ASSISTANT", text: "Hello.", sources: [], safety: null } });
    render(<MemoryRouter><AssistantChat /></MemoryRouter>);
    await userEvent.type(screen.getByLabelText("Type your question"), "hi{Enter}");
    await screen.findByText("Hello.");
    await userEvent.click(screen.getByRole("button", { name: "Start talking with HealthWise" }));
    hear(recs[recs.length - 1], "start over");
    await waitFor(() => expect(recs.length).toBeGreaterThan(0));
    expect(deleteConversation).not.toHaveBeenCalled();
  });
});
