import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { setViewport } from "../../test/viewport";

vi.mock("../../context/AuthContext", () => ({ useAuth: () => ({ user: { id: 2, role: "DOCTOR", grade: "CONSULTANT", full_name: "Dr. Anjali Sharma" } }) }));
vi.mock("../../components/DoctorForms", () => ({ PrescriptionModal: () => null }));
vi.mock("../../components/ClinicalDialogs", () => ({ AdmitDialog: () => null, ReferDialog: () => null }));
vi.mock("../../services/doctorApi", () => ({ getPatientHistory: vi.fn(() => Promise.resolve({ reports: [], prescriptions: [], patient: {} })) }));
vi.mock("../../services/careApi", () => ({
  getWorkspace: vi.fn(),
  saveConsultation: vi.fn(() => Promise.resolve({})), signConsultation: vi.fn(() => Promise.resolve({})), addVitals: vi.fn(), addDiagnosis: vi.fn(), addOrder: vi.fn(), addAddendum: vi.fn(), withdrawDiagnosis: vi.fn(),
}));
import { getWorkspace } from "../../services/careApi";
import Consultation from "./Consultation";

const workspace = (over = {}) => ({
  encounter: { id: 14, status: "OPEN", department_name: "General Medicine" },
  patient: { id: 2, uhid: "HW-26-000002", full_name: "Pranav Sathe", age: 22, gender: "male", allergies: "Penicillin", current_medications: "Metformin" },
  consultation: null, template: null, diagnoses: [], orders: [], prescriptions: [], addenda: [], charges: [],
  vitals: [{ id: 1, pulse: 72, bp_systolic: 120, bp_diastolic: 80, recorded_by: "Nurse", recorded_at: "2026-11-05T06:00:00" }],
  previous_consultations: [{ id: 9, signed_at: "2026-10-01T05:00:00", doctor_name: "Dr. Rohan Mehta", complaint: "Cough", assessment: "Bronchitis" }],
  ...over,
});
const open = () => render(<MemoryRouter initialEntries={["/doctor/consultation/14"]}><Routes><Route path="/doctor/consultation/:encounterId" element={<Consultation />} /></Routes></MemoryRouter>);
beforeEach(() => { vi.clearAllMocks(); getWorkspace.mockResolvedValue(workspace()); });

describe("the consultation as a doctor's workspace", () => {
  it("landscape tablet: a split view (patient information left, the record right), the sticky banner with the red allergy alert, and the sticky action bar", async () => {
    setViewport(1180);
    const { container } = open();
    await screen.findByText("Pranav Sathe");
    expect(container.querySelector("[data-consultation='split']")).toBeTruthy();
    expect(container.querySelector("[data-patient-banner]")).toBeTruthy();
    expect(screen.getByRole("alert").textContent).toMatch(/Allergies: Penicillin/);
    const side = screen.getByRole("complementary", { name: "Patient information" });
    expect(within(side).getByRole("tab", { name: "History" }).getAttribute("aria-selected")).toBe("true");
    expect(within(side).getByText(/Bronchitis/)).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Vital signs" })).toBeTruthy();                       // the record side is there at the same time
    const bar = container.querySelector("[data-action-bar]");
    expect(within(bar).getByRole("button", { name: "Save draft" })).toBeTruthy();
    expect(within(bar).getByRole("button", { name: "Review and sign" })).toBeTruthy();
  });

  it("the side tabs show Medicines and Vitals of the patient", async () => {
    setViewport(1180);
    open();
    const side = await screen.findByRole("complementary", { name: "Patient information" });
    await userEvent.click(within(side).getByRole("tab", { name: "Medicines" }));
    expect(within(side).getByText(/Metformin/)).toBeTruthy();
    await userEvent.click(within(side).getByRole("tab", { name: "Vitals" }));
    expect(within(side).getByText(/Pulse 72/)).toBeTruthy();
  });

  it("phone: one pane at a time, switched with Write / Patient information; the banner and action bar stay", async () => {
    setViewport(390);
    const { container } = open();
    await screen.findByText("Pranav Sathe");
    expect(container.querySelector("[data-consultation='single']")).toBeTruthy();
    expect(screen.queryByRole("complementary", { name: "Patient information" })).toBeNull();
    expect(screen.getByRole("heading", { name: "Vital signs" })).toBeTruthy();
    await userEvent.click(screen.getByRole("tab", { name: "Patient information" }));
    expect(screen.getByRole("complementary", { name: "Patient information" })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Vital signs" })).toBeNull();
    expect(container.querySelector("[data-patient-banner]")).toBeTruthy();
    expect(container.querySelector("[data-action-bar]")).toBeTruthy();
  });

  it("a signed consultation is locked: no action bar", async () => {
    setViewport(1180);
    getWorkspace.mockResolvedValue(workspace({ consultation: { status: "SIGNED", signed_at: "2026-11-05T06:30:00", complaint: "Cough" } }));
    const { container } = open();
    await screen.findByText("Pranav Sathe");
    expect(container.querySelector("[data-action-bar]")).toBeNull();
  });
});
