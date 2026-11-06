// Layout check for phones, tablets and desktop. Opens every main route of every demo role (patient and all staff roles) in a browser of each size, portrait and
// landscape, and FAILS on:
//   - horizontal overflow (the page is wider than the screen),
//   - a tap target smaller than 44 x 44 px (on touch sizes: phones and tablets, up to 1280 px wide),
//   - content hidden under a fixed bar at the bottom of the screen,
//   - a console error or an uncaught page error.
// It needs the backend (with the demo accounts) and the frontend dev server running:
//   cd backend && python -m uvicorn app.main:app --port 8000      (demo accounts: python -m app.seed_demo)
//   cd frontend && npm run dev                                    (http://localhost:5173)
//   cd frontend && npm run test:layout
// Settings (environment variables):
//   BASE (default http://localhost:5173)   API (default http://localhost:8000/api)
//   VIEWPORTS  default "360x800,412x915,768x1024,1024x768,820x1180,800x1280,1280x800,1440x900"; any list of WIDTHxHEIGHT
//   ROLES      default all, e.g. "PATIENT,DOCTOR"          WORKERS  roles run in parallel (default 3)
//   BROWSER_PATH  a Chrome or Edge .exe (default: Playwright's own browser)
// Demo accounts only, password Demo@12345. It reads pages; it writes nothing.
import { chromium } from "playwright-core";

const BASE = process.env.BASE || "http://localhost:5173";
const API = process.env.API || "http://localhost:8000/api";
const VIEWPORTS = (process.env.VIEWPORTS || "360x800,412x915,768x1024,1024x768,820x1180,800x1280,1280x800,1440x900").split(",").map((v) => v.split("x").map(Number));
const ACCOUNTS = {
  PATIENT: "rahul.patil", DOCTOR: "anjali.sharma", JUNIOR: "intern", EMPLOYEE: "priya.joshi", PHARMACY: "pharmacy", LAB: "lab", PATHOLOGIST: "pathologist",
  RADIOLOGY: "radiology.tech", NURSE: "nurse", ADMIN: "admin", STORE: "inventory", OT: "ot", BLOOD: "bloodbank", BILLING: "billing", ACCOUNTS: "accounts", TPA: "tpa",
};
export const ROUTES = {
  PATIENT: ["/patient", "/patient/assistant", "/patient/health-history", "/patient/reports", "/patient/bills", "/patient/history", "/patient/notes", "/patient/recommendations", "/patient/prescriptions", "/patient/appointments", "/patient/profile", "/emergency-card", "/change-password"],
  DOCTOR: ["/doctor", "/doctor/patients", "/doctor/appointments", "/doctor/queue", "/doctor/inpatients", "/doctor/emergency", "/doctor/referral-requests", "/doctor/beds", "/doctor/referrals", "/doctor/emergency-access", "/doctor/reports", "/doctor/notes", "/doctor/recommendations", "/doctor/prescriptions", "/doctor/countersign", "/doctor/profile"],
  JUNIOR: ["/trainee", "/trainee/take-history", "/trainee/referrals", "/trainee/profile"],
  EMPLOYEE: ["/employee", "/employee/patients", "/employee/opd", "/employee/emergency", "/employee/beds", "/employee/register", "/employee/upload", "/employee/appointments", "/employee/reports", "/employee/tests", "/employee/profile"],
  PHARMACY: ["/pharmacy", "/pharmacy/billing", "/pharmacy/bills", "/pharmacy/prescriptions", "/pharmacy/history", "/pharmacy/inventory", "/pharmacy/profile"],
  LAB: ["/lab", "/lab/approvals", "/lab/advised", "/lab/profile"],
  PATHOLOGIST: ["/lab", "/lab/approvals"],
  RADIOLOGY: ["/radiology", "/radiology/profile"],
  NURSE: ["/nurse", "/nurse/emergency", "/nurse/beds", "/nurse/profile", "/ward-requests"],
  ADMIN: ["/admin", "/admin/users", "/admin/doctors", "/admin/employees", "/admin/pharmacy-staff", "/admin/lab-staff", "/admin/radiology-staff", "/admin/nurses", "/admin/integrations", "/admin/patients", "/admin/appointments", "/admin/reports", "/admin/audit-logs", "/admin/hospital", "/admin/settings", "/admin/beds", "/admin/profile"],
  STORE: ["/stock", "/procurement"],
  OT: ["/ot"],
  BLOOD: ["/bloodbank", "/transfusions"],
  BILLING: ["/billing", "/claims"],
  ACCOUNTS: ["/finance-reports", "/billing"],
  TPA: ["/claims"],
};

const login = async (user) => {
  const res = await fetch(`${API}/auth/login`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ email: `${user}@healthwise.demo.com`, password: "Demo@12345" }) });
  if (!res.ok) throw new Error(`demo login for ${user} failed (${res.status}): is the backend running with the demo accounts?`);
  return (await res.json()).access_token;
};
const get = async (token, url) => { try { const r = await fetch(API + url, { headers: { Authorization: `Bearer ${token}` } }); return r.ok ? await r.json() : null; } catch { return null; } };

/** Pages that need an id (a patient, a visit, a prescription): the first ones found in the demo data. */
async function dynamicRoutes(role, token) {
  const out = [];
  if (role === "DOCTOR") {
    const patients = (await get(token, "/doctor/patients")) || [];
    if (patients[0]) out.push(`/doctor/patients/${patients[0].id}`, `/doctor/patients/${patients[0].id}/take-history`);
    for (let back = 0; back < 4 && out.filter((r) => r.includes("consultation")).length < 2; back++) {
      const day = new Date(Date.now() - back * 864e5).toISOString().slice(0, 10);
      for (const t of ((await get(token, `/opd/queue?day=${day}`)) || []).slice(0, 2)) out.push(`/doctor/consultation/${t.encounter_id}`);
    }
    const dash = await get(token, "/doctor/dashboard");
    if (dash?.reports_waiting?.[0]) out.push(`/doctor/reports/${dash.reports_waiting[0].id}`);
    for (const state of ["ADMITTED", "DISCHARGED"]) { const a = (await get(token, `/ipd/admissions?state=${state}`)) || []; if (a[0]) { out.push(`/doctor/inpatients/${a[0].id}`); break; } }
  }
  if (role === "NURSE") for (const state of ["ADMITTED", "DISCHARGED"]) { const a = (await get(token, `/ipd/admissions?state=${state}`)) || []; if (a[0]) { out.push(`/nurse/chart/${a[0].id}`); break; } }
  if (role === "PHARMACY") {
    const rx = (await get(token, "/pharmacy/prescriptions")) || [];
    const open = rx.find((r) => ["ACTIVE", "PARTIALLY_DISPENSED"].includes(r.status)) || rx[0];
    if (open) out.push(`/pharmacy/dispensing/${open.id}`);
  }
  if (role === "ADMIN" || role === "EMPLOYEE") { const reps = (await get(token, "/reports")) || []; if (reps[0]) out.push(`/${role.toLowerCase()}/reports/${reps[0].id}`); }
  return out;
}

/** Runs inside the page: what is wrong with this screen? */
function inspect(touch) {
  const doc = document.documentElement;
  const vw = doc.clientWidth;
  const vh = window.innerHeight;
  const rect = (el) => el.getBoundingClientRect();
  const problems = [];
  if (doc.scrollWidth > vw) problems.push(`horizontal overflow: page is ${doc.scrollWidth}px wide on a ${vw}px screen`);

  const sideMenu = document.querySelector("aside");
  const inline = (el) => {                                   // a link inside a sentence is exempt, like in WCAG 2.2 (target size, inline)
    const p = el.parentElement;
    return el.tagName === "A" && p && ["P", "LI", "SPAN", "LABEL"].includes(p.tagName) && [...p.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
  };
  if (touch) {
    const seen = new Set();
    for (const el of document.querySelectorAll("a[href],button,select,textarea,summary,[role=button],input:not([type=hidden])")) {
      if (sideMenu && sideMenu.contains(el)) continue;         // the closed drawer is off screen
      const r = rect(el);
      const style = getComputedStyle(el);
      if (style.visibility === "hidden" || style.display === "none" || r.width <= 2 || r.height <= 2) continue;   // hidden file inputs and the like
      if ((el.type === "checkbox" || el.type === "radio") && el.closest("label") && rect(el.closest("label")).height >= 44) continue;   // the whole label is the target
      if (inline(el)) continue;
      if (r.width < 44 || r.height < 44) {
        const name = (el.getAttribute("aria-label") || el.textContent || el.name || el.tagName).trim().replace(/\s+/g, " ").slice(0, 30);
        const key = `${name}|${Math.round(r.width)}x${Math.round(r.height)}`;
        if (!seen.has(key)) { seen.add(key); problems.push(`small tap target: "${name}" ${Math.round(r.width)}x${Math.round(r.height)}px`); }
      }
    }
  }
  // content hidden under a fixed bar: scroll to the end; the last thing on the page must end above the top of every bar fixed to the bottom
  window.scrollTo(0, 1e7);
  const bars = [...document.querySelectorAll("body *")].filter((e) => {
    if (getComputedStyle(e).position !== "fixed") return false;
    const r = rect(e);
    return r.height > 20 && r.height < 200 && r.bottom >= vh - 2 && r.width > vw * 0.5 && !(sideMenu && sideMenu.contains(e));
  });
  const main = document.querySelector("main");
  if (bars.length && main) {
    const top = Math.min(...bars.map((e) => rect(e).top));
    const clipped = (e) => { for (let a = e.parentElement; a && a !== main; a = a.parentElement) { const o = getComputedStyle(a); if (/(auto|scroll|hidden)/.test(o.overflowY) && a.getBoundingClientRect().bottom <= top + 1) return true; } return false; };   // things inside a scrolling or clipped box are not "under the bar"
    const last = [...main.querySelectorAll("*")].filter((e) => rect(e).height > 0 && !clipped(e)).map((e) => rect(e).bottom).sort((a, b) => b - a)[0] || 0;
    if (last > top + 2) problems.push(`content hidden under a fixed bar (${Math.round(last - top)}px)`);
  }
  window.scrollTo(0, 0);
  return problems;
}

const roles = (process.env.ROLES || Object.keys(ROUTES).join(",")).split(",");
const browser = await chromium.launch({ headless: true, ...(process.env.BROWSER_PATH ? { executablePath: process.env.BROWSER_PATH } : {}) });
const failures = [];
let checked = 0;

async function runRole(role) {
  const token = await login(ACCOUNTS[role]);
  const routes = [...ROUTES[role], ...(await dynamicRoutes(role, token))];
  for (const [width, height] of VIEWPORTS) {
    const touch = width <= 1280;                              // phones and tablets (a 1280 x 800 Android tablet is a tablet); 1440 and up is a desktop with a mouse
    const context = await browser.newContext({ viewport: { width, height }, hasTouch: touch, isMobile: width < 768 });
    await context.addInitScript((t) => { localStorage.setItem("healthwise_token", t); localStorage.setItem("hw_voice_notice", "yes"); sessionStorage.setItem("hw_launch_seen", "1"); }, token);   // the launch screen is a quick fade here: these checks are about the screens
    const page = await context.newPage();
    let errors = [];
    page.on("console", (m) => { if (m.type() === "error" && !/WebSocket connection to 'wss?:\/\/[^']*\?token=/.test(m.text())) errors.push(m.text().slice(0, 200)); });   // the dev server's own hot-reload socket is not the app's error
    page.on("pageerror", (e) => errors.push(`uncaught: ${e.message.slice(0, 200)}`));
    for (const route of routes) {
      errors = [];
      try {
        await page.goto(BASE + route, { waitUntil: "networkidle", timeout: 30000 });
        await page.waitForFunction(() => !document.querySelector(".skeleton") && !document.querySelector(".animate-spin"), null, { timeout: 9000 }).catch(() => {});
        await page.waitForTimeout(500);
        const problems = [...(await page.evaluate(inspect, touch)), ...[...new Set(errors)].map((e) => `console error: ${e}`)];
        checked++;
        if (problems.length) failures.push({ role, width, height, route, problems });
      } catch (e) {
        failures.push({ role, width, height, route, problems: [`could not open: ${e.message.slice(0, 120)}`] });
      }
    }
    await context.close();
  }
}

const queue = [...roles];
await Promise.all(Array.from({ length: Number(process.env.WORKERS || 3) }, async () => { while (queue.length) await runRole(queue.shift()); }));
await browser.close();

console.log(`Checked ${checked} screens (${roles.length} roles at ${VIEWPORTS.map((v) => v.join("x")).join(", ")}).`);
for (const f of failures) console.log(`FAIL ${f.role} ${f.width}x${f.height} ${f.route}\n  - ${f.problems.join("\n  - ")}`);
console.log(failures.length ? `\n${failures.length} screen(s) failed.` : "\nAll screens passed: no overflow, no small tap targets, nothing hidden under a bar, no console errors.");
process.exit(failures.length ? 1 : 0);
