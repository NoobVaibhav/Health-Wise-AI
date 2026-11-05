// One prescription written the way an Indian doctor's prescription pad looks: letterhead, patient strip, diagnosis, the Rx table, advice, signature.
// Both people use it: variant="patient" (the patient and the doctor) and variant="pharmacy" (the medical shop). The pharmacy variant NEVER shows tests,
// even if some were passed in. It prints on A4 (only this sheet; everything marked no-print or outside .print-area stays off the paper), in black and white,
// and on a phone the table turns into one card per medicine. Anything that is not recorded is simply left out: no placeholder text, nothing invented.
import { AlertTriangle, Pill, Printer } from "lucide-react";
import Barcode from "./Barcode";
import { Button, fmtDate } from "./ui";
import { ageSex, collectionState, doctorLabel, frequencyShorthand, has, statusBanner } from "../utils/prescriptionFormat";

const TONE = { done: "border-emerald-700 text-emerald-900", part: "border-amber-700 text-amber-900", stop: "border-red-700 text-red-800", wait: "border-slate-500 text-slate-700" };

function Cell({ label, children }) {
  if (!has(children)) return null;
  return (
    <div className="min-w-0 border-slate-300 px-3 py-1.5 sm:border-r sm:last:border-r-0">
      <p className="text-sm text-slate-600">{label}</p>
      <p className="break-words text-sm font-semibold text-slate-900">{children}</p>
    </div>
  );
}

export default function PrescriptionSheet({ rx, variant = "patient", onPrint }) {
  const shop = variant === "pharmacy";
  const doctor = rx.doctor_info || {};
  const patient = rx.patient_info || {};
  const hospital = rx.hospital || {};
  const banner = statusBanner(rx.status);
  const tests = shop ? [] : rx.tests || [];                           // the pharmacy never sees tests
  const items = rx.items || [];
  const subtitle = [doctor.specialization, doctor.department].filter(has).join(" · ");

  return (
    <div>
      {banner && (
        <div role="status" className="mb-3 flex items-start gap-3 rounded-2xl border-2 border-slate-800 bg-slate-100 p-4 text-slate-900 print:border-4">
          <AlertTriangle className="mt-0.5 shrink-0" size={22} aria-hidden="true" />
          <div><p className="text-base font-extrabold tracking-wide">{banner.title}</p><p className="text-sm">{banner.text}</p></div>
        </div>
      )}
      {onPrint && <div className="no-print mb-3 flex justify-end"><Button type="button" variant="secondary" onClick={onPrint}><Printer size={18} className="mr-1 inline" /> Print / Download PDF</Button></div>}

      <section className="print-area rx-sheet rounded-3xl border border-slate-300 bg-white p-5 text-slate-900 shadow-sm print:rounded-none print:border-0 print:p-[5mm] print:shadow-none sm:p-8" aria-label={`Prescription ${rx.code}`}>
        <table className="w-full border-collapse">
          <thead className="rx-run-head hidden print:table-header-group">
            <tr><td className="border-b border-slate-400 pb-1 text-xs">Patient: <b>{rx.patient_name}</b> ({rx.patient_code}) · Prescription {rx.code} · {fmtDate(rx.prescription_date)}</td></tr>
          </thead>
          <tbody>
            <tr><td className="align-top">
              {/* 1. letterhead */}
              <div className="rx-letterhead flex flex-wrap items-start justify-between gap-4 border-b-4 border-brand-700 pb-3">  {/* a div: the app's print rule hides every <header> */}
                <div className="flex min-w-0 items-start gap-3">
                  <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-xl border-2 border-dashed border-slate-400 text-slate-400" aria-hidden="true"><Pill size={24} /></div>
                  <div className="min-w-0">
                    {has(hospital.name) && <p className="break-words text-lg font-extrabold uppercase tracking-wide text-slate-900">{hospital.name}</p>}
                    <p className="break-words text-base font-bold text-slate-900">{doctorLabel(rx.doctor_name)}</p>
                    {has(doctor.qualification) && <p className="break-words text-sm text-slate-700">{doctor.qualification}</p>}
                    {has(subtitle) && <p className="break-words text-sm text-slate-700">{subtitle}</p>}
                    {has(doctor.registration_number) && <p className="text-sm text-slate-700">Reg. No.: {doctor.registration_number}</p>}
                  </div>
                </div>
                {(has(hospital.address) || has(hospital.phone) || has(hospital.email)) && (
                  <div className="min-w-0 text-sm text-slate-700 sm:text-right">
                    {has(hospital.address) && <p className="break-words">{hospital.address}</p>}
                    {has(hospital.phone) && <p>Phone: {hospital.phone}</p>}
                    {has(hospital.email) && <p className="break-all">{hospital.email}</p>}
                  </div>
                )}
              </div>

              {/* 2. patient strip */}
              <div className="mt-3 grid grid-cols-1 rounded-lg border border-slate-400 sm:grid-cols-3 lg:grid-cols-4">
                <Cell label="Patient">{rx.patient_name}</Cell>
                <Cell label="Age / Sex">{ageSex(patient)}</Cell>
                <Cell label="Patient ID">{rx.patient_code}</Cell>
                <Cell label="Phone">{patient.phone}</Cell>
                <Cell label="Prescription no.">{rx.code}</Cell>
                <Cell label="Date">{fmtDate(rx.prescription_date)}</Cell>
                <Cell label="Valid until">{fmtDate(rx.valid_until)}</Cell>
              </div>
              {has(patient.allergies) && (
                <p className="mt-2 rounded-lg border-2 border-red-700 px-3 py-1.5 text-sm font-bold text-red-700 print:border-black print:text-black">
                  <span aria-hidden="true">⚠ </span>ALLERGY: <span className="break-words">{patient.allergies}</span>
                </p>
              )}

              {/* 3. clinical */}
              {has(rx.clinical_indication) && (
                <p className="mt-3 text-sm"><b>Diagnosis / reason:</b> <span className="break-words">{rx.clinical_indication}</span></p>
              )}

              {/* 4. the Rx body */}
              <div className="mt-3 flex items-start gap-3">
                <span className="select-none font-serif text-5xl font-bold leading-none text-brand-700 print:text-black" aria-hidden="true">℞</span>
                <div className="min-w-0 flex-1">
                  <table className="hidden w-full border-collapse text-sm sm:table print:table">
                    <thead>
                      <tr className="border-b-2 border-slate-700 text-left">
                        <th scope="col" className="w-8 py-1.5 pr-2">#</th>
                        <th scope="col" className="py-1.5 pr-2">Medicine</th>
                        <th scope="col" className="py-1.5 pr-2">Dose</th>
                        <th scope="col" className="py-1.5 pr-2">Frequency</th>
                        <th scope="col" className="py-1.5 pr-2">Duration</th>
                        <th scope="col" className="py-1.5 pr-2 text-right">Qty</th>
                        {!shop && <th scope="col" className="py-1.5 pl-2 print:hidden">Pharmacy</th>}
                      </tr>
                    </thead>
                    <tbody>
                      {items.map((item, index) => {
                        const short = frequencyShorthand(item.frequency);
                        const state = collectionState(item);
                        return (
                          <tr key={item.id ?? index} className="border-b border-slate-300 align-top" style={{ breakInside: "avoid" }}>
                            <td className="py-2 pr-2">{index + 1}</td>
                            <td className="min-w-0 break-words py-2 pr-2">
                              <p className="font-bold">{item.medicine_name}</p>
                              {has(item.instructions) && <p className="text-sm italic text-slate-700">{item.instructions}</p>}
                            </td>
                            <td className="py-2 pr-2">{item.dosage}</td>
                            <td className="py-2 pr-2">{short && <span className="mr-1 rounded border border-slate-500 px-1 font-mono text-xs font-bold">{short}</span>}{item.frequency}</td>
                            <td className="py-2 pr-2">{item.duration}</td>
                            <td className="py-2 pr-2 text-right font-semibold">{item.quantity}</td>
                            {!shop && <td className="py-2 pl-2 print:hidden"><span className={`inline-block rounded-full border-2 px-2 py-0.5 text-xs font-bold ${TONE[state.tone]}`}>{state.label}</span></td>}
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>

                  <ol className="space-y-2 sm:hidden print:hidden" aria-label="Medicines">
                    {items.map((item, index) => {
                      const short = frequencyShorthand(item.frequency);
                      const state = collectionState(item);
                      return (
                        <li key={item.id ?? index} className="rounded-xl border border-slate-300 p-3" style={{ breakInside: "avoid" }}>
                          <p className="break-words text-base font-bold">{index + 1}. {item.medicine_name}</p>
                          {has(item.instructions) && <p className="text-sm italic text-slate-700">{item.instructions}</p>}
                          <dl className="mt-1 grid grid-cols-2 gap-x-3 text-sm">
                            <div><dt className="text-slate-600">Dose</dt><dd className="font-semibold">{item.dosage}</dd></div>
                            <div><dt className="text-slate-600">Quantity</dt><dd className="font-semibold">{item.quantity}</dd></div>
                            <div><dt className="text-slate-600">Frequency</dt><dd className="font-semibold">{short && <span className="mr-1 font-mono">{short}</span>}{item.frequency}</dd></div>
                            <div><dt className="text-slate-600">Duration</dt><dd className="font-semibold">{item.duration}</dd></div>
                          </dl>
                          {!shop && <p className={`mt-2 inline-block rounded-full border-2 px-2 py-0.5 text-xs font-bold ${TONE[state.tone]}`}>{state.label}</p>}
                        </li>
                      );
                    })}
                  </ol>
                </div>
              </div>

              {/* 5. advice and tests */}
              {has(rx.notes) && (
                <div className="mt-4 rounded-lg border border-slate-400 p-3" style={{ breakInside: "avoid" }}>
                  <p className="text-sm font-bold">Advice / Notes</p>
                  <p className="mt-0.5 whitespace-pre-line break-words text-sm">{rx.notes}</p>
                </div>
              )}
              {tests.length > 0 && (
                <div className="mt-3 rounded-lg border border-slate-400 p-3" style={{ breakInside: "avoid" }}>
                  <p className="text-sm font-bold">Investigations advised</p>
                  <ul className="mt-0.5 list-disc pl-5 text-sm">{tests.map((t) => <li key={t} className="break-words">{t}</li>)}</ul>
                </div>
              )}

              {/* 6. footer */}
              <footer className="mt-6 grid gap-4 border-t border-slate-400 pt-3 sm:grid-cols-2" style={{ breakInside: "avoid" }}>
                <div className="min-w-0 text-sm">
                  <p>Valid until: <b>{fmtDate(rx.valid_until)}</b></p>
                  <div className="mt-1"><Barcode value={rx.code} height={36} width={1.6} showText /></div>
                  <p className="mt-1 text-xs text-slate-700">Computer-generated prescription. Not valid without the doctor's signature.</p>
                </div>
                <div className="flex flex-col items-end justify-end text-sm">
                  <div role="img" className="h-16 w-full max-w-[16rem] rounded border border-dashed border-slate-400" aria-label="Space for the doctor's stamp and signature" />
                  <div className="w-full max-w-[16rem] border-t border-slate-800 pt-1 text-center font-semibold">{doctorLabel(rx.doctor_name)}</div>
                </div>
              </footer>
            </td></tr>
          </tbody>
        </table>
      </section>

      {/* pharmacy only, on the screen only: what was prescribed, what was given, what is left */}
      {shop && items.length > 0 && (
        <section className="no-print mt-4 rounded-3xl border border-slate-300 bg-white p-4 shadow-sm" aria-label="Dispensing status">
          <h2 className="text-base font-extrabold text-slate-900">Dispensing status</h2>
          <div className="mt-2 overflow-x-auto" tabIndex={0} role="region" aria-label="Medicine table: scroll sideways for more">
            <table className="w-full min-w-[28rem] border-collapse text-sm">
              <thead><tr className="border-b-2 border-slate-700 text-left"><th scope="col" className="py-1.5 pr-2">Medicine</th><th scope="col" className="py-1.5 pr-2 text-right">Prescribed</th><th scope="col" className="py-1.5 pr-2 text-right">Given</th><th scope="col" className="py-1.5 pr-2 text-right">Remaining</th><th scope="col" className="py-1.5">Status</th></tr></thead>
              <tbody>
                {items.map((item) => {
                  const state = collectionState(item);
                  return (
                    <tr key={item.id} className="border-b border-slate-200">
                      <td className="break-words py-1.5 pr-2 font-semibold">{item.medicine_name}</td>
                      <td className="py-1.5 pr-2 text-right">{item.quantity}</td>
                      <td className="py-1.5 pr-2 text-right">{item.dispensed_quantity}</td>
                      <td className="py-1.5 pr-2 text-right font-bold">{item.remaining_quantity}</td>
                      <td className="py-1.5"><span className={`inline-block rounded-full border-2 px-2 py-0.5 text-xs font-bold ${TONE[state.tone]}`}>{state.label}</span></td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}
