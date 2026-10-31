// One reusable page for creating and listing doctors, employees, pharmacy staff and laboratory staff (admin only).
import { useState } from "react";
import { Plus } from "lucide-react";
import { createStaff } from "../../services/adminApi";
import DepartmentSpecializationSelect from "../../components/DepartmentSpecializationSelect";
import PeopleList from "../../components/PeopleList";
import AccountCreatedDialog from "../../components/AccountCreatedDialog";
import { useToast } from "../../components/Toast";
import { getErrorMessage } from "../../services/api";
import { Button, Input, Modal } from "../../components/ui";
import { FormField, PasswordInput } from "../../components/FormField";
import useValidation from "../../hooks/useValidation";
import * as v from "../../utils/validators";
import { ErrorBox, PageTitle } from "../../components/Feedback";

const KINDS = {
  doctors: { role: "DOCTOR", title: "Doctors", single: "doctor" },
  employees: { role: "EMPLOYEE", title: "Employees", single: "employee" },
  "pharmacy-staff": { role: "PHARMACY", title: "Pharmacy Staff", single: "pharmacy staff member" },
  "lab-staff": { role: "LAB", title: "Laboratory Staff", single: "laboratory staff member" },
};

export default function StaffManager({ kind }) {
  const cfg = KINDS[kind];
  const [creating, setCreating] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const toast = useToast();
  const [created, setCreated] = useState(null);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <PageTitle title={cfg.title} subtitle={`Add new ${cfg.title.toLowerCase()} and see when they last logged in`} />
        <Button onClick={() => { setCreating(true); setCreated(null); }}><Plus size={16} className="mr-1 inline" /> Add {cfg.single}</Button>
      </div>
      {created && <AccountCreatedDialog kind={cfg.single} name={created.user.full_name} email={created.user.email} password={created.temporary_password} onClose={() => setCreated(null)} />}
      <PeopleList role={cfg.role} reloadKey={refresh} emptyHint={`Use "Add ${cfg.single}" to create the first account.`} />
      {creating && <CreateModal kind={kind} cfg={cfg} onClose={() => setCreating(false)} onCreated={(r) => { setCreated(r); setRefresh((n) => n + 1); toast(`${r.user.full_name} was added`); }} />}
    </div>
  );
}

const STAFF_RULES = {
  full_name: (value) => v.personName(value),
  email: (value) => v.email(value),
  password: (value, all) => (value ? v.password(value, { email: all.email }) : ""),         // empty = the starting password is used
  phone: (value) => v.phone(value),
  specialization_id: () => "",
  department_id: (value, all) => (all.kind === "doctors" && !value ? "Please choose a department." : ""),
  designation: (value) => v.text(value, { max: 100 }),
  pharmacy_name: (value) => v.text(value, { max: 150 }),
  lab_name: (value) => v.text(value, { max: 150 }),
};

function CreateModal({ kind, cfg, onClose, onCreated }) {
  const [form, setForm] = useState({ full_name: "", email: "", password: "", phone: "", department_id: "", specialization_id: "", designation: "", pharmacy_name: "", lab_name: "" });
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const check = useValidation(STAFF_RULES);
  const set = (k) => (e) => { setForm({ ...form, [k]: e.target.value }); check.clear(k); };
  const blur = (k) => () => check.check(k, form);
  const submit = async (e) => {
    e.preventDefault();
    if (busy) return;
    if (!check.validateAll({ ...form, kind })) return;
    setBusy(true);
    setError("");
    try {
      const payload = Object.fromEntries(Object.entries(form).map(([k, val]) => [k, String(val).trim() === "" ? null : (typeof val === "string" ? val.trim() : val)]));
      payload.email = payload.email.toLowerCase();
      if (payload.department_id) payload.department_id = Number(payload.department_id);
      if (payload.specialization_id) payload.specialization_id = Number(payload.specialization_id);
      onCreated(await createStaff(kind, payload));
      onClose();
    } catch (err) {
      if (!check.fromServer(err)) setError(getErrorMessage(err));        // the typed details stay in the form
    } finally { setBusy(false); }
  };
  return (
    <Modal title={`Add ${cfg.single}`} onClose={onClose}>
      <form onSubmit={submit} noValidate className="space-y-4" aria-busy={busy}>
        <FormField label="Full name *" name="full_name" error={check.errors.full_name}><Input autoComplete="off" maxLength={150} value={form.full_name} onChange={set("full_name")} onBlur={blur("full_name")} /></FormField>
        <FormField label="Email (used to log in) *" name="email" error={check.errors.email}><Input type="email" inputMode="email" autoComplete="off" maxLength={254} value={form.email} onChange={set("email")} onBlur={blur("email")} /></FormField>
        <FormField label="Password" name="password" error={check.errors.password} hint="Leave empty to use the default starting password (the person must change it at first login)">
          <PasswordInput meter value={form.password} onChange={set("password")} onBlur={blur("password")} placeholder="Leave empty for the starting password" />
        </FormField>
        <FormField label="Phone" name="phone" error={check.errors.phone} hint="For example 98765 43210 or +91 98765 43210"><Input type="tel" inputMode="tel" autoComplete="off" maxLength={20} value={form.phone} onChange={set("phone")} onBlur={blur("phone")} /></FormField>
        {kind === "doctors" && (<>
          <DepartmentSpecializationSelect departmentRequired departmentId={form.department_id} specializationId={form.specialization_id}
            departmentError={check.errors.department_id} specializationError={check.errors.specialization_id}
            onChange={(next) => { setForm({ ...form, ...next }); check.clear("department_id"); check.clear("specialization_id"); }} />
        </>)}
        {kind === "employees" && <FormField label="Designation" name="designation" error={check.errors.designation}><Input placeholder="Receptionist, lab assistant ..." maxLength={100} value={form.designation} onChange={set("designation")} onBlur={blur("designation")} /></FormField>}
        {kind === "pharmacy-staff" && <FormField label="Pharmacy name" name="pharmacy_name" error={check.errors.pharmacy_name}><Input maxLength={150} value={form.pharmacy_name} onChange={set("pharmacy_name")} onBlur={blur("pharmacy_name")} /></FormField>}
        {kind === "lab-staff" && <FormField label="Laboratory name" name="lab_name" error={check.errors.lab_name}><Input maxLength={150} value={form.lab_name} onChange={set("lab_name")} onBlur={blur("lab_name")} /></FormField>}
        {error && <ErrorBox message={error} />}
        <Button disabled={busy}>{busy ? "Creating..." : "Create account"}</Button>
      </form>
    </Modal>
  );
}
