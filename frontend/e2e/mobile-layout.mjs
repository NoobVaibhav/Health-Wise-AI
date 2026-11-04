// Mobile layout check. Opens every main route of every demo role in a phone-sized browser and FAILS on:
//   - horizontal overflow (page wider than the screen),
//   - a tap target smaller than 44 x 44 px,
//   - a console error or an uncaught page error.
// It needs the backend (demo data) and the frontend dev server running:
//   cd backend && python -m uvicorn app.main:app --port 8000      (demo accounts: python -m app.seed_demo)
//   cd frontend && npm run dev                                    (http://localhost:5173)
//   cd frontend && npm run test:layout
// Settings (environment variables): BASE (default http://localhost:5173), API (default http://localhost:8000/api),
// WIDTHS (default "360", e.g. "360,390,412,768"), ROLES (default all, e.g. "PATIENT,DOCTOR"), BROWSER_PATH (a Chrome or Edge .exe; default: Playwright's own).
// Demo accounts only, password Demo@12345. No real data is read or written.
import { chromium } from "playwright-core";

const BASE = process.env.BASE || "http://localhost:5173";
const API = process.env.API || "http://localhost:8000/api";
const WIDTHS = (process.env.WIDTHS || "360").split(",").map(Number);
const HEIGHT = 800;
const ACCOUNTS = { PATIENT: "rahul.patil", DOCTOR: "anjali.sharma", JUNIOR: "intern", EMPLOYEE: "priya.joshi", PHARMACY: "pharmacy", LAB: "lab", ADMIN: "admin", NURSE: "nurse", RADIOLOGY: "radiology.tech" };
export const ROUTES = {
  PATIENT: ["/patient", "/patient/assistant", "/patient/health-history", "/patient/reports", "/patient/bills", "/patient/history", "/patient/notes", "/patient/recommendations", "/patient/prescriptions", "/patient/appointments", "/patient/profile", "/emergency-card", "/change-password"],
  DOCTOR: ["/doctor", "/doctor/patients", "/doctor/appointments", "/doctor/queue", "/doctor/inpatients", "/doctor/emergency", "/doctor/referral-requests", "/doctor/beds", "/doctor/referrals", "/doctor/emergency-access", "/doctor/reports", "/doctor/notes", "/doctor/recommendations", "/doctor/prescriptions", "/doctor/countersign", "/doctor/profile"],
  JUNIOR: ["/trainee", "/trainee/take-history", "/trainee/referrals", "/trainee/profile"],
  EMPLOYEE: ["/employee", "/employee/patients", "/employee/opd", "/employee/emergency", "/employee/beds", "/employee/register", "/employee/upload", "/employee/appointments", "/employee/reports", "/employee/tests", "/employee/profile"],
  PHARMACY: ["/pharmacy", "/pharmacy/billing", "/pharmacy/bills", "/pharmacy/prescriptions", "/pharmacy/history", "/pharmacy/inventory", "/pharmacy/profile"],
  LAB: ["/lab", "/lab/approvals", "/lab/advised", "/lab/profile"],
  ADMIN: ["/admin", "/admin/users", "/admin/doctors", "/admin/employees", "/admin/pharmacy-staff", "/admin/lab-staff", "/admin/radiology-staff", "/admin/nurses", "/admin/integrations", "/admin/patients", "/admin/appointments", "/admin/reports", "/admin/audit-logs", "/admin/hospital", "/admin/settings", "/admin/beds", "/admin/profile"],
  NURSE: ["/nurse", "/nurse/emergency", "/nurse/beds"],
  RADIOLOGY: ["/radiology"],
};

/** Runs inside the page: what is wrong with this screen? */
function inspect() {
  const doc = document.documentElement;
  const vw = doc.clientWidth;
  const problems = [];
  if (doc.scrollWidth > vw) problems.push(`horizontal overflow: page is ${doc.scrollWidth}px wide on a ${vw}px screen`);

  const sideMenu = document.querySelector("aside");
  const inline = (el) => {                                   // a link inside a sentence is exempt, like in WCAG 2.2 (target size, inline)
    const p = el.parentElement;
    return el.tagName === "A" && p && ["P", "LI", "SPAN", "LABEL"].includes(p.tagName) && [...p.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
  };
  const seen = new Set();
  for (const el of document.querySelectorAll("a[href],button,select,textarea,summary,[role=button],input:not([type=hidden])")) {
    if (sideMenu && sideMenu.contains(el)) continue;         // the closed drawer is off screen
    const r = el.getBoundingClientRect();
    const style = getComputedStyle(el);
    if (style.visibility === "hidden" || style.display === "none" || r.width <= 2 || r.height <= 2) continue;   // hidden file inputs and the like
    if ((el.type === "checkbox" || el.type === "radio") && el.closest("label")?.getBoundingClientRect().height >= 44) continue;   // the whole label is the target
    if (inline(el)) continue;
    if (r.width < 44 || r.height < 44) {
      const name = (el.getAttribute("aria-label") || el.textContent || el.name || el.tagName).trim().replace(/\s+/g, " ").slice(0, 30);
      const key = `${name}|${Math.round(r.width)}x${Math.round(r.height)}`;
      if (!seen.has(key)) { seen.add(key); problems.push(`small tap target: "${name}" ${Math.round(r.width)}x${Math.round(r.height)}px`); }
    }
  }
  return problems;
}

async function login(role) {
  const res = await fetch(`${API}/auth/login`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ email: `${ACCOUNTS[role]}@healthwise.demo.com`, password: "Demo@12345" }) });
  if (!res.ok) throw new Error(`demo login for ${role} failed (${res.status}): is the backend running with the demo accounts?`);
  return (await res.json()).access_token;
}

const roles = (process.env.ROLES || Object.keys(ROUTES).join(",")).split(",");
const browser = await chromium.launch({ headless: true, ...(process.env.BROWSER_PATH ? { executablePath: process.env.BROWSER_PATH } : {}) });
const failures = [];
let checked = 0;
for (const role of roles) {
  const token = await login(role);
  for (const width of WIDTHS) {
    const context = await browser.newContext({ viewport: { width, height: HEIGHT }, hasTouch: true, isMobile: width < 768 });
    await context.addInitScript((t) => localStorage.setItem("healthwise_token", t), token);
    const page = await context.newPage();
    let errors = [];
    page.on("console", (m) => { if (m.type() === "error") errors.push(m.text().slice(0, 200)); });
    page.on("pageerror", (e) => errors.push(`uncaught: ${e.message.slice(0, 200)}`));
    for (const route of ROUTES[role]) {
      errors = [];
      try {
        await page.goto(BASE + route, { waitUntil: "networkidle", timeout: 30000 });
        await page.waitForTimeout(400);
        const problems = [...(await page.evaluate(inspect)), ...[...new Set(errors)].map((e) => `console error: ${e}`)];
        checked++;
        if (problems.length) failures.push({ role, width, route, problems });
      } catch (e) {
        failures.push({ role, width, route, problems: [`could not open: ${e.message.slice(0, 120)}`] });
      }
    }
    await context.close();
  }
}
await browser.close();

console.log(`Checked ${checked} screens (${roles.join(", ")} at ${WIDTHS.join(", ")} px).`);
for (const f of failures) console.log(`FAIL ${f.role} ${f.width}px ${f.route}\n  - ${f.problems.join("\n  - ")}`);
console.log(failures.length ? `\n${failures.length} screen(s) failed.` : "\nAll screens passed: no overflow, no small tap targets, no console errors.");
process.exit(failures.length ? 1 : 0);
