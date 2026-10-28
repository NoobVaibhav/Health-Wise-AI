import { describe, expect, it } from "vitest";
import { summaryPoints } from "./summaryPoints";

describe("summaryPoints", () => {
  it("uses the points the server sent", () => {
    const pts = [{ text: "58 tests read", items: ["HbA1c: high"] }];
    expect(summaryPoints({ insights: { summary_points: pts }, ai_summary: "ignored." })).toEqual(pts);
  });
  it("splits a written summary into its sentences", () => {
    expect(summaryPoints({ ai_summary: "ECG tracing. 6 key statements were found. The findings: \"Sinus rhythm.\"" }).map((p) => p.text))
      .toEqual(["ECG tracing.", "6 key statements were found.", "The findings: \"Sinus rhythm.\""]);
  });
  it("is empty when there is no summary", () => { expect(summaryPoints({})).toEqual([]); });
});
