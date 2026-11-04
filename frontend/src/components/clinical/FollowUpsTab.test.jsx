import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

let release;
vi.mock("../../services/clinicalApi", () => ({
  getFollowUps: vi.fn(() => Promise.resolve({ tasks: [], derived: [], upcoming_appointments: [] })),
  createFollowUp: vi.fn(() => new Promise((resolve) => { release = () => resolve({ tasks: [{ id: 1, title: "Repeat ECG", status: "PENDING", created_by: "Dr. A" }], derived: [], upcoming_appointments: [] }); })),
  updateFollowUp: vi.fn(),
  getMedicationHistory: vi.fn(),
}));
vi.mock("../Toast", () => ({ useToast: () => vi.fn() }));
import { createFollowUp } from "../../services/clinicalApi";
import { FollowUpsTab } from "./MedsFollowTabs";

describe("FollowUpsTab", () => {
  it("a double click on Add sends one request, and the date box stops at 2 years ahead like the server", async () => {
    render(<FollowUpsTab patientId={5} onOpen={() => {}} />);
    await userEvent.type(await screen.findByPlaceholderText(/What must happen/), "Repeat ECG");
    const add = screen.getByRole("button", { name: /Add/ });
    await userEvent.dblClick(add);
    expect(createFollowUp).toHaveBeenCalledTimes(1);
    expect(add.disabled).toBe(true);
    const limit = new Date(screen.getByLabelText("Due date").getAttribute("max"));
    expect((limit - Date.now()) / 864e5).toBeGreaterThan(720);
    release();
    await waitFor(() => expect(add.disabled).toBe(false));
  });
});
