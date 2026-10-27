import { useState } from "react";
import { Users as UsersIcon } from "lucide-react";
import PeopleList from "../../components/PeopleList";
import { Hint, PageTitle } from "../../components/Feedback";

const ROLES = [["", "Everyone"], ["DOCTOR", "Doctors"], ["EMPLOYEE", "Employees"], ["PHARMACY", "Pharmacy staff"], ["LAB", "Laboratory staff"], ["PATIENT", "Patients"], ["ADMIN", "Admins"]];

export default function Users() {
  const [role, setRole] = useState("");
  return (
    <div className="space-y-5">
      <PageTitle title="People" subtitle="Everyone who can log in to the hospital system" icon={UsersIcon} />
      <Hint title="Deactivate or delete?">Deactivate: the person can no longer log in, but nothing they did is deleted, and you can switch them back on. Delete: removes the account for good, and works only for an account with nothing linked to it (for example one made by mistake). Anyone with records can only be deactivated.</Hint>
      <div className="flex flex-wrap gap-2">
        {ROLES.map(([value, label]) => (
          <button key={value} onClick={() => setRole(value)}
            className={`rounded-full px-3.5 py-1.5 text-sm font-semibold ${role === value ? "bg-brand-600 text-white shadow-sm" : "bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50"}`}>{label}</button>
        ))}
      </div>
      <PeopleList role={role} />
    </div>
  );
}
