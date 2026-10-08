import { Ban, PackageCheck, PackageMinus } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import { getDispensingHistory } from "../../services/pharmacyApi";
import { Section } from "../../components/HealthCard";
import { StatusPill } from "../../components/StatusBadge";
import { clockTime, friendlyDay, localDayKey, timeAgo } from "../../components/DataViews";
import { EmptyState, ErrorBox, Loading, PageTitle } from "../../components/Feedback";

// Each line reads like a sentence: "4 of 10 Medicine A given to Rahul Patil".
export default function DispensingHistory() {
  const { data, loading, error, reload } = useFetch(getDispensingHistory);
  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;

  const groups = [];
  for (const d of data) {
    const key = localDayKey(d.dispensed_at);
    const last = groups[groups.length - 1];
    if (last && last.key === key) last.items.push(d); else groups.push({ key, items: [d] });
  }
  return (
    <div className="space-y-5">
      <PageTitle title="Medicine history" subtitle="Everything the pharmacy has given out, newest first" icon={PackageCheck} />
      {data.length === 0 ? <EmptyState message="Nothing has been given out yet" hint="When you give medicine from a prescription, it will be listed here." /> : (
        groups.map((g) => (
          <Section key={g.key} title={friendlyDay(g.key + "T12:00:00")}>
            <ul className="space-y-4">
              {g.items.map((d) => {
                const none = d.quantity_dispensed === 0;
                const Icon = none ? Ban : d.status === "DISPENSED" ? PackageCheck : PackageMinus;
                return (
                  <li key={d.id} className="flex items-start gap-3">
                    <span className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-white ${none ? "bg-red-500" : d.status === "DISPENSED" ? "bg-emerald-500" : "bg-amber-500"}`}><Icon size={17} /></span>
                    <div className="flex-1">
                      <p className="text-[15px] text-slate-700">
                        {none
                          ? <><b className="text-slate-900">{d.medicine_name}</b> was marked as <b>not in stock</b> for <b className="text-slate-900">{d.patient_name}</b></>
                          : <><b className="text-slate-900">{d.quantity_dispensed}</b> of {d.quantity_prescribed} <b className="text-slate-900">{d.medicine_name}</b> given to <b className="text-slate-900">{d.patient_name}</b></>}
                      </p>
                      <p className="text-xs text-slate-400">Prescription {d.prescription_code} - by {d.pharmacy_staff_name} - {clockTime(d.dispensed_at + "Z")} ({timeAgo(d.dispensed_at)})</p>
                      {d.notes && <p className="mt-0.5 text-sm text-slate-500">Note: {d.notes}</p>}
                    </div>
                    <StatusPill value={d.status} />
                  </li>
                );
              })}
            </ul>
          </Section>
        ))
      )}
    </div>
  );
}
