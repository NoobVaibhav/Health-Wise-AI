import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

const createStaff = vi.fn();
vi.mock("../../services/adminApi", () => ({ createStaff: (...a) => createStaff(...a), listPeople: () => Promise.resolve([]), checkDeleteUser: vi.fn(), deleteUser: vi.fn(), updateUser: vi.fn() }));
vi.mock("../../services/catalogApi", () => ({
  getDepartments: () => Promise.resolve([{ id: 1, name: "Cardiology" }, { id: 2, name: "Neurology" }]),
  getSpecializations: (id) => Promise.resolve(id === 1 ? [{ id: 11, name: "Interventional Cardiologist" }] : [{ id: 21, name: "Neurologist" }]),
}));
vi.mock("../../services/doctorApi", () => ({ listDoctors: () => Promise.resolve([{ id: 7, full_name: "Dr. Heart", department_id: 1, grade: "CONSULTANT" }, { id: 8, full_name: "Dr. Brain", department_id: 2, grade: "CONSULTANT" }, { id: 9, full_name: "Dr. Junior", department_id: 1, grade: "PG_RESIDENT" }]) }));
vi.mock("../../context/AuthContext", () => ({ useAuth: () => ({ user: { id: 1, role: "ADMIN" } }) }));
vi.mock("../../components/Toast", () => ({ useToast: () => vi.fn() }));
import StaffManager from "./StaffManager";

beforeEach(() => vi.clearAllMocks());

async function openForm() {
  render(<MemoryRouter><StaffManager kind="doctors" /></MemoryRouter>);
  await userEvent.click(screen.getByRole("button", { name: /Add doctor/ }));
  await userEvent.type(screen.getByLabelText("Full name *"), "Anita Rao");
  await userEvent.type(screen.getByLabelText("Email (used to log in) *"), "anita.rao@hospital.example.com");
}

describe("Add doctor form", () => {
  it("needs a department, and posts the department and specialization ids", async () => {
    createStaff.mockResolvedValue({ user: { full_name: "Anita Rao", email: "anita.rao@hospital.example.com" }, temporary_password: "x" });
    await openForm();
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("Please choose a department.")).toBeTruthy();
    expect(createStaff).not.toHaveBeenCalled();
    await userEvent.selectOptions(screen.getByLabelText("Department *"), "1");
    await userEvent.selectOptions(await screen.findByRole("combobox", { name: "Specialization" }), "11");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    const [kind, payload] = createStaff.mock.calls[0];
    expect(kind).toBe("doctors");
    expect(payload).toMatchObject({ department_id: 1, specialization_id: 11, full_name: "Anita Rao" });
    expect(payload.specialization).toBeUndefined();
  });

  it("does not show the department boxes for other staff", async () => {
    render(<MemoryRouter><StaffManager kind="employees" /></MemoryRouter>);
    await userEvent.click(screen.getByRole("button", { name: /Add employee/ }));
    expect(screen.queryByLabelText("Department *")).toBeNull();
  });

  it("the grade changes the form: a consultant keeps it as it was, an intern has no specialization, a PG resident has year and branch, juniors need a supervising consultant of the department", async () => {
    createStaff.mockResolvedValue({ user: { full_name: "Neha", email: "neha@hospital.example.com" }, temporary_password: "x" });
    await openForm();
    expect(screen.getByLabelText("Doctor grade").value).toBe("CONSULTANT");
    expect(screen.getByLabelText("Specialization")).toBeTruthy();
    expect(screen.queryByLabelText("Supervising consultant *")).toBeNull();
    await userEvent.selectOptions(screen.getByLabelText("Doctor grade"), "INTERN");
    expect(screen.queryByLabelText("Specialization")).toBeNull();
    expect(screen.getByLabelText("Supervising consultant *")).toBeTruthy();
    expect(screen.queryByLabelText("PG year *")).toBeNull();
    await userEvent.selectOptions(screen.getByLabelText("Doctor grade"), "PG_RESIDENT");
    expect(screen.getByLabelText("PG year *")).toBeTruthy();
    expect(screen.getByLabelText("PG branch *")).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("Please choose a department.")).toBeTruthy();
    expect(screen.getByText("Please choose the PG year.")).toBeTruthy();
    expect(screen.getByText(/Please enter the PG branch/)).toBeTruthy();
    expect(screen.getByText("Please choose the supervising consultant.")).toBeTruthy();
    expect(createStaff).not.toHaveBeenCalled();
    await userEvent.selectOptions(screen.getByLabelText("Department *"), "1");
    const supervisor = screen.getByLabelText("Supervising consultant *");
    await waitFor(() => expect([...supervisor.options].map((o) => o.text)).toEqual(["Choose a consultant", "Dr. Heart"]));      // only consultants of the department, not Dr. Junior
    await userEvent.selectOptions(screen.getByLabelText("PG year *"), "2");
    await userEvent.type(screen.getByLabelText("PG branch *"), "MD Medicine");
    await userEvent.selectOptions(supervisor, "7");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    const [kind, payload] = createStaff.mock.calls[0];
    expect(kind).toBe("doctors");
    expect(payload).toMatchObject({ grade: "PG_RESIDENT", pg_year: 2, pg_branch: "MD Medicine", department_id: 1, supervisor_id: 7 });
  });

  it("an intern is sent without a specialization or PG fields", async () => {
    createStaff.mockResolvedValue({ user: { full_name: "Neha", email: "neha@hospital.example.com" }, temporary_password: "x" });
    await openForm();
    await userEvent.selectOptions(screen.getByLabelText("Doctor grade"), "INTERN");
    await userEvent.selectOptions(screen.getByLabelText("Department *"), "2");
    await userEvent.selectOptions(screen.getByLabelText("Supervising consultant *"), "8");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(createStaff.mock.calls[0][1]).toMatchObject({ grade: "INTERN", department_id: 2, supervisor_id: 8, specialization_id: null, pg_year: null });
  });

  it("the other staff forms are unchanged and have no grade", async () => {
    render(<MemoryRouter><StaffManager kind="employees" /></MemoryRouter>);
    await userEvent.click(screen.getByRole("button", { name: /Add employee/ }));
    expect(screen.queryByLabelText("Doctor grade")).toBeNull();
  });
});
