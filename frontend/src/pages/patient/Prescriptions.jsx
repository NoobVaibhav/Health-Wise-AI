import { useState } from "react";
import { FileText } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import { getMyPrescriptions } from "../../services/patientApi";
import { PrescriptionCard } from "../../components/Cards";
import PrescriptionSheet from "../../components/PrescriptionSheet";
import { EmptyState, ErrorBox, Loading, PageTitle } from "../../components/Feedback";
import { Button } from "../../components/ui";
import { printAs } from "../../utils/printTitle";

export default function PatientPrescriptions() {
  const { data, loading, error, reload } = useFetch(getMyPrescriptions);
  const [openId, setOpenId] = useState(null);                 // one sheet at a time: only one thing can be on the paper
  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return (
    <div className="space-y-5">
      <PageTitle title="My Medicines" subtitle="Medicines your doctor prescribed, and how much the pharmacy has given you" />
      {data.length === 0 ? <EmptyState message="No prescriptions yet." /> : (
        <div className="space-y-3">
          {data.map((p) => (
            <div key={p.id}>
              <PrescriptionCard rx={p} />
              <Button type="button" variant="secondary" className="mt-2" aria-expanded={openId === p.id} onClick={() => setOpenId(openId === p.id ? null : p.id)}>
                <FileText size={18} className="mr-1 inline" /> {openId === p.id ? "Close the prescription" : "Open the prescription to print or download"}
              </Button>
              {openId === p.id && <div className="mt-3"><PrescriptionSheet rx={p} variant="patient" onPrint={() => printAs(p.patient_name, p.code, "Prescription")} /></div>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
