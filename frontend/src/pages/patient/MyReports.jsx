import useFetch from "../../hooks/useFetch";
import { listReports } from "../../services/reportApi";
import { Section } from "../../components/HealthCard";
import { ReportsTable } from "../../components/Cards";
import { ErrorBox, Loading, PageTitle } from "../../components/Feedback";
import LabTestProgress from "../../components/LabTestProgress";
import RadiologyProgress from "../../components/RadiologyProgress";

export default function MyReports() {
  const { data, loading, error, reload } = useFetch(() => listReports(), []);
  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return (
    <div className="space-y-5">
      <PageTitle title="My Reports" subtitle="Your lab reports. Results appear here after your doctor has checked them." />
      <LabTestProgress base="/patient/reports" /><RadiologyProgress />
      <Section><ReportsTable reports={data} base="/patient/reports" showPatient={false} /></Section>
    </div>
  );
}
