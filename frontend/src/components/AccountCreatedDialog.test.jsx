import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AccountCreatedDialog from "./AccountCreatedDialog";

describe("AccountCreatedDialog", () => {
  it("shows who was created, the login email and the starting password, with a copy button for each", async () => {
    const writeText = vi.fn(() => Promise.resolve());
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    render(<AccountCreatedDialog kind="patient" name="Hari Lad" code="P-0005" email="hari@example.com" password="Welcome@123" onClose={() => {}} />);
    expect(screen.getByText("Account created")).toBeTruthy();
    expect(screen.getByText("Hari Lad")).toBeTruthy();
    expect(screen.getByText("hari@example.com")).toBeTruthy();
    expect(screen.getByText("Welcome@123")).toBeTruthy();
    expect(screen.getByText(/asked to choose their own password/)).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Copy the starting password" }));
    expect(writeText).toHaveBeenCalledWith("Welcome@123");
    expect(await screen.findByText("Copied")).toBeTruthy();
  });

  it("says the password was chosen when none was generated, and closes with Done", async () => {
    const onClose = vi.fn();
    render(<AccountCreatedDialog kind="doctor" name="Dr. New" email="new@example.com" password={null} onClose={onClose} actions={<button>Extra</button>} />);
    expect(screen.getByText("The password you chose")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Copy the starting password" })).toBeNull();
    expect(screen.getByRole("button", { name: "Extra" })).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Done" }));
    expect(onClose).toHaveBeenCalled();
  });
});
