import { beforeEach, describe, expect, it, vi } from "vitest";

const h = vi.hoisted(() => ({ native: true, permission: "granted", pending: [], scheduled: [], cancelled: [], handlers: {}, channels: [] }));
vi.mock("@capacitor/core", () => ({ Capacitor: { isNativePlatform: () => h.native } }));
vi.mock("@capacitor/local-notifications", () => ({
  LocalNotifications: {
    checkPermissions: vi.fn(async () => ({ display: h.permission })),
    requestPermissions: vi.fn(async () => { if (h.permission === "prompt") h.permission = h.willAllow === false ? "denied" : "granted"; return { display: h.permission }; }),
    createChannel: vi.fn(async (c) => { h.channels.push(c); }),
    getPending: vi.fn(async () => ({ notifications: h.pending })),
    cancel: vi.fn(async ({ notifications }) => { h.cancelled.push(...notifications.map((n) => n.id)); h.pending = []; }),
    schedule: vi.fn(async ({ notifications }) => { h.scheduled = notifications; h.pending = notifications.map((n) => ({ id: n.id })); }),
    addListener: vi.fn(async (name, fn) => { h.handlers[name] = fn; return { remove: () => { delete h.handlers[name]; } }; }),
  },
}));
import { LocalNotifications } from "@capacitor/local-notifications";
import { REMINDER_URL, buildReminders, disableReminders, enableReminders, onReminderTap, reminderId, reminderText, remindersEnabled, syncReminders } from "./nativeNotifications";

// 06 Nov 2026, 10:00 on the hospital's clock (UTC+5:30) = 04:30 UTC
const NOW = new Date("2026-11-06T04:30:00Z");
const at = (hhmm, day = 6) => new Date(`2026-11-${String(day).padStart(2, "0")}T${hhmm}:00+05:30`);
const dose = (iso, status = "DUE") => ({ id: Math.random(), status, remind_at: iso });
const schedule = (over = {}) => ({ status: "ACTIVE", times: ["08:00", "20:00"], start_date: "2026-11-01", end_date: "2026-11-30", medicine: "Metformin", ...over });

beforeEach(() => {
  h.native = true; h.permission = "granted"; h.willAllow = true; h.pending = []; h.scheduled = []; h.cancelled = []; h.handlers = {}; h.channels = [];
  localStorage.clear();
  vi.clearAllMocks();
});

describe("which reminders are worked out", () => {
  it("today: only doses still due and still ahead; taken, skipped and past ones are left out; a snooze uses the new time", () => {
    const doses = [dose("2026-11-06T02:30:00Z", "DUE"), dose("2026-11-06T08:30:00Z", "DUE"), dose("2026-11-06T09:30:00Z", "TAKEN"), dose("2026-11-06T10:30:00Z", "SKIPPED"), dose("2026-11-06T14:30:00Z", "DUE")];
    const out = buildReminders({ doses, schedules: [], now: NOW });
    expect(out.map((r) => r.at.toISOString())).toEqual(["2026-11-06T08:30:00.000Z", "2026-11-06T14:30:00.000Z"]);        // the 08:00 one (02:30 UTC) is in the past
  });
  it("the next two days come from the confirmed schedules on the hospital's clock, within the dates of the course", () => {
    const out = buildReminders({ doses: [], schedules: [schedule()], now: NOW });
    expect(out.map((r) => r.at.getTime())).toEqual([at("08:00", 7), at("20:00", 7), at("08:00", 8), at("20:00", 8)].map((d) => d.getTime()));
    const ends = buildReminders({ doses: [], schedules: [schedule({ end_date: "2026-11-07" })], now: NOW });
    expect(ends).toHaveLength(2);                                                                                       // the course ends on the 7th: nothing on the 8th
    const starts = buildReminders({ doses: [], schedules: [schedule({ start_date: "2026-11-08" })], now: NOW });
    expect(starts).toHaveLength(2);                                                                                     // it starts on the 8th: nothing on the 7th
  });
  it("a schedule that is not confirmed (proposed, needs the person, stopped) never reminds", () => {
    for (const status of ["PROPOSED", "NEEDS_MANUAL", "STOPPED", "COMPLETED"]) expect(buildReminders({ schedules: [schedule({ status })], now: NOW })).toEqual([]);
  });
  it("two medicines at the same time are one reminder, and ids are whole numbers that stay the same for the same time", () => {
    const out = buildReminders({ schedules: [schedule(), schedule({ medicine: "Atorvastatin" })], now: NOW });
    expect(out).toHaveLength(4);
    expect(out.every((r) => Number.isInteger(r.id) && r.id > 0 && r.id < 2147483647)).toBe(true);
    expect(new Set(out.map((r) => r.id)).size).toBe(4);
    expect(buildReminders({ schedules: [schedule()], now: NOW }).map((r) => r.id)).toEqual(buildReminders({ schedules: [schedule()], now: NOW }).map((r) => r.id));
    expect(reminderId(at("08:00", 7))).toBe(Math.floor(at("08:00", 7).getTime() / 60000));
  });
  it("ignores a time that is not HH:MM, and a time only seconds away", () => {
    expect(buildReminders({ schedules: [schedule({ times: ["8am", "25", "08:00"] })], now: NOW })).toHaveLength(2);
    expect(buildReminders({ doses: [dose("2026-11-06T04:30:10Z")], now: NOW })).toEqual([]);
  });
  it("a different time zone on the phone changes nothing: the times are the hospital's", () => {
    const late = new Date("2026-11-06T18:30:00Z");                                                                     // 07 Nov, 00:00 in India
    const out = buildReminders({ schedules: [schedule()], now: late });
    expect(out[0].at.getTime()).toBe(at("08:00", 8).getTime());                                                        // today is the 7th: tomorrow is the 8th
  });
});

describe("the text", () => {
  it("is generic in all three languages and never holds a medicine name or a dose", () => {
    for (const language of ["en", "hi", "mr"]) {
      const t = reminderText(language);
      expect(t.title).toBeTruthy();
      expect(`${t.title} ${t.body}`).not.toMatch(/metformin|atorvastatin|\d\s*mg|tablet/i);
    }
    expect(reminderText("fr")).toEqual(reminderText("en"));
  });
});

describe("on the phone", () => {
  it("does nothing unless the person switched it on", async () => {
    expect(await syncReminders({ doses: [dose("2026-11-06T08:30:00Z")], schedules: [], now: NOW })).toBe(0);
    expect(LocalNotifications.schedule).not.toHaveBeenCalled();
  });
  it("asks permission only when switching on, remembers the choice and makes a private channel", async () => {
    h.permission = "prompt";
    expect(await enableReminders("en")).toBe("granted");
    expect(remindersEnabled()).toBe(true);
    expect(LocalNotifications.requestPermissions).toHaveBeenCalledTimes(1);
    expect(h.channels[0]).toMatchObject({ id: "medicine", visibility: 0, importance: 4 });                                // private on the lock screen
  });
  it("a 'no' to the permission leaves the reminders off", async () => {
    h.permission = "prompt"; h.willAllow = false;
    expect(await enableReminders("en")).toBe("denied");
    expect(remindersEnabled()).toBe(false);
    expect(await syncReminders({ doses: [dose("2026-11-06T08:30:00Z")], schedules: [], now: NOW })).toBe(0);
  });
  it("replaces everything scheduled before, with generic text, a deep link, and while-idle delivery", async () => {
    await enableReminders("hi");
    h.pending = [{ id: 11 }, { id: 12 }];
    const n = await syncReminders({ doses: [dose("2026-11-06T08:30:00Z")], schedules: [schedule()], language: "hi", now: NOW });
    expect(n).toBe(5);
    expect(h.cancelled).toEqual([11, 12]);
    expect(h.scheduled).toHaveLength(5);
    expect(h.scheduled[0]).toMatchObject({ title: reminderText("hi").title, body: reminderText("hi").body, channelId: "medicine", extra: { url: REMINDER_URL } });
    expect(h.scheduled[0].schedule).toMatchObject({ allowWhileIdle: true });
    expect(JSON.stringify(h.scheduled)).not.toMatch(/Metformin/);
  });
  it("with the Medicines category switched off in the settings, everything is removed and nothing scheduled", async () => {
    await enableReminders("en");
    await syncReminders({ doses: [dose("2026-11-06T08:30:00Z")], schedules: [], now: NOW });
    expect(h.pending).toHaveLength(1);
    expect(await syncReminders({ doses: [dose("2026-11-06T08:30:00Z")], schedules: [], enabled: false, now: NOW })).toBe(0);
    expect(h.pending).toHaveLength(0);
  });
  it("switching off removes the reminders already on the phone, and permission taken away stops new ones", async () => {
    await enableReminders("en");
    await syncReminders({ doses: [dose("2026-11-06T08:30:00Z")], schedules: [], now: NOW });
    expect(h.pending).toHaveLength(1);
    h.permission = "denied";
    expect(await syncReminders({ doses: [dose("2026-11-06T09:30:00Z")], schedules: [], now: NOW })).toBe(0);
    h.permission = "granted";
    await disableReminders();
    expect(remindersEnabled()).toBe(false);
    expect(h.pending).toHaveLength(0);
  });
  it("in a browser nothing runs", async () => {
    h.native = false;
    expect(await enableReminders("en")).toBe("unsupported");
    expect(await syncReminders({ doses: [dose("2026-11-06T08:30:00Z")], now: NOW })).toBe(0);
    expect(LocalNotifications.schedule).not.toHaveBeenCalled();
    const stop = onReminderTap(() => {});
    stop();
    expect(LocalNotifications.addListener).not.toHaveBeenCalled();
  });
});

describe("tapping a reminder", () => {
  it("opens the page named in it, and only a page inside the app", async () => {
    const handler = vi.fn();
    const stop = onReminderTap(handler);
    await Promise.resolve();
    const tap = h.handlers.localNotificationActionPerformed;
    tap({ notification: { extra: { url: "/patient/medicines" } } });
    tap({ notification: { extra: { url: "https://evil.example/x" } } });
    tap({ notification: { extra: { url: "//evil.example/x" } } });
    tap({ notification: { extra: {} } });
    tap({});
    expect(handler.mock.calls).toEqual([["/patient/medicines"]]);
    stop();
  });
});
