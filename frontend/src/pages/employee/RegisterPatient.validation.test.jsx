import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

const registerPatient = vi.fn();
vi.mock("../../services/patientApi", () => ({ registerPatient: (...a) => registerPatient(...a) }));
vi.mock("../../services/doctorApi", () => ({ listDoctors: vi.fn(() => Promise.resolve([{ id: 3, full_name: "Dr. Anjali Sharma" }])) }));
import RegisterPatient from "./RegisterPatient";
import { todayISO } from "../../utils/validators";

beforeEach(() => { vi.clearAllMocks(); });
const open = () => render(<MemoryRouter><RegisterPatient /></MemoryRouter>);
const type = (label, text) => userEvent.type(screen.getByLabelText(label), text);

describe("RegisterPatient form", () => {
  it("shows what is wrong under each field, focuses the first one and sends nothing", async () => {
    open();
    await type("Full name *", "Rahul7");
    await type("Email (used to log in) *", "rahul-at-example");
    await type("Phone", "12345");
    await userEvent.click(screen.getByRole("button", { name: "Register patient" }));
    expect(screen.getByText(/only letters, spaces/)).toBeTruthy();
    expect(screen.getByText(/valid e-mail address/)).toBeTruthy();
    expect(screen.getByText(/10-digit mobile number/)).toBeTruthy();
    expect(registerPatient).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(screen.getByLabelText("Full name *"));
    expect(screen.getByLabelText("Phone").getAttribute("aria-invalid")).toBe("true");
    expect(screen.getByLabelText("Full name *").value).toBe("Rahul7");                      // what was typed stays
  });

  it("the date of birth cannot be picked in the future, and unusual ages only give a warning", async () => {
    open();
    const dob = screen.getByLabelText("Date of birth");
    expect(dob.getAttribute("max")).toBe(todayISO());
    expect(dob.getAttribute("min")).toBe("1930-01-01");
    await userEvent.type(dob, "2999-01-01");
    await userEvent.tab();
    expect(await screen.findByText("The date of birth cannot be in the future.")).toBeTruthy();
    await userEvent.clear(dob);
    await userEvent.type(dob, todayISO());
    await userEvent.tab();
    expect(await screen.findByText(/under 1 year old/)).toBeTruthy();
    expect(screen.queryByText("The date of birth cannot be in the future.")).toBeNull();
  });

  it("the emergency contact cannot be the patient's own number", async () => {
    open();
    await type("Phone", "98765 43210");
    await type("Emergency contact", "Mother 9876543210");
    await userEvent.tab();
    expect(await screen.findByText(/different person/)).toBeTruthy();
  });

  it("counts the characters of long text and limits them", async () => {
    open();
    await type("Address", "12 MG Road");
    expect(screen.getByText("10/300")).toBeTruthy();
    expect(screen.getByLabelText("Address").getAttribute("maxlength")).toBe("300");
    expect(screen.getByLabelText("Phone").getAttribute("type")).toBe("tel");
    expect(screen.getByLabelText("Phone").getAttribute("inputmode")).toBe("tel");
  });

  it("sends clean values when everything is right and does not send twice", async () => {
    let finish;
    registerPatient.mockImplementation(() => new Promise((resolve) => { finish = () => resolve({ patient: { full_name: "Rahul Patil", patient_code: "P-0009", email: "rahul@example.com" }, temporary_password: "x" }); }));
    open();
    await type("Full name *", "  Rahul   Patil ");
    await type("Email (used to log in) *", " Rahul@Example.com ");
    await type("Phone", "+91 98765 43210");
    await userEvent.selectOptions(screen.getByLabelText("Blood group"), "O+");
    await userEvent.click(screen.getByRole("button", { name: "Register patient" }));
    const sent = registerPatient.mock.calls[0][0];
    expect(sent).toMatchObject({ full_name: "Rahul   Patil", email: "rahul@example.com", phone: "+91 98765 43210", blood_group: "O+", date_of_birth: null, address: null });
    await userEvent.click(screen.getByRole("button", { name: "Registering..." }));
    expect(registerPatient).toHaveBeenCalledTimes(1);
    finish();
  });

  it("shows the server's message under the right field", async () => {
    registerPatient.mockRejectedValue({ response: { status: 422, data: { detail: "Phone: Bad.", errors: [{ field: "phone", label: "Phone", message: "The server did not like this phone number." }] } } });
    open();
    await type("Full name *", "Rahul Patil");
    await type("Email (used to log in) *", "rahul@example.com");
    await userEvent.click(screen.getByRole("button", { name: "Register patient" }));
    expect(await screen.findByText("The server did not like this phone number.")).toBeTruthy();
    expect(screen.getByLabelText("Full name *").value).toBe("Rahul Patil");
  });
});
