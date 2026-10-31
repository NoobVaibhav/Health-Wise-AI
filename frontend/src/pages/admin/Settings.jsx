// Hospital settings: the departments and, inside each, the specializations a doctor can be given. Nothing is deleted: a department or specialization that is
// no longer used is switched off (hidden from the dropdowns), and the doctors who have it keep it.
import { useState } from "react";
import { ChevronDown, ChevronRight, Pencil, Power } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import { addDepartment, addSpecialization, adminDepartments, adminSpecializations, renameDepartment, renameSpecialization, setDepartmentActive, setSpecializationActive } from "../../services/catalogApi";
import { getErrorMessage } from "../../services/api";
import { Section } from "../../components/HealthCard";
import { Button, Input } from "../../components/ui";
import { ErrorBox, Loading, PageTitle } from "../../components/Feedback";
import { useToast } from "../../components/Toast";

function AddForm({ label, onAdd }) {
  const [name, setName] = useState("");
  const [problem, setProblem] = useState("");
  const submit = async (e) => {
    e.preventDefault();
    setProblem("");
    try { await onAdd(name); setName(""); } catch (err) { setProblem(getErrorMessage(err)); }
  };
  return (
    <form onSubmit={submit} className="mt-3" noValidate>
      <div className="flex gap-2">
        <Input aria-label={label} placeholder={label} maxLength={100} value={name} onChange={(e) => { setName(e.target.value); setProblem(""); }} aria-invalid={problem ? "true" : undefined} />
        <Button disabled={!name.trim()}>Add</Button>
      </div>
      {problem && <p role="alert" className="mt-1 text-sm font-medium text-red-600">{problem}</p>}
    </form>
  );
}

function Row({ item, noun, onRename, onToggle, children }) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(item.name);
  const [problem, setProblem] = useState("");
  const save = async (e) => {
    e.preventDefault();
    try { await onRename(item.id, name); setEditing(false); setProblem(""); } catch (err) { setProblem(getErrorMessage(err)); }
  };
  return (
    <li className="py-2">
      <div className="flex flex-wrap items-center gap-2">
        {editing ? (
          <form onSubmit={save} className="flex flex-1 gap-2" noValidate>
            <Input aria-label={`New name for ${item.name}`} maxLength={100} value={name} onChange={(e) => setName(e.target.value)} autoFocus />
            <Button>Save</Button><Button type="button" variant="secondary" onClick={() => { setEditing(false); setName(item.name); setProblem(""); }}>Cancel</Button>
          </form>
        ) : (
          <>
            <span className={`flex-1 font-semibold ${item.is_active ? "text-slate-900" : "text-slate-400 line-through"}`}>{item.name}</span>
            <span className="text-xs text-slate-500">{item.doctor_count} {item.doctor_count === 1 ? "doctor" : "doctors"}{!item.is_active && " · switched off"}</span>
            <Button type="button" variant="secondary" aria-label={`Rename ${noun} ${item.name}`} onClick={() => setEditing(true)}><Pencil size={14} className="mr-1 inline" /> Rename</Button>
            <Button type="button" variant={item.is_active ? "secondary" : "soft"} aria-label={`${item.is_active ? "Switch off" : "Switch on"} ${noun} ${item.name}`} onClick={() => onToggle(item)}>
              <Power size={14} className="mr-1 inline" /> {item.is_active ? "Switch off" : "Switch on"}
            </Button>
          </>
        )}
      </div>
      {problem && <p role="alert" className="mt-1 text-sm font-medium text-red-600">{problem}</p>}
      {children}
    </li>
  );
}

function Specializations({ department }) {
  const { data, loading, error, reload } = useFetch(() => adminSpecializations(department.id), [department.id]);
  const toast = useToast();
  const toggle = async (s) => { try { await setSpecializationActive(s.id, !s.is_active); reload(); } catch (err) { toast(getErrorMessage(err), "error"); } };
  return (
    <div className="ml-4 mt-2 border-l-2 border-sky-100 pl-4">
      {loading && !data ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> : (
        <ul className="divide-y" aria-label={`Specializations of ${department.name}`}>
          {data.length === 0 && <li className="py-2 text-slate-500">No specializations for this department yet.</li>}
          {data.map((s) => <Row key={s.id} item={s} noun="specialization" onRename={async (id, name) => { await renameSpecialization(id, name); reload(); }} onToggle={toggle} />)}
        </ul>)}
      <AddForm label={`New specialization in ${department.name}`} onAdd={async (name) => { await addSpecialization(department.id, name); reload(); }} />
    </div>
  );
}

export default function Settings() {
  const { data, loading, error, reload } = useFetch(adminDepartments);
  const toast = useToast();
  const [open, setOpen] = useState(null);
  const toggle = async (d) => { try { await setDepartmentActive(d.id, !d.is_active); reload(); } catch (err) { toast(getErrorMessage(err), "error"); } };
  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <PageTitle title="Settings" subtitle="Hospital departments and their specializations" />
      <Section title="Departments and specializations">
        <p className="mb-3 text-sm text-slate-600">Doctors choose a department and then a specialization from its list. Switching one off hides it from the lists; doctors who already have it keep it.</p>
        {loading && !data ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> : (
          <ul className="divide-y">
            {data.length === 0 && <li className="py-2 text-slate-500">No departments yet.</li>}
            {data.map((d) => (
              <Row key={d.id} item={d} noun="department" onRename={async (id, name) => { await renameDepartment(id, name); reload(); }} onToggle={toggle}>
                <button type="button" aria-expanded={open === d.id} onClick={() => setOpen(open === d.id ? null : d.id)} className="mt-1 flex items-center gap-1 text-sm font-semibold text-sky-700">
                  {open === d.id ? <ChevronDown size={16} /> : <ChevronRight size={16} />} Specializations of {d.name}
                </button>
                {open === d.id && <Specializations department={d} />}
              </Row>
            ))}
          </ul>)}
        <AddForm label="New department name" onAdd={async (name) => { await addDepartment(name); reload(); }} />
      </Section>
    </div>
  );
}
