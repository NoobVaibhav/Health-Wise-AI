// Keyboard-only walk through the doctor's consultation and the pharmacy's dispensing screen (a tablet with an external keyboard).
// It presses Tab through the page and checks: every stop has a name, none is hidden under a fixed bar, a visible focus outline is drawn, the main buttons are
// reachable, and focus never gets trapped. Same setup and environment variables as mobile-layout.mjs. Demo accounts only; it reads, and writes nothing.
import { chromium } from "playwright-core";

const BASE = process.env.BASE || "http://localhost:5173", API = process.env.API || "http://localhost:8000/api";
const [width, height] = (process.env.VIEWPORT || "1024x768").split("x").map(Number);
const CASES = [
  { who: "anjali.sharma", route: process.env.CONSULTATION || "/doctor/consultation/14", must: ["Save draft", "Review and sign"] },
  { who: "pharmacy", route: process.env.DISPENSING || "/pharmacy/dispensing/8", must: ["Print / Download PDF"] },
];
const browser = await chromium.launch({ headless: true, ...(process.env.BROWSER_PATH ? { executablePath: process.env.BROWSER_PATH } : {}) });
let failed = 0;
for (const c of CASES) {
  const res = await fetch(`${API}/auth/login`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ email: `${c.who}@healthwise.demo.com`, password: "Demo@12345" }) });
  const token = (await res.json()).access_token;
  const context = await browser.newContext({ viewport: { width, height } });
  await context.addInitScript((t) => { localStorage.setItem("healthwise_token", t); sessionStorage.setItem("hw_launch_seen", "1"); }, token);
  const page = await context.newPage();
  await page.goto(BASE + c.route, { waitUntil: "networkidle" });
  await page.waitForFunction(() => !document.querySelector(".skeleton"), null, { timeout: 9000 }).catch(() => {});
  await page.waitForTimeout(600);
  await page.evaluate(() => document.activeElement?.blur());
  const stops = [], problems = [];
  for (let i = 0; i < 120; i++) {
    await page.keyboard.press("Tab");
    const s = await page.evaluate(() => {
      const el = document.activeElement;
      if (!el || el === document.body) return null;
      const r = el.getBoundingClientRect();
      const cs = getComputedStyle(el);
      const labelled = el.getAttribute("aria-labelledby") ? document.getElementById(el.getAttribute("aria-labelledby"))?.textContent : null;
      const name = (el.getAttribute("aria-label") || labelled || el.labels?.[0]?.textContent || el.textContent || el.getAttribute("placeholder") || el.name || "").trim().replace(/\s+/g, " ").slice(0, 40);
      const under = document.elementFromPoint(Math.min(Math.max(r.left + r.width / 2, 0), innerWidth - 1), Math.min(Math.max(r.top + r.height / 2, 0), innerHeight - 1));
      const visible = under && (el === under || el.contains(under) || under.contains(el));
      const outline = cs.outlineStyle !== "none" && parseFloat(cs.outlineWidth) > 0 || cs.boxShadow !== "none";
      return { name, tag: el.tagName, visible, outline, inView: r.bottom > 0 && r.top < innerHeight };
    });
    if (!s) break;
    stops.push(s);
    if (!s.name) problems.push(`stop ${i + 1} (${s.tag}) has no name`);
    if (!s.visible && s.inView) problems.push(`"${s.name}" is covered by something else when focused`);
    if (!s.outline) problems.push(`"${s.name}" shows no focus outline`);
  }
  for (const label of c.must) if (!stops.some((s) => s.name.includes(label))) problems.push(`"${label}" cannot be reached with Tab`);
  if (stops.length >= 120) problems.push("focus did not leave the page after 120 Tab presses (a trap?)");
  console.log(`${c.route} at ${width}x${height}: ${stops.length} tab stops, ${problems.length} problem(s)`);
  for (const p of [...new Set(problems)]) console.log("  - " + p);
  failed += problems.length;
  await context.close();
}
await browser.close();
process.exit(failed ? 1 : 0);
