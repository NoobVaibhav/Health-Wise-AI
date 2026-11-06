import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import BrandLogo, { BrandMark } from "./BrandLogo";

let loading = true;
vi.mock("../context/AuthContext", () => ({ useAuth: () => ({ loading }) }));
import LaunchGate, { CAP_MS, LaunchScreen, MIN_MS } from "./LaunchScreen";

const screenEl = () => screen.queryByTestId("launch-screen");
const advance = (ms) => act(() => { vi.advanceTimersByTime(ms); });
const reduced = (on) => { window.matchMedia = (q) => ({ matches: on && /reduced-motion/.test(q), media: q, addEventListener() {}, removeEventListener() {} }); };

beforeEach(() => {
  vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "Date", "performance", "requestAnimationFrame", "cancelAnimationFrame"] });
  sessionStorage.clear();
  document.documentElement.className = "";
  document.body.innerHTML = "";
  reduced(false);
  loading = true;
});
afterEach(() => { vi.useRealTimers(); });

describe("the launch screen", () => {
  it("plays the full sequence on the first start of a session, announces itself once, and takes over from the static first frame in index.html", () => {
    const first = document.createElement("div"); first.id = "hw-launch"; document.body.appendChild(first);
    render(<LaunchScreen ready={false} />);
    expect(screenEl().dataset.mode).toBe("full");
    expect(document.documentElement.classList.contains("hw-launching")).toBe(true);
    expect(screen.getAllByRole("status").map((s) => s.textContent)).toEqual(["HealthWise AI, loading"]);   // one polite announcement, nothing noisy
    advance(50);
    expect(document.getElementById("hw-launch")).toBeNull();                                     // the first frame is removed only after this one is painted
    expect(screenEl().querySelector(".hw-l-stage").getAttribute("aria-hidden")).toBe("true");       // the picture is hidden from screen readers
  });

  it("never flashes: an app that is ready at once still shows it for the minimum time, then lifts and is removed", () => {
    render(<LaunchScreen ready />);
    advance(MIN_MS - 100);
    expect(screenEl().dataset.phase).not.toBe("leaving");
    advance(100);
    expect(screenEl().dataset.phase).toBe("leaving");
    expect(screenEl().getAttribute("aria-hidden")).toBe("true");
    expect(screen.queryByRole("status")).toBeNull();                                             // the announcement goes with it
    expect(document.documentElement.classList.contains("hw-launching")).toBe(false);              // the app behind is released as the screen lifts
    advance(500);
    expect(screenEl()).toBeNull();
  });

  it("an app that is slow shows only the calm breathing state after the sequence, never a restart, and is released at the 4 second cap", () => {
    const { rerender } = render(<LaunchScreen ready={false} />);
    expect(screenEl().dataset.phase).toBe("intro");
    advance(1600);
    expect(screenEl().dataset.phase).toBe("hold");
    advance(2000);
    expect(screenEl().dataset.phase).toBe("hold");
    advance(CAP_MS - 3600 + 10);
    expect(screenEl().dataset.phase).toBe("leaving");                                            // the cap: the app is shown, with its own loading state
    rerender(<LaunchScreen ready />);                                                            // a late "ready" does nothing more
    advance(600);
    expect(screenEl()).toBeNull();
  });

  it("when the app becomes ready during the hold it lifts at once", () => {
    const { rerender } = render(<LaunchScreen ready={false} />);
    advance(2500);
    rerender(<LaunchScreen ready />);
    advance(10);
    expect(screenEl().dataset.phase).toBe("leaving");
  });

  it("a quick return in the same session (the flag is in sessionStorage) is only a short fade", () => {
    sessionStorage.setItem("hw_launch_seen", "1");
    render(<LaunchScreen ready />);
    expect(screenEl().dataset.mode).toBe("quick");
    advance(200);
    expect(screenEl().dataset.phase).toBe("leaving");
    advance(300);
    expect(screenEl()).toBeNull();
  });

  it("remembers the first start in sessionStorage and stores nothing about the person", () => {
    render(<LaunchScreen ready />);
    advance(MIN_MS + 10);
    expect(sessionStorage.getItem("hw_launch_seen")).toBe("1");
    expect(Object.keys(sessionStorage)).toEqual(["hw_launch_seen"]);
  });

  it("still works when storage is blocked", () => {
    const spy = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
    const set = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
    render(<LaunchScreen ready />);
    expect(screenEl().dataset.mode).toBe("full");
    advance(MIN_MS + 10);
    expect(screenEl().dataset.phase).toBe("leaving");
    advance(500);
    expect(screenEl()).toBeNull();
    spy.mockRestore(); set.mockRestore();
  });

  it("a tap skips it at once", () => {
    render(<LaunchScreen ready={false} />);
    advance(300);
    fireEvent.pointerDown(window);
    expect(screenEl().dataset.phase).toBe("leaving");
    advance(500);
    expect(screenEl()).toBeNull();
  });

  it("a key press skips it at once", () => {
    render(<LaunchScreen ready={false} />);
    fireEvent.keyDown(window, { key: "Enter" });
    expect(screenEl().dataset.phase).toBe("leaving");
  });

  it("with reduced motion it is a still logo with a simple 300 ms fade: no sequence, no breathing", () => {
    reduced(true);
    render(<LaunchScreen ready={false} />);
    expect(screenEl().dataset.mode).toBe("reduced");
    advance(2000);
    expect(screenEl().dataset.phase).toBe("intro");                                              // no hold state: nothing breathes
    const { rerender } = render(<LaunchScreen ready />);
    rerender(<LaunchScreen ready />);
    advance(350);
    expect(screen.getAllByTestId("launch-screen").some((el) => el.dataset.phase === "leaving")).toBe(true);
  });

  it("does not trap focus or take it: nothing inside can be focused", () => {
    render(<LaunchScreen ready={false} />);
    expect(screenEl().querySelectorAll("a, button, input, select, textarea, [tabindex]")).toHaveLength(0);
  });

  it("is wired to the start of the app: it lifts after the sign-in check finishes", () => {
    loading = true;
    const { rerender } = render(<LaunchGate />);
    advance(MIN_MS + 100);
    expect(screenEl().dataset.phase).not.toBe("leaving");
    loading = false;
    rerender(<LaunchGate />);
    advance(10);
    expect(screenEl().dataset.phase).toBe("leaving");
  });
});

describe("the logo component", () => {
  it("the full logo has the name for screen readers; decorative ones are hidden", () => {
    const { container, rerender } = render(<BrandLogo />);
    expect(screen.getByRole("img", { name: "HealthWise AI" })).toBeTruthy();
    rerender(<BrandLogo decorative />);
    expect(container.querySelector("svg").getAttribute("aria-hidden")).toBe("true");
  });
  it("draws the mark with the pulse cut out, and uses only palette colours", () => {
    const { container } = render(<BrandMark variant="color" />);
    expect(container.querySelector("mask")).toBeTruthy();
    const colours = [...container.innerHTML.matchAll(/(?:stop-color|fill|stroke)="(#[0-9A-Fa-f]{3,6})"/g)].map((m) => m[1].toUpperCase());
    for (const c of colours) expect(["#164E63", "#0A7C99", "#22D3EE", "#0F172A", "#FFF", "#FFFFFF", "#000"]).toContain(c);
  });
  it("the one-colour and white versions have a single ink", () => {
    const dark = render(<BrandLogo variant="dark" decorative />).container.innerHTML;
    expect(dark).not.toMatch(/linearGradient/);
    expect(dark).toMatch(/#0F172A/);
    const white = render(<BrandLogo variant="white" decorative />).container.innerHTML;
    expect(white).toMatch(/fill="#fff"/);
  });
  it("two logos on one page do not share ids (no clashing masks or gradients)", () => {
    const { container } = render(<><BrandMark /><BrandMark /></>);
    const ids = [...container.querySelectorAll("[id]")].map((e) => e.id);
    expect(new Set(ids).size).toBe(ids.length);
  });
});
