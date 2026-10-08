import { useState } from "react";
import { Link } from "react-router-dom";
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
      <PageTitle title="Prescriptions" subtitle="Search by prescription code (RX-00001), patient name or patient ID" />
      <div className="flex flex-wrap gap-3">
        <input className={`${inputClass} max-w-md`} placeholder="Search prescriptions" value={q} onChange={(e) => setQ(e.target.value)} />
        <div className="w-56"><Select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option><option value="ACTIVE">Active (pending)</option><option value="PARTIALLY_DISPENSED">Partially dispensed</option>
          <option value="DISPENSED">Dispensed</option><option value="EXPIRED">Expired</option></Select></div>
      </div>
      {loading && !data ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> : data.length === 0 ? <EmptyState message="No active prescription found." /> : (
        <div className="space-y-3">
          {data.map((rx) => (
            <div key={rx.id}>
              <PrescriptionCard rx={rx} showPatient />
              <Link to={`/pharmacy/dispensing/${rx.id}`} className="mt-1 inline-block text-sm font-medium text-brand-700">Open and dispense →</Link>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
