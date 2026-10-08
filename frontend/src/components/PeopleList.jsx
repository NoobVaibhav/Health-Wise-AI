// Cards for people (doctors, employees, pharmacy staff, patients, admins) with an activate/deactivate button.
import { useState } from "react";
import { Search, UserCheck, UserX } from "lucide-react";
import useFetch from "../hooks/useFetch";
import { useAuth } from "../context/AuthContext";
import { listPeople, updateUser } from "../services/adminApi";
import { getErrorMessage } from "../services/api";
import { PersonCard, timeAgo } from "./DataViews";
import { StatusPill } from "./StatusBadge";
import { EmptyState, ErrorBox, Loading } from "./Feedback";
import { Button, inputClass } from "./ui";
import { useToast } from "./Toast";

export default function PeopleList({ role, reloadKey, emptyHint }) {
  const { user: me } = useAuth();
  const toast = useToast();
  const [q, setQ] = useState("");
  const { data, loading, error, reload } = useFetch(() => listPeople(role, q), [role, q, reloadKey]);

  const toggle = async (p) => {
    try {
      await updateUser(p.id, { is_active: !p.is_active });
      toast(p.is_active ? `${p.full_name} was deactivated` : `${p.full_name} can log in again`);
      reload();
    } catch (e) { toast(getErrorMessage(e), "error"); }
  };

  return (
    <div className="space-y-4">
      <div className="relative">
        <Search className="pointer-events-none absolute left-3.5 top-3 text-slate-400" size={18} />
        <input className={`${inputClass} pl-10`} placeholder="Search by name or email" value={q} onChange={(e) => setQ(e.target.value)} />
      </div>
      {loading && !data ? <Loading /> : error ? <ErrorBox message={error} onRetry={reload} /> : data.length === 0 ? (
        <EmptyState message={q ? "Nobody matches your search" : "Nobody here yet"} hint={q ? "Try a different name or email." : emptyHint} />
      ) : (
        <div className="space-y-3">
          {data.map((p) => (
            <PersonCard key={p.id} name={p.full_name} muted={!p.is_active}
              subtitle={p.email}
              badge={<>{!role && <StatusPill value={p.role} />}{!p.is_active && <span className="rounded-full bg-red-100 px-2.5 py-1 text-xs font-bold text-red-700">Cannot log in</span>}</>}
              facts={[...p.details, ...(p.phone ? [["Phone", p.phone]] : []), ["Last login", timeAgo(p.last_login)]]}
              actions={p.id !== me.id && (
                <Button variant={p.is_active ? "secondary" : "soft"} onClick={() => toggle(p)}>
                  {p.is_active ? <><UserX size={15} className="mr-1.5 inline" /> Deactivate</> : <><UserCheck size={15} className="mr-1.5 inline" /> Activate</>}
                </Button>)} />
          ))}
        </div>
      )}
    </div>
  );
}
