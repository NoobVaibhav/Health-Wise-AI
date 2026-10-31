// The live bed board: every ward with its beds and counts. A bed with a patient can be moved to a free bed; a free bed can be sent to cleaning or maintenance.
// The server (and the database) decide: a bed taken a moment ago is a clear message, never two patients in one bed.
import { useState } from "react";
import { Link } from "react-router-dom";
import { BedDouble } from "lucide-react";
import useFetch from "../hooks/useFetch";
import useSave from "../hooks/useSave";
import { listWards, moveBed, setBedStatus } from "../services/careApi";
import { Section } from "./HealthCard";
import { EmptyState, ErrorBox, Loading } from "./Feedback";
import { Button, Field, Input, Modal, Select } from "./ui";

const TONE = {
  AVAILABLE: "border-emerald-300 bg-emerald-50 text-emerald-900", OCCUPIED: "border-rose-300 bg-rose-50 text-rose-900", RESERVED: "border-amber-300 bg-amber-50 text-amber-900",
  CLEANING: "border-sky-300 bg-sky-50 text-sky-900", MAINTENANCE: "border-slate-300 bg-slate-100 text-slate-700",
};
const LABEL = { AVAILABLE: "Free", OCCUPIED: "Occupied", RESERVED: "Reserved", CLEANING: "Cleaning", MAINTENANCE: "Maintenance" };

export default function BedBoard({ admissionLink }) {
  const { data, loading, error, reload } = useFetch(listWards);
  const [picked, setPicked] = useState(null);
  const total = (data || []).reduce((acc, w) => { Object.entries(w.counts).forEach(([k, v]) => { acc[k] = (acc[k] || 0) + v; }); return acc; }, {});
  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  if (data.length === 0) return <EmptyState message="No wards yet" hint="The administrator adds wards and beds under Hospital > Wards and beds." icon={BedDouble} />;
  const free = data.flatMap((w) => w.beds.filter((b) => b.status === "AVAILABLE").map((b) => ({ ...b, ward: w.name })));
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2" aria-label="Bed counts">
        {Object.keys(LABEL).map((k) => <span key={k} className={`rounded-full border px-3 py-1 text-sm font-bold ${TONE[k]}`}>{LABEL[k]}: {total[k] || 0}</span>)}
      </div>
      {data.map((w) => (
        <Section key={w.id} title={`${w.name} (${w.ward_type.replace("_", " ").toLowerCase()})`}>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
            {w.beds.map((b) => (
              <button key={b.id} type="button" onClick={() => setPicked({ bed: b, ward: w })} aria-label={`Bed ${b.code} in ${w.name}, ${LABEL[b.status]}${b.patient ? `, ${b.patient.full_name}` : ""}`}
                className={`min-h-20 rounded-2xl border-2 p-3 text-left ${TONE[b.status]}`}>
                <span className="block text-lg font-extrabold">{b.code}</span>
                <span className="block text-xs font-bold uppercase">{LABEL[b.status]}</span>
                {b.patient && <span className="block truncate text-sm">{b.patient.full_name}</span>}
              </button>))}
            {w.beds.length === 0 && <p className="col-span-full text-slate-500">No beds in this ward yet.</p>}
          </div>
        </Section>))}
      {picked && <BedDialog picked={picked} free={free} admissionLink={admissionLink} onClose={() => setPicked(null)} onChanged={() => { setPicked(null); reload(); }} />}
    </div>
  );
}

function BedDialog({ picked, free, admissionLink, onClose, onChanged }) {
  const { bed, ward } = picked;
  const { problem, busy, run } = useSave();
  const [target, setTarget] = useState("");
  const [reason, setReason] = useState("");
  const setStatus = async (status) => { if (await run(() => setBedStatus(bed.id, status), "Bed updated")) onChanged(); };
  return (
    <Modal title={`Bed ${bed.code}, ${ward.name}`} onClose={onClose}>
      <div className="space-y-3">
        <p className="text-slate-700"><b>{LABEL[bed.status]}</b></p>
        {bed.patient && (
          <>
            <p><b>{bed.patient.full_name}</b> · {bed.patient.uhid} · {bed.patient.admission_no}</p>
            {admissionLink && <Link to={admissionLink(bed.patient.admission_id)} className="inline-block font-semibold text-brand-700 underline">Open the chart</Link>}
            <Field label="Move to a free bed"><Select value={target} onChange={(e) => setTarget(e.target.value)}><option value="">Choose a free bed</option>{free.map((f) => <option key={f.id} value={f.id}>{f.ward}: {f.code}</option>)}</Select></Field>
            <Field label="Reason (optional)"><Input maxLength={200} value={reason} onChange={(e) => setReason(e.target.value)} /></Field>
            <Button type="button" disabled={!target || busy} onClick={async () => { if (await run(() => moveBed(bed.patient.admission_id, Number(target), reason), "Patient moved")) onChanged(); }}>Move patient</Button>
          </>)}
        {!bed.patient && (
          <div className="flex flex-wrap gap-2">
            {bed.status !== "AVAILABLE" && <Button type="button" disabled={busy} onClick={() => setStatus("AVAILABLE")}>Mark as free</Button>}
            {bed.status !== "CLEANING" && <Button type="button" variant="secondary" disabled={busy} onClick={() => setStatus("CLEANING")}>Send to cleaning</Button>}
            {bed.status !== "MAINTENANCE" && <Button type="button" variant="secondary" disabled={busy} onClick={() => setStatus("MAINTENANCE")}>Maintenance</Button>}
          </div>)}
        {problem && <ErrorBox message={problem} />}
      </div>
    </Modal>
  );
}
