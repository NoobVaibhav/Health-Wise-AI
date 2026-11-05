// Accessibility audit (axe-core) of the main screens in a phone-sized browser. Prints the violations per screen; exit code 1 if there are any
// "serious" or "critical" ones. Same setup and environment variables as mobile-layout.mjs; VIEWPORTS picks the sizes (default phone, iPad portrait and landscape). Demo accounts only.
import { chromium } from "playwright-core";
import { createRequire } from "module";
import fs from "fs";
const axeSource = fs.readFileSync(createRequire(import.meta.url).resolve("axe-core/axe.min.js"), "utf8");
const BASE = process.env.BASE || "http://localhost:5173", API = process.env.API || "http://localhost:8000/api";
const VIEWPORTS = (process.env.VIEWPORTS || "390x844,768x1024,1024x768").split(",").map((v) => v.split("x").map(Number));
const SCREENS = [
  [null, "/login"], ["rahul.patil", "/patient"], ["rahul.patil", "/patient/assistant"], ["rahul.patil", "/patient/reports"], ["rahul.patil", "/patient/appointments"], ["rahul.patil", "/patient/profile"],
  ["anjali.sharma", "/doctor"], ["anjali.sharma", "/doctor/patients"], ["priya.joshi", "/employee"], ["priya.joshi", "/employee/register"], ["pharmacy", "/pharmacy"], ["pharmacy", "/pharmacy/inventory"],
  ["lab", "/lab"], ["admin", "/admin"], ["admin", "/admin/users"], ["admin", "/admin/doctors"],
  ["anjali.sharma", "/doctor/consultation/14"], ["anjali.sharma", "/doctor/patients/17/take-history"], ["pharmacy", "/pharmacy/billing"], ["pharmacy", "/pharmacy/dispensing/8"], ["nurse", "/nurse"], ["inventory", "/stock"],
];
const browser = await chromium.launch({ headless: true, ...(process.env.BROWSER_PATH ? { executablePath: process.env.BROWSER_PATH } : {}) });
let serious = 0;
for (const [width, height] of VIEWPORTS) for (const [who, route] of SCREENS) {
  const context = await browser.newContext({ viewport: { width, height }, hasTouch: true, isMobile: width < 768 });
  if (who) {
    const res = await fetch(`${API}/auth/login`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ email: `${who}@healthwise.demo.com`, password: "Demo@12345" }) });
    await context.addInitScript((t) => localStorage.setItem("healthwise_token", t), (await res.json()).access_token);
  }
  const page = await context.newPage();
  await page.goto(BASE + route, { waitUntil: "networkidle" });
  await page.waitForFunction(() => !document.querySelector(".skeleton"), null, { timeout: 9000 }).catch(() => {});
  await page.waitForTimeout(900);
  await page.evaluate(axeSource);
  const result = await page.evaluate(() => window.axe.run(document, { runOnly: ["wcag2a", "wcag2aa", "wcag21aa", "best-practice"] }));
  const bad = result.violations.filter((v) => ["serious", "critical"].includes(v.impact));
  serious += bad.length;
  console.log(`${width}x${height} ${route.padEnd(34)} ${who || "(logged out)"}: ${result.violations.length} violation(s), ${bad.length} serious/critical`);
  for (const v of result.violations) console.log(`   [${v.impact}] ${v.id}: ${v.help} (${v.nodes.length}) e.g. ${v.nodes[0].target.join(" ").slice(0, 90)}`);
  await context.close();
}
await browser.close();
process.exit(serious ? 1 : 0);
