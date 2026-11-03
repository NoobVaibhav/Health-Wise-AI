import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
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
  it("the voice panel is a centred column: the settings are an icon button with a label, not a wide text row", () => {
    open();
    const settings = screen.getByLabelText("Voice settings").closest("summary");
    expect(settings.className).toMatch(/min-w-11/);
    expect(settings.querySelector("span.hidden")).toBeTruthy();                       // the words appear from the sm breakpoint up
    expect(screen.getByLabelText("Ask HealthWise assistant").className).toMatch(/dvh/);   // dynamic viewport height, never 100vh
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

describe("Disclaimer banner on a phone", () => {
  it("keeps the whole text in the page and lets a phone expand it", async () => {
    render(<DisclaimerBanner />);
    expect(screen.getByText(/must be reviewed by a qualified healthcare professional/)).toBeTruthy();
    const more = screen.getByRole("button", { name: "More" });
    await userEvent.click(more);
    expect(screen.getByRole("button", { name: "Less" }).getAttribute("aria-expanded")).toBe("true");
  });
});
