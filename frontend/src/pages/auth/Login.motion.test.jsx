import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

const login = vi.fn();
vi.mock("../../context/AuthContext", () => ({ ROLE_HOME: { ADMIN: "/admin", PATIENT: "/patient" }, useAuth: () => ({ user: null, login, registerFirstAdmin: vi.fn() }) }));
vi.mock("../../services/authApi", () => ({ getSetupStatus: vi.fn(() => Promise.resolve({ needs_setup: false })) }));
import Login from "./Login";

const reduceMotion = (on) => { window.matchMedia = vi.fn().mockImplementation((query) => ({ matches: on && query.includes("reduce"), media: query, addEventListener: () => {}, removeEventListener: () => {} })); };
const open = () => render(<MemoryRouter initialEntries={["/login"]}><Routes><Route path="/login" element={<Login />} /><Route path="/admin" element={<p>ADMIN HOME</p>} /></Routes></MemoryRouter>);
const fill = async () => {
  await userEvent.type(screen.getByLabelText("Email"), "a@b.co");
  await userEvent.type(screen.getByLabelText("Password"), "Secret-123");
};

beforeEach(() => { vi.clearAllMocks(); reduceMotion(false); });
afterEach(() => { vi.useRealTimers(); });

describe("Login: motion and feedback", () => {
  it("plays the entrance and the loops by default, but no shake on load", () => {
    const { container } = open();
    expect(container.querySelector(".hw-ecg-line")).toBeTruthy();
    expect(container.querySelector(".hw-orb-a")).toBeTruthy();
    expect(container.querySelector(".hw-rise")).toBeTruthy();
    expect(container.querySelector(".hw-shake")).toBeNull();
    expect(container.querySelector("[aria-hidden='true'] .hw-ecg-line, svg[aria-hidden='true']")).toBeTruthy();         // the art is decoration
  });

  it("with reduce-motion on there are no looping animations, no parallax and no shake after an error", async () => {
    reduceMotion(true);
    login.mockRejectedValue({ response: { status: 401, data: { detail: "Incorrect email or password." } } });
    const { container } = open();
    expect(container.querySelector("[data-reduced='true']")).toBeTruthy();
    for (const loop of [".hw-ecg-line", ".hw-orb-a", ".hw-orb-b", ".hw-float-a", ".hw-ring", ".hw-parallax", ".hw-rise", ".hw-logo-in"]) expect(container.querySelector(loop), loop).toBeNull();
    await fill();
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(container.querySelector(".hw-shake")).toBeNull();
  });

  it("a failed login shakes the card once and announces the error", async () => {
    login.mockRejectedValue({ response: { status: 401, data: { detail: "Incorrect email or password." } } });
    const { container } = open();
    await fill();
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect((await screen.findByRole("alert")).textContent).toBe("Incorrect email or password.");
    expect(container.querySelector(".hw-shake")).toBeTruthy();
    expect(screen.getByRole("alert").parentElement.getAttribute("aria-live")).toBe("assertive");
    const card = container.querySelector(".hw-shake");
    await act(async () => { const e = new Event("animationend", { bubbles: true }); e.animationName = "hw-shake"; card.dispatchEvent(e); });
    expect(container.querySelector(".hw-shake")).toBeNull();                                           // it does not repeat
    expect(screen.getByLabelText("Email").value).toBe("a@b.co");                                       // nothing typed was lost
  });

  it("the button is off and shows the loading state while the request runs", async () => {
    let finish;
    login.mockImplementation(() => new Promise((resolve) => { finish = () => resolve({ role: "ADMIN" }); }));
    open();
    await fill();
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    const busy = screen.getByRole("button", { name: "Logging in..." });
    expect(busy.disabled).toBe(true);
    expect(busy.querySelector("svg[aria-hidden='true']")).toBeTruthy();
    await act(async () => finish());
  });

  it("success shows the check mark and moves on within about 600 ms", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    login.mockResolvedValue({ role: "ADMIN" });
    open();
    await fill();
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect(await screen.findByRole("status", { name: "Signed in" })).toBeTruthy();
    expect(screen.queryByText("ADMIN HOME")).toBeNull();
    await act(async () => { vi.advanceTimersByTime(600); });
    await waitFor(() => expect(screen.getByText("ADMIN HOME")).toBeTruthy());
  });

  it("the password can be shown and hidden with a keyboard-reachable button", async () => {
    open();
    const box = screen.getByLabelText("Password");
    expect(box.getAttribute("type")).toBe("password");
    const toggle = screen.getByRole("button", { name: "Show password" });
    expect(toggle.getAttribute("aria-pressed")).toBe("false");
    await userEvent.tab();                                   // email
    await userEvent.tab();                                   // password
    await userEvent.tab();                                   // the eye button
    expect(document.activeElement).toBe(toggle);
    await userEvent.keyboard("{Enter}");
    expect(box.getAttribute("type")).toBe("text");
    expect(screen.getByRole("button", { name: "Hide password" }).getAttribute("aria-pressed")).toBe("true");
  });

  it("each field has a label tied to it, and an error is linked to its field", async () => {
    open();
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    const email = screen.getByLabelText("Email");
    expect(email.getAttribute("aria-invalid")).toBe("true");
    expect(document.getElementById(email.getAttribute("aria-describedby")).textContent).toBe("Please enter your e-mail address.");
  });
});
