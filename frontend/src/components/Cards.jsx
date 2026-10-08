// Cards that show doctor-written content. They always carry a visible "Doctor's ..." label.
import { Link } from "react-router-dom";
import { ChevronRight, ClipboardList, Pill, Stethoscope, StickyNote } from "lucide-react";
import { Avatar, CountdownChip, DateTile, daysFromToday } from "./DataViews";
import { StatusPill } from "./StatusBadge";
import { fmtDate, fmtUtc, fmtUtcDate } from "./ui";

// Left-edge colour tells the urgency at a glance: green = normal, amber = important, red = follow-up needed.
const ACCENT = { NORMAL: "bg-emerald-400", IMPORTANT: "bg-amber-400", FOLLOW_UP_REQUIRED: "bg-red-500" };

// Small "who is this about" chip with an avatar.
const PatientChip = ({ name }) => (
  <span className="inline-flex items-center gap-2 rounded-full bg-slate-100 py-1 pl-1 pr-3 text-sm font-semibold text-slate-700">
    <Avatar name={name} size={26} />{name}
  </span>
);

// Who wrote it and when, at the bottom of every doctor card.
const Signature = ({ doctor, when }) => (
  <p className="mt-4 flex items-center gap-2 border-t border-slate-100 pt-3 text-xs text-slate-500">
    <Avatar name={doctor} size={22} /> Written by <b className="text-slate-700">{doctor}</b> <span className="text-slate-300">|</span> {when}
  </p>
);

export function DoctorNoteCard({ note, showPatient }) {
  return (
    <div className="relative overflow-hidden rounded-3xl border border-slate-200/70 bg-white p-5 pl-6 shadow-sm">
      <span className={`absolute inset-y-0 left-0 w-1.5 ${ACCENT[note.priority] || ACCENT.NORMAL}`} />
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-400 to-emerald-600 text-white shadow"><StickyNote size={21} /></span>
          <p className="text-xs font-extrabold uppercase tracking-wider text-emerald-700">Doctor's Note</p>
        </div>
        <StatusPill value={note.priority} />
      </div>
      {showPatient && <div className="mt-3"><PatientChip name={note.patient_name} /></div>}
      <p className="mt-3 whitespace-pre-wrap text-[16px] leading-relaxed text-slate-800">{note.note}</p>
      <Signature doctor={note.doctor_name} when={fmtUtc(note.created_at)} />
    </div>
  );
}

export function RecommendationCard({ rec, showPatient }) {
  const days = rec.follow_up_date ? daysFromToday(rec.follow_up_date) : null;
  // The title and the description are often the same words: do not show them twice.
  const sameText = rec.recommendation.trim().toLowerCase() === rec.title.trim().toLowerCase();
  const followUpTone = days === null ? "brand" : days < 0 ? "red" : days === 0 ? "green" : "brand";
  return (
    <div className="relative overflow-hidden rounded-3xl border border-slate-200/70 bg-white p-5 pl-6 shadow-sm">
      <span className={`absolute inset-y-0 left-0 w-1.5 ${ACCENT[rec.priority] || ACCENT.NORMAL}`} />
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-400 to-emerald-600 text-white shadow"><Stethoscope size={21} /></span>
          <p className="text-xs font-extrabold uppercase tracking-wider text-emerald-700">Doctor's Recommendation</p>
        </div>
        <StatusPill value={rec.priority} />
      </div>

      <p className="mt-3 text-xl font-extrabold capitalize-first text-slate-900">{rec.title}</p>
      {showPatient && <div className="mt-2"><PatientChip name={rec.patient_name} /></div>}
      {!sameText && <p className="mt-3 whitespace-pre-wrap text-[15px] leading-relaxed text-slate-700">{rec.recommendation}</p>}

      {rec.follow_up_date && (
        <div className={`mt-4 flex items-center gap-4 rounded-2xl p-3 ${days < 0 ? "bg-red-50" : "bg-brand-50"}`}>
          <DateTile value={rec.follow_up_date} tone={followUpTone} size="sm" />
          <div>
            <p className="text-xs font-bold uppercase tracking-wider text-slate-500">Follow-up visit</p>
            <p className="text-[15px] font-extrabold text-slate-900">Come back on {new Date(rec.follow_up_date).toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" })}</p>
            <div className="mt-1"><CountdownChip days={days} overdueWord="overdue" /></div>
          </div>
        </div>
      )}
      <Signature doctor={rec.doctor_name} when={fmtUtcDate(rec.created_at)} />
    </div>
  );
}

export function PrescriptionCard({ rx, showPatient }) {
  return (
    <div className="rounded-3xl border border-slate-200/70 bg-white p-5 shadow-sm">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-3">
          <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-amber-400 to-orange-500 text-white"><Pill size={20} /></span>
          <div>
            <p className="font-extrabold text-slate-900">Prescription {rx.code}</p>
            <p className="text-xs text-slate-500">By {rx.doctor_name} on {fmtDate(rx.prescription_date)} - valid until {fmtDate(rx.valid_until)}</p>
          </div>
        </div>
        <StatusPill value={rx.status} />
      </div>
      {showPatient && <p className="mb-1 text-sm font-semibold text-slate-700">Patient: {rx.patient_name} ({rx.patient_code})</p>}
      {rx.clinical_indication && <p className="mb-2 text-sm text-slate-600">Reason: {rx.clinical_indication}</p>}
      <div className="space-y-2">
        {rx.items.map((i) => (
          <div key={i.id} className="flex flex-wrap items-center justify-between gap-2 rounded-2xl bg-slate-50 p-3">
            <div>
              <p className="font-bold text-slate-900">{i.medicine_name} <span className="font-medium text-slate-500">{i.dosage}</span></p>
              <p className="text-sm text-slate-600">{i.frequency} for {i.duration} - {i.quantity} to take in total</p>
              {i.instructions && <p className="text-sm text-slate-500">How: {i.instructions}</p>}
            </div>
            <div className="text-right">
              <StatusPill value={i.dispense_status} />
              <p className="mt-1 text-xs text-slate-500">{i.dispensed_quantity} of {i.quantity} given</p>
            </div>
          </div>
        ))}
      </div>
      {rx.notes && <p className="mt-2 text-sm text-slate-600">Doctor's remark: {rx.notes}</p>}
    </div>
  );
}

// Table of reports (used by employee, admin, doctor, patient). `base` is the role's URL prefix.
export function ReportsTable({ reports, base, showPatient = true }) {
  if (!reports.length) return <p className="py-4 text-center text-slate-500">No reports found.</p>;
  return (
    <div className="space-y-2">
      {reports.map((r) => (
        <Link key={r.id} to={`${base}/${r.id}`} className="tile flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-4">
          <div className="flex items-center gap-3">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-brand-50 text-brand-600"><ClipboardList size={22} /></span>
            <div>
              <p className="font-bold text-slate-900">{r.filename}</p>
              <p className="text-sm text-slate-500">
                {showPatient && <>{r.patient_name} ({r.patient_code}) - </>}{r.report_type_label.split(" (")[0]} - report date {fmtDate(r.report_date)}{r.parameter_count > 0 && ` - ${r.parameter_count} tests`} - uploaded by {r.uploaded_by_name}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <StatusPill value={r.display_status} />
            <ChevronRight className="text-slate-400" size={20} />
          </div>
        </Link>
      ))}
    </div>
  );
}
