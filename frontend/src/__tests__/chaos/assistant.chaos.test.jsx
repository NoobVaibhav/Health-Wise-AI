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
  window.speechSynthesis = { speak: (u) => setTimeout(() => u.onend?.(), 0), cancel: () => {}, pause: () => {}, resume: () => {}, getVoices: () => [] };   // the voice finishes at once
  window.SpeechSynthesisUtterance = class { constructor(t) { this.text = t; } };
  localStorage.setItem("hw_voice_notice", "yes");
  localStorage.setItem("hw_assistant_sounds", "no");
});
const hear = (rec, text) => rec.onresult({ results: [Object.assign([{ transcript: text }], { isFinal: true })] });

describe("voice assistant, spoken commands", () => {
  it("V-01: the words 'start over' heard in the background do not delete the conversation until the person says yes", async () => {
    sendChat.mockResolvedValue({ conversation_id: 7, message: { id: 1, role: "PATIENT", text: "hi" }, reply: { id: 2, role: "ASSISTANT", text: "Hello.", sources: [], safety: null } });
    render(<MemoryRouter><AssistantChat /></MemoryRouter>);
    await userEvent.type(screen.getByLabelText("Type your question"), "hi{Enter}");
    await screen.findByText("Hello.");
    await userEvent.click(screen.getByRole("button", { name: "Start talking with HealthWise" }));
    hear(recs[recs.length - 1], "start over");
    expect(await screen.findByText(/Do you want to clear this chat/)).toBeTruthy();
    expect(deleteConversation).not.toHaveBeenCalled();                               // asked first, nothing deleted yet
    await waitFor(() => expect(recs.length).toBeGreaterThan(1), { timeout: 2000 });  // it listens for the answer
    const before = recs.length;
    hear(recs[recs.length - 1], "no thanks");                                       // not a yes: nothing is deleted and the sentence is taken as a question
    await waitFor(() => expect(sendChat).toHaveBeenCalledTimes(2));
    expect(deleteConversation).not.toHaveBeenCalled();
    await waitFor(() => expect(recs.length).toBeGreaterThan(before), { timeout: 2000 });
    const again = recs.length;
    hear(recs[recs.length - 1], "clear the chat");
    await waitFor(() => expect(recs.length).toBeGreaterThan(again), { timeout: 2000 });
    hear(recs[recs.length - 1], "yes");
    await waitFor(() => expect(deleteConversation).toHaveBeenCalledWith(7));
  });
});
