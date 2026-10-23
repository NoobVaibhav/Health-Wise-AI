// Shared pieces of the detailed past-history screens and printed sheet: where information came from, "Not recorded" labels, small layout helpers.
import { BadgeCheck, FileText, History as HistoryIcon, UserRound } from "lucide-react";
import { fmtUtc } from "../ui";

export const NOT_RECORDED = "Not recorded";
export const Nr = () => <i className="text-slate-400">{NOT_RECORDED}</i>;
export const show = (x) => (x === null || x === undefined || x === "" ? <Nr /> : x);

export const ANSWER = { YES: "Yes", NO: "No", UNKNOWN: "Not recorded" };
export const CONTROL = { GOOD: "Good", FAIR: "Fair", POOR: "Poor", UNKNOWN: "Not recorded" };
export const ADHERENCE = { REGULAR: "Takes regularly", SOMETIMES_MISSED: "Sometimes misses doses", OFTEN_MISSED: "Often misses doses", UNKNOWN: "Not recorded" };
export const ADMISSION_TYPE = { EMERGENCY: "Emergency", PLANNED: "Planned", REFERRAL: "Referral", OTHER: "Other" };
export const IMPLANT = { true: "Yes", false: "No" };
export const SOURCES = [["PATIENT_REPORTED", "Told by the patient"], ["DOCTOR_VERIFIED", "Checked by a doctor"], ["HOSPITAL_RECORD", "From a hospital record"]];

/** Where a record came from. "Checked by a doctor" also says who and when, so a reader can tell a patient's word from a verified fact. */
export function SourceBadge({ item, print }) {
  const verified = item.source === "DOCTOR_VERIFIED" && item.verified;
  const tone = verified ? "bg-emerald-50 text-emerald-800 ring-emerald-200" : item.source === "HOSPITAL_RECORD" ? "bg-sky-50 text-sky-800 ring-sky-200"
    : item.source === "EARLIER_ENTRY" ? "bg-slate-100 text-slate-600 ring-slate-200" : "bg-amber-50 text-amber-800 ring-amber-200";
  const Icon = verified ? BadgeCheck : item.source === "HOSPITAL_RECORD" ? FileText : item.source === "EARLIER_ENTRY" ? HistoryIcon : UserRound;
  const text = verified ? `Checked by ${item.verified_by_name || "a doctor"}${item.verified_at ? `, ${fmtUtc(item.verified_at).split(",")[0]}` : ""}` : item.source_label;
  if (print) return <span className="text-[10px] font-bold uppercase tracking-wide text-slate-600">[{verified ? "Checked by a doctor" : item.source === "HOSPITAL_RECORD" ? "Hospital record" : item.source === "EARLIER_ENTRY" ? "Entered earlier" : "Told by patient"}]</span>;
  return <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-bold ring-1 ${tone}`}><Icon size={13} />{text}</span>;
}

/** label + value row; shows "Not recorded" for an empty value unless `hideEmpty`. */
export const Fact = ({ label, children, hideEmpty, wide }) => {
  const empty = children === null || children === undefined || children === "" || children === false;
  if (empty && hideEmpty) return null;
  return (
    <div className="flex flex-col gap-0.5 py-1 sm:flex-row sm:gap-3">
      <dt className={`shrink-0 text-sm font-bold text-slate-500 ${wide ? "sm:w-56" : "sm:w-44"}`}>{label}</dt>
      <dd className="min-w-0 flex-1 whitespace-pre-line text-slate-900">{empty ? <Nr /> : children}</dd>
    </div>
  );
};

export const medLine = (m) => [m.name, m.dose, m.frequency, m.route].filter(Boolean).join(", ");
export const num = (x) => (x === "" || x === null || x === undefined ? null : Number(x));
export const blank = (x) => (typeof x === "string" ? (x.trim() === "" ? null : x.trim()) : x ?? null);

/** the whole stay as one readable line, e.g. "3 days 5 hours" or "Not recorded (discharge time missing)" */
export const stayText = (a) => (a.length_of_stay ? a.length_of_stay.text : a.admitted_at && !a.discharged_at ? "Not recorded (no discharge time)" : "Not recorded");
