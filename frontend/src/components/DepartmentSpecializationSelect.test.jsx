import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const getDepartments = vi.fn();
const getSpecializations = vi.fn();
vi.mock("../services/catalogApi", () => ({ getDepartments: (...a) => getDepartments(...a), getSpecializations: (...a) => getSpecializations(...a) }));
import DepartmentSpecializationSelect from "./DepartmentSpecializationSelect";

const DEPARTMENTS = [{ id: 1, name: "Cardiology" }, { id: 2, name: "Neurology" }, { id: 3, name: "Genetics" }];
const SPECS = { 1: [{ id: 11, name: "Interventional Cardiologist" }], 2: [{ id: 21, name: "Neurologist" }, { id: 22, name: "Neurosurgeon" }], 3: [] };

beforeEach(() => {
  vi.clearAllMocks();
  getDepartments.mockResolvedValue(DEPARTMENTS);
  getSpecializations.mockImplementation((id) => Promise.resolve(SPECS[id]));
});

function Harness({ onChange = () => {}, start = {} }) {
  const [v, setV] = useState({ department_id: "", specialization_id: "", ...start });
  return <DepartmentSpecializationSelect departmentRequired departmentId={v.department_id} specializationId={v.specialization_id} onChange={(n) => { setV(n); onChange(n); }} />;
}
const department = () => screen.getByLabelText("Department *");
const specialization = () => screen.getByLabelText("Specialization");

describe("DepartmentSpecializationSelect", () => {
  it("marks the department as required and keeps the specialization disabled until a department is chosen", async () => {
    render(<Harness />);
    await screen.findByRole("option", { name: "Cardiology" });
    expect(department().getAttribute("aria-required")).toBe("true");
    expect(specialization().disabled).toBe(true);
    expect(getSpecializations).not.toHaveBeenCalled();
    expect(screen.getByText("Choose a department first", { selector: "p" })).toBeTruthy();
  });

  it("loads the specializations of the chosen department only", async () => {
    render(<Harness />);
    await userEvent.selectOptions(await screen.findByLabelText("Department *"), "2");
    await screen.findByRole("option", { name: "Neurosurgeon" });
    expect(getSpecializations).toHaveBeenCalledWith(2);
    expect(specialization().disabled).toBe(false);
    expect(screen.queryByRole("option", { name: "Interventional Cardiologist" })).toBeNull();
  });

  it("clears the specialization when the department changes, and reports both ids", async () => {
    const onChange = vi.fn();
    render(<Harness onChange={onChange} />);
    await userEvent.selectOptions(await screen.findByLabelText("Department *"), "2");
    await userEvent.selectOptions(await screen.findByRole("combobox", { name: "Specialization" }), "22");
    expect(onChange).toHaveBeenLastCalledWith({ department_id: "2", specialization_id: "22" });
    await userEvent.selectOptions(department(), "1");
    expect(onChange).toHaveBeenLastCalledWith({ department_id: "1", specialization_id: "" });
    await screen.findByRole("option", { name: "Interventional Cardiologist" });
    expect(specialization().value).toBe("");
  });

  it("says so when a department has no specializations", async () => {
    render(<Harness />);
    await userEvent.selectOptions(await screen.findByLabelText("Department *"), "3");
    expect((await screen.findAllByText("No specializations for this department yet")).length).toBeGreaterThan(0);
  });

  it("keeps the chosen values when loading the specializations fails, and can try again", async () => {
    getSpecializations.mockRejectedValueOnce(new Error("down")).mockResolvedValue(SPECS[2]);
    render(<Harness start={{ department_id: "2", specialization_id: "22" }} />);
    await userEvent.click(await screen.findByRole("button", { name: "Try again" }));
    await screen.findByRole("option", { name: "Neurologist" });
    expect(specialization().value).toBe("22");
  });

  it("shows an error and a retry button when the departments cannot be loaded", async () => {
    getDepartments.mockRejectedValueOnce(new Error("down")).mockResolvedValue(DEPARTMENTS);
    render(<Harness />);
    expect((await screen.findAllByText(/./, { selector: "p.text-red-600" })).length).toBeGreaterThan(0);
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(screen.getByRole("option", { name: "Cardiology" })).toBeTruthy());
  });

  it("shows a message under the field", async () => {
    render(<DepartmentSpecializationSelect departmentId="" specializationId="" onChange={() => {}} departmentRequired departmentError="Please choose a department." />);
    expect(await screen.findByText("Please choose a department.")).toBeTruthy();
    expect(department().getAttribute("aria-invalid")).toBe("true");
  });
});
