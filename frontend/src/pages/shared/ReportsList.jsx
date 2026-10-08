// List of reports for admin / employee / doctor. `pendingOnly` is used by the doctor's "Reports to Review" page.
import { useState } from "react";
import useFetch from "../../hooks/useFetch";
import { listReports } from "../../services/reportApi";
import { Section } from "../../components/HealthCard";
import { ReportsTable } from "../../components/Cards";
import { ErrorBox, Loading, PageTitle } from "../../components/Feedback";
import { inputClass } from "../../components/ui";

export default function ReportsList({ base, pendingOnly = false, title = "Reports", subtitle }) {
  const { data, loading, error, reload } = useFetch(() => listReports(), []);
  const [q, setQ] = useState("");
  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const needle = q.trim().toLowerCase();
  const rows = data
    .filter((r) => !pendingOnly || r.doctor_review_status === "PENDING")
    .filter((r) => !needle || r.patient_name.toLowerCase().includes(needle) || r.filename.toLowerCase().includes(needle) || r.patient_code.toLowerCase().includes(needle));
  return (
    <div className="space-y-5">
      <PageTitle title={title} subtitle={subtitle} />
      <input className={inputClass} placeholder="Filter by patient, patient ID or file name" value={q} onChange={(e) => setQ(e.target.value)} />
      <Section>
        {pendingOnly && rows.length === 0 ? <p className="py-4 text-center text-slate-500">No reports are waiting for review.</p> : <ReportsTable reports={rows} base={base} />}
      </Section>
    </div>
  );
}
