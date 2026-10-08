import useFetch from "../../hooks/useFetch";
import { getMyNotes } from "../../services/patientApi";
import { DoctorNoteCard } from "../../components/Cards";
import { EmptyState, ErrorBox, Loading, PageTitle } from "../../components/Feedback";

export default function PatientNotes() {
  const { data, loading, error, reload } = useFetch(getMyNotes);
  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return (
    <div className="space-y-5">
      <PageTitle title="Doctor's Notes" subtitle="Messages written by your doctor. They are read-only." />
      {data.length === 0 ? <EmptyState message="No notes from your doctor yet." /> : <div className="space-y-3">{data.map((n) => <DoctorNoteCard key={n.id} note={n} />)}</div>}
    </div>
  );
}
