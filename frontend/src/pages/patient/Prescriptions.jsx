import useFetch from "../../hooks/useFetch";
import { getMyPrescriptions } from "../../services/patientApi";
import PrescriptionList from "../../components/PrescriptionList";
import { EmptyState, ErrorBox, Loading, PageTitle } from "../../components/Feedback";

export default function PatientPrescriptions() {
  const { data, loading, error, reload } = useFetch(getMyPrescriptions);
  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return (
    <div className="space-y-5">
      <PageTitle title="My Medicines" subtitle="Medicines your doctor prescribed, and how much the pharmacy has given you" />
      {data.length === 0 ? <EmptyState message="No prescriptions yet." /> : <PrescriptionList items={data} variant="patient" />}
    </div>
  );
}
