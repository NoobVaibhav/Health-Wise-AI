import { CheckCircle2, ClipboardList, Clock, PackageCheck, Pill, Package, History, ReceiptText } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import { getPharmacyDashboard } from "../../services/pharmacyApi";
import HealthCard, { Section } from "../../components/HealthCard";
import { Hero, HeroButton, QuickActions } from "../../components/Hero";
import { ErrorBox, Hint, Loading } from "../../components/Feedback";
import { fmtDate, greeting } from "../../components/ui";
import { useAuth } from "../../context/AuthContext";

export default function PharmacyDashboard() {
  const { user } = useAuth();
  const { data: d, loading, error, reload } = useFetch(getPharmacyDashboard);
  if (loading) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const open = d.pending_prescriptions + d.partially_dispensed;
  return (
    <div className="space-y-6">
      <Hero title={`${greeting()}, ${user.full_name}`} subtitle={open > 0 ? `${open} prescription${open === 1 ? "" : "s"} still need medicine given out.` : "No prescriptions are waiting right now."}>
        <HeroButton to="/pharmacy/billing" primary>Sell medicine and make a bill</HeroButton>
        <HeroButton to="/pharmacy/prescriptions">Give prescribed medicine</HeroButton>
        <HeroButton to="/pharmacy/inventory">Medicine stock</HeroButton>
      </Hero>

      <h2 className="text-xl font-extrabold text-slate-900">What do you want to do?</h2>
      <QuickActions items={[
        { to: "/pharmacy/billing", icon: ReceiptText, label: "Sell & make bill", hint: "Scan the barcode, take payment, print the bill" },
        { to: "/pharmacy/prescriptions", icon: ClipboardList, label: "Give medicine", hint: "Open a prescription and hand over the medicine" },
        { to: "/pharmacy/inventory", icon: Package, label: "Medicine stock", hint: "See what is on the shelf, add new stock" },
        { to: "/pharmacy/history", icon: History, label: "Medicine history", hint: "See what was already given" },
      ]} />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <HealthCard title="New prescriptions today" icon={ClipboardList} value={d.todays_prescriptions} />
        <HealthCard title="Waiting for medicine" icon={Clock} tone="amber" value={d.pending_prescriptions} />
        <HealthCard title="Partly given" icon={PackageCheck} tone="sky" value={d.partially_dispensed} />
        <HealthCard title="All medicine given" icon={CheckCircle2} tone="emerald" value={d.dispensed} />
      </div>

      <Hint title="Remember">You can only give medicine that a doctor has prescribed. You cannot change a prescription. If a medicine is out of stock, press "Not in stock" so the patient can see it.</Hint>

      <div className="grid gap-4 lg:grid-cols-2">
        <Section title="Running low (10 or fewer)">
          {d.low_stock.length === 0 ? <p className="text-base text-slate-600">Nothing is running low.</p> : <ul className="divide-y text-base">{d.low_stock.map((i) => <li key={i.id} className="flex justify-between py-2.5"><span>{i.medicine_name}</span><b className="text-red-600">{i.quantity} left</b></li>)}</ul>}
        </Section>
        <Section title="Expiring in 30 days">
          {d.expiring_soon.length === 0 ? <p className="text-base text-slate-600">Nothing is expiring soon.</p> : <ul className="divide-y text-base">{d.expiring_soon.map((i) => <li key={i.id} className="flex justify-between py-2.5"><span>{i.medicine_name} ({i.quantity})</span><b>{fmtDate(i.expiry_date)}</b></li>)}</ul>}
        </Section>
      </div>
    </div>
  );
}
