import useFetch from "../../hooks/useFetch";
import { getMyRecommendations } from "../../services/patientApi";
import { RecommendationCard } from "../../components/Cards";
import { EmptyState, ErrorBox, Loading, PageTitle } from "../../components/Feedback";

export default function PatientRecommendations() {
  const { data, loading, error, reload } = useFetch(getMyRecommendations);
  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return (
    <div className="space-y-5">
      <PageTitle title="Doctor's Advice" subtitle="What your doctor suggests you do next" />
      {data.length === 0 ? <EmptyState message="No recommendations yet." /> : <div className="space-y-3">{data.map((r) => <RecommendationCard key={r.id} rec={r} />)}</div>}
    </div>
  );
}
