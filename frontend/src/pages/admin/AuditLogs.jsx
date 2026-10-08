// Activity log written as sentences ("Priya Joshi uploaded Report_A.pdf for Rahul Patil"), grouped by day,
// with plain-word filters. Nobody needs to know what "USER_CREATED" means.
import { useMemo, useState } from "react";
import {
  CalendarClock, ClipboardCheck, FileText, KeyRound, LogIn, Pill, Search, ShieldAlert, StickyNote, Stethoscope, UserPlus, UserCog, Eye,
} from "lucide-react";
import useFetch from "../../hooks/useFetch";
import { getAuditLogs } from "../../services/adminApi";
import { Section } from "../../components/HealthCard";
import { StatusPill } from "../../components/StatusBadge";
import { clockTime, friendlyDay, localDayKey, timeAgo } from "../../components/DataViews";
import { EmptyState, ErrorBox, Loading, PageTitle } from "../../components/Feedback";
import { inputClass } from "../../components/ui";

const ROLE_WORD = { DOCTOR: "a doctor", EMPLOYEE: "an employee", PHARMACY: "a pharmacy staff", "first admin": "the first administrator" };
const READ_WORD = { pdf_text: "the PDF text", ocr: "a scan or photo (OCR)", text: "a text file" };
const DECISION = { APPROVED: "and agreed with the computer's summary", MODIFIED: "and changed the computer's summary", CLARIFIED: "and added an explanation" };

// For every kind of action: which filter it belongs to, an icon, a colour, and how to write it as a sentence.
// `say(l)` returns [what they did, the thing it was done to].
const ACTIONS = {
  LOGIN: { cat: "Logins", icon: LogIn, tone: "bg-slate-400", say: () => ["logged in", null] },
  LOGIN_FAILED: { cat: "Logins", icon: ShieldAlert, tone: "bg-red-500", say: (l) => ["- someone tried to log in with a wrong password", l.details ? `for ${l.details}` : null], anonymous: true },
  USER_CREATED: { cat: "Accounts", icon: UserPlus, tone: "bg-sky-500", say: (l) => [`created ${ROLE_WORD[l.details] || "an"} account for`, l.entity_label] },
  USER_CHANGED: { cat: "Accounts", icon: UserCog, tone: "bg-sky-500", say: (l) => [l.details === "active=False" ? "deactivated the account of" : l.details === "active=True" ? "re-activated the account of" : "changed the account of", l.entity_label] },
  PATIENT_CREATED: { cat: "Accounts", icon: UserPlus, tone: "bg-sky-500", say: (l) => ["registered a new patient:", l.entity_label] },
  PATIENT_UPDATED: { cat: "Accounts", icon: UserCog, tone: "bg-sky-500", say: (l) => ["updated the details of", l.entity_label] },
  REPORT_UPLOADED: { cat: "Reports", icon: FileText, tone: "bg-brand-600", say: (l) => ["uploaded the report", l.entity_label] },
  REPORT_ANALYZED: { cat: "Reports", icon: FileText, tone: "bg-violet-500", say: (l) => { const m = /(\d+) parameters via (\w+)/.exec(l.details || ""); return [`- the computer read the report and found ${m ? m[1] : "some"} test results by reading ${m ? READ_WORD[m[2]] || m[2] : "it"}:`, l.entity_label]; }, computer: true },
  REPORT_REVIEWED: { cat: "Doctor work", icon: ClipboardCheck, tone: "bg-emerald-500", say: (l) => [`checked the report`, `${l.entity_label || ""} ${DECISION[l.details] || ""}`.trim()] },
  REPORT_FILE_VIEWED: { cat: "Reports", icon: Eye, tone: "bg-slate-400", say: (l) => ["opened the original file of", l.entity_label] },
  NOTE_ADDED: { cat: "Doctor work", icon: StickyNote, tone: "bg-emerald-500", say: (l) => ["wrote", l.entity_label] },
  RECOMMENDATION_ADDED: { cat: "Doctor work", icon: Stethoscope, tone: "bg-emerald-500", say: (l) => ["wrote", l.entity_label] },
  PRESCRIPTION_CREATED: { cat: "Doctor work", icon: Pill, tone: "bg-emerald-500", say: (l) => ["wrote", l.entity_label] },
  PRESCRIPTION_CANCELLED: { cat: "Doctor work", icon: Pill, tone: "bg-red-500", say: (l) => ["cancelled", l.entity_label] },
  PRESCRIPTION_VIEWED: { cat: "Medicines", icon: Eye, tone: "bg-amber-500", say: (l) => ["opened", l.entity_label] },
  MEDICINE_DISPENSED: { cat: "Medicines", icon: Pill, tone: "bg-amber-500", say: (l) => { const q = /qty (\d+)/.exec(l.details || ""); return [q && q[1] !== "0" ? `gave ${q[1]} unit${q[1] === "1" ? "" : "s"} of medicine for` : "marked a medicine as not in stock for", l.entity_label]; } },
  APPOINTMENT_CREATED: { cat: "Appointments", icon: CalendarClock, tone: "bg-indigo-500", say: (l) => ["booked an appointment:", l.entity_label] },
  APPOINTMENT_UPDATED: { cat: "Appointments", icon: CalendarClock, tone: "bg-indigo-500", say: (l) => [`changed an appointment${l.details ? ` to "${l.details.toLowerCase()}"` : ""}:`, l.entity_label] },
};

const CATEGORIES = ["All", "Logins", "Accounts", "Reports", "Doctor work", "Medicines", "Appointments"];

export default function AuditLogs() {
  const { data, loading, error, reload } = useFetch(() => getAuditLogs(), []);
  const [category, setCategory] = useState("All");
  const [q, setQ] = useState("");

  const sentences = useMemo(() => (data || []).map((l) => {
    const cfg = ACTIONS[l.action] || { cat: "All", icon: KeyRound, tone: "bg-slate-400", say: () => [l.action.toLowerCase().replaceAll("_", " "), l.entity_label] };
    let [did, what] = cfg.say(l);
    // no record name available (e.g. an older server): drop dangling words like "for" or ":" so the sentence still reads well
    if (!what) did = did.replace(/[:\s]+(for|of|to)?$/, "");
    const who = cfg.computer ? "The system" : l.user_name || "Someone";
    return { l, cfg, who, did, what, text: `${who} ${did} ${what || ""}`.toLowerCase() };
  }), [data]);

  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;

  const needle = q.trim().toLowerCase();
  const shown = sentences.filter((s) => (category === "All" || s.cfg.cat === category) && (!needle || s.text.includes(needle)));
  const groups = [];
  for (const s of shown) {
    const key = localDayKey(s.l.timestamp);
    const last = groups[groups.length - 1];
    if (last && last.key === key) last.items.push(s); else groups.push({ key, items: [s] });
  }

  return (
    <div className="space-y-5">
      <PageTitle title="Activity log" subtitle="A diary of what happened in the system, newest first. It cannot be edited." icon={KeyRound} />

      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-[240px] flex-1">
          <Search className="pointer-events-none absolute left-3.5 top-3 text-slate-400" size={18} />
          <input className={`${inputClass} pl-10`} placeholder="Search by name, patient or action" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        {CATEGORIES.map((c) => (
          <button key={c} onClick={() => setCategory(c)}
            className={`rounded-full px-3.5 py-1.5 text-sm font-semibold ${category === c ? "bg-brand-600 text-white shadow-sm" : "bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50"}`}>{c}</button>
        ))}
      </div>

      {shown.length === 0 ? <EmptyState message="Nothing to show" hint="No activity matches your filters yet." /> : (
        <div className="space-y-6">
          {groups.map((g) => (
            <Section key={g.key} title={friendlyDay(g.key + "T12:00:00")}>
              <ol className="space-y-4">
                {g.items.map(({ l, cfg, who, did, what }) => {
                  const Icon = cfg.icon;
                  return (
                    <li key={l.id} className="flex items-start gap-3">
                      <span className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-white ${cfg.tone}`}><Icon size={17} /></span>
                      <div className="min-w-0 flex-1">
                        <p className="text-[15px] leading-snug text-slate-700">
                          <b className="text-slate-900">{who}</b> {l.user_role && !cfg.computer && <span className="mr-1 align-middle"><StatusPill value={l.user_role} /></span>}
                          {did} {what && <b className="text-slate-900">{what}</b>}
                        </p>
                        <p className="text-xs text-slate-400">{clockTime(l.timestamp + "Z")} - {timeAgo(l.timestamp)}</p>
                      </div>
                    </li>
                  );
                })}
              </ol>
            </Section>
          ))}
        </div>
      )}
    </div>
  );
}
