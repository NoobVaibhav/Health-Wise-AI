import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

const login = vi.fn();
const registerFirstAdmin = vi.fn();
vi.mock("../../context/AuthContext", () => ({
  ROLE_HOME: { ADMIN: "/admin", PATIENT: "/patient" },
  useAuth: () => ({ user: null, login, registerFirstAdmin }),
}));
vi.mock("../../services/authApi", () => ({ getSetupStatus: vi.fn(() => Promise.resolve({ needs_setup: true })) }));
import Login from "./Login";
import Register from "./Register";

beforeEach(() => { vi.clearAllMocks(); });
const open = (ui) => render(<MemoryRouter>{ui}</MemoryRouter>);

describe("Login form", () => {
  it("shows an error under each empty field, puts the cursor in the first one and sends nothing", async () => {
    open(<Login />);
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect(screen.getByText("Please enter your e-mail address.")).toBeTruthy();
    expect(screen.getByText("Please enter your password.")).toBeTruthy();
    expect(document.activeElement).toBe(screen.getByLabelText("Email"));
    expect(screen.getByLabelText("Email").getAttribute("aria-invalid")).toBe("true");
    expect(screen.getByLabelText("Email").getAttribute("aria-describedby")).toBe("email-error");
    expect(login).not.toHaveBeenCalled();
  });

  it("checks the e-mail when the person leaves the field, not on every key", async () => {
    open(<Login />);
    const box = screen.getByLabelText("Email");
    await userEvent.type(box, "not-an-email");
    expect(screen.queryByText(/valid e-mail address/)).toBeNull();
    await userEvent.tab();
    expect(await screen.findByText(/valid e-mail address/)).toBeTruthy();
    await userEvent.clear(box);
    await userEvent.type(box, "a@b.co");
    expect(screen.queryByText(/valid e-mail address/)).toBeNull();
  });

  it("sends the e-mail trimmed and in lower case, keeps the button off while it works, and keeps what was typed when the answer is no", async () => {
    let finish;
    login.mockImplementation(() => new Promise((_, reject) => { finish = () => reject({ response: { status: 401, data: { detail: "Incorrect email or password." } } }); }));
    open(<Login />);
    await userEvent.type(screen.getByLabelText("Email"), "  Rahul.Patil@Example.COM ");
    await userEvent.type(screen.getByLabelText("Password"), "wrong-pass1");
    await userEvent.click(screen.getByRole("button", { name: "Log in" }));
    expect(login).toHaveBeenCalledWith("rahul.patil@example.com", "wrong-pass1");
    const busy = screen.getByRole("button", { name: "Logging in..." });
    expect(busy.disabled).toBe(true);
    await userEvent.click(busy);
    expect(login).toHaveBeenCalledTimes(1);                                              // no double submit
    finish();
    expect((await screen.findByRole("alert")).textContent).toBe("Incorrect email or password.");
    expect(screen.getByLabelText("Email").value).toBe("Rahul.Patil@Example.COM");            // nothing was cleared (an e-mail box trims the spaces itself)
    expect(screen.getByLabelText("Password").value).toBe("wrong-pass1");
  });

  it("uses the right input types for a browser's helpers", () => {
    open(<Login />);
    const email = screen.getByLabelText("Email");
    expect(email.getAttribute("type")).toBe("email");
    expect(email.getAttribute("autocomplete")).toBe("email");
    expect(email.getAttribute("maxlength")).toBe("254");
    expect(screen.getByLabelText("Password").getAttribute("autocomplete")).toBe("current-password");
  });
});

describe("Register (first administrator) form", () => {
  const fill = async (over = {}) => {
    const v = { name: "Anjali Sharma", email: "anjali@example.com", pw: "Zebra-Clock-81", again: "Zebra-Clock-81", ...over };
    await userEvent.type(await screen.findByLabelText("Full name"), v.name);
    await userEvent.type(screen.getByLabelText("Email"), v.email);
    await userEvent.type(screen.getByPlaceholderText("Password (at least 8 characters)"), v.pw);
    await userEvent.type(screen.getByPlaceholderText("Type the password again"), v.again);
  };

  it("refuses a name with digits, a weak password and a different confirmation, and sends nothing", async () => {
    open(<Register />);
    await fill({ name: "Anjali7", pw: "password1", again: "password2" });
    await userEvent.click(screen.getByRole("button", { name: "Create administrator" }));
    expect(screen.getByText(/only letters, spaces/)).toBeTruthy();
    expect(screen.getByText(/too common/)).toBeTruthy();
    expect(screen.getByText(/not the same/)).toBeTruthy();
    expect(registerFirstAdmin).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(screen.getByLabelText("Full name"));
  });

  it("shows a live strength hint and refuses a password that holds the e-mail name", async () => {
    open(<Register />);
    await userEvent.type(await screen.findByPlaceholderText("Password (at least 8 characters)"), "abc");
    expect(screen.getByText(/Password strength: Weak/)).toBeTruthy();
    await userEvent.clear(screen.getByPlaceholderText("Password (at least 8 characters)"));
    await fill({ name: "Anjali Sharma", email: "anjali.sharma@example.com", pw: "Anjali.Sharma99", again: "Anjali.Sharma99" });
    await userEvent.click(screen.getByRole("button", { name: "Create administrator" }));
    expect(screen.getAllByText(/must not contain your e-mail name/).length).toBeGreaterThan(0);
    expect(registerFirstAdmin).not.toHaveBeenCalled();
  });

  it("sends clean values when everything is right, and shows the server's message under the field when it says no", async () => {
    registerFirstAdmin.mockRejectedValue({ response: { status: 422, data: { detail: "Email: taken.", errors: [{ field: "email", label: "Email", message: "This e-mail address is already used." }] } } });
    open(<Register />);
    await fill({ name: "Anjali   Sharma", email: "  Anjali@Example.com " });
    await userEvent.click(screen.getByRole("button", { name: "Create administrator" }));
    expect(registerFirstAdmin).toHaveBeenCalledWith({ full_name: "Anjali Sharma", email: "anjali@example.com", password: "Zebra-Clock-81" });
    expect(await screen.findByText("This e-mail address is already used.")).toBeTruthy();
    expect(screen.getByLabelText("Full name").value).toBe("Anjali   Sharma");             // nothing was cleared
  });

  it("can show and hide the password", async () => {
    open(<Register />);
    const box = await screen.findByPlaceholderText("Password (at least 8 characters)");
    expect(box.getAttribute("type")).toBe("password");
    await userEvent.click(screen.getAllByRole("button", { name: "Show password" })[0]);
    expect(box.getAttribute("type")).toBe("text");
    expect(box.getAttribute("autocomplete")).toBe("new-password");
  });
});

describe("the server's 422 answer", () => {
  it("becomes one readable sentence", async () => {
    const { getErrorMessage, getFieldErrors } = await import("../../services/api");
    const error = { response: { status: 422, data: { detail: [{ msg: "Value error, The name is bad." }, { msg: "Value error, The name is bad." }, { msg: "Field required" }] } } };
    expect(getErrorMessage(error)).toBe("The name is bad. Field required");
    expect(getFieldErrors({ response: { data: { errors: [{ field: "phone", message: "Bad phone." }] } } })).toEqual({ phone: "Bad phone." });
    expect(getFieldErrors({})).toEqual({});
  });
});
