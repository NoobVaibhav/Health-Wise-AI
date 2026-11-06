// List of reports for admin / employee / doctor. `pendingOnly` is used by the doctor's "Reports to Review" page.
// The filtering is done by the server (before paging), so a waiting report is never hidden behind the first page.
import { useEffect, useState } from "react";
import usePagedFetch from "../../hooks/usePagedFetch";
import ShowMore from "../../components/ShowMore";
import { listReportsPage } from "../../services/reportApi";
import { Section } from "../../components/HealthCard";
import { ReportsTable } from "../../components/Cards";
import { ErrorBox, Loading, PageTitle } from "../../components/Feedback";
import { inputClass } from "../../components/ui";

export default function ReportsList({ base, pendingOnly = false, title = "Reports", subtitle }) {
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");           // the typed text, sent to the server a moment after the typing stops
  useEffect(() => { const t = setTimeout(() => setSearch(q), 250); return () => clearTimeout(t); }, [q]);
  const { data, total, loading, loadingMore, error, reload, loadMore, hasMore } = usePagedFetch(
    (offset) => listReportsPage({ needsReview: pendingOnly, q: search }, offset), [pendingOnly, search]);
  if (loading && !data) return <Loading />;
  if (error && !data) return <ErrorBox message={error} onRetry={reload} />;
  const rows = data || [];
  return (
    <div className="space-y-5">
      <PageTitle title={title} subtitle={subtitle} />
      <input className={inputClass} placeholder="Filter by patient, patient ID or file name" value={q} onChange={(e) => setQ(e.target.value)} />
      {error && <ErrorBox message={error} onRetry={reload} />}
      <Section>
        {pendingOnly && rows.length === 0 && !search ? <p className="py-4 text-center text-slate-500">No reports are waiting for review.</p> : <ReportsTable reports={rows} base={base} onChanged={reload} />}
        <ShowMore shown={rows.length} total={total} hasMore={hasMore} loading={loadingMore} onMore={loadMore} noun="reports" />
      </Section>
    </div>
  );
}
