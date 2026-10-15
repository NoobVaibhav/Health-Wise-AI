import { useState } from "react";
import { Link } from "react-router-dom";
import { Pill, Search } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import { searchPrescriptions } from "../../services/pharmacyApi";
import { PrescriptionCard } from "../../components/Cards";
import { EmptyState, ErrorBox, Loading, PageTitle } from "../../components/Feedback";
import { Select, inputClass } from "../../components/ui";

export default function PharmacyPrescriptions() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const { data, loading, error, reload } = useFetch(() => searchPrescriptions(q, status), [q, status]);
  return (
    <div className="space-y-5">
      <PageTitle title="Prescriptions" subtitle="Step 1: find the patient. Step 2: press the big button on their prescription to give the medicine." icon={Pill} />
      <div className="flex flex-wrap gap-3">
        <div className="relative w-full max-w-md">
          <Search className="pointer-events-none absolute left-3.5 top-3.5 text-slate-500" size={20} />
          <input className={`${inputClass} pl-11`} placeholder="Type patient name, patient ID or RX code" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <div className="w-64"><Select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">Show all</option><option value="ACTIVE">Waiting for medicine</option><option value="PARTIALLY_DISPENSED">Partly given</option>
          <option value="DISPENSED">All medicine given</option><option value="EXPIRED">Expired</option></Select></div>
      </div>
      {loading && !data ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> : data.length === 0 ? <EmptyState message="No prescription found. Check the spelling or clear the search." /> : (
        <div className="space-y-3">
          {data.map((rx) => (
            <div key={rx.id}>
              <PrescriptionCard rx={rx} showPatient />
              <Link to={`/pharmacy/dispensing/${rx.id}`} className="mt-2 inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-xl border-2 border-brand-800 bg-brand-700 px-5 py-2.5 text-base font-bold text-white shadow-md hover:bg-brand-800 sm:w-auto">Open this prescription and give medicine →</Link>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
