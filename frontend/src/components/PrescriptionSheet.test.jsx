import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
vi.mock("./Barcode", () => ({ default: ({ value }) => <svg role="img" aria-label={`Barcode ${value}`} /> }));       // the barcode library needs a real canvas
import PrescriptionSheet from "./PrescriptionSheet";
import { collectionState, frequencyShorthand, statusBanner } from "../utils/prescriptionFormat";

const item = (over = {}) => ({ id: 1, medicine_name: "Tab. Paracetamol", dosage: "500 mg", frequency: "Twice a day", duration: "5 days", quantity: 10, instructions: "after food",
  dispense_status: "PENDING", dispensed_quantity: 0, remaining_quantity: 10, ...over });
const rx = (over = {}) => ({
  id: 7, code: "RX-00007", patient_name: "Rahul Patil", patient_code: "P-0001", doctor_name: "Dr. Anjali Sharma", prescription_date: "2026-10-28", valid_until: "2026-11-27",
  clinical_indication: "Fever and cough", notes: "Drink plenty of fluids.", status: "ACTIVE", items: [item()], tests: ["Chest X-ray", "CBC"],
  doctor_info: { qualification: "MBBS, MD", specialization: "Physician", department: "General Medicine", registration_number: "MH-12345" },
  patient_info: { age: 34, gender: "male", phone: "9876543210", allergies: null }, hospital: { name: "City Hospital", address: "12 MG Road, Pune", phone: "020 1234 5678", email: "info@city.example" },
  ...over,
});
const text = () => document.body.textContent;

describe("PrescriptionSheet", () => {
  it("shows every section of a prescription pad", () => {
    render(<PrescriptionSheet rx={rx()} variant="patient" />);
    expect(screen.getByText("City Hospital")).toBeTruthy();                                   // letterhead
    expect(screen.getAllByText("Dr. Anjali Sharma").length).toBeGreaterThan(0);               // not "Dr. Dr."
    expect(text()).toMatch(/MBBS, MD/); expect(text()).toMatch(/Physician · General Medicine/); expect(text()).toMatch(/Reg\. No\.: MH-12345/);
    expect(text()).toMatch(/12 MG Road, Pune/); expect(text()).toMatch(/020 1234 5678/);
    expect(text()).toMatch(/34 y \/ Male/); expect(text()).toMatch(/P-0001/); expect(text()).toMatch(/9876543210/);   // patient strip
    expect(text()).toMatch(/RX-00007/); expect(text()).toMatch(/Valid until/);
    expect(text()).toMatch(/Diagnosis \/ reason:\s*Fever and cough/);                          // clinical
    expect(screen.getAllByText("℞").length).toBe(1);                                          // the Rx body
    expect(screen.getByRole("img", { name: "Barcode RX-00007" })).toBeTruthy();                // the code to look the prescription up
    expect(text()).toMatch(/Advice \/ Notes/); expect(text()).toMatch(/Drink plenty of fluids/);       // advice
    expect(text()).toMatch(/Computer-generated prescription\. Not valid without the doctor's signature\./);   // footer
    expect(screen.getByLabelText("Space for the doctor's stamp and signature")).toBeTruthy();
  });

  it("the patient variant shows the tests and the collected / pending badge; the pharmacy variant never shows tests", () => {
    const { unmount } = render(<PrescriptionSheet rx={rx()} variant="patient" />);
    expect(text()).toMatch(/Investigations advised/); expect(text()).toMatch(/Chest X-ray/); expect(text()).toMatch(/Pending/);
    unmount();
    render(<PrescriptionSheet rx={rx()} variant="pharmacy" />);                              // the tests are even passed in, and still not shown
    expect(text()).not.toMatch(/Investigations advised/); expect(text()).not.toMatch(/Chest X-ray/); expect(text()).not.toMatch(/CBC/);
    expect(screen.getByRole("region", { name: "Dispensing status" })).toBeTruthy();
  });

  it("the allergy line appears only when there is an allergy, and says so in words", () => {
    const { unmount } = render(<PrescriptionSheet rx={rx()} variant="patient" />);
    expect(text()).not.toMatch(/ALLERGY/);
    unmount();
    render(<PrescriptionSheet rx={rx({ patient_info: { age: 34, gender: "male", allergies: "Penicillin" } })} variant="patient" />);
    expect(text()).toMatch(/ALLERGY:\s*Penicillin/);
  });

  it("missing details are left out: no 'undefined', no 'null', no empty labelled boxes", () => {
    render(<PrescriptionSheet rx={rx({ doctor_info: {}, patient_info: {}, hospital: {}, clinical_indication: null, notes: null, tests: [], items: [item({ instructions: null })] })} variant="patient" />);
    expect(text()).not.toMatch(/undefined|null|NaN/);
    expect(text()).not.toMatch(/Reg\. No\./); expect(text()).not.toMatch(/Phone/); expect(text()).not.toMatch(/Age \/ Sex/);
    expect(text()).not.toMatch(/Diagnosis/); expect(text()).not.toMatch(/Advice \/ Notes/); expect(text()).not.toMatch(/Investigations/);
    expect(screen.getAllByText("Dr. Anjali Sharma").length).toBeGreaterThan(0);                // what is known is still there
    expect(text()).toMatch(/Prescription no\./);
  });

  it("a doctor name without 'Dr.' gets it, one with it is not doubled", () => {
    render(<PrescriptionSheet rx={rx({ doctor_name: "Anjali Sharma" })} variant="patient" />);
    expect(screen.getAllByText("Dr. Anjali Sharma").length).toBeGreaterThan(0);
    expect(text()).not.toMatch(/Dr\. Dr\./);
  });

  it("thirty medicines with very long names all render", () => {
    const many = Array.from({ length: 30 }, (_, i) => item({ id: i + 1, medicine_name: `Tab. Medicine${i + 1} ${"VeryLongMedicineNameWithoutAnySpaces".repeat(3)}` }));
    render(<PrescriptionSheet rx={rx({ items: many })} variant="patient" />);
    expect(document.querySelectorAll("table.sm\\:table tbody tr").length).toBe(30);
    expect(document.querySelectorAll("ol li").length).toBe(30);                                // the phone cards
    expect(screen.getAllByText(/Medicine30/).length).toBeGreaterThan(0);
  });

  it("shows a banner above the sheet when the prescription is expired, fully dispensed or cancelled, not on a normal one", () => {
    const { unmount } = render(<PrescriptionSheet rx={rx()} variant="pharmacy" />);
    expect(screen.queryByRole("status")).toBeNull();
    unmount();
    for (const [status, word] of [["EXPIRED", "EXPIRED"], ["DISPENSED", "FULLY DISPENSED"], ["CANCELLED", "CANCELLED"]]) {
      const view = render(<PrescriptionSheet rx={rx({ status })} variant="pharmacy" />);
      expect(within(screen.getByRole("status")).getByText(word)).toBeTruthy();
      expect(screen.getByRole("status").closest("section")).toBeNull();                       // above the sheet, not inside it
      view.unmount();
    }
  });

  it("has a print button that is kept off the paper, and the sheet is the one print area", () => {
    const onPrint = vi.fn();
    render(<PrescriptionSheet rx={rx()} variant="patient" onPrint={onPrint} />);
    const button = screen.getByRole("button", { name: /Print/ });
    expect(button.closest(".no-print")).toBeTruthy();
    button.click();
    expect(onPrint).toHaveBeenCalled();
    expect(document.querySelectorAll(".print-area").length).toBe(1);
    expect(document.querySelector(".print-area").getAttribute("aria-label")).toBe("Prescription RX-00007");
  });

  it("uses a real table with column headers", () => {
    render(<PrescriptionSheet rx={rx()} variant="patient" />);
    const headers = [...document.querySelectorAll("table.sm\\:table th")].map((h) => h.textContent);
    expect(headers).toEqual(expect.arrayContaining(["#", "Medicine", "Dose", "Frequency", "Duration", "Qty"]));
    expect(document.querySelector("table.sm\\:table th").getAttribute("scope")).toBe("col");
  });
});

describe("prescription formatting helpers", () => {
  it.each([["Twice a day", "1-0-1"], ["BD", "1-0-1"], ["TDS", "1-1-1"], ["Three times a day", "1-1-1"], ["1-0-1", "1-0-1"], ["1-1-1-1", "1-1-1-1"], ["At bedtime", "0-0-1"], ["Every morning", "1-0-0"],
    ["Once a day", ""], ["Daily", ""], ["As needed", ""], ["", ""], [null, ""], ["Morning and night", ""]])("frequency %j -> %j", (input, expected) => expect(frequencyShorthand(input)).toBe(expected));

  it("collection state and banners", () => {
    expect(collectionState({ dispense_status: "DISPENSED" }).label).toBe("Collected");
    expect(collectionState({ dispense_status: "PARTIALLY_DISPENSED", dispensed_quantity: 4, quantity: 10 }).label).toBe("Partly collected (4 of 10)");
    expect(collectionState({ dispense_status: "UNAVAILABLE" }).label).toBe("Not in stock");
    expect(collectionState({ dispense_status: "PENDING" }).label).toBe("Pending");
    expect(statusBanner("ACTIVE")).toBeNull(); expect(statusBanner("EXPIRED").title).toBe("EXPIRED");
  });
});
