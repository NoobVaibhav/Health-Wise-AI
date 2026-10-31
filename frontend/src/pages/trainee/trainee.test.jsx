import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";

const api = {
  startTraineeHistory: vi.fn(), saveTraineeHistory: vi.fn(), completeTraineeHistory: vi.fn(), getDoctorSuggestion: vi.fn(), listDepartmentDoctors: vi.fn(),
  createReferral: vi.fn(), listTraineePatients: vi.fn(), listMyReferrals: vi.fn(),
};
vi.mock("../../services/traineeApi", () => ({
  startTraineeHistory: (...a) => api.startTraineeHistory(...a), saveTraineeHistory: (...a) => api.saveTraineeHistory(...a), completeTraineeHistory: (...a) => api.completeTraineeHistory(...a),
  getDoctorSuggestion: (...a) => api.getDoctorSuggestion(...a), listDepartmentDoctors: (...a) => api.listDepartmentDoctors(...a), createReferral: (...a) => api.createReferral(...a),
  listTraineePatients: (...a) => api.listTraineePatients(...a), listMyReferrals: (...a) => api.listMyReferrals(...a),
}));
vi.mock("../../services/catalogApi", () => ({
  getDepartments: () => Promise.resolve([{ id: 1, name: "General Medicine" }, { id: 2, name: "Cardiology" }]),
  getSpecializations: () => Promise.resolve([]),
}));
import TakeHistory, { completionErrors, vitalError } from "./TakeHistory";
import SelectDoctor from "./SelectDoctor";

const EMPTY_DATA = { symptoms: [], vitals: {} };
const history = (over = {}) => ({ id: 5, status: "DRAFT", data: { ...EMPTY_DATA }, patient: { id: 9, full_name: "Rahul Patil", patient_code: "P-0001", age: 34, gender: "male" }, ...over });

beforeEach(() => {
  vi.clearAllMocks();
  api.startTraineeHistory.mockResolvedValue(history());
  api.saveTraineeHistory.mockResolvedValue({});
});

const openForm = () => render(
  <MemoryRouter initialEntries={["/trainee/take-history/9"]}>
    <Routes><Route path="/trainee/take-history/:patientId" element={<TakeHistory />} /><Route path="/trainee/select-doctor/:historyId" element={<p>SELECT DOCTOR PAGE</p>} /></Routes>
  </MemoryRouter>);

describe("history rules", () => {
  it("needs the complaint, the duration and an explicit allergy answer", () => {
    expect(Object.keys(completionErrors({ chief_complaint: "", duration: "", allergies: "" }))).toEqual(["chief_complaint", "duration", "allergies"]);
    expect(completionErrors({ chief_complaint: "Fever", duration: "2 days", allergies: "NONE" })).toEqual({});
    expect(completionErrors({ chief_complaint: "Fever", duration: "2 days", allergies: "YES", allergy_details: " " }).allergy_details).toMatch(/allergic to/);
  });
  it.each([["pulse", "5", true], ["pulse", "80", false], ["spo2", "130", true], ["temperature_f", "98.6", false], ["temperature_f", "500", true], ["bp_systolic", "abc", true], ["weight_kg", "", false]])("vital %s=%s", (key, value, bad) => {
    expect(!!vitalError(key, value)).toBe(bad);
  });
});

describe("Take history form", () => {
  it("shows what is missing under the fields, sends nothing and keeps what was typed", async () => {
    openForm();
    await userEvent.type(await screen.findByLabelText("Main complaint *"), "Chest pain");
    await userEvent.click(screen.getByRole("button", { name: /Mark complete/ }));
    expect(await screen.findByText("Please write how long it has been going on.")).toBeTruthy();
    expect(screen.getByText("Please choose None or Yes. None is an answer too.")).toBeTruthy();
    expect(api.completeTraineeHistory).not.toHaveBeenCalled();
    expect(screen.getByLabelText("Main complaint *").value).toBe("Chest pain");
  });

  it("None is an allergy answer on its own; Yes asks what the patient is allergic to", async () => {
    openForm();
    await userEvent.click(await screen.findByRole("button", { name: "Yes" }));
    expect(screen.getByLabelText("Allergic to what? *")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "None" }));
    expect(screen.queryByLabelText("Allergic to what? *")).toBeNull();
  });

  it("marks a vital outside the allowed range and does not save the draft", async () => {
    openForm();
    await userEvent.type(await screen.findByLabelText("Pulse (beats a minute)"), "900");
    expect(await screen.findByText("Should be between 20 and 250.")).toBeTruthy();
    expect(await screen.findByText("Fix the marked values to save the draft.")).toBeTruthy();
    await new Promise((r) => setTimeout(r, 1500));
    expect(api.saveTraineeHistory).not.toHaveBeenCalled();
  });

  it("saves the draft by itself, and keeps the typed text and offers Try again when saving fails", async () => {
    api.saveTraineeHistory.mockRejectedValueOnce(new Error("offline")).mockResolvedValue({});
    openForm();
    await userEvent.type(await screen.findByLabelText("Main complaint *"), "Fever");
    expect(await screen.findByText(/Not saved yet/, {}, { timeout: 4000 })).toBeTruthy();
    expect(screen.getByLabelText("Main complaint *").value).toBe("Fever");
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Draft saved")).toBeTruthy();
    expect(api.saveTraineeHistory).toHaveBeenLastCalledWith(5, expect.objectContaining({ chief_complaint: "Fever" }));
  });

  it("completes the history and goes on to choose a doctor", async () => {
    api.completeTraineeHistory.mockResolvedValue({});
    openForm();
    await userEvent.type(await screen.findByLabelText("Main complaint *"), "Fever");
    await userEvent.type(screen.getByLabelText("For how long? *"), "2 days");
    await userEvent.click(screen.getByRole("button", { name: "None" }));
    await userEvent.click(screen.getByRole("button", { name: /Mark complete/ }));
    expect(await screen.findByText("SELECT DOCTOR PAGE")).toBeTruthy();
    expect(api.completeTraineeHistory).toHaveBeenCalledWith(5);
  });

  it("asks the female patient for the menstrual history only", async () => {
    openForm();
    await screen.findByLabelText("Main complaint *");
    expect(screen.queryByLabelText(/Menstrual/)).toBeNull();
  });

  it("shows the server's message when the patient cannot be opened", async () => {
    api.startTraineeHistory.mockRejectedValue({ response: { data: { detail: "You do not have permission to access this information." } } });
    openForm();
    expect(await screen.findByText(/do not have permission/)).toBeTruthy();
  });
});

describe("Select doctor (referral)", () => {
  const suggestion = { department_id: 2, department_name: "Cardiology", specialization: null, reason: "Chest pain: chest or heart symptoms", matched: ["chest pain"],
    doctors: [{ id: 21, full_name: "Dr. Heart", specialization_name: "Interventional Cardiologist", department_name: "Cardiology", today_appointments: 3, waiting_referrals: 1, availability: "Available" }] };
  const openSelect = () => render(
    <MemoryRouter initialEntries={["/trainee/select-doctor/5"]}>
      <Routes><Route path="/trainee/select-doctor/:historyId" element={<SelectDoctor />} /><Route path="/trainee/referrals" element={<p>REFERRALS PAGE</p>} /></Routes>
    </MemoryRouter>);

  it("shows the suggestion with its reason and the doctors with today's load", async () => {
    api.getDoctorSuggestion.mockResolvedValue(suggestion);
    openSelect();
    expect(await screen.findByText("Suggested: Cardiology")).toBeTruthy();
    expect(screen.getAllByText(/Chest pain: chest or heart symptoms/).length).toBeGreaterThan(0);
    expect(screen.getByText(/3 appointments today · 1 referral waiting/)).toBeTruthy();
  });

  it("needs a doctor, then sends the referral with the urgent flag and the suggested department", async () => {
    api.getDoctorSuggestion.mockResolvedValue(suggestion);
    api.createReferral.mockResolvedValue({});
    openSelect();
    await screen.findByText("Suggested: Cardiology");
    await userEvent.click(screen.getByRole("button", { name: /Confirm and send/ }));
    expect(await screen.findByText("Please choose a doctor.")).toBeTruthy();
    expect(api.createReferral).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: /Dr\. Heart/ }));
    await userEvent.click(screen.getByLabelText(/Urgent/));
    await userEvent.click(screen.getByRole("button", { name: /Confirm and send/ }));
    await waitFor(() => expect(api.createReferral).toHaveBeenCalledWith(expect.objectContaining({ history_id: 5, doctor_id: 21, urgent: true, suggested_department_id: 2 })));
    expect(await screen.findByText("REFERRALS PAGE")).toBeTruthy();
  });

  it("lets the trainee choose another department and lists its doctors", async () => {
    api.getDoctorSuggestion.mockResolvedValue(suggestion);
    api.listDepartmentDoctors.mockResolvedValue([{ id: 31, full_name: "Dr. General", specialization_name: "General Physician", department_name: "General Medicine", today_appointments: 0, waiting_referrals: 0, availability: "Available" }]);
    openSelect();
    await userEvent.click(await screen.findByLabelText(/Choose a different department myself/));
    await userEvent.selectOptions(await screen.findByLabelText("Department *"), "1");
    expect(await screen.findByRole("button", { name: /Dr\. General/ })).toBeTruthy();
    expect(api.listDepartmentDoctors).toHaveBeenCalledWith(1);
    expect(screen.queryByRole("button", { name: /Dr\. Heart/ })).toBeNull();
  });

  it("keeps the choice and shows the message when the server refuses", async () => {
    api.getDoctorSuggestion.mockResolvedValue(suggestion);
    api.createReferral.mockRejectedValue({ response: { data: { detail: "This history has already been sent to a doctor." } } });
    openSelect();
    await userEvent.click(await screen.findByRole("button", { name: /Dr\. Heart/ }));
    await userEvent.click(screen.getByRole("button", { name: /Confirm and send/ }));
    expect(await screen.findByText(/already been sent/)).toBeTruthy();
    expect(screen.getByRole("button", { name: /Dr\. Heart/ }).getAttribute("aria-pressed")).toBe("true");
  });
});
