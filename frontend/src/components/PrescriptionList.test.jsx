import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

const printAs = vi.fn();
vi.mock("../utils/printTitle", () => ({ printAs: (...a) => printAs(...a) }));
vi.mock("./Barcode", () => ({ default: ({ value }) => <svg role="img" aria-label={`Barcode ${value}`} /> }));
import PrescriptionList from "./PrescriptionList";

const rx = (id, patient) => ({ id, code: `RX-0000${id}`, patient_name: patient, patient_code: `P-000${id}`, doctor_name: "Dr. Anjali Sharma", prescription_date: "2026-10-29", valid_until: "2026-11-28",
  status: "ACTIVE", clinical_indication: null, notes: null, tests: [], doctor_info: {}, patient_info: {}, hospital: {},
  items: [{ id: id * 10, medicine_name: "Tab. Test", dosage: "5 mg", frequency: "Twice a day", duration: "5 days", quantity: 10, dispense_status: "PENDING", dispensed_quantity: 0, remaining_quantity: 10 }] });
const open = (items = [rx(1, "Hari Lad"), rx(2, "Rahul Patil")]) => render(<MemoryRouter><PrescriptionList items={items} showPatient /></MemoryRouter>);
beforeEach(() => printAs.mockClear());

describe("PrescriptionList", () => {
  it("every card has a big Open and a big Print button in its top-right corner", () => {
    open();
    expect(screen.getByRole("button", { name: "Open prescription RX-00001" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Print prescription RX-00002" })).toBeTruthy();
    expect(screen.getAllByRole("button", { name: /^(Open|Print) prescription/ }).length).toBe(4);
    expect(document.querySelectorAll(".print-area").length).toBe(0);
  });

  it("Open shows the full sheet under that card, and only one sheet is open at a time", async () => {
    open();
    await userEvent.click(screen.getByRole("button", { name: "Open prescription RX-00001" }));
    expect(document.querySelectorAll(".print-area").length).toBe(1);
    expect(screen.getByRole("button", { name: "Close prescription RX-00001" }).getAttribute("aria-expanded")).toBe("true");
    await userEvent.click(screen.getByRole("button", { name: "Open prescription RX-00002" }));
    expect(document.querySelectorAll(".print-area").length).toBe(1);
    expect(document.querySelector(".print-area").getAttribute("aria-label")).toBe("Prescription RX-00002");
    await userEvent.click(screen.getByRole("button", { name: "Close prescription RX-00002" }));
    expect(document.querySelectorAll(".print-area").length).toBe(0);
  });

  it("Print opens the sheet and prints it once, named after the patient and the prescription", async () => {
    open();
    await userEvent.click(screen.getByRole("button", { name: "Print prescription RX-00002" }));
    await waitFor(() => expect(printAs).toHaveBeenCalledTimes(1));
    expect(printAs).toHaveBeenCalledWith("Rahul Patil", "RX-00002", "Prescription");
    expect(document.querySelector(".print-area").getAttribute("aria-label")).toBe("Prescription RX-00002");
  });

  it("shows extra content under a card (for example the doctor's cancel link)", () => {
    render(<MemoryRouter><PrescriptionList items={[rx(1, "Hari Lad")]} renderBelow={() => <button>Cancel prescription</button>} /></MemoryRouter>);
    expect(screen.getByRole("button", { name: "Cancel prescription" })).toBeTruthy();
  });
});
