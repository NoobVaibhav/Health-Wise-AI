import { describe, expect, it } from "vitest";
import * as v from "./validators";

const iso = (days) => { const d = new Date(Date.now() + days * 86_400_000); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`; };

describe("email", () => {
  it.each(["a@b.co", "  rahul.patil@example.com ", "a+tag@b.io"])("accepts %s", (x) => expect(v.email(x)).toBe(""));
  it.each(["", "   ", "no-at-sign", "a b@c.com", "a@", "@b.com", "a@b", "x".repeat(250) + "@b.com"])("refuses %j", (x) => expect(v.email(x)).not.toBe(""));
  it("is optional when asked", () => expect(v.email("", { required: false })).toBe(""));
});

describe("personName", () => {
  it.each(["Anjali Sharma", "Dr. Anjali Sharma", "O'Neil-Smith", "Zoë Müller", "अंजली शर्मा", "Ab"])("accepts %s", (x) => expect(v.personName(x)).toBe(""));
  it.each(["", "   ", "A", "Rahul7", "Rahul_Patil", "Rahul \u{1F600}", "<b>Rahul</b>", "Rahul@Patil", "N".repeat(151)])("refuses %j", (x) => expect(v.personName(x)).not.toBe(""));
});

describe("phone", () => {
  it.each(["9876543210", "+91 98765 43210", "098765-43210", "(98765) 43210", "+44 20 7946 0958"])("accepts %s", (x) => expect(v.phone(x, { required: true })).toBe(""));
  it.each(["1234567890", "98765", "abcdefghij", "98765432101", "9876543210; DROP"])("refuses %s", (x) => expect(v.phone(x)).not.toBe(""));
  it("is optional unless required", () => { expect(v.phone("")).toBe(""); expect(v.phone("", { required: true })).not.toBe(""); });
  it("normalises like the server", () => {
    expect(v.normalisePhone("+91 98765 43210")).toBe("9876543210");
    expect(v.normalisePhone("+44 20 7946 0958")).toBe("+442079460958");
    expect(v.normalisePhone("12345")).toBe("");
  });
  it("the emergency contact must not hold the patient's own number", () => {
    expect(v.emergencyContact("Sunita 98765 43210", "9876543210")).not.toBe("");
    expect(v.emergencyContact("Sunita 91234 56789", "9876543210")).toBe("");
    expect(v.emergencyContact("", "9876543210")).toBe("");
  });
});

describe("dates", () => {
  it("date of birth boundaries", () => {
    expect(v.dateOfBirth(v.todayISO())).toBe("");
    expect(v.dateOfBirth("1990-05-14")).toBe("");
    expect(v.dateOfBirth(iso(1))).toMatch(/future/);
    expect(v.dateOfBirth("2999-01-01")).toMatch(/future/);
    expect(v.dateOfBirth("1929-12-31")).toMatch(/before 1930/);
    expect(v.dateOfBirth("1930-01-01")).toBe("");
    expect(v.dateOfBirth("2026-02-30")).toMatch(/real date/);
    expect(v.dateOfBirth("not a date")).toMatch(/real date/);
    expect(v.dateOfBirth("")).toBe("");
    expect(v.dateOfBirth("", { required: true })).not.toBe("");
  });
  it("age warnings are warnings, not errors", () => {
    expect(v.ageWarning(iso(-100))).toMatch(/under 1/);
    expect(v.ageWarning("1990-01-01")).toBe("");
    expect(v.ageWarning(iso(1))).toBe("");
  });
  it("appointment time", () => {
    const at = (days) => new Date(Date.now() + days * 86_400_000).toISOString().slice(0, 16);
    expect(v.appointmentTime(at(2))).toBe("");
    expect(v.appointmentTime(at(-1))).toMatch(/future/);
    expect(v.appointmentTime(at(400))).toMatch(/1 year/);
    expect(v.appointmentTime("")).not.toBe("");
  });
});

describe("gender, blood group, address, text", () => {
  it("accepts only the allowed values", () => {
    expect(v.gender("Male")).toBe(""); expect(v.gender("")).toBe(""); expect(v.gender("robot")).not.toBe("");
    expect(v.bloodGroup("ab-")).toBe(""); expect(v.bloodGroup("Z+")).not.toBe(""); expect(v.bloodGroup("")).toBe("");
  });
  it("address and text limits count the cleaned text", () => {
    expect(v.address("x".repeat(300))).toBe(""); expect(v.address("x".repeat(301))).toMatch(/too long/);
    expect(v.text("<b>hi</b>", { max: 5 })).toBe(""); expect(v.text("x".repeat(6), { max: 5 })).toMatch(/under 5/);
    expect(v.text("   ", { required: true })).toMatch(/required/);
  });
  it("cleanText strips tags, control characters and extra spaces", () => {
    expect(v.cleanText("  <script>x</script>  a \u0000  b ")).toBe("x a b");
    expect(v.cleanText("a\n\n b ", { multiline: true })).toBe("a\n\n b");
  });
});

describe("passwords", () => {
  it.each(["abcdefg1", "Correct-Horse-9"])("accepts %s", (x) => expect(v.password(x)).toBe(""));
  it.each(["", "short1", "abcdefgh", "12345678", "password1", "Welcome@123", "a".repeat(129) + "1"])("refuses %j", (x) => expect(v.password(x)).not.toBe(""));
  it("refuses the e-mail name and the current password", () => {
    expect(v.password("Rahul.Patil99", { email: "rahul.patil@example.com" })).toMatch(/e-mail name/);
    expect(v.password("Zebra-Clock-81", { email: "rahul.patil@example.com" })).toBe("");
    expect(v.password("Zebra-Clock-81", { current: "Zebra-Clock-81" })).toMatch(/different/);
  });
  it("confirm must match", () => {
    expect(v.confirmPassword("abc12345", "abc12345")).toBe("");
    expect(v.confirmPassword("abc12345", "abc12346")).toMatch(/not the same/);
    expect(v.confirmPassword("abc12345", "")).not.toBe("");
  });
  it("strength hint", () => {
    expect(v.passwordStrength("").level).toBe("");
    expect(v.passwordStrength("abc").level).toBe("weak");
    expect(v.passwordStrength("password1").level).toBe("weak");
    expect(v.passwordStrength("abcdefg1").level).toBe("weak");
    expect(v.passwordStrength("Abcdefg123").level).toBe("okay");
    expect(v.passwordStrength("Correct-Horse-9!x").level).toBe("strong");
  });
});

describe("clinical, money and files", () => {
  it("vital signs", () => {
    expect(v.vital("pulse", 72)).toBe(""); expect(v.vital("pulse", 19)).toMatch(/between 20 and 250/); expect(v.vital("pulse", "abc")).toMatch(/number/);
    expect(v.vital("spo2", 101)).not.toBe(""); expect(v.vital("temperature_c", 36.6)).toBe(""); expect(v.vital("height_cm", "")).toBe("");
  });
  it("numbers, percent, barcode", () => {
    expect(v.nonNegativeNumber("-1", { label: "Price" })).toMatch(/negative/);
    expect(v.nonNegativeNumber("NaN")).toMatch(/number/);
    expect(v.percent("101", "GST")).toMatch(/between 0 and 100/);
    expect(v.positiveInteger("0", { label: "Quantity" })).toMatch(/above zero/); expect(v.positiveInteger("2.5")).not.toBe(""); expect(v.positiveInteger("5")).toBe("");
    expect(v.barcode("AB-1234")).toBe(""); expect(v.barcode("ab")).not.toBe(""); expect(v.barcode("AB CD")).not.toBe("");
  });
  it("files: type, size and empty", () => {
    const f = (name, size) => ({ name, size });
    expect(v.file(f("r.pdf", 1000))).toBe("");
    expect(v.file(f("r.PNG", 1000))).toBe("");
    expect(v.file(f("r.webp", 1000))).toMatch(/not accepted/);
    expect(v.file(f("r.exe", 1000))).not.toBe("");
    expect(v.file(f("r.pdf", 0))).toMatch(/empty/);
    expect(v.file(f("r.pdf", 11 * 1024 * 1024))).toMatch(/too large/);
    expect(v.file(f("p.jpg", 3 * 1024 * 1024), v.AVATAR_FILE)).toMatch(/too large/);
    expect(v.file(f("p.png", 1000), v.AVATAR_FILE)).toBe("");
    expect(v.file(null)).not.toBe("");
  });
  it("validateAll gathers the messages of a form", () => {
    const rules = { a: (x) => (x ? "" : "A is needed."), b: (x, all) => (x === all.a ? "" : "B must equal A.") };
    expect(v.validateAll(rules, { a: "1", b: "1" })).toEqual({});
    expect(v.validateAll(rules, { a: "", b: "x" })).toEqual({ a: "A is needed.", b: "B must equal A." });
  });
});
