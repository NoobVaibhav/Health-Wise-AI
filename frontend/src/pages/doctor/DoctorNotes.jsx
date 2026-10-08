import useFetch from "../../hooks/useFetch";
import { getDoctorNotes } from "../../services/doctorApi";
import { DoctorNoteCard } from "../../components/Cards";
import { EmptyState, ErrorBox, Loading, PageTitle } from "../../components/Feedback";

export default function DoctorNotes() {
  const { data, loading, error, reload } = useFetch(getDoctorNotes);
  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return (
    <div className="space-y-5">
      <PageTitle title="Doctor Notes" subtitle="Notes you have written (add new notes from a patient or report page)" />
      {data.length === 0 ? <EmptyState message="You have not written any notes yet." /> : <div className="space-y-3">{data.map((n) => <DoctorNoteCard key={n.id} note={n} showPatient />)}</div>}
    </div>
  );
}
