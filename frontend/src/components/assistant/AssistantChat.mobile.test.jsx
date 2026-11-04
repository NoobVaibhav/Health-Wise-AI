import { afterEach, describe, expect, it, vi, beforeEach } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

vi.mock("react-router-dom", async (orig) => ({ ...(await orig()), useNavigate: () => vi.fn() }));
vi.mock("../../services/assistantApi", () => ({
  getAssistantInfo: vi.fn(() => Promise.resolve({ disclaimer: "Not a doctor.", ai_wording_available: false })),
  getSuggestions: vi.fn(() => Promise.resolve([{ key: "a", text: "Explain my latest report" }, { key: "b", text: "Abnormal results" }, { key: "c", text: "Compare my reports" }, { key: "d", text: "My medicines" }])),
  sendChat: vi.fn(),
  deleteConversation: vi.fn(() => Promise.resolve()),
}));
import { sendChat, deleteConversation } from "../../services/assistantApi";
import AssistantChat from "./AssistantChat";
import DisclaimerBanner from "../DisclaimerBanner";

const answer = { conversation_id: 7, message: { id: 1, role: "PATIENT", text: "q" }, reply: { id: 2, role: "ASSISTANT", text: "Here is your report.", sources: [], safety: null, ai_used: false } };
const open = () => render(<MemoryRouter><AssistantChat /></MemoryRouter>);
beforeEach(() => { vi.clearAllMocks(); localStorage.clear(); delete window.SpeechRecognition; delete window.webkitSpeechRecognition; });

describe("Assistant on a phone", () => {
  it("the voice panel is one slim strip: the settings are an icon button with a label, not a wide text row", () => {
    open();
    const settings = screen.getByLabelText("Voice settings").closest("summary");
    expect(settings.className).toMatch(/min-w-11/);
    expect(settings.querySelector("span.hidden")).toBeTruthy();                       // the words appear from the sm breakpoint up
    // the card has no fixed height of its own: it fills what the page frame leaves (the frame is h-dvh, see Layout.test), so a keyboard or large text never cuts the input off
    expect(screen.getByLabelText("Ask HealthWise assistant").className).toMatch(/min-h-0 flex-1/);
    expect(screen.getByLabelText("Ask HealthWise assistant").className).not.toMatch(/h-\[|min-h-\[|vh/);
  });

  it("the long microphone note sits behind an info button: the full text opens in a dialog and closes again", async () => {
    open();
    expect(screen.queryByRole("dialog", { name: "How the microphone works" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "How the microphone works" }));
    const sheet = screen.getByRole("dialog", { name: "How the microphone works" });
    expect(sheet.textContent).toMatch(/does not record or keep your voice/);
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog", { name: "How the microphone works" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "How the microphone works" }));
    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog", { name: "How the microphone works" })).toBeNull();
  });

  it("an empty chat offers suggested questions; tapping one sends it, and the input bar stays once there are messages", async () => {
    sendChat.mockResolvedValue(answer);
    open();
    await userEvent.click(await screen.findByRole("button", { name: "Explain my latest report" }));
    expect(sendChat).toHaveBeenCalledWith(expect.objectContaining({ message: "Explain my latest report" }));
    expect(await screen.findByText("Here is your report.")).toBeTruthy();
    expect(screen.getByLabelText("Type your question")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Speak your question" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Send question" })).toBeTruthy();
  });

  it("clearing the chat asks first; keeping it deletes nothing, confirming deletes", async () => {
    sendChat.mockResolvedValue(answer);
    open();
    await userEvent.click(await screen.findByRole("button", { name: "My medicines" }));
    await screen.findByText("Here is your report.");
    await userEvent.click(screen.getByRole("button", { name: "Clear chat" }));
    await userEvent.click(screen.getByRole("button", { name: "Keep it" }));
    expect(deleteConversation).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Clear chat" }));
    await userEvent.click(screen.getByRole("button", { name: /Yes, clear chat/ }));
    await waitFor(() => expect(deleteConversation).toHaveBeenCalledWith(7));
  });
});

describe("Assistant voice states on a phone", () => {
  class Rec { constructor() { Rec.last = this; } start() { Rec.started = (Rec.started || 0) + 1; setTimeout(() => this.onstart?.(), 0); } stop() { setTimeout(() => this.onend?.(), 0); } abort() { setTimeout(() => this.onend?.(), 0); } }
  const orb = () => document.querySelector("button[data-state]");
  const hide = () => { Object.defineProperty(document, "visibilityState", { value: "hidden", configurable: true }); document.dispatchEvent(new Event("visibilitychange")); };
  afterEach(() => { Object.defineProperty(document, "visibilityState", { value: "visible", configurable: true }); delete window.SpeechRecognition; delete window.webkitSpeechRecognition; });

  it("listening starts from the round button and goes back to ready when the phone goes to the background", async () => {
    window.SpeechRecognition = Rec;
    localStorage.setItem("hw_voice_notice", "yes");
    open();
    expect(orb().dataset.state).toBe("idle");
    await userEvent.click(orb());
    await waitFor(() => expect(orb().dataset.state).toBe("listening"));
    act(() => hide());
    await waitFor(() => expect(orb().dataset.state).toBe("idle"));
  });

  it("when the microphone is blocked the state returns to ready with a clear message, and the button works again", async () => {
    class Denied extends Rec { start() { setTimeout(() => { this.onerror?.({ error: "not-allowed" }); this.onend?.(); }, 0); } }
    window.SpeechRecognition = Denied;
    localStorage.setItem("hw_voice_notice", "yes");
    open();
    await userEvent.click(orb());
    expect((await screen.findByRole("status")).textContent).toMatch(/microphone is blocked/i);
    expect(orb().dataset.state).toBe("idle");
    expect(screen.getByLabelText("Type your question")).toBeTruthy();                // typing stays available
  });

  it("without voice support the round button explains it and moves the cursor to the text box", async () => {
    open();
    await userEvent.click(orb());
    expect((await screen.findByRole("status")).textContent).toMatch(/not available in this browser/i);
    expect(document.activeElement).toBe(screen.getByLabelText("Type your question"));
  });

  it("the input bar (text box, microphone, send) is a fixed part of the card, outside the scrolling conversation", async () => {
    sendChat.mockResolvedValue(answer);
    open();
    await userEvent.click(await screen.findByRole("button", { name: "Explain my latest report" }));
    await screen.findByText("Here is your report.");
    const log = screen.getByRole("log");
    const box = screen.getByLabelText("Type your question");
    expect(log.contains(box)).toBe(false);
    expect(log.className).toMatch(/overflow-y-auto/);
    expect(box.closest("footer")).toBeTruthy();
  });

  it("the long privacy text and the outside-AI choice live in the info sheet, not in the bar", async () => {
    open();
    expect(screen.queryByText(/does not record or keep your voice/)).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "How the microphone works" }));
    expect(screen.getByRole("dialog").textContent).toMatch(/does not record or keep your voice/);
  });

  it("follow-up suggestion chips sit in one scrolling line above the input", async () => {
    sendChat.mockResolvedValue({ ...answer, reply: { ...answer.reply, follow_ups: [{ key: "x", text: "Explain my latest report" }, { key: "y", text: "Compare my reports" }] } });
    open();
    await userEvent.click(await screen.findByRole("button", { name: "My medicines" }));
    await screen.findByText("Here is your report.");
    const chips = screen.getByLabelText("Suggested questions");
    expect(chips.className).toMatch(/overflow-x-auto/);
    expect(chips.closest("footer")).toBeTruthy();
  });
});

describe("Disclaimer banner on a phone", () => {
  it("keeps the whole text in the page and lets a phone expand it", async () => {
    render(<DisclaimerBanner />);
    expect(screen.getByText(/must be reviewed by a qualified healthcare professional/)).toBeTruthy();
    const more = screen.getByRole("button", { name: "More" });
    await userEvent.click(more);
    expect(screen.getByRole("button", { name: "Less" }).getAttribute("aria-expanded")).toBe("true");
  });
});
