import useFetch from "../../hooks/useFetch";
import { listMyReferrals } from "../../services/traineeApi";
import { Section } from "../../components/HealthCard";
import { EmptyState, ErrorBox, Loading, PageTitle } from "../../components/Feedback";
import { fmtUtc } from "../../components/ui";

const TONE = { SENT: "bg-sky-100 text-sky-800", SEEN: "bg-amber-100 text-amber-800", COMPLETED: "bg-emerald-100 text-emerald-800" };

export function ReferralStatus({ r }) {
  return (
    <span className="inline-flex items-center gap-2">
      {r.urgent && <span className="rounded-full bg-red-100 px-2.5 py-1 text-xs font-bold text-red-700">URGENT</span>}
      <span className={`rounded-full px-2.5 py-1 text-xs font-bold ${TONE[r.status]}`}>{r.status_label}</span>
    </span>
  );
}

export default function MyReferrals() {
  const { data, loading, error, reload } = useFetch(listMyReferrals);
  return (
    <div className="space-y-5">
      <PageTitle title="My referrals" subtitle="Patients you sent to a doctor, and what happened next" />
      {loading ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> : data.length === 0 ? (
        <EmptyState message="You have not sent anybody yet" hint="Finish a history and choose a doctor, and the referral appears here." actionTo="/trainee/take-history" actionText="Take a history" />
      ) : (
        <Section>
          <ul className="divide-y">{data.map((r) => (
            <li key={r.id} className="space-y-1 py-3">
              <div className="flex flex-wrap items-center justify-between gap-2"><p><b>{r.patient_name}</b> <span className="text-sm text-slate-500">{r.patient_code}</span> to <b>{r.doctor_name}</b></p><ReferralStatus r={r} /></div>
              <p className="text-sm text-slate-600">{r.reason}</p>
              <p className="text-xs text-slate-500">Sent {fmtUtc(r.created_at)}{r.seen_at ? ` · seen ${fmtUtc(r.seen_at)}` : ""}{r.history_status === "VERIFIED" ? " · history verified by the doctor" : ""}{r.supervisor_note ? ` · supervisor: ${r.supervisor_note}` : ""}</p>
            </li>))}</ul>
        </Section>)}
    </div>
  );
}
