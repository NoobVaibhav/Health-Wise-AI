// Finance reports: the day's cash by method and by person, who still owes money and for how long, and revenue by kind of service.
import { useState } from "react";
import { BarChart3 } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import { getDailyCash, getOutstanding, getRevenue } from "../../services/financeApi";
import { Section } from "../../components/HealthCard";
import { ErrorBox, Loading, PageTitle } from "../../components/Feedback";
import { Field, Input, Tabs } from "../../components/ui";

const rupee = (n) => `Rs ${Number(n || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
const today = () => new Date().toISOString().slice(0, 10);
const Stat = ({ label, value, tone = "" }) => <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"><p className="text-sm font-bold text-slate-500">{label}</p><p className={`text-2xl font-extrabold ${tone}`}>{value}</p></div>;

function Cash() {
  const [day, setDay] = useState(today());
  const { data, loading, error, reload } = useFetch(() => getDailyCash(day), [day]);
  return (
    <div className="space-y-4">
      <Field label="Day"><Input type="date" value={day} onChange={(e) => setDay(e.target.value)} /></Field>
      {loading && !data ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4"><Stat label="Collected" value={rupee(data.collected)} tone="text-emerald-700" /><Stat label="Refunds paid" value={rupee(data.refunds_paid)} tone="text-red-700" /><Stat label="Net cash" value={rupee(data.net)} /><Stat label="Invoices made final" value={data.invoices_final} /></div>
          <div className="grid gap-4 md:grid-cols-2">
            <Section title="By payment method">{Object.keys(data.by_method).length === 0 ? <p className="text-sm text-slate-500">Nothing collected.</p> : <ul className="divide-y text-sm">{Object.entries(data.by_method).map(([k, v]) => <li key={k} className="flex justify-between py-1.5"><span>{k}</span><b>{rupee(v)}</b></li>)}</ul>}</Section>
            <Section title="By person at the counter">{Object.keys(data.by_user).length === 0 ? <p className="text-sm text-slate-500">Nothing collected.</p> : <ul className="divide-y text-sm">{Object.entries(data.by_user).map(([k, v]) => <li key={k} className="flex justify-between py-1.5"><span>{k}</span><b>{rupee(v)}</b></li>)}</ul>}</Section>
          </div>
          <p className="text-sm text-slate-600">Insurer settlements today: {rupee(data.insurer_settlements)}. Paid from advances: {rupee(data.advance_used)}. These are not counter cash.</p>
        </>)}
    </div>
  );
}

function Outstanding() {
  const { data, loading, error, reload } = useFetch(getOutstanding);
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4"><Stat label="Total outstanding" value={rupee(data.total_outstanding)} tone="text-red-700" />{Object.entries(data.aging).map(([k, v]) => <Stat key={k} label={`${k} days`} value={rupee(v)} />)}</div>
      <Section title="Invoices with a balance">{data.invoices.length === 0 ? <p className="text-sm text-slate-500">Nothing is outstanding.</p> : (
        <div className="overflow-x-auto"><table className="w-full min-w-[34rem] text-left text-sm"><thead><tr className="border-b text-xs uppercase text-slate-500"><th className="py-1.5 pr-3">Invoice</th><th className="pr-3">Patient</th><th className="pr-3">Total</th><th className="pr-3">Balance</th><th className="pr-3">Days</th><th>Claim</th></tr></thead>
          <tbody>{data.invoices.map((i) => <tr key={i.invoice_id} className="border-b border-slate-100"><td className="py-1.5 pr-3 font-mono">{i.number}</td><td className="pr-3">{i.patient_name} ({i.patient_code})</td><td className="pr-3">{rupee(i.total)}</td><td className="pr-3 font-bold text-red-700">{rupee(i.balance)}</td><td className="pr-3">{i.age_days}</td><td>{i.claim_status ? i.claim_status.toLowerCase().replace("_", " ") : "-"}</td></tr>)}</tbody></table></div>)}</Section>
    </div>
  );
}

function Revenue() {
  const [range, setRange] = useState({ from: new Date(Date.now() - 30 * 864e5).toISOString().slice(0, 10), to: today() });
  const { data, loading, error, reload } = useFetch(() => getRevenue(range.from, range.to), [range.from, range.to]);
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-3"><Field label="From"><Input type="date" value={range.from} onChange={(e) => setRange({ ...range, from: e.target.value })} /></Field><Field label="To"><Input type="date" value={range.to} onChange={(e) => setRange({ ...range, to: e.target.value })} /></Field></div>
      {loading && !data ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> : (
        <>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3"><Stat label="Invoiced (after discounts)" value={rupee(data.invoiced_total)} /><Stat label="Discounts given" value={rupee(data.discounts_given)} /><Stat label="Pharmacy counter sales" value={`${rupee(data.pharmacy_sales.total)} (${data.pharmacy_sales.bills} bills)`} /></div>
          <Section title="By kind of service">{data.by_category.length === 0 ? <p className="text-sm text-slate-500">No final invoice in this period.</p> : <ul className="divide-y text-sm">{data.by_category.map((r) => <li key={r.category} className="flex justify-between py-1.5"><span>{r.category} ({r.lines} lines)</span><span>{rupee(r.amount)} + GST {rupee(r.tax)}</span></li>)}</ul>}</Section>
        </>)}
    </div>
  );
}

export default function FinanceReports() {
  return (
    <div className="space-y-5">
      <PageTitle title="Finance reports" subtitle="Cash, outstanding balances and revenue. Everything is read from the invoices and payments themselves." icon={BarChart3} />
      <Tabs tabs={[["cash", "Daily cash", <Cash />], ["out", "Outstanding", <Outstanding />], ["rev", "Revenue", <Revenue />]]} />
    </div>
  );
}
