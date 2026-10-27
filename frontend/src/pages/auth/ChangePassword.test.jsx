import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

const refresh = vi.fn(() => Promise.resolve());
const logout = vi.fn();
vi.mock("../../context/AuthContext", () => ({ ROLE_HOME: { PATIENT: "/patient" }, useAuth: () => ({ user: { full_name: "Lyubochka", role: "PATIENT", must_change_password: true }, refresh, logout }) }));
vi.mock("../../services/authApi", () => ({ changePassword: vi.fn(() => Promise.resolve({ access_token: "new-token" })) }));
import { changePassword } from "../../services/authApi";
import ChangePasswordDialog from "../../components/ChangePasswordDialog";
import ProtectedRoute from "../../routes/ProtectedRoute";

const open = () => render(<MemoryRouter><ChangePasswordDialog /></MemoryRouter>);
beforeEach(() => { vi.clearAllMocks(); localStorage.clear(); });

describe("Change-password pop-up (first login)", () => {
  it("opens as a dialog that greets the person by name and cannot be closed", () => {
    open();
    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(screen.getByRole("heading").textContent).toMatch(/Choose your own password/);
    expect(screen.getByText("Lyubochka")).toBeTruthy();
    expect(screen.queryByLabelText("Close")).toBeNull();
  });

  it("is shown instead of the page for a person who still has the starting password", () => {
    render(<MemoryRouter><ProtectedRoute /></MemoryRouter>);
    expect(screen.getByRole("dialog")).toBeTruthy();
  });

  it("shows the rules as they are met and keeps Save off until the password is valid and typed twice", async () => {
    open();
    const save = screen.getByRole("button", { name: /Save my password/ });
    expect(save.disabled).toBe(true);
    await userEvent.type(screen.getByPlaceholderText(/Starting password/), "Welcome@123");
    await userEvent.type(screen.getByPlaceholderText("New password"), "abc");
    expect(save.disabled).toBe(true);
    await userEvent.type(screen.getByPlaceholderText("New password"), "defgh1");
    await userEvent.type(screen.getByPlaceholderText(/again/), "abcdefgh1");
    expect(save.disabled).toBe(false);
    await userEvent.clear(screen.getByPlaceholderText(/again/));
    await userEvent.type(screen.getByPlaceholderText(/again/), "different1");
    expect(screen.getByText(/not the same/)).toBeTruthy();
    expect(save.disabled).toBe(true);
  });

  it("saves, keeps the person signed in with the new token and refreshes the session", async () => {
    open();
    await userEvent.type(screen.getByPlaceholderText(/Starting password/), "Welcome@123");
    await userEvent.type(screen.getByPlaceholderText("New password"), "MyOwnPass9");
    await userEvent.type(screen.getByPlaceholderText(/again/), "MyOwnPass9");
    await userEvent.click(screen.getByRole("button", { name: /Save my password/ }));
    expect(changePassword).toHaveBeenCalledWith({ current_password: "Welcome@123", new_password: "MyOwnPass9" });
    await vi.waitFor(() => expect(refresh).toHaveBeenCalled());
    expect(localStorage.getItem("healthwise_token")).toBe("new-token");
  });

  it("can show and hide what is typed, and the person can log out instead", async () => {
    open();
    const box = screen.getByPlaceholderText("New password");
    expect(box.getAttribute("type")).toBe("password");
    await userEvent.click(screen.getAllByRole("button", { name: "Show password" })[1]);
    expect(box.getAttribute("type")).toBe("text");
    await userEvent.click(screen.getByRole("button", { name: /Log out instead/ }));
    expect(logout).toHaveBeenCalled();
  });
});
