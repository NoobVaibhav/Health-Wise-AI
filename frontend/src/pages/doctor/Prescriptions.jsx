import useFetch from "../../hooks/useFetch";
import { cancelPrescription, listPrescriptions } from "../../services/prescriptionApi";
import { getErrorMessage } from "../../services/api";
import { PrescriptionCard } from "../../components/Cards";
import { EmptyState, ErrorBox, Loading, PageTitle } from "../../components/Feedback";

export default function DoctorPrescriptions() {
  const { data, loading, error, reload } = useFetch(() => listPrescriptions(), []);
  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const cancel = async (rx) => {
    if (!window.confirm(`Cancel prescription ${rx.code}? The pharmacy will no longer be able to dispense it.`)) return;
    try { await cancelPrescription(rx.id); reload(); } catch (e) { alert(getErrorMessage(e)); }
  };
  return (
    <div className="space-y-5">
      <PageTitle title="Prescriptions" subtitle="Prescriptions you have written (create new ones from a patient or report page)" />
      {data.length === 0 ? <EmptyState message="You have not written any prescriptions yet." /> : (
        <div className="space-y-3">
          {data.map((rx) => (
            <div key={rx.id}>
              <PrescriptionCard rx={rx} showPatient />
              {["ACTIVE", "PARTIALLY_DISPENSED"].includes(rx.status) && <button onClick={() => cancel(rx)} className="mt-1 text-sm text-red-600">Cancel prescription</button>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
