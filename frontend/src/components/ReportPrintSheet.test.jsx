import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import ReportPrintSheet from "./ReportPrintSheet";

const base = { analysis_visible: true, patient_name: "Rahul Patil", patient_code: "P-0001", report_type_label: "Laboratory test report", filename: "x.pdf", report_date: "2026-01-02",
  ai_summary: "The computer read 2 test results.", counts: { WITHIN_RANGE: 1, ABOVE_RANGE: 1, BELOW_RANGE: 0, UNKNOWN: 0 }, parameters: [
    { id: 1, test_name: "HbA1c", normalized_name: "HbA1c", value: 7.1, unit: "%", reference_text: "below 5.7", status: "ABOVE_RANGE" },
    { id: 2, test_name: "Hemoglobin", normalized_name: "Hemoglobin", value: 14, unit: "g/dL", reference_text: "13 - 17", status: "WITHIN_RANGE" }],
  insights: { priority: [{ name: "HbA1c", value: 7.1, unit: "%", range: "below 5.7", direction: "HIGH", how_far: "about 25% above the upper limit", meaning: "A blood sugar test." }],
    slightly_outside: [], doctor_suggestions: ["Compare with earlier reports."], patient_recommendations: ["Walk daily."] } };

describe("ReportPrintSheet", () => {
  it("prints the patient, the ranked results and every test, with the tips for the role", () => {
    render(<ReportPrintSheet report={base} role="PATIENT" />);
    expect(screen.getByText(/Rahul Patil/)).toBeTruthy();
    expect(screen.getByText("about 25% above the upper limit")).toBeTruthy();
    expect(screen.getByText("Hemoglobin")).toBeTruthy();
    expect(screen.getByText("Walk daily.")).toBeTruthy();
    expect(screen.queryByText("Compare with earlier reports.")).toBeNull();
  });
  it("gives the doctor the points to consider instead", () => {
    render(<ReportPrintSheet report={base} role="DOCTOR" />);
    expect(screen.getByText("Compare with earlier reports.")).toBeTruthy();
  });
  it("prints nothing while the analysis is not yet visible to this person", () => {
    const { container } = render(<ReportPrintSheet report={{ ...base, analysis_visible: false }} role="PATIENT" />);
    expect(container.innerHTML).toBe("");
  });
});
