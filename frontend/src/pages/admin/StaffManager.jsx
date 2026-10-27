// One reusable page for creating and listing doctors, employees, pharmacy staff and laboratory staff (admin only).
import { useState } from "react";
import { Plus } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import { createStaff, listDepartments } from "../../services/adminApi";
import PeopleList from "../../components/PeopleList";
import AccountCreatedDialog from "../../components/AccountCreatedDialog";
import { useToast } from "../../components/Toast";
import { getErrorMessage } from "../../services/api";
import { Button, Field, Input, Modal, Select } from "../../components/ui";
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

function CreateModal({ kind, cfg, onClose, onCreated }) {
  const { data: departments } = useFetch(listDepartments, []);
  const [form, setForm] = useState({ full_name: "", email: "", password: "", phone: "", department_id: "", specialization: "", designation: "", pharmacy_name: "", lab_name: "" });
  const [error, setError] = useState("");
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });
  const submit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      const payload = Object.fromEntries(Object.entries(form).map(([k, v]) => [k, v === "" ? null : v]));
      if (payload.department_id) payload.department_id = Number(payload.department_id);
      onCreated(await createStaff(kind, payload));
      onClose();
    } catch (err) { setError(getErrorMessage(err)); }
  };
  return (
    <Modal title={`Add ${cfg.single}`} onClose={onClose}>
      <form onSubmit={submit} className="space-y-4">
        <Field label="Full name"><Input required value={form.full_name} onChange={set("full_name")} /></Field>
        <Field label="Email (used to log in)"><Input type="email" required value={form.email} onChange={set("email")} /></Field>
        <Field label="Password" hint="Leave empty to use the default starting password (the person must change it at first login)"><Input type="password" minLength={8} value={form.password} onChange={set("password")} /></Field>
        <Field label="Phone"><Input value={form.phone} onChange={set("phone")} /></Field>
        {kind === "doctors" && (<>
          <Field label="Department"><Select value={form.department_id} onChange={set("department_id")}><option value="">None</option>{(departments || []).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</Select></Field>
          <Field label="Specialization"><Input value={form.specialization} onChange={set("specialization")} /></Field>
        </>)}
        {kind === "employees" && <Field label="Designation"><Input placeholder="Receptionist, lab assistant ..." value={form.designation} onChange={set("designation")} /></Field>}
        {kind === "pharmacy-staff" && <Field label="Pharmacy name"><Input value={form.pharmacy_name} onChange={set("pharmacy_name")} /></Field>}
        {kind === "lab-staff" && <Field label="Laboratory name"><Input value={form.lab_name} onChange={set("lab_name")} /></Field>}
        {error && <ErrorBox message={error} />}
        <Button>Create account</Button>
      </form>
    </Modal>
  );
}
