// Integrations: what is really connected and what is not, the notification outbox, and the buttons that queue reminders and try to deliver what is waiting.
import { Plug } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import useSave from "../../hooks/useSave";
import api from "../../services/api";
import { Section } from "../../components/HealthCard";
import { ErrorBox, Loading, PageTitle } from "../../components/Feedback";
import { Button, fmtUtc } from "../../components/ui";

const get = (url) => api.get(url).then((r) => r.data);
const post = (url, body) => api.post(url, body ?? {}).then((r) => r.data);
const TONE = { READY: "bg-emerald-100 text-emerald-900", BUILT_UNVERIFIED: "bg-amber-100 text-amber-900", PARTIAL: "bg-sky-100 text-sky-900", ADAPTER_ONLY: "bg-violet-100 text-violet-900", NOT_BUILT: "bg-slate-200 text-slate-700" };
const LABEL = { READY: "Ready", BUILT_UNVERIFIED: "Built, not verified", PARTIAL: "Partly built", ADAPTER_ONLY: "Adapter only", NOT_BUILT: "Not built" };
const OUT = { QUEUED: "bg-amber-100 text-amber-900", SENT: "bg-emerald-100 text-emerald-900", FAILED: "bg-red-100 text-red-900" };

export default function Integrations() {
  const status = useFetch(() => get("/integrations/status"));
  const outbox = useFetch(() => get("/integrations/outbox"));
  const { problem, busy, run } = useSave();
  if ((status.loading && !status.data) || (outbox.loading && !outbox.data)) return <Loading />;
  if (status.error || outbox.error) return <ErrorBox message={status.error || outbox.error} onRetry={() => { status.reload(); outbox.reload(); }} />;
  return (
    <div className="space-y-5">
      <PageTitle title="Integrations" subtitle="Said plainly: what is connected, what only waits for a service, and what is not built." icon={Plug} />
      <Section title="Status">
        <ul className="divide-y">{status.data.map((i) => (
          <li key={i.key} className="flex flex-wrap items-start justify-between gap-2 py-2.5"><span><b>{i.name}</b><span className="block text-sm text-slate-600">{i.note}</span></span><span className={`rounded-full px-3 py-1 text-xs font-bold ${TONE[i.state]}`}>{LABEL[i.state]}</span></li>))}</ul>
      </Section>
      <Section title="Notification outbox" action={<span className="flex gap-2">
        <Button variant="secondary" disabled={busy} onClick={async () => { if (await run(() => post("/integrations/reminders/run", { hours_ahead: 24 }), "Reminders queued")) outbox.reload(); }}>Queue reminders (next 24 h)</Button>
        <Button disabled={busy} onClick={async () => { if (await run(() => post("/integrations/outbox/dispatch"), "Tried to deliver")) outbox.reload(); }}>Deliver what is waiting</Button></span>}>
        {problem && <ErrorBox message={problem} />}
        {outbox.data.length === 0 ? <p className="text-sm text-slate-500">The outbox is empty.</p> : (
          <div className="overflow-x-auto"><table className="w-full min-w-[34rem] text-left text-sm"><thead><tr className="border-b text-xs uppercase text-slate-500"><th className="py-1.5 pr-3">When</th><th className="pr-3">Channel</th><th className="pr-3">To</th><th className="pr-3">Message</th><th>Status</th></tr></thead>
            <tbody>{outbox.data.map((r) => <tr key={r.id} className="border-b border-slate-100 align-top"><td className="py-1.5 pr-3">{fmtUtc(r.created_at)}</td><td className="pr-3">{r.channel}</td><td className="pr-3">{r.address}</td><td className="pr-3">{r.subject}{r.error && <span className="block text-xs text-slate-500">{r.error}</span>}</td>
              <td><span className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${OUT[r.status]}`}>{r.status}</span></td></tr>)}</tbody></table></div>)}
      </Section>
    </div>
  );
}
