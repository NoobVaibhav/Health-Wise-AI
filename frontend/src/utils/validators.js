// The input rules of the forms, in one place. They repeat the rules of the server (backend/app/utils/validators.py) only to give an answer at once:
// the server checks everything again and is the real check. Every function returns an error sentence, or "" when the value is fine.
// See docs/VALIDATION_RULES.md.

/** Trim, remove HTML tags and control characters. */
export const cleanText = (value, { multiline = false } = {}) => {
  const text = String(value ?? "").replace(/<[^>]*>?/g, "").replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f​-‏‪-‮⁦-⁩]/g, "");
  return multiline ? text.trim() : text.replace(/\s+/g, " ").trim();
};

const empty = (value) => String(value ?? "").trim() === "";

// ------------------------------------------------------------------ e-mail, names, phone
export const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

export function email(value, { required = true } = {}) {
  const v = String(value ?? "").trim();
  if (v === "") return required ? "Please enter your e-mail address." : "";
  if (/\s/.test(v)) return "The e-mail address cannot contain spaces.";
  if (v.length > 254) return "The e-mail address is too long (254 characters at most).";
  if (!EMAIL_RE.test(v)) return "Please enter a valid e-mail address, for example name@example.com.";
  return "";
}

export function personName(value, { required = true, label = "name" } = {}) {
  if (/[<>]/.test(String(value ?? ""))) return "The name can contain only letters, spaces, apostrophes, hyphens and dots.";
  const v = cleanText(value);
  if (v === "") return required ? `Please enter the ${label}.` : "";
  if (v.length < 2) return "Please enter the full name (at least 2 characters).";
  if (v.length > 150) return "The name is too long (150 characters at most).";
  if (!/^[\p{L}\p{M}][\p{L}\p{M}\s'.’-]*$/u.test(v)) return "The name can contain only letters, spaces, apostrophes, hyphens and dots.";
  return "";
}

/** "+91 98765 43210", "098765-43210" -> "9876543210"; a number with another country code -> "+<digits>". Returns "" if it is not a phone number. */
export function normalisePhone(value) {
  const raw = String(value ?? "").trim();
  const plus = raw.startsWith("+");
  let digits = raw.slice(plus ? 1 : 0).replace(/[\s\-().]/g, "");
  if (!/^\d+$/.test(digits)) return "";
  if (plus) {
    if (digits.startsWith("91") && digits.length === 12 && "6789".includes(digits[2])) return digits.slice(2);
    return digits.length >= 8 && digits.length <= 15 ? `+${digits}` : "";
  }
  if (digits.length === 11 && digits.startsWith("0")) digits = digits.slice(1);
  if (digits.length === 12 && digits.startsWith("91")) digits = digits.slice(2);
  return /^[6-9]\d{9}$/.test(digits) ? digits : "";
}

export function phone(value, { required = false } = {}) {
  if (empty(value)) return required ? "Please enter a phone number." : "";
  if (!/^[+\d\s\-().]+$/.test(String(value))) return "The phone number can contain only digits, spaces, dashes, brackets and a leading +.";
  return normalisePhone(value) ? "" : "Please enter a 10-digit mobile number starting with 6, 7, 8 or 9 (or a number with a + and country code).";
}

/** The emergency contact must be somebody else: it must not hold the patient's own number. */
export function emergencyContact(contact, ownPhone) {
  if (empty(contact)) return "";
  if (String(contact).length > 150) return "Please keep this under 150 characters.";
  const last10 = (s) => String(s ?? "").replace(/\D/g, "").slice(-10);
  if (last10(ownPhone).length >= 10 && last10(contact) === last10(ownPhone)) return "The emergency contact must be a different person: this is the patient's own phone number.";
  return "";
}

export function address(value) {
  const v = cleanText(value);
  return v.length > 300 ? `The address is too long (300 characters at most, it has ${v.length}).` : "";
}

export const GENDERS = ["male", "female", "other"];
export const BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"];
export const gender = (value) => (empty(value) || GENDERS.includes(String(value).toLowerCase()) ? "" : "Please choose male, female or other.");
export const bloodGroup = (value) => (empty(value) || BLOOD_GROUPS.includes(String(value).toUpperCase().replace(/\s/g, "")) ? "" : "Please choose a blood group from the list.");

// ------------------------------------------------------------------ dates
const pad = (n) => String(n).padStart(2, "0");
/** Today's date in the person's own calendar (not the UTC date, which is still "yesterday" in the early morning in India). */
export const todayISO = () => { const d = new Date(); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; };
export const MIN_DOB = "1930-01-01";         // the earliest date of birth: the date box starts here

const realDate = (value) => {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const [y, m, day] = value.split("-").map(Number);
  const d = new Date(y, m - 1, day);                                         // local calendar date: a day that does not exist (30 February) moves to the next month
  return d.getFullYear() === y && d.getMonth() === m - 1 && d.getDate() === day ? d : null;
};

export const ageOf = (value, now = new Date()) => {
  const d = realDate(value);
  if (!d) return null;
  return now.getFullYear() - d.getFullYear() - ((now.getMonth() < d.getMonth() || (now.getMonth() === d.getMonth() && now.getDate() < d.getDate())) ? 1 : 0);
};

export function dateOfBirth(value, { required = false } = {}) {
  if (empty(value)) return required ? "Please enter the date of birth." : "";
  const d = realDate(String(value));
  if (!d) return "Please enter a real date.";
  if (value > todayISO()) return "The date of birth cannot be in the future.";
  if (value < MIN_DOB) return "The date of birth cannot be before 1930.";
  if (ageOf(value) > 120) return "The age cannot be more than 120 years.";
  return "";
}

/** A warning, not an error: possible but unusual ages. */
export function ageWarning(value) {
  if (dateOfBirth(value) !== "" || empty(value)) return "";
  const age = ageOf(value);
  if (age < 1) return "This patient is under 1 year old. Please check the date of birth.";
  if (age > 110) return `This patient would be ${age} years old. Please check the date of birth.`;
  return "";
}

export function appointmentTime(value) {
  if (empty(value)) return "Please choose the date and time.";
  const t = new Date(value);
  if (Number.isNaN(t.getTime())) return "Please choose a real date and time.";
  if (t.getTime() < Date.now() - 5 * 60_000) return "The appointment time must be in the future.";
  if (t.getTime() > Date.now() + 366 * 86_400_000) return "Appointments can be booked up to 1 year ahead.";
  return "";
}

export const notFuture = (value) => (empty(value) || value <= todayISO() ? "" : "This date cannot be in the future.");

// ------------------------------------------------------------------ passwords
const COMMON = new Set(["password", "password1", "password12", "password123", "password1234", "passw0rd", "p@ssw0rd", "12345678", "123456789", "1234567890", "qwerty123", "qwerty1234",
  "qwertyuiop", "1q2w3e4r", "1qaz2wsx", "admin123", "admin1234", "welcome1", "welcome123", "welcome@123", "letmein123", "iloveyou1", "iloveyou123", "abc12345", "abcd1234", "abcd12345",
  "monkey123", "dragon123", "changeme1", "changeme123", "india123", "india@123", "hospital1", "hospital123", "health123", "doctor123", "patient123", "pharmacy123", "test1234", "test12345"]);

/** True if the password contains the name part of the e-mail address (4 letters or more). */
export function passwordHasEmailName(pw, mail) {
  const local = String(mail ?? "").split("@")[0].toLowerCase();
  if (!local || !String(mail).includes("@")) return false;
  const pieces = new Set([local, ...local.split(/[^a-z]+/).filter((p) => p.length >= 4)]);
  return [...pieces].some((p) => p.length >= 4 && pw.toLowerCase().includes(p));
}

export function password(value, { email: mail = "", current = "" } = {}) {
  const v = String(value ?? "");
  if (v === "") return "Please choose a password.";
  if (v.length < 8) return "The password must have at least 8 characters.";
  if (v.length > 128) return "The password is too long (128 characters at most).";
  if (!/[A-Za-z]/.test(v) || !/\d/.test(v)) return "The password must contain at least one letter and one number.";
  const lower = v.toLowerCase();
  if (COMMON.has(lower) || COMMON.has(lower.replace(/[!@#$%^&*]+$/, ""))) return "This password is too common. Please choose another one.";
  if (passwordHasEmailName(v, mail)) return "The password must not contain your e-mail name.";
  if (current && v === current) return "The new password must be different from the current one.";
  return "";
}

export const confirmPassword = (pw, confirm) => (String(confirm ?? "") === "" ? "Please type the password again." : pw === confirm ? "" : "The two passwords are not the same.");

/** weak / okay / strong for the live hint (length, mixed case, digits, symbols, no common password). */
export function passwordStrength(value) {
  const v = String(value ?? "");
  if (v.length === 0) return { level: "", label: "", score: 0 };
  if (password(v) !== "" && (v.length < 8 || COMMON.has(v.toLowerCase()))) return { level: "weak", label: "Weak", score: 1 };
  let score = 0;
  if (v.length >= 8) score += 1;
  if (v.length >= 12) score += 1;
  if (/[a-z]/.test(v) && /[A-Z]/.test(v)) score += 1;
  if (/\d/.test(v)) score += 1;
  if (/[^A-Za-z0-9]/.test(v)) score += 1;
  if (!/[A-Za-z]/.test(v) || !/\d/.test(v)) score = Math.min(score, 2);
  if (score <= 2) return { level: "weak", label: "Weak", score: 1 };
  if (score <= 3) return { level: "okay", label: "Okay", score: 2 };
  return { level: "strong", label: "Strong", score: 3 };
}

// ------------------------------------------------------------------ numbers, vitals, text, files
export const VITALS = {
  height_cm: ["Height", 30, 260, "cm"], weight_kg: ["Weight", 1, 500, "kg"], pulse: ["Pulse", 20, 250, "beats a minute"], bp_systolic: ["Upper blood pressure", 50, 300, "mmHg"],
  bp_diastolic: ["Lower blood pressure", 30, 200, "mmHg"], spo2: ["Oxygen level", 50, 100, "%"], temperature_c: ["Temperature", 30, 45, "°C"],
};

export function vital(key, value) {
  const spec = VITALS[key];
  if (!spec || empty(value)) return "";
  const [label, low, high, unit] = spec;
  const n = Number(value);
  if (!Number.isFinite(n)) return `${label} must be a number.`;
  return n < low || n > high ? `${label} should be between ${low} and ${high} ${unit}.` : "";
}

export function nonNegativeNumber(value, { label = "This value", max = 10_000_000, required = false } = {}) {
  if (empty(value)) return required ? `${label} is required.` : "";
  const n = Number(value);
  if (!Number.isFinite(n)) return `${label} must be a number.`;
  if (n < 0) return `${label} cannot be negative.`;
  return n > max ? `${label} is too large.` : "";
}

export const percent = (value, label = "This value") => {
  const msg = nonNegativeNumber(value, { label, max: 100 });
  return msg === `${label} is too large.` ? `${label} must be between 0 and 100.` : msg;
};

export function positiveInteger(value, { label = "This value", max = 1_000_000 } = {}) {
  if (empty(value)) return `${label} is required.`;
  const n = Number(value);
  if (!Number.isInteger(n) || n <= 0) return `${label} must be a whole number above zero.`;
  return n > max ? `${label} is too large.` : "";
}

export const barcode = (value) => (empty(value) || /^[A-Za-z0-9-]{4,64}$/.test(String(value).trim()) ? "" : "The barcode must have 4 to 64 letters, digits or hyphens.");

export function text(value, { max, min = 0, required = false, label = "This" } = {}) {
  const v = cleanText(value, { multiline: true });
  if (v === "") return required ? `${label === "This" ? "This is" : `${label} is`} required.` : "";
  if (min && v.length < min) return `Please enter at least ${min} characters.`;
  return max && v.length > max ? `Please keep this under ${max} characters (it has ${v.length}).` : "";
}

export const REPORT_FILE = { maxMB: 10, extensions: ["pdf", "png", "jpg", "jpeg", "txt", "csv"], hint: "PDF, PNG or JPG (a plain text or CSV export is also accepted), up to 10 MB" };
export const AVATAR_FILE = { maxMB: 2, extensions: ["png", "jpg", "jpeg"], hint: "JPG or PNG, up to 2 MB" };

export function file(f, rules = REPORT_FILE) {
  if (!f) return "Please choose a file.";
  if (f.size === 0) return "The file is empty. Please choose another one.";
  if (f.size > rules.maxMB * 1024 * 1024) return `The file is too large (${(f.size / 1048576).toFixed(1)} MB). The most allowed is ${rules.maxMB} MB.`;
  const ext = String(f.name || "").split(".").pop().toLowerCase();
  return rules.extensions.includes(ext) ? "" : `This kind of file is not accepted. Please choose: ${rules.hint}.`;
}

/** Runs a table of rules: { field: (value, allValues) => message }. Returns { field: message } for the fields that have a message. */
export function validateAll(rules, values) {
  const errors = {};
  for (const [name, rule] of Object.entries(rules)) {
    const message = rule(values[name], values);
    if (message) errors[name] = message;
  }
  return errors;
}
