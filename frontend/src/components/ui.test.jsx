import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { useState } from "react";
import { Field, Input, Modal } from "./ui";
import { Loading } from "./Feedback";
import { ReportsTable } from "./Cards";

function Host({ onClose = () => {} }) {
  const [name, setName] = useState("");
  return (
    <>
      <button>Opener</button>
      <Modal title="Edit details" onClose={onClose}>
        <Input aria-label="Name" value={name} onChange={(e) => setName(e.target.value)} />
      </Modal>
    </>
  );
}

describe("Modal (a bottom sheet on a phone)", () => {
  it("is a labelled modal dialog that rises from the bottom edge and scrolls inside itself", () => {
    render(<Host />);
    const sheet = screen.getByRole("dialog", { name: "Edit details" });
    expect(sheet.getAttribute("aria-modal")).toBe("true");
    expect(sheet.className).toMatch(/rounded-t-3xl/);
    expect(sheet.className).toMatch(/max-h-\[92dvh\]/);                              // never taller than the screen; the keyboard-safe unit
    expect(sheet.className).toMatch(/sheet-up/);
    expect(document.body.style.overflow).toBe("hidden");
  });

  it("closes with the X button, with Escape, and with a tap on the dim area, but not with a tap inside", async () => {
    const onClose = vi.fn();
    const { container } = render(<Host onClose={onClose} />);
    await userEvent.click(screen.getByRole("dialog"));
    expect(onClose).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Close" }));
    await userEvent.keyboard("{Escape}");
    await userEvent.click(container.querySelector(".fixed.inset-0"));
    expect(onClose).toHaveBeenCalledTimes(3);
  });

  it("typing inside it keeps the focus in the box (a re-render does not steal it), and closing releases the page lock", async () => {
    const { unmount } = render(<Host />);
    const box = screen.getByLabelText("Name");
    await userEvent.type(box, "Asha");
    expect(document.activeElement).toBe(box);
    expect(box.value).toBe("Asha");
    unmount();
    expect(document.body.style.overflow).toBe("");
  });
});

describe("Field", () => {
  it("shows an error as an alert under the field, in place of the hint", () => {
    render(<Field label="Phone" hint="10 digits" error="Enter a 10 digit number"><Input aria-invalid="true" /></Field>);
    expect(screen.getByRole("alert").textContent).toBe("Enter a 10 digit number");
    expect(screen.queryByText("10 digits")).toBeNull();
  });
  it("shows the hint when there is no error", () => {
    render(<Field label="Phone" hint="10 digits"><Input /></Field>);
    expect(screen.getByText("10 digits")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe("loading and lists on a phone", () => {
  it("Loading is a skeleton that is still announced as a status", () => {
    const { container } = render(<Loading />);
    expect(screen.getByRole("status").textContent).toBe("Loading...");
    expect(container.querySelectorAll(".skeleton").length).toBeGreaterThan(1);
  });

  it("the reports list is a stack of tappable cards, never a wide table, and says so when the date is not printed", () => {
    const reports = [{ id: 1, filename: "a-very-long-report-file-name-that-would-break-a-narrow-table.pdf", patient_name: "Rahul Patil", patient_code: "P-1", report_type_label: "Laboratory test report (blood)", report_date: null, parameter_count: 9, uploaded_by_name: "Priya", display_status: "WAITING_FOR_DOCTOR" }];
    const { container } = render(<MemoryRouter><ReportsTable reports={reports} base="/doctor/reports" /></MemoryRouter>);
    expect(container.querySelector("table")).toBeNull();
    const card = screen.getByRole("link");
    expect(card.getAttribute("href")).toBe("/doctor/reports/1");
    expect(card.textContent).toMatch(/report date not printed/);
    expect(container.querySelector("p.break-words")).toBeTruthy();                   // a long file name wraps instead of widening the page
  });
});
