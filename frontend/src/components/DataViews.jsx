// Friendly building blocks that replace dense tables: avatars, person cards, date tiles, stock meters,
// and helpers that turn raw dates into words like "Today" or "2 hours ago".
import useAvatarUrl from "../hooks/useAvatarUrl";
import { ArrowRight, Clock, MessageSquareText } from "lucide-react";
import { StatusPill } from "./StatusBadge";

// ---------------------------------------------------------------- dates in words
const asUtc = (iso) => (iso && !/[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso + "Z" : iso);
const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate());

/** "Today", "Tomorrow", "Yesterday", or "Mon, 12 Oct 2026". Pass a Date or ISO text (local, not UTC). */
export function friendlyDay(value) {
  const d = new Date(value);
  const diff = Math.round((startOfDay(d) - startOfDay(new Date())) / 86400000);
  if (diff === 0) return "Today";
  if (diff === 1) return "Tomorrow";
  if (diff === -1) return "Yesterday";
  return d.toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short", year: "numeric" });
}

export const clockTime = (value) => new Date(value).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });

/** "just now", "5 minutes ago", "3 hours ago", "2 days ago". For times the server stored in UTC. */
export function timeAgo(utcIso) {
  if (!utcIso) return "never";
  const seconds = Math.max(0, (Date.now() - new Date(asUtc(utcIso)).getTime()) / 1000);
  if (seconds < 45) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} minute${minutes === 1 ? "" : "s"} ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days} day${days === 1 ? "" : "s"} ago`;
  return new Date(asUtc(utcIso)).toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

/** Local date of a UTC timestamp, as "YYYY-MM-DD" (used to group the activity feed by day). */
export const localDayKey = (utcIso) => {
  const d = new Date(asUtc(utcIso));
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

// ---------------------------------------------------------------- avatars and people
const AVATAR_TONES = ["from-brand-500 to-brand-700", "from-sky-400 to-blue-600", "from-emerald-400 to-emerald-600",
  "from-violet-400 to-violet-600", "from-amber-400 to-orange-500", "from-rose-400 to-rose-600"];

export function Avatar({ name: rawName, size = 48, userId, version, round }) {
  const name = rawName || "?";                         // a record without a name must not take the whole page down
  const picture = useAvatarUrl(userId, version);      // only people who have a photo (version is set) are fetched
  const shape = round ? "rounded-full" : "rounded-2xl";
  if (picture) {
    return <img src={picture} alt={`Photo of ${name}`} width={size} height={size} style={{ width: size, height: size }} className={`shrink-0 object-cover shadow ${shape}`} />;
  }
  const initials = name.replace(/^(dr\.?|mr\.?|mrs\.?|ms\.?)\s+/i, "").split(/\s+/).slice(0, 2).map((w) => w[0]?.toUpperCase()).join("");
  const tone = AVATAR_TONES[[...name].reduce((sum, c) => sum + c.charCodeAt(0), 0) % AVATAR_TONES.length];
  return (
    <span className={`flex shrink-0 items-center justify-center bg-gradient-to-br font-extrabold text-white shadow ${shape} ${tone}`}
      style={{ width: size, height: size, fontSize: size * 0.36 }} aria-label={name} role="img">{initials}</span>
  );
}

/** One person as a card: avatar, name, small facts as label/value pairs, optional buttons on the right. */
export function PersonCard({ name, subtitle, badge, facts = [], actions, muted, userId, avatarVersion }) {
  return (
    <div className={`flex flex-wrap items-center justify-between gap-4 rounded-3xl border border-slate-200/70 bg-white p-4 shadow-sm ${muted ? "opacity-60" : ""}`}>
      <div className="flex min-w-0 items-center gap-4">
        <Avatar name={name} userId={userId} version={avatarVersion} />
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-lg font-extrabold text-slate-900">{name}</p>
            {badge}
          </div>
          {subtitle && <p className="truncate text-sm text-slate-500">{subtitle}</p>}
          {facts.length > 0 && (
            <div className="mt-1.5 flex flex-wrap gap-x-5 gap-y-1 text-sm">
              {facts.map(([label, value]) => (
                <span key={label}><span className="text-slate-400">{label}: </span><span className="font-semibold text-slate-700">{value}</span></span>
              ))}
            </div>
          )}
        </div>
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

/** Whole days from today to a date: 0 = today, 1 = tomorrow, -1 = yesterday. */
export function daysFromToday(value) {
  return Math.round((startOfDay(new Date(value)) - startOfDay(new Date())) / 86400000);
}

/** A small chip that says how far away a date is ("Today", "Tomorrow", "In 5 days", "2 days ago"). */
export function CountdownChip({ days, overdueWord = "ago" }) {
  const [text, style] =
    days === 0 ? ["Today", "bg-emerald-100 text-emerald-800"]
    : days === 1 ? ["Tomorrow", "bg-sky-100 text-sky-800"]
    : days > 1 ? [`In ${days} days`, "bg-slate-100 text-slate-700"]
    : days === -1 ? [overdueWord === "ago" ? "Yesterday" : "1 day overdue", overdueWord === "ago" ? "bg-slate-100 text-slate-600" : "bg-red-100 text-red-800"]
    : [`${-days} days ${overdueWord === "ago" ? "ago" : "overdue"}`, overdueWord === "ago" ? "bg-slate-100 text-slate-600" : "bg-red-100 text-red-800"];
  return <span className={`inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-bold ${style}`}><Clock size={12} />{text}</span>;
}

/** Calendar tile: weekday, big day number, month. `tone` colours it (brand = upcoming, green = today, gray = done). */
export function DateTile({ value, tone = "brand", size = "lg" }) {
  const d = new Date(value);
  const tones = {
    brand: "bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow-md shadow-brand-500/30",
    green: "bg-gradient-to-br from-emerald-400 to-emerald-600 text-white shadow-md shadow-emerald-500/30",
    amber: "bg-gradient-to-br from-amber-400 to-orange-500 text-white shadow-md shadow-amber-500/30",
    gray: "bg-slate-100 text-slate-500", red: "bg-red-100 text-red-600",
  };
  const dims = size === "sm" ? "h-14 w-14" : "h-[76px] w-[76px]";
  return (
    <span className={`flex ${dims} shrink-0 flex-col items-center justify-center rounded-2xl ${tones[tone]}`}>
      <span className="text-xs font-bold uppercase tracking-wider opacity-90">{d.toLocaleDateString(undefined, { weekday: "short" })}</span>
      <span className={`${size === "sm" ? "text-xl" : "text-3xl"} font-extrabold leading-none`}>{d.getDate()}</span>
      <span className="text-xs font-bold uppercase tracking-wider opacity-90">{d.toLocaleDateString(undefined, { month: "short" })}</span>
    </span>
  );
}

/** Appointment as a card. `actions` are buttons shown on the right. */
export function AppointmentCard({ a, showPatient = true, actions }) {
  const days = daysFromToday(a.scheduled_at);
  const open = ["SCHEDULED", "CONFIRMED"].includes(a.status);
  const tone = a.status === "CANCELLED" ? "red" : a.status === "COMPLETED" ? "gray" : days === 0 ? "green" : "brand";
  const accent = { red: "bg-red-400", gray: "bg-slate-300", green: "bg-emerald-500", brand: "bg-brand-500" }[tone];
  return (
    <div className={`relative flex flex-wrap items-center justify-between gap-4 overflow-hidden rounded-3xl border border-slate-200/70 bg-white p-4 pl-6 shadow-sm ${a.status === "CANCELLED" ? "opacity-70" : ""}`}>
      <span className={`absolute inset-y-0 left-0 w-1.5 ${accent}`} />
      <div className="flex items-center gap-4">
        <DateTile value={a.scheduled_at} tone={tone} />
        <div className="space-y-2">
          {/* 1. WHEN: the time, big, and how far away it is */}
          <div className="flex flex-wrap items-center gap-2">
            <p className={`flex items-center gap-1.5 text-2xl font-extrabold ${a.status === "COMPLETED" ? "text-slate-500" : "text-slate-900"}`}>{clockTime(a.scheduled_at)}</p>
            {open && <CountdownChip days={days} />}
          </div>
          {/* 2. WHO: patient and doctor with avatars */}
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-sm">
            {showPatient && (
              <span className="inline-flex items-center gap-2">
                <Avatar name={a.patient_name} size={28} /><b className="text-slate-900">{a.patient_name}</b><span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs font-bold text-slate-500">{a.patient_code}</span>
              </span>
            )}
            <span className="inline-flex flex-wrap items-center gap-2 text-slate-600">
              {showPatient && <ArrowRight size={14} className="text-slate-300" />}
              <Avatar name={a.doctor_name} size={28} />{!showPatient && <span className="text-slate-400">with</span>}<b className="whitespace-nowrap text-slate-800">{a.doctor_name}</b>
              {a.department_name && <span className="rounded-full bg-sky-50 px-2 py-0.5 text-xs font-semibold text-sky-700">{a.department_name}</span>}
            </span>
          </div>
          {/* 3. WHY: the short reason, and what the patient said is happening (only the patient and the doctor receive these) */}
          {(a.reason || a.symptoms?.length > 0 || a.details) && (
            <div className="space-y-1.5 rounded-xl bg-slate-50 px-2.5 py-2 text-sm text-slate-700">
              {a.reason && <p className="flex items-start gap-1.5"><MessageSquareText size={15} className="mt-0.5 shrink-0 text-slate-400" /><b>{a.reason}</b>{a.duration ? <span className="text-slate-500"> - since {a.duration.toLowerCase()}</span> : null}</p>}
              {a.symptoms?.length > 0 && <p className="flex flex-wrap gap-1.5">{a.symptoms.map((s) => <span key={s} className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-bold text-amber-900">{s}</span>)}</p>}
              {a.details && <p className="text-slate-600">{a.details}</p>}
            </div>
          )}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <StatusPill value={a.status} />
        {actions}
      </div>
    </div>
  );
}

/** Stock level as a coloured bar, with plain words ("Running low", "Expires soon"). */
export function StockMeter({ quantity, max = 100 }) {
  const pct = Math.max(4, Math.min(100, (quantity / Math.max(max, 1)) * 100));
  const low = quantity <= 10;
  return (
    <div className="w-40">
      <div className="h-2.5 overflow-hidden rounded-full bg-slate-200">
        <div className={`h-full rounded-full ${low ? "bg-red-500" : quantity <= 30 ? "bg-amber-500" : "bg-emerald-500"}`} style={{ width: `${pct}%` }} />
      </div>
      <p className={`mt-1 text-sm font-bold ${low ? "text-red-700" : "text-slate-600"}`}>{quantity} in stock{low ? " - running low" : ""}</p>
    </div>
  );
}

/** Wrapper that groups items under headings ("Today", "Tomorrow" ...). groups: [{ title, items: [node] }] */
export function Grouped({ groups }) {
  return (
    <div className="space-y-6">
      {groups.map((g) => (
        <div key={g.title}>
          <p className="mb-2 text-sm font-extrabold uppercase tracking-wide text-slate-400">{g.title}</p>
          <div className="space-y-3">{g.items}</div>
        </div>
      ))}
    </div>
  );
}
