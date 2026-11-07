// Medicine reminders that the PHONE itself shows, in the Android app (Capacitor local notifications). They are scheduled on the device from the patient's own medicine
// schedule, so they appear at the right time even when the app is closed or the phone has no connection. In a normal browser nothing here does anything.
//
// Privacy: the text is always generic ("Time for your medicine"). A medicine name, a dose or a doctor is never put in a notification, because a lock screen can be read by anyone
// near the phone. The channel is "private" on the lock screen. Reminders only help memory; they never change a prescription.
// Limit: the phone can only be told about doses the app knows. Doses for today come from the server (taken, skipped and snoozed ones are respected); the next two days are worked out
// from the confirmed schedules. Reminders are refreshed whenever the app is opened and every few minutes while it is open, so a day on which the app is never opened has no reminders
// beyond those already scheduled. Android may deliver a reminder a minute or two late to save battery (exact alarms need a special permission that is not requested).
import { Capacitor } from "@capacitor/core";
import { LocalNotifications } from "@capacitor/local-notifications";

const KEY = "hw_native_reminders";
const CHANNEL = "medicine";
const IST_MINUTES = 330;                                   // the hospital's clock (India has no daylight saving time)
const DAYS_AHEAD = 3;                                      // today and the two days after it
export const REMINDER_URL = "/patient/medicines";

const store = {
  get: () => { try { return localStorage.getItem(KEY); } catch { return null; } },
  set: (v) => { try { localStorage.setItem(KEY, v); } catch { /* storage may be blocked: the choice is then not remembered */ } },
};

export const isNativeApp = () => Capacitor.isNativePlatform();
export const remindersEnabled = () => store.get() === "yes";

// The words, in the languages of the app. The Hindi and Marathi wording must be checked by a native speaker before real use (see docs/NOTIFICATIONS.md).
const TEXT = {
  en: { title: "Time for your medicine", body: "Open HealthWise AI to mark it as taken.", channel: "Medicine reminders" },
  hi: { title: "आपकी दवा का समय हो गया है", body: "लेने के बाद HealthWise AI खोलकर निशान लगाइए।", channel: "दवा के रिमाइंडर" },
  mr: { title: "तुमच्या औषधाची वेळ झाली आहे", body: "घेतल्यानंतर HealthWise AI उघडून खूण करा.", channel: "औषधाचे रिमाइंडर" },
};
export const reminderText = (language) => TEXT[language] || TEXT.en;

const pad = (n) => String(n).padStart(2, "0");
/** The date (yyyy-mm-dd) on the hospital's clock at an instant. */
const istDate = (instant) => { const d = new Date(instant.getTime() + IST_MINUTES * 60000); return `${d.getUTCFullYear()}-${pad(d.getUTCMonth() + 1)}-${pad(d.getUTCDate())}`; };
/** The instant of "HH:MM" on a hospital-clock date. */
const istInstant = (date, hhmm) => { const [y, m, d] = date.split("-").map(Number); const [h, min] = hhmm.split(":").map(Number); return new Date(Date.UTC(y, m - 1, d, h, min) - IST_MINUTES * 60000); };
const addDays = (date, n) => { const [y, m, d] = date.split("-").map(Number); const t = new Date(Date.UTC(y, m - 1, d + n)); return `${t.getUTCFullYear()}-${pad(t.getUTCMonth() + 1)}-${pad(t.getUTCDate())}`; };
/** A whole number for Android (a notification needs one): the minute of the reminder since 1970, which is unique per reminder time and the same every time it is worked out. */
export const reminderId = (instant) => Math.floor(instant.getTime() / 60000);

/** The reminders to schedule: [{ id, at, url }], soonest first, one per distinct minute.
 *  doses: today's doses from the server ({ remind_at, status }); schedules: the patient's schedules ({ status, times, start_date, end_date }); now: a Date. */
export function buildReminders({ doses = [], schedules = [], now = new Date(), days = DAYS_AHEAD } = {}) {
  const horizon = new Date(now.getTime() + 20000);                              // a time that is only seconds away is not scheduled
  const found = new Map();
  const add = (instant) => { if (instant > horizon) found.set(reminderId(instant), instant); };
  for (const dose of doses) {                                                   // today: the server knows what was taken, skipped or snoozed
    if (dose.status === "DUE" && dose.remind_at) add(new Date(dose.remind_at));
  }
  const today = istDate(now);
  for (let offset = 1; offset < days; offset += 1) {                            // the next days: worked out from the confirmed schedules
    const date = addDays(today, offset);
    for (const s of schedules) {
      if (s.status !== "ACTIVE" || !Array.isArray(s.times)) continue;
      if ((s.start_date && date < s.start_date) || (s.end_date && date > s.end_date)) continue;
      for (const hhmm of s.times) if (/^\d{2}:\d{2}$/.test(hhmm)) add(istInstant(date, hhmm));
    }
  }
  return [...found.entries()].sort((a, b) => a[0] - b[0]).map(([id, at]) => ({ id, at, url: REMINDER_URL }));
}

// ------------------------------------------------------------------ the phone
/** "unsupported" (not the Android app), "granted", "denied" or "prompt". */
export async function permissionState() {
  if (!isNativeApp()) return "unsupported";
  try { const r = await LocalNotifications.checkPermissions(); return r.display || "prompt"; } catch { return "unsupported"; }
}

async function ensureChannel(language) {
  try {
    await LocalNotifications.createChannel({ id: CHANNEL, name: reminderText(language).channel, importance: 4, visibility: 0, vibration: true });   // visibility 0: private on the lock screen
  } catch { /* a phone without channels (old Android) still shows the notifications */ }
}

async function cancelAll() {
  try {
    const { notifications } = await LocalNotifications.getPending();
    if (notifications?.length) await LocalNotifications.cancel({ notifications: notifications.map((n) => ({ id: n.id })) });
  } catch { /* nothing pending, or not available */ }
}

/** Asks the person (the page has already explained why) and, when they agree, switches the reminders on. Returns the permission state. */
export async function enableReminders(language = "en") {
  if (!isNativeApp()) return "unsupported";
  let state = await permissionState();
  if (state !== "granted") {
    try { state = (await LocalNotifications.requestPermissions()).display || "denied"; } catch { state = "denied"; }
  }
  if (state === "granted") { store.set("yes"); await ensureChannel(language); }
  return state;
}

/** Switches the reminders off and removes the ones already scheduled on the phone. */
export async function disableReminders() {
  store.set("no");
  if (isNativeApp()) await cancelAll();
}

/** Puts the phone's reminders in line with the schedule: everything scheduled before is replaced. Does nothing unless the person switched reminders on and allowed notifications.
 *  Returns how many reminders are now scheduled (0 when off, not allowed or nothing is due). */
export async function syncReminders({ doses, schedules, language = "en", enabled = true, now = new Date() } = {}) {
  if (!isNativeApp() || !remindersEnabled()) return 0;
  if ((await permissionState()) !== "granted") return 0;
  await cancelAll();
  if (!enabled) return 0;                                                       // the person switched the "Medicines" category off in the notification settings
  const reminders = buildReminders({ doses, schedules, now });
  if (!reminders.length) return 0;
  await ensureChannel(language);
  const text = reminderText(language);
  await LocalNotifications.schedule({
    notifications: reminders.map((r) => ({ id: r.id, title: text.title, body: text.body, channelId: CHANNEL, schedule: { at: r.at, allowWhileIdle: true }, extra: { url: r.url } })),
  });
  return reminders.length;
}

/** Calls handler(path) when the person taps a reminder. Only a path inside the app is passed on. Returns a function that stops listening. */
export function onReminderTap(handler) {
  if (!isNativeApp()) return () => {};
  let handle = null;
  let stopped = false;
  LocalNotifications.addListener("localNotificationActionPerformed", (event) => {
    const url = event?.notification?.extra?.url;
    if (typeof url === "string" && url.startsWith("/") && !url.startsWith("//")) handler(url);
  }).then((h) => { if (stopped) h.remove(); else handle = h; }).catch(() => {});
  return () => { stopped = true; handle?.remove?.(); };
}
