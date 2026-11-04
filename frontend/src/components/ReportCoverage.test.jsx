import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { CoverageNote, OtherResults, TableNote, groupOtherResults } from "./ReportCoverage";
import ReportPrintSheet from "./ReportPrintSheet";

const other = [
  { section: "SEROLOGY & IMMUNOLOGY", title: "Widal Test (Slide Method)", subgroup: null, name: "Salmonella Typhi 'O'", value: "1:20", unit: null, reference: null, printed_flag: null },
  { section: "MISCELLANEOUS / Mantoux test", title: "Mantoux test", subgroup: null, name: "RESULTS", value: "Negative", unit: null, reference: null, printed_flag: null },
];
const incomplete = { complete: false, message: "44 of 66 printed result rows were analysed against the printed range.", unread_rows: [{ section: "BIOCHEMISTRY", text: "Serum Zorblax Factor 12.5 mg/dl 1 - 5" }], skipped_sections: [] };

describe("coverage and other results", () => {
  it("warns that not the whole report was analysed, with the rows that could not be read", () => {
    render(<CoverageNote report={{ insights: { coverage: incomplete } }} />);
    expect(screen.getByText("Not the whole report was analysed")).toBeTruthy();
    expect(screen.getByText(/44 of 66/)).toBeTruthy();
    expect(screen.getByText(/Zorblax/)).toBeTruthy();
  });
  it("shows nothing when the whole report was analysed, or when there is no coverage information", () => {
    expect(render(<CoverageNote report={{ insights: { coverage: { complete: true } } }} />).container.innerHTML).toBe("");
    expect(render(<CoverageNote report={{ insights: {} }} />).container.innerHTML).toBe("");
  });
  it("groups the other results by test and shows the printed values with no verdict", () => {
    expect(groupOtherResults(other).map((g) => g.title)).toEqual(["Widal Test (Slide Method)", "Mantoux test"]);
    render(<OtherResults report={{ insights: { other_results: other } }} />);
    expect(screen.getByText("1:20")).toBeTruthy();
    expect(screen.getByText("Negative")).toBeTruthy();
    expect(screen.queryByText(/Too high|Too low|Normal$/)).toBeNull();
  });
  it("shows the report's own table note beside a result", () => {
    render(<TableNote text="The report's own interpretation table lists LDL below 100 mg/dl as Optimal." />);
    expect(screen.getByText(/lists LDL below 100/)).toBeTruthy();
  });
  it("prints the coverage warning and the other results on the PDF sheet", () => {
    const report = { analysis_visible: true, patient_name: "A B", patient_code: "P-1", report_type_label: "Laboratory test report", filename: "x.pdf", report_date: "2021-05-14",
      ai_summary: "x", counts: {}, parameters: [], insights: { coverage: incomplete, other_results: other, priority: [], slightly_outside: [] } };
    render(<ReportPrintSheet report={report} role="DOCTOR" />);
    expect(screen.getByText("Not the whole report was analysed.")).toBeTruthy();
    expect(screen.getByText("Widal Test (Slide Method)")).toBeTruthy();
  });
});
