import { describe, expect, it, vi, beforeEach } from "vitest";
import { fileName, fileSafe, printAs } from "./printTitle";

describe("print file names", () => {
  it("builds patient_name_what-it-contains names", () => {
    expect(fileName("Rahul Patil", "Medical history")).toBe("Rahul_Patil_Medical_History");
    expect(fileName("Dr. Anjali Sharma", "Clinical summary")).toBe("Dr_Anjali_Sharma_Clinical_Summary");
    expect(fileName("Rahul Patil", "Emergency card")).toBe("Rahul_Patil_Emergency_Card");
    expect(fileName("Walk-in customer", "BILL-20261023-0001", "Bill")).toBe("Walk_In_Customer_BILL_20261023_0001_Bill");
  });
  it("removes characters that are not allowed in a file name but keeps Hindi and Marathi names", () => {
    expect(fileSafe('A/B:C*D?"E<F>G|H')).toBe("A_B_C_D_E_F_G_H");
    expect(fileSafe("  वैभव लाड  ")).toBe("वैभव_लाड");
    expect(fileName(undefined, null, "History")).toBe("History");
  });
});

describe("printAs", () => {
  beforeEach(() => { document.title = "HealthWise AI"; });
  it("names the page for the print window and puts the title back afterwards", () => {
    let titleWhenPrinting;
    window.print = vi.fn(() => { titleWhenPrinting = document.title; });
    printAs("Rahul Patil", "Medical history");
    expect(titleWhenPrinting).toBe("Rahul_Patil_Medical_History");
    window.dispatchEvent(new Event("afterprint"));
    expect(document.title).toBe("HealthWise AI");
  });
  it("still prints, with the normal title, when there is no name to use", () => {
    window.print = vi.fn();
    printAs(undefined, "");
    expect(window.print).toHaveBeenCalled();
    expect(document.title).toBe("HealthWise AI");
  });
});
