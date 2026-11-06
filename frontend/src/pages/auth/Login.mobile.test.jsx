import { ALL_DEMO } from "../../components/auth/demoAccounts";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

let signedIn = null;
const loginWithOtp = vi.fn();
const requestOtp = vi.fn();
vi.mock("../../context/AuthContext", () => ({ ROLE_HOME: { PATIENT: "/patient" }, useAuth: () => ({ user: signedIn, login: vi.fn(), loginWithOtp, registerFirstAdmin: vi.fn() }) }));
vi.mock("../../services/authApi", () => ({ getSetupStatus: vi.fn(() => Promise.resolve({ needs_setup: false })), requestOtp: (...a) => requestOtp(...a) }));
import Login, { tenDigits } from "./Login";

const open = () => render(<MemoryRouter initialEntries={["/login"]}><Routes><Route path="/login" element={<Login />} /><Route path="/patient" element={<p>PATIENT HOME</p>} /></Routes></MemoryRouter>);
beforeEach(() => { vi.clearAllMocks(); window.matchMedia = vi.fn().mockImplementation((q) => ({ matches: false, media: q, addEventListener: () => {}, removeEventListener: () => {} })); });

describe("mobile numbers", () => {
  it("accepts a 10-digit mobile number in any style and refuses the rest", () => {
    for (const ok of ["9000000001", "+91 90000 00001", "090000-00001", "91 9000000001"]) expect(tenDigits(ok), ok).toBe("9000000001");
    for (const bad of ["", "12345", "5000000001", "90000000011", "abc"]) expect(tenDigits(bad), bad).toBe("");
  });
});

describe("Login with a mobile code", () => {
  it("asks for a code, shows the demo code only when the server sends it, and signs in when the six digits are complete", async () => {
    requestOtp.mockResolvedValue({ message: "sent", expires_in: 300, demo_code: "123456" });
    loginWithOtp.mockResolvedValue({ role: "PATIENT" });
    open();
    await userEvent.click(screen.getByRole("tab", { name: /Mobile code/ }));
    await userEvent.type(screen.getByLabelText("Mobile number"), "90000 00001");
    await userEvent.click(screen.getByRole("button", { name: /Send the code/ }));
    expect(await screen.findByLabelText("Digit 1")).toBeTruthy();
    expect(requestOtp).toHaveBeenCalledWith("9000000001");
    expect(screen.getByText(/no SMS is sent/)).toBeTruthy();
    await userEvent.paste("123456");
    await waitFor(() => expect(loginWithOtp).toHaveBeenCalledWith("9000000001", "123456"));
  });

  it("does not mention a demo code when the server did not send one, and a wrong code is shown as an error with the boxes cleared", async () => {
    requestOtp.mockResolvedValue({ message: "sent", expires_in: 300 });
    loginWithOtp.mockRejectedValue({ response: { status: 401, data: { detail: "That code is incorrect or has expired." } } });
    open();
    await userEvent.click(screen.getByRole("tab", { name: /Mobile code/ }));
    await userEvent.type(screen.getByLabelText("Mobile number"), "9000000001");
    await userEvent.click(screen.getByRole("button", { name: /Send the code/ }));
    await screen.findByLabelText("Digit 1");
    expect(screen.queryByText(/no SMS is sent/)).toBeNull();
    await userEvent.type(screen.getByLabelText("Digit 1"), "654321");
    expect(await screen.findByRole("alert")).toHaveProperty("textContent", "That code is incorrect or has expired.");
    expect(screen.getByLabelText("Digit 1").value).toBe("");
  });

  it("refuses a number that cannot be a mobile number without asking the server", async () => {
    open();
    await userEvent.click(screen.getByRole("tab", { name: /Mobile code/ }));
    await userEvent.type(screen.getByLabelText("Mobile number"), "12345");
    await userEvent.click(screen.getByRole("button", { name: /Send the code/ }));
    expect(await screen.findByText("Please enter a 10-digit mobile number.")).toBeTruthy();
    expect(requestOtp).not.toHaveBeenCalled();
  });

  it("the demo accounts are a dropdown under the button: closed until asked for, every account in one list grouped by role, a click fills the e-mail, the password and the phone, and it can be searched", async () => {
    open();
    const toggle = screen.getByRole("button", { name: /Demo accounts/ });
    expect(toggle.getAttribute("aria-expanded")).toBe("false");
    expect(document.getElementById("demo-sheet").getAttribute("aria-hidden")).toBe("true");                // closed: nothing in it can be tabbed to
    expect(screen.getByLabelText("Email")).toBeTruthy();                                                   // and the form is always there
    await userEvent.click(toggle);
    expect(document.getElementById("demo-sheet").getAttribute("data-open")).toBe("true");
    expect(document.querySelectorAll("#demo-sheet .hw-demo").length).toBe(ALL_DEMO.length);                              // all of them, no tabs to click through
    await userEvent.click(screen.getByRole("button", { name: /Fill in Billing: Bina Shah/ }));
    expect(document.getElementById("demo-sheet").getAttribute("data-open")).toBe("false");                 // choosing closes it so the form is in view
    expect(screen.getByLabelText("Email").value).toBe("billing@healthwise.demo.com");
    expect(screen.getByLabelText("Password").value).toBe("Demo@12345");
    expect(document.querySelectorAll(".hw-flash").length).toBe(2);                                         // both fields flash once
    await userEvent.click(screen.getByRole("button", { name: /Demo accounts/ }));
    await userEvent.type(screen.getByPlaceholderText("Search a role or name"), "radiolog");
    expect(screen.queryByRole("button", { name: /Fill in Billing/ })).toBeNull();
    expect(screen.getByRole("button", { name: /Fill in Radiologist/ })).toBeTruthy();
    await userEvent.keyboard("{Escape}");
    expect(document.getElementById("demo-sheet").getAttribute("data-open")).toBe("false");
    await userEvent.click(screen.getByRole("tab", { name: /Mobile code/ }));
    expect(screen.getByLabelText("Mobile number").value).toBe("9000000115");                              // the phone of the account picked (Bina Shah)
  });

  it("a click outside the dropdown closes it", async () => {
    open();
    await userEvent.click(screen.getByRole("button", { name: /Demo accounts/ }));
    expect(document.getElementById("demo-sheet").getAttribute("data-open")).toBe("true");
    await userEvent.click(screen.getByLabelText("Email"));
    expect(document.getElementById("demo-sheet").getAttribute("data-open")).toBe("false");
  });
});

describe("Login when someone is already signed in", () => {
  it("sends them to their home page without crashing (the hooks run in the same order every time)", () => {
    signedIn = null;
    const { rerender } = open();
    expect(screen.getByRole("tab", { name: /Mobile code/ })).toBeTruthy();
    signedIn = { role: "PATIENT" };
    rerender(<MemoryRouter initialEntries={["/login"]}><Routes><Route path="/login" element={<Login />} /><Route path="/patient" element={<p>PATIENT HOME</p>} /></Routes></MemoryRouter>);
    expect(screen.getByText("PATIENT HOME")).toBeTruthy();
    signedIn = null;
  });
});
