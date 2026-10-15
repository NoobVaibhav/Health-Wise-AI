// "Tests advised by doctors": the list laboratory staff and hospital employees use to see which tests a patient must get done.
// The pharmacy never sees this list (the backend does not send it to them).
import { useState } from "react";
import { FlaskConical, Search, User } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import { getTestOrders } from "../../services/labApi";
import { EmptyState, ErrorBox, Hint, Loading, PageTitle } from "../../components/Feedback";
import { fmtDate, inputClass } from "../../components/ui";

export default function TestOrders() {
  const [q, setQ] = useState("");
  const { data, loading, error, reload } = useFetch(() => getTestOrders(q), [q]);
  return (
    <div className="space-y-5">
      <PageTitle title="Tests to do" subtitle="Tests the doctors have asked for, newest first. Find a patient, then see which tests they need." icon={FlaskConical} />
      <div className="relative w-full max-w-xl">
        <Search className="pointer-events-none absolute left-3.5 top-3.5 text-slate-500" size={20} />
        <input className={`${inputClass} pl-11`} placeholder="Type patient name, patient ID, RX code or test name" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      {loading && !data ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> : data.length === 0 ? (
        <EmptyState message={q ? "No test matches your search" : "No tests have been advised yet"} hint={q ? "Check the spelling or clear the search." : "When a doctor advises a test, it will appear here."} icon={FlaskConical} />
      ) : (
        <div className="space-y-3">
          {data.map((o) => (
            <div key={o.id} className="rounded-3xl border-2 border-brand-200 bg-white p-5 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="flex items-center gap-3">
                  <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-400 to-violet-600 text-white"><User size={22} /></span>
                  <div>
                    <p className="text-lg font-extrabold text-slate-900">{o.patient_name} <span className="font-semibold text-slate-500">({o.patient_code})</span></p>
                    <p className="text-base text-slate-600">Advised by {o.doctor_name} on {fmtDate(o.date)} - {o.code}</p>
                  </div>
                </div>
              </div>
              {o.reason && <p className="mt-2 text-base text-slate-700">Reason: {o.reason}</p>}
              <p className="mt-3 text-sm font-bold text-slate-600">Tests to get done ({o.tests.length})</p>
              <ul className="mt-1 flex flex-wrap gap-2">
                {o.tests.map((t) => (
                  <li key={t} className="inline-flex items-center gap-1.5 rounded-full border-2 border-brand-300 bg-brand-100 px-3.5 py-1.5 text-base font-bold text-brand-900"><FlaskConical size={16} /> {t}</li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      )}
      <Hint title="Please note">This list only shows which tests the doctor asked for. Medicines are not shown here.</Hint>
    </div>
  );
}
