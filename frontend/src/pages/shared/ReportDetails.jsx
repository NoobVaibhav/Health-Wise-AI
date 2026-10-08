// Report details for patient / employee / admin (the doctor uses ReportReview). The backend filters the content.
import { useParams } from "react-router-dom";
import useFetch from "../../hooks/useFetch";
import { useAuth } from "../../context/AuthContext";
import { getReport } from "../../services/reportApi";
import ReportView from "../../components/ReportView";
import { ErrorBox, Loading } from "../../components/Feedback";

export default function ReportDetails() {
  const { id } = useParams();
  const { user } = useAuth();
  const { data, loading, error, reload } = useFetch(() => getReport(id), [id]);
  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return <ReportView report={data} canOpenFile={user.role !== "ADMIN"} />;
}
