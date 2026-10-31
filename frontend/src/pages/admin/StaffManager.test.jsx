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
vi.mock("../../services/doctorApi", () => ({ listDoctors: () => Promise.resolve([{ id: 7, full_name: "Dr. Heart", department_id: 1 }, { id: 8, full_name: "Dr. Brain", department_id: 2 }]) }));
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

  it("trainee form: no Specialization, a type, year and branch only for a PG student, and supervisors of the chosen department", async () => {
    createStaff.mockResolvedValue({ user: { full_name: "Neha", email: "neha@hospital.example.com" }, temporary_password: "x" });
    render(<MemoryRouter><StaffManager kind="trainees" /></MemoryRouter>);
    await userEvent.click(screen.getByRole("button", { name: /Add trainee/ }));
    await userEvent.type(screen.getByLabelText("Full name *"), "Neha Kulkarni");
    await userEvent.type(screen.getByLabelText("Email (used to log in) *"), "neha@hospital.example.com");
    expect(screen.queryByLabelText("Specialization")).toBeNull();
    expect(screen.queryByLabelText("Year and branch *")).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText("Please choose Intern or PG student.")).toBeTruthy();
    expect(screen.getByText("Please choose a department.")).toBeTruthy();
    expect(createStaff).not.toHaveBeenCalled();
    await userEvent.selectOptions(screen.getByLabelText("Type *"), "PG_STUDENT");
    expect(screen.getByLabelText("Year and branch *")).toBeTruthy();
    await userEvent.selectOptions(screen.getByLabelText("Department *"), "1");
    const supervisor = screen.getByLabelText("Supervising doctor");
    await waitFor(() => expect([...supervisor.options].map((o) => o.text)).toEqual(["None", "Dr. Heart"]));   // only the doctors of the department
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(await screen.findByText(/Please enter the year and branch/)).toBeTruthy();
    await userEvent.type(screen.getByLabelText("Year and branch *"), "MD Medicine, Year 2");
    await userEvent.selectOptions(supervisor, "7");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    const [kind, payload] = createStaff.mock.calls[0];
    expect(kind).toBe("trainees");
    expect(payload).toMatchObject({ trainee_type: "PG_STUDENT", year_branch: "MD Medicine, Year 2", department_id: 1, supervisor_id: 7 });
  });

  it("an intern needs no year and branch and it is not sent", async () => {
    createStaff.mockResolvedValue({ user: { full_name: "Neha", email: "neha@hospital.example.com" }, temporary_password: "x" });
    render(<MemoryRouter><StaffManager kind="trainees" /></MemoryRouter>);
    await userEvent.click(screen.getByRole("button", { name: /Add trainee/ }));
    await userEvent.type(screen.getByLabelText("Full name *"), "Neha Kulkarni");
    await userEvent.type(screen.getByLabelText("Email (used to log in) *"), "neha@hospital.example.com");
    await userEvent.selectOptions(screen.getByLabelText("Type *"), "INTERN");
    expect(screen.queryByLabelText("Year and branch *")).toBeNull();
    await userEvent.selectOptions(screen.getByLabelText("Department *"), "2");
    await userEvent.click(screen.getByRole("button", { name: "Create account" }));
    expect(createStaff.mock.calls[0][1]).toMatchObject({ trainee_type: "INTERN", year_branch: null, supervisor_id: null, department_id: 2 });
  });

  it("the doctor form is unchanged: department and specialization, no trainee fields", async () => {
    render(<MemoryRouter><StaffManager kind="doctors" /></MemoryRouter>);
    await userEvent.click(screen.getByRole("button", { name: /Add doctor/ }));
    expect(screen.getByLabelText("Specialization")).toBeTruthy();
    expect(screen.queryByLabelText("Type *")).toBeNull();
  });
});
