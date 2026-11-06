import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

let release;
vi.mock("../../services/appointmentApi", () => ({
  listAppointments: vi.fn(() => Promise.resolve([])),
  updateAppointment: vi.fn(),
  createAppointment: vi.fn(),
  listSlots: vi.fn(),
}));
vi.mock("../../services/doctorApi", () => ({ listDoctors: vi.fn(() => Promise.resolve([{ id: 7, full_name: "Dr. Anjali Sharma", department_id: 1, department_name: "General Medicine", specialization_name: "Physician" }])) }));
vi.mock("../../services/patientApi", () => ({ listPatients: vi.fn(() => Promise.resolve([])) }));
import { createAppointment, listSlots } from "../../services/appointmentApi";
import { NewAppointment } from "./Appointments";

const SLOTS = [
  { time: "09:00", at: "x", available: false, reason: "unavailable" },
  { time: "09:15", at: "x", available: false, reason: "taken" },
  { time: "09:30", at: "x", available: true, reason: null },
];

// 19:00 UTC on 5 November is already 00:30 on 6 November in India: the date box must start on the 6th, not the 5th
beforeEach(() => { vi.useFakeTimers({ toFake: ["Date"] }); vi.setSystemTime(new Date("2026-11-05T19:00:00Z")); vi.clearAllMocks(); listSlots.mockResolvedValue({ slots: SLOTS }); });
afterEach(() => vi.useRealTimers());

async function open(role = "PATIENT") {
  const onSaved = vi.fn(), onClose = vi.fn();
  render(<MemoryRouter><NewAppointment role={role} onSaved={onSaved} onClose={onClose} /></MemoryRouter>);
  const user = userEvent.setup({ advanceTimers: () => {} });
  await screen.findByRole("option", { name: /Anjali/ });                          // the doctor list has arrived
  await user.selectOptions(screen.getByRole("combobox"), "7");
  return { user, onSaved, onClose };
}

describe("booking an appointment", () => {
  it("the date box starts today at the hospital and stops 30 days ahead", async () => {
    await open();
    const date = screen.getByLabelText(/^Date/);
    expect(date.getAttribute("min")).toBe("2026-11-06");
    expect(date.getAttribute("max")).toBe("2026-12-06");
  });

  it("slots that are taken or passed cannot be chosen", async () => {
    const { user } = await open();
    await user.type(screen.getByLabelText(/^Date/), "2026-11-06");
    const free = await screen.findByRole("button", { name: "09:30" });
    expect(free.disabled).toBe(false);
    expect(screen.getByRole("button", { name: "09:15" }).disabled).toBe(true);
    expect(screen.getByRole("button", { name: "09:00" }).disabled).toBe(true);
    expect(listSlots).toHaveBeenCalledWith(7, "2026-11-06");
  });

  it("shows the server's message under the time, keeps what was typed, and a double click sends one request", async () => {
    createAppointment.mockImplementation(() => new Promise((_, reject) => { release = () => reject({ response: { status: 409, data: { detail: "This doctor already has an appointment at that time." } } }); }));
    const { user, onSaved } = await open();
    await user.type(screen.getByLabelText(/^Date/), "2026-11-06");
    await user.type(screen.getByLabelText(/main problem/i), "Fever since yesterday");
    await user.click(await screen.findByRole("button", { name: "09:30" }));
    const book = screen.getByRole("button", { name: /Book appointment/ });
    await user.dblClick(book);
    expect(createAppointment).toHaveBeenCalledTimes(1);
    expect(createAppointment.mock.calls[0][0]).toMatchObject({ doctor_id: 7, scheduled_at: "2026-11-06T09:30" });
    release();
    const alert = await screen.findByText(/already has an appointment at that time/);
    expect(alert.closest("fieldset")).not.toBeNull();                              // under the Time field
    expect(screen.getByLabelText(/main problem/i).value).toBe("Fever since yesterday");
    expect(onSaved).not.toHaveBeenCalled();
    await waitFor(() => expect(listSlots).toHaveBeenCalledTimes(2));            // the list is fetched again after a clash
    expect(screen.getByRole("button", { name: /Book appointment/ }).disabled).toBe(false);
  });

  it("asks for a date and time before sending anything", async () => {
    const { user } = await open();
    await user.click(screen.getByRole("button", { name: /Book appointment/ }));
    expect(await screen.findByText("Please choose the date.")).toBeTruthy();
    expect(createAppointment).not.toHaveBeenCalled();
  });
});
