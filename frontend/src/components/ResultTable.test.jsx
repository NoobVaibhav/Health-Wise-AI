import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import ResultTable from "./ResultTable";

const row = (over) => ({ id: 1, name: "Potassium", value: "6.8", unit: "mmol/L", method: "ISE", ref_low: 3.5, ref_high: 5, flag: "CRITICAL_HIGH", flag_text: "Critically high", previous: null, ...over });

describe("ResultTable", () => {
  it("shows the value, unit, range and the flag in words", () => {
    render(<ResultTable results={[row()]} />);
    expect(screen.getByText("Potassium")).toBeTruthy();
    expect(screen.getByText("Critically high")).toBeTruthy();
    expect(screen.getByText("3.5 - 5")).toBeTruthy();
  });
  it("says when the hospital set no range, and shows the earlier value with its direction", () => {
    render(<ResultTable results={[row({ id: 2, name: "Widget", flag: "UNRATED", flag_text: "No range set", ref_low: null, ref_high: null, previous: { value: "4.0", unit: "mmol/L", date: "2026-10-01", change: "up" } })]} />);
    expect(screen.getByText("no range set")).toBeTruthy();
    expect(screen.getByText(/now higher/)).toBeTruthy();
  });
  it("shows nothing for an empty list", () => {
    const { container } = render(<ResultTable results={[]} />);
    expect(container.firstChild).toBeNull();
  });
});
