import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

let mockUser = { id: 1, role: "PATIENT", full_name: "Rahul Patil", permissions: [] };
vi.mock("../context/AuthContext", () => ({
  ROLE_HOME: { PATIENT: "/patient", DOCTOR: "/doctor" },
  useAuth: () => ({ user: mockUser, loading: false, logout: vi.fn() }),
}));
vi.mock("./DataViews", () => ({ Avatar: () => <span /> }));
import Layout from "./Layout";

// a phone: the media query for the drawer matches
const phone = (matches = true) => { window.matchMedia = (query) => ({ matches, media: query, addEventListener() {}, removeEventListener() {} }); };
const open = (path) => render(
  <MemoryRouter initialEntries={[path]}>
    <Routes><Route element={<Layout />}>
      <Route path="/patient" element={<p>Home page</p>} />
      <Route path="/patient/assistant" element={<p>Assistant page</p>} />
      <Route path="/patient/reports" element={<p>Reports page</p>} />
      <Route path="/doctor" element={<p>Doctor page</p>} />
    </Route></Routes>
  </MemoryRouter>,
);
beforeEach(() => { phone(); document.body.style.overflow = ""; mockUser = { id: 1, role: "PATIENT", full_name: "Rahul Patil", permissions: [] }; });

describe("the page frame on a phone", () => {
  it("a patient gets a tab bar with the five main pages, and the current one is marked", () => {
    open("/patient/reports");
    const bar = screen.getByRole("navigation", { name: "Main" });
    const tabs = [...bar.querySelectorAll("a")].map((a) => a.textContent);
    expect(tabs).toEqual(["Home", "Reports", "Assistant", "Visits", "Profile"]);
    expect(bar.querySelector("[aria-current='page']").textContent).toBe("Reports");
    expect(bar.className).toMatch(/lg:hidden/);                                     // the side menu takes over on a wide screen
  });

  it("the tab bar steps aside while a text box has the keyboard, and comes back", async () => {
    open("/patient/assistant");
    const field = document.createElement("textarea");
    document.body.appendChild(field);
    field.focus();
    await vi.waitFor(() => expect(screen.queryByRole("navigation", { name: "Main" })).toBeNull());
    field.blur();
    await vi.waitFor(() => expect(screen.getByRole("navigation", { name: "Main" })).toBeTruthy());
    field.remove();
  });

  it("other roles get no tab bar", () => {
    mockUser = { id: 2, role: "DOCTOR", full_name: "Dr. Anjali Sharma", permissions: [] };
    open("/doctor");
    expect(screen.queryByRole("navigation", { name: "Main" })).toBeNull();
  });

  it("the assistant page fills the screen exactly (dynamic viewport height, no page scroll); other pages scroll normally", () => {
    const { container, unmount } = open("/patient/assistant");
    expect(container.firstChild.className).toMatch(/h-dvh/);
    expect(container.firstChild.className).toMatch(/overflow-hidden/);
    unmount();
    const other = open("/patient/reports");
    expect(other.container.firstChild.className).not.toMatch(/(^| )h-dvh/);       // only min-h-dvh: the page may grow and scroll
  });
});

describe("the menu drawer", () => {
  it("opens as a modal dialog that holds focus, locks the page, and closes with Escape", async () => {
    open("/patient");
    expect(screen.queryByRole("dialog", { name: "Menu" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Open menu" }));
    const drawer = screen.getByRole("dialog", { name: "Menu" });
    expect(drawer.getAttribute("aria-modal")).toBe("true");
    expect(drawer.contains(document.activeElement)).toBe(true);                     // focus moved inside
    expect(document.body.style.overflow).toBe("hidden");
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog", { name: "Menu" })).toBeNull();
    expect(document.body.style.overflow).toBe("");
  });

  it("Tab wraps inside the open drawer instead of leaving it", async () => {
    open("/patient");
    await userEvent.click(screen.getByRole("button", { name: "Open menu" }));
    const drawer = screen.getByRole("dialog", { name: "Menu" });
    const items = drawer.querySelectorAll("a[href],button:not([disabled])");
    items[items.length - 1].focus();
    await userEvent.tab();
    expect(document.activeElement).toBe(items[0]);
    await userEvent.tab({ shift: true });
    expect(document.activeElement).toBe(items[items.length - 1]);
  });

  it("a closed drawer on a phone is hidden from keyboard and screen readers", () => {
    open("/patient");
    const aside = document.querySelector("aside");
    expect(aside.hasAttribute("inert")).toBe(true);
    expect(aside.getAttribute("aria-hidden")).toBe("true");
  });

  it("on a wide screen the menu is always there and is not a dialog", () => {
    phone(false);
    open("/patient");
    const aside = document.querySelector("aside");
    expect(aside.hasAttribute("inert")).toBe(false);
    expect(aside.getAttribute("role")).toBeNull();
  });
});
