import { describe, expect, it, vi, beforeEach } from "vitest";
import { act, render } from "@testing-library/react";

const getMe = vi.fn();
vi.mock("../../services/authApi", () => ({ getMe: (...a) => getMe(...a), login: vi.fn(), registerFirstAdmin: vi.fn() }));
import { AuthProvider, useAuth } from "../../context/AuthContext";
import api, { tokenStore } from "../../services/api";

let auth;
const Probe = () => { auth = useAuth(); return null; };
beforeEach(() => { localStorage.clear(); getMe.mockReset(); });

describe("session", () => {
  it("drops a stored token that the server no longer accepts and shows the login page, without a crash", async () => {
    localStorage.setItem("healthwise_token", "expired.or.tampered");
    getMe.mockRejectedValue({ response: { status: 401 } });
    await act(async () => { render(<AuthProvider><Probe /></AuthProvider>); });
    expect(auth.user).toBeNull();
    expect(auth.loading).toBe(false);
    expect(tokenStore.get()).toBeNull();
  });

  it("a 401 from any later call clears the token (the session ended in another tab or on the server)", async () => {
    localStorage.setItem("healthwise_token", "t");
    const handler = api.interceptors.response.handlers.find(Boolean);
    const saved = window.location;
    delete window.location;
    window.location = { pathname: "/doctor", href: "/doctor" };
    await expect(handler.rejected({ response: { status: 401 }, config: { url: "/reports" } })).rejects.toBeTruthy();
    expect(tokenStore.get()).toBeNull();
    expect(window.location.href).toBe("/login");
    window.location = saved;
  });

  it("a wrong password on the login call is not treated as an ended session", async () => {
    localStorage.setItem("healthwise_token", "t");
    const handler = api.interceptors.response.handlers.find(Boolean);
    await expect(handler.rejected({ response: { status: 401 }, config: { url: "/auth/login" } })).rejects.toBeTruthy();
    expect(tokenStore.get()).toBe("t");
  });

  it.fails("F-02: logging out removes the patient history drafts that were saved in the browser (patient details must not stay on a shared computer)", async () => {
    localStorage.setItem("healthwise_token", "t");
    localStorage.setItem("hw_history_draft_7", JSON.stringify({ f: { chief_complaint: "Chest pain, HIV positive" }, v: {} }));
    getMe.mockResolvedValue({ id: 1, role: "DOCTOR" });
    await act(async () => { render(<AuthProvider><Probe /></AuthProvider>); });
    await act(async () => { auth.logout(); });
    expect(localStorage.getItem("hw_history_draft_7")).toBeNull();
  });

  it.fails("F-03: logging out in one tab ends the session on screen in the other tabs at once", async () => {
    localStorage.setItem("healthwise_token", "t");
    getMe.mockResolvedValue({ id: 1, role: "DOCTOR" });
    await act(async () => { render(<AuthProvider><Probe /></AuthProvider>); });
    expect(auth.user).toBeTruthy();
    await act(async () => {
      localStorage.removeItem("healthwise_token");
      window.dispatchEvent(new StorageEvent("storage", { key: "healthwise_token", oldValue: "t", newValue: null }));
    });
    expect(auth.user).toBeNull();
  });
});
