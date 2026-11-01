// Blood bank: stock, requests from doctors (cross-match, issue, verify), donors and collection, and screening of donations.
// Different people do the paired steps: collect and screen, issue and verify. Only compatible, in-date units can be matched.
import { useState } from "react";
import { Droplets } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import useSave from "../../hooks/useSave";
import { addDonor, collectBlood, crossmatch, discardUnit, getBloodRequests, getBloodRules, getBloodStock, getBloodUnits, getCandidates, getDonations, getDonors, issueBlood, rejectBloodRequest, returnBlood, screenDonation, verifyIssue } from "../../services/operationsApi";
import { Section } from "../../components/HealthCard";
import { EmptyState, ErrorBox, Hint, Loading, PageTitle } from "../../components/Feedback";
import { Button, Field, Input, Select, Tabs, fmtUtc } from "../../components/ui";

const GROUPS = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"];
const COMPONENTS = [["PRBC", "Red cells"], ["WHOLE_BLOOD", "Whole blood"], ["FFP", "Plasma"], ["PLATELETS", "Platelets"]];
const label = (c) => COMPONENTS.find(([k]) => k === c)?.[1] || c;

function Stock() {
  const { data, loading, error, reload } = useFetch(getBloodStock);
  const rules = useFetch(getBloodRules);
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return (
    <div className="space-y-4">
      <Section title="Units in stock">
        {data.length === 0 ? <p className="text-sm text-slate-500">No blood in stock yet.</p> : (
          <div className="overflow-x-auto"><table className="w-full min-w-[28rem] text-left text-sm"><thead><tr className="border-b text-xs uppercase text-slate-500"><th className="py-1.5 pr-3">Component</th><th className="pr-3">Group</th><th className="pr-3">Available</th><th className="pr-3">Reserved</th><th>In quarantine</th></tr></thead>
            <tbody>{data.map((r) => <tr key={`${r.component}${r.blood_group}`} className="border-b border-slate-100"><td className="py-1.5 pr-3">{label(r.component)}</td><td className="pr-3 font-bold">{r.blood_group}</td><td className="pr-3 font-bold text-emerald-700">{r.available}</td><td className="pr-3">{r.reserved}</td><td>{r.quarantine}</td></tr>)}</tbody></table></div>)}
      </Section>
      {rules.data && <Hint title="Limits in use">{rules.data.note} Donor age {rules.data.rules.min_age} to {rules.data.rules.max_age}, at least {rules.data.rules.min_weight_kg} kg and {rules.data.rules.min_haemoglobin} g/dL haemoglobin; {rules.data.rules.interval_days_male} days between donations for men, {rules.data.rules.interval_days_female} for women.</Hint>}
    </div>
  );
}

function RequestCard({ r, reload }) {
  const [open, setOpen] = useState(false);
  const cands = useFetch(() => (open ? getCandidates(r.id) : Promise.resolve([])), [open, r.status]);
  const { problem, busy, run } = useSave();
  return (
    <Section>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="font-bold">{r.units_requested} x {label(r.component)} for {r.patient_name} <span className="text-sm font-normal text-slate-500">({r.patient_code}, group {r.blood_group || "not known"})</span>{r.urgency !== "ROUTINE" && <span className="ml-2 rounded-full bg-red-600 px-2 py-0.5 text-xs font-bold text-white">{r.urgency}</span>}</p>
        <span className="rounded-full bg-slate-100 px-3 py-1 text-sm font-bold">{r.status}</span>
      </div>
      <p className="text-sm text-slate-600">{r.indication} - {r.doctor}, {fmtUtc(r.created_at)}. Matched {r.units_matched}, issued {r.units_issued}.</p>
      {problem && <ErrorBox message={problem} />}
      {r.issues.map((i) => <p key={i.id} className="mt-1 flex flex-wrap items-center gap-2 text-sm">Unit {i.unit_number}: {i.returned ? "returned" : i.verified ? "issued and verified" : "issued, waiting for a second person to verify"}
        {!i.verified && !i.returned && <Button variant="secondary" disabled={busy} onClick={async () => { if (await run(() => verifyIssue(i.id), "Verified")) reload(); }}>Verify as the second person</Button>}
        {!i.returned && <Button variant="soft" disabled={busy} onClick={async () => { const why = window.prompt("Why is it returned?"); if (why) { const cold = window.confirm("Was the cold chain kept (unit kept cold, back within 30 minutes)?"); if (await run(() => returnBlood(i.id, why, cold), "Returned")) reload(); } }}>Return</Button>}</p>)}
      {["PENDING", "CROSSMATCHED"].includes(r.status) && (
        <div className="mt-2 flex flex-wrap gap-2"><Button variant="secondary" onClick={() => setOpen(!open)}>{open ? "Hide units" : "Find compatible units"}</Button>
          <Button variant="soft" disabled={busy} onClick={async () => { const why = window.prompt("Why is it rejected?"); if (why && await run(() => rejectBloodRequest(r.id, why), "Rejected")) reload(); }}>Reject</Button></div>)}
      {open && (cands.loading ? <Loading /> : (cands.data || []).length === 0 ? <p className="mt-2 text-sm text-slate-500">No compatible unit is available.</p> : (
        <ul className="mt-2 divide-y rounded-xl bg-slate-50 p-2">{cands.data.map((u) => <li key={u.id} className="flex flex-wrap items-center justify-between gap-2 py-1.5 text-sm"><span><b>{u.unit_number}</b> {u.blood_group} {label(u.component)}, expires {fmtUtc(u.expires_at)}</span>
          <span className="flex gap-2"><Button disabled={busy} onClick={async () => { if (await run(() => crossmatch(r.id, u.id, "COMPATIBLE"), "Cross-match compatible: unit reserved")) reload(); }}>Cross-match compatible</Button>
            <Button variant="secondary" disabled={busy} onClick={async () => { if (await run(() => crossmatch(r.id, u.id, "INCOMPATIBLE"), "Recorded as incompatible")) cands.reload(); }}>Incompatible</Button></span></li>)}</ul>))}
      {r.status === "CROSSMATCHED" && r.issues.filter((i) => !i.returned).length < r.units_matched && <MatchedIssue r={r} reload={reload} />}
    </Section>
  );
}

function MatchedIssue({ r, reload }) {
  const units = useFetch(() => getBloodUnits({ status_filter: "RESERVED" }), [r.status, r.units_matched]);
  const { problem, busy, run } = useSave();
  const mine = (units.data || []).filter((u) => u.reserved_for === r.id);
  if (!mine.length) return null;
  return <div className="mt-2 rounded-xl bg-emerald-50 p-2 text-sm">{problem && <ErrorBox message={problem} />}{mine.map((u) => <p key={u.id} className="flex flex-wrap items-center gap-2">Matched: <b>{u.unit_number}</b> ({u.blood_group})
    <Button disabled={busy} onClick={async () => { if (await run(() => issueBlood(r.id, u.id), "Issued: a second person must verify")) reload(); }}>Issue</Button></p>)}</div>;
}

function Requests() {
  const { data, loading, error, reload } = useFetch(() => getBloodRequests());
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const open = data.filter((r) => ["PENDING", "CROSSMATCHED", "ISSUED"].includes(r.status));
  return open.length === 0 ? <EmptyState message="No request is open" hint="Doctors ask for blood from the patient's page." icon={Droplets} /> : <div className="space-y-3">{open.map((r) => <RequestCard key={r.id} r={r} reload={reload} />)}</div>;
}

function Donors() {
  const { data, loading, error, reload } = useFetch(() => getDonors());
  const [form, setForm] = useState({ full_name: "", gender: "male", date_of_birth: "", phone: "", blood_group: "O+" });
  const [coll, setColl] = useState({ donor: null, volume_ml: "450", haemoglobin: "", weight_kg: "", components: ["PRBC"] });
  const { problem, busy, run } = useSave();
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const toggle = (c) => setColl({ ...coll, components: c === "WHOLE_BLOOD" ? ["WHOLE_BLOOD"] : coll.components.filter((x) => x !== "WHOLE_BLOOD").includes(c) ? coll.components.filter((x) => x !== c) : [...coll.components.filter((x) => x !== "WHOLE_BLOOD"), c] });
  return (
    <div className="space-y-4">
      <Section title="Register a donor">
        <div className="grid gap-3 sm:grid-cols-5">
          <Field label="Name *"><Input maxLength={150} value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} /></Field>
          <Field label="Gender"><Select value={form.gender} onChange={(e) => setForm({ ...form, gender: e.target.value })}><option value="male">Male</option><option value="female">Female</option><option value="other">Other</option></Select></Field>
          <Field label="Date of birth *"><Input type="date" value={form.date_of_birth} onChange={(e) => setForm({ ...form, date_of_birth: e.target.value })} /></Field>
          <Field label="Phone"><Input maxLength={30} value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} /></Field>
          <Field label="Blood group *"><Select value={form.blood_group} onChange={(e) => setForm({ ...form, blood_group: e.target.value })}>{GROUPS.map((g) => <option key={g}>{g}</option>)}</Select></Field>
        </div>
        {problem && !coll.donor && <ErrorBox message={problem} />}
        <Button className="mt-3" disabled={busy || form.full_name.trim().length < 2 || !form.date_of_birth} onClick={async () => { if (await run(() => addDonor({ ...form, phone: form.phone || null }), "Donor registered")) { setForm({ ...form, full_name: "", date_of_birth: "", phone: "" }); reload(); } }}>Register</Button>
      </Section>
      <Section title="Donors">
        {data.length === 0 ? <p className="text-sm text-slate-500">No donor yet.</p> : data.map((d) => (
          <div key={d.id} className="border-b border-slate-100 py-2 last:border-0">
            <div className="flex flex-wrap items-center justify-between gap-2"><span><b>{d.full_name}</b> <span className="text-sm text-slate-500">{d.donor_no}, {d.age} years, group {d.blood_group}</span></span>
              <Button variant="secondary" onClick={() => setColl({ ...coll, donor: coll.donor === d.id ? null : d.id })}>Collect blood</Button></div>
            {d.ineligible_reasons.length > 0 && <p className="text-sm text-red-700">{d.ineligible_reasons.join(" ")}</p>}
            {coll.donor === d.id && (
              <div className="mt-2 space-y-2 rounded-xl bg-slate-50 p-3">
                <div className="grid gap-2 sm:grid-cols-3"><Field label="Volume (ml)"><Input inputMode="numeric" value={coll.volume_ml} onChange={(e) => setColl({ ...coll, volume_ml: e.target.value })} /></Field><Field label="Haemoglobin (g/dL) *"><Input inputMode="decimal" value={coll.haemoglobin} onChange={(e) => setColl({ ...coll, haemoglobin: e.target.value })} /></Field><Field label="Weight (kg) *"><Input inputMode="decimal" value={coll.weight_kg} onChange={(e) => setColl({ ...coll, weight_kg: e.target.value })} /></Field></div>
                <div className="flex flex-wrap gap-3 text-sm">{COMPONENTS.map(([k, name]) => <label key={k} className="flex items-center gap-1.5"><input type="checkbox" checked={coll.components.includes(k)} onChange={() => toggle(k)} />{name}</label>)}</div>
                {problem && <ErrorBox message={problem} />}
                <Button disabled={busy || !coll.haemoglobin || !coll.weight_kg || coll.components.length === 0} onClick={async () => { if (await run(() => collectBlood(d.id, { volume_ml: Number(coll.volume_ml), haemoglobin: Number(coll.haemoglobin), weight_kg: Number(coll.weight_kg), components: coll.components }), "Collected: the units wait in quarantine for screening")) { setColl({ ...coll, donor: null, haemoglobin: "", weight_kg: "" }); reload(); } }}>Save the collection</Button>
              </div>)}
          </div>))}
      </Section>
    </div>
  );
}

function Screening() {
  const { data, loading, error, reload } = useFetch(() => getDonations(true));
  const { problem, busy, run } = useSave();
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  return (
    <div className="space-y-3">
      <Hint title="Second person">The person who collected the blood cannot record its screening. Until a screening is cleared, the units stay in quarantine.</Hint>
      {problem && <ErrorBox message={problem} />}
      {data.length === 0 ? <EmptyState message="Nothing waits for screening" icon={Droplets} /> : data.map((d) => (
        <Section key={d.id}>
          <p className="font-bold">{d.donor_no} <span className="text-sm font-normal text-slate-500">{fmtUtc(d.donated_at)}: {d.units.map((u) => `${u.unit_number} ${label(u.component)} ${u.blood_group}`).join(", ")}</span></p>
          <div className="mt-2 flex gap-2"><Button disabled={busy} onClick={async () => { if (await run(() => screenDonation(d.id, "CLEARED"), "Cleared: units are available")) reload(); }}>Screening cleared</Button>
            <Button variant="secondary" disabled={busy} onClick={async () => { const note = window.prompt("What was found?"); if (note && await run(() => screenDonation(d.id, "REACTIVE", note), "Units discarded, donor deferred")) reload(); }}>Reactive</Button></div>
        </Section>))}
    </div>
  );
}

function Units() {
  const [status, setStatus] = useState("AVAILABLE");
  const { data, loading, error, reload } = useFetch(() => getBloodUnits({ status_filter: status }), [status]);
  const { busy, run } = useSave();
  return (
    <Section title="Units">
      <div className="mb-3 max-w-xs"><Select value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Status">{["AVAILABLE", "RESERVED", "QUARANTINE", "ISSUED", "TRANSFUSED", "EXPIRED", "DISCARDED"].map((s) => <option key={s}>{s}</option>)}</Select></div>
      {loading && !data ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> : data.length === 0 ? <p className="text-sm text-slate-500">None.</p> : (
        <ul className="divide-y">{data.map((u) => <li key={u.id} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm"><span><b>{u.unit_number}</b> {u.blood_group} {label(u.component)}, {u.volume_ml} ml, expires {fmtUtc(u.expires_at)}{u.discard_reason ? ` - ${u.discard_reason}` : ""}</span>
          {["AVAILABLE", "QUARANTINE", "RESERVED"].includes(u.status) && <Button variant="secondary" disabled={busy} onClick={async () => { const why = window.prompt("Why is it discarded?"); if (why && await run(() => discardUnit(u.id, why), "Discarded")) reload(); }}>Discard</Button>}</li>)}</ul>)}
    </Section>
  );
}

export default function BloodBank() {
  return (
    <div className="space-y-5">
      <PageTitle title="Blood bank" subtitle="Strict by design: two people for screening, two for issue, and a bedside check for every transfusion." icon={Droplets} />
      <Tabs tabs={[["stock", "Stock", <Stock />], ["req", "Requests", <Requests />], ["donors", "Donors", <Donors />], ["screen", "Screening", <Screening />], ["units", "Units", <Units />]]} />
    </div>
  );
}
