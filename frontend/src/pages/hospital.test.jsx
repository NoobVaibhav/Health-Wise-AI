import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

const registerPatient = vi.fn();
vi.mock("../services/patientApi", () => ({ registerPatient: (...a) => registerPatient(...a), listPatients: vi.fn(() => Promise.resolve([])) }));
vi.mock("../services/doctorApi", () => ({ listDoctors: vi.fn(() => Promise.resolve([])) }));
const hosp = { getRegistry: vi.fn(), addConsent: vi.fn(), withdrawConsent: vi.fn(), saveAbha: vi.fn(), addInsurance: vi.fn(), deactivateInsurance: vi.fn(), mergePatients: vi.fn(), lookupForBreakGlass: vi.fn(), openBreakGlass: vi.fn() };
vi.mock("../services/hospitalApi", () => ({
  getRegistry: (...a) => hosp.getRegistry(...a), addConsent: (...a) => hosp.addConsent(...a), withdrawConsent: (...a) => hosp.withdrawConsent(...a), saveAbha: (...a) => hosp.saveAbha(...a),
  addInsurance: (...a) => hosp.addInsurance(...a), deactivateInsurance: (...a) => hosp.deactivateInsurance(...a), mergePatients: (...a) => hosp.mergePatients(...a),
  lookupForBreakGlass: (...a) => hosp.lookupForBreakGlass(...a), openBreakGlass: (...a) => hosp.openBreakGlass(...a),
}));
const auth = { user: { id: 1, role: "EMPLOYEE", full_name: "Priya" } };
vi.mock("../context/AuthContext", () => ({ useAuth: () => auth }));
vi.mock("../components/Toast", () => ({ useToast: () => vi.fn() }));
import RegisterPatient from "./employee/RegisterPatient";
import PatientRegistryPanel from "../components/PatientRegistryPanel";
import EmergencyAccess from "./doctor/EmergencyAccess";

beforeEach(() => { vi.clearAllMocks(); auth.user.role = "EMPLOYEE"; });

describe("Register patient: possible duplicate", () => {
  const fill = async () => {
    render(<MemoryRouter><RegisterPatient /></MemoryRouter>);
    await userEvent.type(screen.getByLabelText("Full name *"), "Sunita Kale");
    await userEvent.type(screen.getByLabelText("Email (used to log in) *"), "sunita@example.com");
    await userEvent.type(screen.getByLabelText("Phone"), "9811111111");
  };
  const duplicate = { response: { status: 409, data: { detail: "A patient with the same name and date of birth is already registered.", duplicates: [{ id: 5, uhid: "HW-26-000005", patient_code: "P-0005", full_name: "Sunita Kale", date_of_birth: "1985-04-04", phone: "9811111111", reasons: ["same name and date of birth"], strong: true }] } } };

  it("shows the existing patient, keeps the typed details, and registers only after the confirmation", async () => {
    registerPatient.mockRejectedValueOnce(duplicate).mockResolvedValue({ patient: { full_name: "Sunita Kale", uhid: "HW-26-000006", patient_code: "P-0006", email: "sunita@example.com" }, temporary_password: "x" });
    await fill();
    await userEvent.click(screen.getByRole("button", { name: "Register patient" }));
    expect(await screen.findByText("This person may already be registered")).toBeTruthy();
    expect(screen.getByText(/HW-26-000005/)).toBeTruthy();
    expect(screen.getByLabelText("Full name *").value).toBe("Sunita Kale");
    expect(registerPatient.mock.calls[0][0].allow_duplicate).toBeUndefined();
    await userEvent.click(screen.getByRole("button", { name: /register anyway/ }));
    await waitFor(() => expect(registerPatient).toHaveBeenCalledTimes(2));
    expect(registerPatient.mock.calls[1][0].allow_duplicate).toBe(true);
    expect((await screen.findAllByText(/HW-26-000006/)).length).toBeGreaterThan(0);                               // the UHID is what reception hands over
  });
});

describe("Patient registry panel", () => {
  const registry = (over = {}) => ({ id: 7, uhid: "HW-26-000007", patient_code: "P-0007", full_name: "Rahul Patil", abha_id: null, merged_into_id: null, consents: [], insurance: [], ...over });

  it("keeps the ABHA box locked until the ABHA consent is recorded", async () => {
    hosp.getRegistry.mockResolvedValue(registry());
    render(<PatientRegistryPanel patient={{ id: 7, full_name: "Rahul Patil" }} onClose={() => {}} />);
    expect(await screen.findByText("HW-26-000007")).toBeTruthy();
    expect(screen.getByLabelText("14-digit ABHA number").disabled).toBe(true);
    expect(screen.getByText(/Nothing is sent to any ABDM service/)).toBeTruthy();
  });

  it("with the consent the number can be saved; the server message is shown when it refuses", async () => {
    hosp.getRegistry.mockResolvedValue(registry({ consents: [{ id: 1, kind: "ABHA", given_by: "Rahul Patil", granted_at: "2026-10-31T10:00:00", active: true }] }));
    hosp.saveAbha.mockRejectedValueOnce({ response: { data: { detail: "An ABHA number has 14 digits, for example 12-3456-7890-1234." } } }).mockResolvedValue({ abha_id: "12-3456-7890-1234" });
    render(<PatientRegistryPanel patient={{ id: 7, full_name: "Rahul Patil" }} onClose={() => {}} />);
    await userEvent.type(await screen.findByLabelText("14-digit ABHA number"), "123");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText(/has 14 digits/)).toBeTruthy();
    expect(screen.getByLabelText("14-digit ABHA number").value).toBe("123");                    // what was typed stays
    await userEvent.clear(screen.getByLabelText("14-digit ABHA number"));
    await userEvent.type(screen.getByLabelText("14-digit ABHA number"), "12345678901234");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() => expect(hosp.saveAbha).toHaveBeenLastCalledWith(7, "12345678901234"));
  });

  it("only the administrator sees the merge block, and it needs a written reason", async () => {
    hosp.getRegistry.mockResolvedValue(registry());
    const { unmount } = render(<PatientRegistryPanel patient={{ id: 7, full_name: "Rahul Patil" }} onClose={() => {}} />);
    await screen.findByText("HW-26-000007");
    expect(screen.queryByText(/Merge a duplicate record/)).toBeNull();
    unmount();
    auth.user.role = "ADMIN";
    render(<PatientRegistryPanel patient={{ id: 7, full_name: "Rahul Patil" }} onClose={() => {}} />);
    expect(await screen.findByText(/Merge a duplicate record/)).toBeTruthy();
  });
});

describe("Emergency access", () => {
  it("finds by the exact UHID, needs a reason of 10 characters, then opens the record link", async () => {
    hosp.lookupForBreakGlass.mockResolvedValue({ id: 9, uhid: "HW-26-000009", full_name: "Glass Patient", age: 40, gender: "male" });
    hosp.openBreakGlass.mockResolvedValue({ patient_id: 9, patient_name: "Glass Patient", expires_at: "2026-10-31T11:00:00" });
    render(<MemoryRouter><EmergencyAccess /></MemoryRouter>);
    await userEvent.type(screen.getByLabelText("Exact UHID of the patient"), "HW-26-000009");
    await userEvent.click(screen.getByRole("button", { name: "Find" }));
    const open = await screen.findByRole("button", { name: "Open this record" });
    expect(open.disabled).toBe(true);
    await userEvent.type(screen.getByLabelText(/Why do you need this record now/), "Unconscious patient in casualty");
    expect(open.disabled).toBe(false);
    await userEvent.click(open);
    expect(await screen.findByRole("link", { name: "Open the record" })).toBeTruthy();
    expect(hosp.openBreakGlass).toHaveBeenCalledWith(9, "Unconscious patient in casualty");
  });

  it("shows the server message when the UHID does not exist", async () => {
    hosp.lookupForBreakGlass.mockRejectedValue({ response: { data: { detail: "No patient with this UHID." } } });
    render(<MemoryRouter><EmergencyAccess /></MemoryRouter>);
    await userEvent.type(screen.getByLabelText("Exact UHID of the patient"), "NOPE-00");
    await userEvent.click(screen.getByRole("button", { name: "Find" }));
    expect(await screen.findByText("No patient with this UHID.")).toBeTruthy();
  });
});
