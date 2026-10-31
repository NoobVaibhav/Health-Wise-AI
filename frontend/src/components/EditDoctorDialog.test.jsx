import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const updateUser = vi.fn();
vi.mock("../services/adminApi", () => ({ updateUser: (...a) => updateUser(...a) }));
vi.mock("../services/catalogApi", () => ({
  getDepartments: () => Promise.resolve([{ id: 1, name: "Cardiology" }, { id: 2, name: "Neurology" }]),
  getSpecializations: (id) => Promise.resolve(id === 1 ? [{ id: 11, name: "Interventional Cardiologist" }] : [{ id: 21, name: "Neurologist" }]),
}));
import EditDoctorDialog from "./EditDoctorDialog";

beforeEach(() => vi.clearAllMocks());
const person = { id: 7, full_name: "Dr. Anjali Sharma", department_id: 1, specialization_id: 11 };

describe("EditDoctorDialog", () => {
  it("sends the numeric ids of the new choice", async () => {
    updateUser.mockResolvedValue({});
    const onSaved = vi.fn();
    render(<EditDoctorDialog person={person} onClose={() => {}} onSaved={onSaved} />);
    await userEvent.selectOptions(await screen.findByLabelText("Department *"), "2");
    await userEvent.selectOptions(await screen.findByRole("combobox", { name: "Specialization" }), "21");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(updateUser).toHaveBeenCalledWith(7, { department_id: 2, specialization_id: 21 });
    expect(onSaved).toHaveBeenCalled();
  });

  it("shows the server's message and keeps the choice when saving fails", async () => {
    updateUser.mockRejectedValue({ response: { data: { detail: "The selected specialization does not belong to the selected department." } } });
    render(<EditDoctorDialog person={person} onClose={() => {}} onSaved={() => {}} />);
    await userEvent.click(await screen.findByRole("button", { name: "Save" }));
    expect(await screen.findByText(/does not belong to the selected department/)).toBeTruthy();
    expect(screen.getByLabelText("Department *").value).toBe("1");
  });

  it("will not save without a department", async () => {
    render(<EditDoctorDialog person={{ ...person, department_id: null, specialization_id: null }} onClose={() => {}} onSaved={() => {}} />);
    await userEvent.click(await screen.findByRole("button", { name: "Save" }));
    expect(await screen.findByText("Please choose a department.")).toBeTruthy();
    expect(updateUser).not.toHaveBeenCalled();
  });
});
