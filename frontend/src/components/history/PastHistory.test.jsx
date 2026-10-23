import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("../../services/historyApi", () => ({
  removeAdmission: vi.fn(), removeCondition: vi.fn(), removeMedicine: vi.fn(), removeSurgery: vi.fn(), verifyRecord: vi.fn(() => Promise.resolve(null)),
  saveAdmission: vi.fn(), saveCondition: vi.fn(), saveMedicine: vi.fn(), saveSurgery: vi.fn(),
}));
import PastHistory from "./PastHistory";

const ver = (over = {}) => ({ source: "PATIENT_REPORTED", source_label: "Told by the patient", verified: false, verified_by_name: null, verified_at: null, ...over });
const past = {
  diabetes: { id: 1, kind: "DIABETES", name: "Diabetes mellitus", diagnosis_type: "Type 2", duration_text: "5 years", diagnosis_year: 2021, years_since_diagnosis: 5, control_status: "FAIR", on_treatment: true,
    control: { hba1c: 7.4, noted_on: "Sep 2026" }, complications: { retinopathy: "NO", neuropathy: "YES", nephropathy: "UNKNOWN", foot: "UNKNOWN", cardiovascular: "UNKNOWN", hypoglycemia: "UNKNOWN" },
    complications_other: null, hospitalisation: { happened: "UNKNOWN" }, other_details: null, notes: null, medications: [{ id: 5, name: "Tab. Metformin", dose: "500 mg", frequency: "twice daily", route: "Oral", is_current: true, ...ver() }],
    ...ver({ source: "DOCTOR_VERIFIED", source_label: "Checked by a doctor", verified: true, verified_by_name: "Dr. Test", verified_at: "2026-10-01T10:00:00" }) },
  hypertension: null, other_conditions: [],
  medications: [{ id: 5, name: "Tab. Metformin", dose: "500 mg", frequency: "twice daily", route: "Oral", since: "2021", prescriber: null, adherence: "SOMETIMES_MISSED", condition_id: 1, reason: null, is_current: true, ...ver() }],
  unlinked_medications: [],
  admissions: [{ id: 9, hospital_name: "City Hospital", admitted_at: "2024-03-10T09:30:00", discharged_at: "2024-03-13T14:45:00", admitted_date_text: null, admission_type: "EMERGENCY", main_complaint: "Fever and vomiting",
    final_diagnosis: "Viral gastroenteritis", length_of_stay: { days: 3, hours: 5, minutes: 15, text: "3 days 5 hours" }, vitals: {}, medications: [], discharge_medications: [], surgeries: [], ...ver({ source: "HOSPITAL_RECORD", source_label: "From a hospital record" }) }],
  standalone_surgeries: [], counts: { conditions: 1, medications: 1, admissions: 1, surgeries: 0 }, unverified: 2,
};

describe("PastHistory", () => {
  it("shows the detailed medical history first, with the source of every record and 'Not recorded' for what is unknown", () => {
    render(<PastHistory patientId={1} past={past} />);
    const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(headings[0]).toMatch(/Detailed medical history/);
    expect(headings[1]).toMatch(/Previous hospital admission history/);
    expect(screen.getByText(/Checked by Dr\. Test/)).toBeTruthy();
    expect(screen.getByText("From a hospital record")).toBeTruthy();
    expect(screen.getAllByText("Not recorded").length).toBeGreaterThan(3);                       // unknown fields are labelled, never guessed
    expect(screen.getByText(/No hypertension history is recorded/)).toBeTruthy();
    expect(screen.getByText("Nerves (neuropathy): Yes")).toBeTruthy();
    expect(screen.getByText("Foot or non-healing wounds: Not recorded")).toBeTruthy();           // an unanswered question is not "No"
    expect(screen.getByText("3 days 5 hours")).toBeTruthy();                                    // length of stay from the real timestamps
  });

  it("is read-only for a patient: no add, edit, remove or check buttons", () => {
    render(<PastHistory past={past} />);
    for (const name of [/Edit/, /Remove/, /Mark as checked/, /Add an admission/, /Add a medicine/, /Add an illness/]) expect(screen.queryByRole("button", { name })).toBeNull();
  });

  it("lets a doctor add, edit, remove and check, and says how many records are still unchecked", async () => {
    render(<PastHistory patientId={1} past={past} editable />);
    expect(screen.getByText(/2 records/)).toBeTruthy();
    expect(screen.getByRole("button", { name: /Add an admission/ })).toBeTruthy();
    expect(screen.getAllByRole("button", { name: /Edit/ }).length).toBeGreaterThan(0);
    await userEvent.click(screen.getByRole("button", { name: /Add hypertension history/ }));
    const dialogTitle = await screen.findByText(/Add: Hypertension/);
    expect(dialogTitle).toBeTruthy();
    const form = dialogTitle.closest("div").parentElement;
    expect(within(form).getByText(/Has the patient had any of these complications/)).toBeTruthy();
    expect(within(form).getAllByRole("button", { name: "Not recorded" }).length).toBe(4);        // three complication questions and "ever admitted", all unanswered by default
  });

  it("does not show a stay as calculated when the discharge time is missing", () => {
    const open = { ...past, admissions: [{ ...past.admissions[0], discharged_at: null, length_of_stay: null }] };
    render(<PastHistory past={open} />);
    expect(screen.getByText(/no discharge time/)).toBeTruthy();
    expect(screen.queryByText("3 days 5 hours")).toBeNull();
  });

  it("offers a list of common long-term illnesses, and a box to type any other name", async () => {
    render(<PastHistory patientId={1} past={past} editable />);
    await userEvent.click(screen.getByRole("button", { name: /Add an illness/ }));
    const list = await screen.findByRole("combobox", { name: /Name of the illness/ });
    const options = within(list).getAllByRole("option").map((o) => o.textContent);
    expect(options).toContain("Bronchial asthma");
    expect(options).toContain("Chronic kidney disease");
    expect(options.at(-1)).toBe("Other (type the name)");
    expect(screen.queryByPlaceholderText("Name of the illness")).toBeNull();                      // no typing box until "Other" is chosen
    await userEvent.selectOptions(list, "__other");
    expect(screen.getByPlaceholderText("Name of the illness")).toBeTruthy();
  });
});
