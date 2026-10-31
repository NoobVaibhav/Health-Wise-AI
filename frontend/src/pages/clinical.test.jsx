import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

const api = vi.hoisted(() => ({
  getWorkspace: vi.fn(), saveConsultation: vi.fn(), signConsultation: vi.fn(), addVitals: vi.fn(), listWards: vi.fn(), moveBed: vi.fn(), setBedStatus: vi.fn(),
  getChart: vi.fn(), actOnDose: vi.fn(), ackAlert: vi.fn(), opdQueue: vi.fn(), checkIn: vi.fn(), walkIn: vi.fn(), closeToken: vi.fn(), edBoard: vi.fn(), edRegister: vi.fn(),
  callNext: vi.fn(), callToken: vi.fn(), nurseDashboard: vi.fn(),
}));
vi.mock("../services/careApi", () => Object.fromEntries(Object.keys(api).map((k) => [k, (...a) => api[k](...a)])));
vi.mock("../services/appointmentApi", () => ({ listAppointments: vi.fn(() => Promise.resolve([{ id: 4, patient_name: "Rahul Patil", patient_code: "P-0001", doctor_name: "Dr. Anjali Sharma", scheduled_at: "2026-11-01T10:00:00", status: "SCHEDULED", encounter_id: null }])) }));
vi.mock("../services/doctorApi", () => ({ listDoctors: vi.fn(() => Promise.resolve([{ id: 3, full_name: "Dr. Anjali Sharma", department_name: "General Medicine", department_id: 1 }])) }));
vi.mock("../services/patientApi", () => ({ listPatients: vi.fn(() => Promise.resolve([])) }));
vi.mock("../components/Toast", () => ({ useToast: () => vi.fn() }));
vi.mock("../components/DoctorForms", () => ({ PrescriptionModal: () => null }));
vi.mock("../context/AuthContext", () => ({ useAuth: () => ({ user: { id: 1, role: "DOCTOR", full_name: "Dr. Anjali Sharma" } }) }));
import Consultation from "./doctor/Consultation";
import BedBoard from "../components/BedBoard";
import { NurseChart } from "./nurse/Nurse";
import OpdDesk from "./employee/OpdDesk";
import OpdQueue from "./doctor/OpdQueue";

beforeEach(() => { vi.clearAllMocks(); });

const workspace = (over = {}) => ({
  encounter: { id: 5, type: "OPD", status: "OPEN", department_name: "General Medicine" }, patient: { id: 9, full_name: "Rahul Patil", uhid: "HW-26-000001", age: 34, gender: "male", allergies: "Penicillin" },
  consultation: null, template: { id: 1, name: "Default consultation", fields: [{ key: "general_exam", label: "General examination", kind: "longtext", options: [] }] }, diagnoses: [], orders: [], vitals: [],
  previous_consultations: [], prescriptions: [], charges: [], addenda: [], ...over,
});
const openConsultation = () => render(<MemoryRouter initialEntries={["/doctor/consultation/5"]}><Routes><Route path="/doctor/consultation/:encounterId" element={<Consultation />} /></Routes></MemoryRouter>);

describe("Consultation", () => {
  it("shows the allergy in red, the template fields, and saves the draft by itself", async () => {
    api.getWorkspace.mockResolvedValue(workspace());
    api.saveConsultation.mockResolvedValue({});
    openConsultation();
    expect(await screen.findByText("Allergies: Penicillin")).toBeTruthy();
    expect(screen.getByLabelText("General examination")).toBeTruthy();
    await userEvent.type(screen.getByLabelText("Complaint *"), "Fever");
    expect(await screen.findByText("Draft saved", {}, { timeout: 4000 })).toBeTruthy();
    expect(api.saveConsultation).toHaveBeenLastCalledWith(5, expect.objectContaining({ complaint: "Fever", template_id: 1 }));
  });

  it("keeps what was typed and offers Try again when saving fails", async () => {
    api.getWorkspace.mockResolvedValue(workspace());
    api.saveConsultation.mockRejectedValueOnce(new Error("offline")).mockResolvedValue({});
    openConsultation();
    await userEvent.type(await screen.findByLabelText("Complaint *"), "Cough");
    expect(await screen.findByText(/Not saved/, {}, { timeout: 4000 })).toBeTruthy();
    expect(screen.getByLabelText("Complaint *").value).toBe("Cough");
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Draft saved")).toBeTruthy();
  });

  it("shows the server's sentence when signing is refused and leaves the draft as it is", async () => {
    api.getWorkspace.mockResolvedValue(workspace());
    api.saveConsultation.mockResolvedValue({});
    api.signConsultation.mockRejectedValue({ response: { data: { detail: "Before signing, please write a diagnosis or an assessment." } } });
    openConsultation();
    await userEvent.type(await screen.findByLabelText("Complaint *"), "Fever");
    await userEvent.click(screen.getByRole("button", { name: "Review and sign" }));
    expect(await screen.findByText(/please write a diagnosis or an assessment/)).toBeTruthy();
    expect(screen.getByLabelText("Complaint *").value).toBe("Fever");
  });

  it("a signed consultation is locked, and says it can only get addenda", async () => {
    api.getWorkspace.mockResolvedValue(workspace({ consultation: { id: 2, status: "SIGNED", complaint: "Fever", signed_at: "2026-10-31T10:00:00", data: {}, doctor_name: "Dr. Anjali Sharma" }, encounter: { id: 5, type: "OPD", status: "CLOSED" } }));
    openConsultation();
    await screen.findByText(/It can no longer be changed/);
    expect(screen.getByLabelText("Complaint *").disabled).toBe(true);
    expect(screen.queryByRole("button", { name: "Review and sign" })).toBeNull();
    expect(screen.getByLabelText("Addendum")).toBeTruthy();
  });
});

describe("Bed board", () => {
  const wards = [{ id: 1, name: "General Ward", ward_type: "GENERAL", counts: { AVAILABLE: 1, OCCUPIED: 1, RESERVED: 0, CLEANING: 0, MAINTENANCE: 0 },
    beds: [{ id: 11, code: "G1", status: "OCCUPIED", patient: { admission_id: 7, admission_no: "ADM-HW-26-000001", full_name: "Rahul Patil", uhid: "HW-26-000001" } }, { id: 12, code: "G2", status: "AVAILABLE" }] }];

  it("shows the counts and moves a patient; a bed taken a moment ago shows the server's message and nothing is lost", async () => {
    api.listWards.mockResolvedValue(wards);
    api.moveBed.mockRejectedValueOnce({ response: { data: { detail: "This bed was taken a moment ago. Please choose another bed." } } }).mockResolvedValue({});
    render(<MemoryRouter><BedBoard /></MemoryRouter>);
    expect(await screen.findByText("Free: 1")).toBeTruthy();
    expect(screen.getByText("Occupied: 1")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: /Bed G1.*Occupied.*Rahul Patil/ }));
    await userEvent.selectOptions(await screen.findByLabelText("Move to a free bed"), "12");
    await userEvent.click(screen.getByRole("button", { name: "Move patient" }));
    expect(await screen.findByText(/taken a moment ago/)).toBeTruthy();
    expect(screen.getByLabelText("Move to a free bed").value).toBe("12");
    await userEvent.click(screen.getByRole("button", { name: "Move patient" }));
    await waitFor(() => expect(api.moveBed).toHaveBeenLastCalledWith(7, 12, ""));
  });

  it("a free bed can be sent to cleaning", async () => {
    api.listWards.mockResolvedValue(wards);
    api.setBedStatus.mockResolvedValue({});
    render(<MemoryRouter><BedBoard /></MemoryRouter>);
    await userEvent.click(await screen.findByRole("button", { name: /Bed G2.*Free/ }));
    await userEvent.click(screen.getByRole("button", { name: "Send to cleaning" }));
    await waitFor(() => expect(api.setBedStatus).toHaveBeenCalledWith(12, "CLEANING"));
  });
});

describe("Nurse chart", () => {
  const chart = {
    admission: { id: 7, status: "ADMITTED", admission_no: "ADM-1", admitting_diagnosis: "Pneumonia", patient: { full_name: "Rahul Patil", uhid: "HW-26-000001" }, bed: { ward: "General Ward", code: "G1" } },
    alerts: [{ id: 1, level: "CRITICAL", message: "Oxygen level below 90 % (measured 85)", patient_name: "Rahul Patil", uhid: "HW-26-000001" }],
    mar: [{ id: 3, medicine_name: "Inj. Ceftriaxone", dose: "1 g", route: "IV", scheduled_at: "2026-10-31T08:00:00", status: "PENDING", overdue: true }], pending_doses: 1, overdue_doses: 1,
    vitals: [], notes: [], care_plan: null, handover: null, totals: { intake: 0, output: 0, balance: 0 }, intake_output: [],
  };
  const open = () => render(<MemoryRouter initialEntries={["/nurse/chart/7"]}><Routes><Route path="/nurse/chart/:id" element={<NurseChart />} /></Routes></MemoryRouter>);

  it("shows the critical alert and the overdue dose, and records a dose as given", async () => {
    api.getChart.mockResolvedValue(chart);
    api.actOnDose.mockResolvedValue({});
    open();
    expect(await screen.findByText(/Oxygen level below 90/)).toBeTruthy();
    expect(screen.getByText("Overdue")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Given" }));
    await waitFor(() => expect(api.actOnDose).toHaveBeenCalledWith(3, "GIVEN"));
  });

  it("a refused dose needs a reason before it can be saved", async () => {
    api.getChart.mockResolvedValue(chart);
    api.actOnDose.mockResolvedValue({});
    open();
    await userEvent.click(await screen.findByRole("button", { name: "Refused" }));
    const save = screen.getAllByRole("button", { name: "Save" })[0];                    // the one under the medicines comes first
    expect(save.disabled).toBe(true);
    await userEvent.type(screen.getByLabelText(/Why was it refused/), "Patient vomiting");
    await userEvent.click(save);
    await waitFor(() => expect(api.actOnDose).toHaveBeenCalledWith(3, "REFUSED", "Patient vomiting"));
  });
});

describe("OPD", () => {
  it("reception checks in a booked patient", async () => {
    api.opdQueue.mockResolvedValue([]);
    api.checkIn.mockResolvedValue({});
    render(<MemoryRouter><OpdDesk /></MemoryRouter>);
    expect(await screen.findByText("Rahul Patil")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Check in" }));
    await waitFor(() => expect(api.checkIn).toHaveBeenCalledWith(4));
  });

  it("the doctor sees the waiting patients with their time, and urgent ones are marked", async () => {
    api.opdQueue.mockResolvedValue([{ id: 1, number: 2, status: "WAITING", urgent: true, waiting_minutes: 12, encounter_id: 5, source: "TRAINEE_REFERRAL", patient: { full_name: "Urgent Person", uhid: "HW-26-000002", age: 50, gender: "male" } }]);
    render(<MemoryRouter><OpdQueue /></MemoryRouter>);
    expect(await screen.findByText("Urgent Person")).toBeTruthy();
    expect(screen.getByText("Urgent")).toBeTruthy();
    expect(screen.getByText("From a trainee")).toBeTruthy();
    expect(screen.getByText("12 min")).toBeTruthy();
  });

  it("the call-next button is off when nobody waits", async () => {
    api.opdQueue.mockResolvedValue([]);
    render(<MemoryRouter><OpdQueue /></MemoryRouter>);
    await screen.findByText("Nobody in your queue yet");
    expect(screen.getByRole("button", { name: "Call the next patient" }).disabled).toBe(true);
  });
});
