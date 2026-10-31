import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

const createStaff = vi.fn();
vi.mock("../../services/adminApi", () => ({ createStaff: (...a) => createStaff(...a), listPeople: () => Promise.resolve([]), checkDeleteUser: vi.fn(), deleteUser: vi.fn(), updateUser: vi.fn() }));
vi.mock("../../services/catalogApi", () => ({
  getDepartments: () => Promise.resolve([{ id: 1, name: "Cardiology" }, { id: 2, name: "Neurology" }]),
  getSpecializations: (id) => Promise.resolve(id === 1 ? [{ id: 11, name: "Interventional Cardiologist" }] : [{ id: 21, name: "Neurologist" }]),
}));
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
});
