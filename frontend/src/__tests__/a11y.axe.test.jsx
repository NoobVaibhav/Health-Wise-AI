// Automated accessibility audit (axe-core) of the pages that can be rendered without a server: names, labels, roles, ARIA, landmarks.
// Colour contrast needs a real browser (jsdom has no layout), so that rule is checked by hand in the browser pane instead.
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import axe from "axe-core";

vi.mock("../context/AuthContext", () => ({ ROLE_HOME: { PATIENT: "/patient" }, useAuth: () => ({ user: null, login: vi.fn(), loginWithOtp: vi.fn(), registerFirstAdmin: vi.fn() }) }));
vi.mock("../services/authApi", () => ({ getSetupStatus: vi.fn(() => Promise.resolve({ needs_setup: false })), requestOtp: vi.fn() }));
vi.mock("react-router-dom", async (orig) => ({ ...(await orig()), useNavigate: () => vi.fn() }));
vi.mock("../services/assistantApi", () => ({
  getAssistantInfo: vi.fn(() => Promise.resolve({ disclaimer: "Not a doctor.", ai_wording_available: false })),
  getSuggestions: vi.fn(() => Promise.resolve([{ key: "a", text: "Explain my latest report" }])),
  sendChat: vi.fn(), deleteConversation: vi.fn(),
}));
import Login from "../pages/auth/Login";
import AssistantChat from "../components/assistant/AssistantChat";
import DisclaimerBanner from "../components/DisclaimerBanner";

async function violations(container) {
  const result = await axe.run(container, { rules: { "color-contrast": { enabled: false } }, resultTypes: ["violations"] });
  return result.violations.map((v) => `${v.id} (${v.impact}): ${v.nodes.slice(0, 2).map((n) => n.target.join(" ")).join(" | ")}`);
}

describe("accessibility audit with axe-core", () => {
  it("control: the audit really finds a button without a name and an input without a label", async () => {
    const { container } = render(<div><button type="button" /><input type="text" /></div>);
    const found = await violations(container);
    expect(found.join(" ")).toMatch(/button-name/);
    expect(found.join(" ")).toMatch(/label/);
  });

  it("login page has no violations (email and mobile code tabs)", async () => {
    window.matchMedia = vi.fn().mockImplementation((q) => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} }));
    const { container } = render(<MemoryRouter><Login /></MemoryRouter>);
    expect(await violations(container)).toEqual([]);
    await userEvent.click(screen.getByRole("tab", { name: /Mobile code/ }));
    expect(await violations(container)).toEqual([]);
  });

  it("the assistant (empty, with the microphone sheet and the clear-chat question open) has no violations", async () => {
    const { container } = render(<MemoryRouter><AssistantChat /></MemoryRouter>);
    await screen.findByRole("button", { name: "Explain my latest report" });
    expect(await violations(container)).toEqual([]);
    await userEvent.click(screen.getByRole("button", { name: "How the microphone works" }));
    expect(await violations(container)).toEqual([]);
    await userEvent.keyboard("{Escape}");
    await userEvent.click(screen.getByRole("button", { name: "Clear chat" }));
    expect(await violations(container)).toEqual([]);
  });

  it("the disclaimer banner has no violations expanded or collapsed", async () => {
    const { container } = render(<DisclaimerBanner />);
    expect(await violations(container)).toEqual([]);
    await userEvent.click(screen.getByRole("button", { name: "More" }));
    expect(await violations(container)).toEqual([]);
  });
});
