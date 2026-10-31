// On the doctor's patient page: the histories interns and PG students took for this patient ("Taken by ... pending doctor review").
import useFetch from "../hooks/useFetch";
import { listPatientTraineeHistories } from "../services/traineeApi";
import { Section } from "./HealthCard";
import TraineeHistoryView from "./TraineeHistoryView";

export default function TraineeHistories({ patientId }) {
  const { data } = useFetch(() => listPatientTraineeHistories(patientId), [patientId]);
  if (!data || data.length === 0) return null;                    // nothing to show, and a failed load must not block the page
  return (
    <Section title="Histories taken by interns and PG students">
      <div className="space-y-4 divide-y">
        {data.map((h) => <div key={h.id} className="pt-4 first:pt-0"><TraineeHistoryView history={h} /></div>)}
      </div>
    </Section>
  );
}
