// Route guards, session handling and error paths. Findings are marked with their ID from docs/BUST_REPORT.md; `it.fails` is a test that asserts the
// secure behaviour and is expected to fail until the finding is fixed (remove `.fails` then).
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

let mockUser = null;
vi.mock("../../context/AuthContext", () => ({
  ROLE_HOME: { ADMIN: "/admin", DOCTOR: "/doctor", EMPLOYEE: "/employee", PATIENT: "/patient", PHARMACY: "/pharmacy", LAB: "/lab" },
  useAuth: () => ({ user: mockUser, loading: false, logout: vi.fn(), refresh: vi.fn() }),
}));
vi.mock("../../services/authApi", () => ({ changePassword: vi.fn() }));
import RoleRoute from "../../routes/RoleRoute";
import ProtectedRoute from "../../routes/ProtectedRoute";

const ROLES = ["ADMIN", "DOCTOR", "EMPLOYEE", "PATIENT", "PHARMACY", "LAB"];
const app = (path) => render(
  <MemoryRouter initialEntries={[path]}>
    <Routes>
      <Route path="/login" element={<p>LOGIN PAGE</p>} />
      <Route element={<ProtectedRoute />}>
        {ROLES.map((role) => (
          <Route key={role} path={`/${role.toLowerCase()}`} element={<RoleRoute roles={[role]} />}>
            <Route index element={<p>{role} HOME</p>} />
            <Route path="secret" element={<p>{role} SECRET</p>} />
          </Route>
        ))}
      </Route>
    </Routes>
  </MemoryRouter>,
);
beforeEach(() => { mockUser = null; localStorage.clear(); });

describe("route guards", () => {
  it("sends a visitor who is not logged in to the login page for every protected URL", () => {
    for (const path of ["/admin", "/doctor/secret", "/patient", "/pharmacy", "/lab"]) {
      const { unmount } = app(path);
      expect(screen.getByText("LOGIN PAGE")).toBeTruthy();
      unmount();
    }
  });

  it("sends every role that types another role's URL back to its own home page", () => {
    for (const me of ROLES) {
      for (const other of ROLES.filter((r) => r !== me)) {
        mockUser = { role: me, full_name: "Tester", must_change_password: false };
        const { unmount } = app(`/${other.toLowerCase()}/secret`);
        expect(screen.queryByText(`${other} SECRET`)).toBeNull();
        expect(screen.getByText(`${me} HOME`)).toBeTruthy();
        unmount();
      }
    }
  });

  it("shows nothing but the password pop-up while the starting password is still in use", () => {
    mockUser = { role: "DOCTOR", full_name: "Dr Temp", must_change_password: true };
    app("/doctor/secret");
    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(screen.queryByText("DOCTOR SECRET")).toBeNull();
  });

  it("an edited role in a stored token changes nothing on screen: the role comes from the server", () => {
    localStorage.setItem("healthwise_token", "eyJhbGciOiJub25lIn0.eyJyb2xlIjoiQURNSU4ifQ.");
    mockUser = { role: "PATIENT", full_name: "Pat", must_change_password: false };
    app("/admin/secret");
    expect(screen.queryByText("ADMIN SECRET")).toBeNull();
  });
});
