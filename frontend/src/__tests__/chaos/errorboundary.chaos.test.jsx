import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import ErrorBoundary from "../../components/ErrorBoundary";

const Boom = () => { throw new Error("the server sent an unexpected shape"); };

describe("a page that fails to draw", () => {
  it("F-05: an error while drawing shows a message and a way out instead of a blank screen", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    render(<ErrorBoundary><Boom /></ErrorBoundary>);
    expect(screen.getByRole("alert").textContent).toMatch(/Something went wrong on this page/);
    expect(screen.getByRole("button", { name: /Try again/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Home page/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Log out/ })).toBeTruthy();
  });
  it("a page that draws well is shown as it is", () => {
    render(<ErrorBoundary><p>All fine</p></ErrorBoundary>);
    expect(screen.getByText("All fine")).toBeTruthy();
  });
});
