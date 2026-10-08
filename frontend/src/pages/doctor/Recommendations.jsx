import useFetch from "../../hooks/useFetch";
import { getDoctorRecommendations } from "../../services/doctorApi";
import { RecommendationCard } from "../../components/Cards";
import { EmptyState, ErrorBox, Loading, PageTitle } from "../../components/Feedback";

export default function Recommendations() {
  const { data, loading, error, reload } = useFetch(getDoctorRecommendations);
  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return (
    <div className="space-y-5">
      <PageTitle title="Recommendations" subtitle="Recommendations you have given to patients" />
      {data.length === 0 ? <EmptyState message="You have not added any recommendations yet." /> : <div className="space-y-3">{data.map((r) => <RecommendationCard key={r.id} rec={r} showPatient />)}</div>}
    </div>
  );
}
