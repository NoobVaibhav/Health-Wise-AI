// Coloured labels in plain language. Each has an icon too, so meaning never depends on colour alone.
import { ArrowDown, ArrowUp, CheckCircle2, Clock, HelpCircle, Minus, XCircle, AlertTriangle, TrendingDown, TrendingUp } from "lucide-react";

const GREEN = "bg-emerald-100 text-emerald-800";
const AMBER = "bg-amber-100 text-amber-900";
const BLUE = "bg-sky-100 text-sky-900";
const GRAY = "bg-slate-100 text-slate-700";
const RED = "bg-red-100 text-red-800";
const INDIGO = "bg-indigo-100 text-indigo-800";

const Pill = ({ icon: Icon, label, style }) => (
  <span className={`inline-flex max-w-full items-center gap-1 rounded-full px-3 py-1 text-sm font-bold leading-snug ${style}`}>
    {Icon && <Icon size={15} className="shrink-0" aria-hidden="true" />}
    {label}
  </span>
);

// Lab value status
const PARAM = {
  WITHIN_RANGE: ["Normal", GREEN, CheckCircle2],
  ABOVE_RANGE: ["Too high", AMBER, ArrowUp],
  BELOW_RANGE: ["Too low", BLUE, ArrowDown],
  UNKNOWN: ["No normal range", GRAY, HelpCircle],
};

export default function StatusBadge({ status }) {
  const [label, style, icon] = PARAM[status] || PARAM.UNKNOWN;
  return <Pill icon={icon} label={label} style={style} />;
}

// Workflow statuses (reports, appointments, prescriptions, roles ...)
const PILL = {
  WAITING_FOR_DOCTOR: ["Waiting for doctor to check", AMBER, Clock],
  DOCTOR_REVIEWED: ["Checked by doctor", GREEN, CheckCircle2],
  PENDING: ["Waiting", AMBER, Clock], REVIEWED: ["Checked", GREEN, CheckCircle2], ANALYZED: ["Read by computer", GREEN, CheckCircle2],
  SCHEDULED: ["Booked", BLUE, Clock], CONFIRMED: ["Confirmed", GREEN, CheckCircle2], COMPLETED: ["Done", GRAY, CheckCircle2], CANCELLED: ["Cancelled", RED, XCircle],
  ACTIVE: ["Ready to collect", GREEN, CheckCircle2], PARTIALLY_DISPENSED: ["Partly given", AMBER, Clock], DISPENSED: ["All medicine given", GREEN, CheckCircle2],
  EXPIRED: ["Expired", GRAY, XCircle], UNAVAILABLE: ["Not in stock", RED, XCircle],
  NORMAL: ["Normal", GRAY], IMPORTANT: ["Important", AMBER, AlertTriangle], FOLLOW_UP_REQUIRED: ["Follow-up needed", RED, AlertTriangle],
  APPROVED: ["Doctor agreed", GREEN, CheckCircle2], MODIFIED: ["Doctor changed it", AMBER], CLARIFIED: ["Doctor explained", BLUE],
  ADMIN: ["Admin", GRAY], DOCTOR: ["Doctor", BLUE], EMPLOYEE: ["Employee", GRAY], PATIENT: ["Patient", GREEN], PHARMACY: ["Pharmacy", AMBER], LAB: ["Laboratory", INDIGO], NURSE: ["Nurse", GREEN],
};

export function StatusPill({ value }) {
  const [label, style, icon] = PILL[value] || [String(value || "-").replaceAll("_", " "), GRAY];
  return <Pill icon={icon} label={label} style={style} />;
}

// Comparison trend
const TREND = {
  IMPROVED: ["Improved", GREEN, TrendingDown],
  STABLE: ["About the same", GRAY, Minus],
  INCREASED: ["Went up", INDIGO, TrendingUp],
  DECREASED: ["Went down", INDIGO, TrendingDown],
  STILL_OUTSIDE_RANGE: ["Still outside normal range", AMBER, AlertTriangle],
  REQUIRES_PROFESSIONAL_FOLLOW_UP: ["Please talk to your doctor", RED, AlertTriangle],
  UNABLE_TO_DETERMINE: ["Cannot compare", GRAY, HelpCircle],
};

export function TrendBadge({ trend }) {
  const [label, style, icon] = TREND[trend] || TREND.UNABLE_TO_DETERMINE;
  return <Pill icon={icon} label={label} style={style} />;
}
