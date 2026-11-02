import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

const login = vi.fn();
vi.mock("../../context/AuthContext", () => ({ ROLE_HOME: { ADMIN: "/admin" }, useAuth: () => ({ user: null, login, loginWithOtp: vi.fn(), registerFirstAdmin: vi.fn() }) }));
vi.mock("../../services/authApi", () => ({ getSetupStatus: vi.fn(() => Promise.resolve({ needs_setup: true })), requestOtp: vi.fn() }));
import Login from "./Login";

const screens = ({ desktop = false, reduce = false }) => {
  window.matchMedia = vi.fn().mockImplementation((q) => ({ matches: q.includes("min-width") ? desktop : q.includes("reduce") ? reduce : false, media: q, addEventListener: () => {}, removeEventListener: () => {} }));
};
const open = () => render(<MemoryRouter initialEntries={["/login"]}><Routes><Route path="/login" element={<Login />} /><Route path="/register" element={<p>SETUP PAGE</p>} /><Route path="/admin" element={<p>ADMIN HOME</p>} /></Routes></MemoryRouter>);
const type = async (email = "a@b.co", password = "Secret-123") => {
  await userEvent.type(screen.getByLabelText("Email"), email);
  await userEvent.type(screen.getByLabelText("Password"), password);
};
beforeEach(() => { vi.clearAllMocks(); screens({}); });
afterEach(() => vi.useRealTimers());

describe("Login: crisp card and honest motion", () => {
  it("the card is a flat surface: no tilt, no backdrop blur, no scaling on the text; the moving layers are separate and hidden from screen readers", () => {
    const { container } = open();
    expect(container.querySelector(".hw-tilt")).toBeNull();
    const body = container.querySelector(".hw-card-body");
    expect(body.className).not.toMatch(/backdrop|blur|scale|rotate/);
    for (const layer of [".hw-card-edge", ".hw-card-glow"]) expect(container.querySelector(layer).getAttribute("aria-hidden")).toBe("true");
    expect(body.contains(container.querySelector(".hw-card-edge"))).toBe(false);                        // the moving edge is behind the card, not around the text
  });

  it("a desktop screen loads the brand panel (its own piece) with the aurora, the heartbeat, the headline and the feature cards", async () => {
    screens({ desktop: true });
    const { container } = open();
    expect(await screen.findByLabelText("About HealthWise AI")).toBeTruthy();
    for (const part of [".hw-orb-a", ".hw-orb-d", ".hw-grain", ".hw-spot", ".hw-ecg-line", ".hw-beat-ring", ".hw-float-a", ".hw-marquee", ".hw-rot", ".hw-word"]) expect(container.querySelector(part), part).toBeTruthy();
    expect(screen.getAllByText("Understand your health reports, without the confusing medical language.")[0].className).toContain("sr-only");        // the sentence is readable at all times
    expect(container.querySelectorAll(".hw-feature").length).toBe(3);
    expect(container.querySelector(".hw-bars")).toBeTruthy();                                         // the microphone sound bars
    expect(container.querySelector(".hw-marquee").querySelectorAll("li[aria-hidden='true']").length).toBe(10);          // the repeated half is hidden from screen readers
  });

  it("the gradient of the rotating word sits on each word, never on the box that holds all four (a gradient clipped to text would show every word at once)", async () => {
    screens({ desktop: true });
    const { container } = open();
    await screen.findByLabelText("About HealthWise AI");
    const box = container.querySelector(".hw-rot");
    expect(box.className).not.toMatch(/bg-clip-text|text-transparent|bg-gradient/);
    const words = [...box.children];
    expect(words.map((w) => w.textContent)).toEqual(["history", "reports", "medicines", "health"]);
    for (const w of words) expect(w.className).toMatch(/bg-clip-text/);
  });

  it("a field the browser filled in by itself lifts its label (autofill is named in the style sheet), so the label never prints over the value", () => {
    const css = readFileSync(resolve(__dirname, "../../auth.css"), "utf8");
    expect(css).toMatch(/\.hw-input:-webkit-autofill \+ \.hw-label \{ transform: translate\(0, -0\.55rem\)/);
    expect(css).toMatch(/\.hw-input:autofill \+ \.hw-label \{ transform: translate\(0, -0\.55rem\)/);
  });

  it("with reduce-motion on, a desktop has no loop, no marquee, no cursor light, no depth and no shake", async () => {
    screens({ desktop: true, reduce: true });
    const { container } = open();
    await screen.findByLabelText("About HealthWise AI");
    for (const gone of [".hw-orb-a", ".hw-orb-b", ".hw-orb-c", ".hw-orb-d", ".hw-spot", ".hw-depth", ".hw-ecg-line", ".hw-beat-ring", ".hw-float-a", ".hw-loop", ".hw-word", ".hw-rise", ".hw-card-in", ".hw-card-glow"]) expect(container.querySelector(gone), gone).toBeNull();
    expect(container.querySelector(".hw-marquee").getAttribute("data-static")).toBe("true");
    expect(container.querySelector(".hw-rot").getAttribute("data-static")).toBe("true");
    login.mockRejectedValue({ response: { status: 401, data: { detail: "Incorrect email or password." } } });
    await type();
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    await screen.findByRole("alert");
    expect(container.querySelector(".hw-shake")).toBeNull();
  });

  it("a phone gets the compact header and never builds the desktop panel", () => {
    const { container } = open();
    expect(screen.queryByLabelText("About HealthWise AI")).toBeNull();
    expect(container.querySelector("header .hw-ecg-line")).toBeTruthy();
    expect(container.querySelector(".hw-marquee")).toBeNull();
  });

  it("a good e-mail gets a tick, a wrong one does not", async () => {
    const { container } = open();
    await userEvent.type(screen.getByLabelText("Email"), "not-an-email");
    expect(container.querySelector(".hw-valid")).toBeNull();
    await userEvent.clear(screen.getByLabelText("Email"));
    await userEvent.type(screen.getByLabelText("Email"), "doctor@hospital.example.com");
    expect(container.querySelector(".hw-valid")).toBeTruthy();
  });
});

describe("Login: the same behaviour as before", () => {
  it("the e-mail login submits the trimmed, lower-case e-mail and the password", async () => {
    login.mockResolvedValue({ role: "ADMIN" });
    open();
    await type("  Doctor@Hospital.Example.com ", "Secret-123");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    await waitFor(() => expect(login).toHaveBeenCalledWith("doctor@hospital.example.com", "Secret-123"));
  });

  it("a failed login shows the message with an icon, announced to screen readers, and the button is usable again", async () => {
    login.mockRejectedValue({ response: { status: 401, data: { detail: "Incorrect email or password." } } });
    const { container } = open();
    expect(container.querySelector(".hw-shake")).toBeNull();                                           // not on page load
    await type();
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toBe("Incorrect email or password.");
    expect(alert.querySelector("svg[aria-hidden='true']")).toBeTruthy();
    expect(alert.parentElement.getAttribute("aria-live")).toBe("assertive");
    expect(container.querySelector(".hw-shake")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Log in" }).disabled).toBe(false);
  });

  it("while it works the button is off and says so; on success it turns into a check, the card fades out and the redirect comes within 600 ms", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let finish;
    login.mockImplementation(() => new Promise((resolve) => { finish = () => resolve({ role: "ADMIN" }); }));
    const { container } = open();
    await type();
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    const busy = screen.getByRole("button", { name: "Logging in..." });
    expect(busy.disabled).toBe(true);
    expect(busy.getAttribute("data-state")).toBe("busy");
    await act(async () => finish());
    expect(await screen.findByRole("status", { name: "Signed in" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Welcome" }).getAttribute("data-state")).toBe("done");
    expect(container.querySelector(".hw-ripple")).toBeTruthy();
    expect(container.querySelector(".hw-card-out")).toBeTruthy();
    await act(async () => { vi.advanceTimersByTime(600); });
    await waitFor(() => expect(screen.getByText("ADMIN HOME")).toBeTruthy());
  });

  it("the first-administrator link shows while the system has no users", async () => {
    open();
    expect(await screen.findByRole("link", { name: /Set up the first administrator/ })).toBeTruthy();
  });

  it("the tabs glide: the pill follows the chosen tab and the form changes", async () => {
    const { container } = open();
    expect(container.querySelector(".hw-tabs").getAttribute("data-tab")).toBe("password");
    await userEvent.click(screen.getByRole("tab", { name: /Mobile code/ }));
    expect(container.querySelector(".hw-tabs").getAttribute("data-tab")).toBe("otp");
    expect(screen.getByLabelText("Mobile number")).toBeTruthy();
    expect(screen.queryByLabelText("Password")).toBeNull();
    await userEvent.click(screen.getByRole("tab", { name: /Email login/ }));
    expect(screen.getByLabelText("Password")).toBeTruthy();
  });
});
