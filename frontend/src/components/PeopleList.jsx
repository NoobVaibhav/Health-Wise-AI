// Cards for people (doctors, employees, pharmacy staff, patients, admins) with an activate/deactivate button.
import { useState } from "react";
import { AlertTriangle, Pencil, Search, Trash2, UserCheck, UserX } from "lucide-react";
import usePagedFetch from "../hooks/usePagedFetch";
import ShowMore from "./ShowMore";
import { useAuth } from "../context/AuthContext";
import { checkDeleteUser, deleteUser, listPeoplePage, updateUser } from "../services/adminApi";
import { getErrorMessage } from "../services/api";
import { PersonCard, timeAgo } from "./DataViews";
import { StatusPill } from "./StatusBadge";
import { EmptyState, ErrorBox, Loading } from "./Feedback";
import { Button, Modal, inputClass } from "./ui";
import EditDoctorDialog from "./EditDoctorDialog";
import { useToast } from "./Toast";

export default function PeopleList({ role, reloadKey, emptyHint }) {
  const { user: me } = useAuth();
  const toast = useToast();
  const [q, setQ] = useState("");
  const { data, total, loading, loadingMore, error, reload, loadMore, hasMore } = usePagedFetch((offset) => listPeoplePage(role, q, offset), [role, q, reloadKey]);

  const [removing, setRemoving] = useState(null);      // { person, check } : the person the admin may delete, and why not if not
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(null);       // a doctor whose department and specialization the admin is changing

  const askDelete = async (p) => {
    try { setRemoving({ person: p, check: await checkDeleteUser(p.id) }); } catch (e) { toast(getErrorMessage(e), "error"); }
  };
  const confirmDelete = async () => {
    setBusy(true);
    try { await deleteUser(removing.person.id); toast(`${removing.person.full_name} was deleted`); setRemoving(null); reload(); } catch (e) { toast(getErrorMessage(e), "error"); setRemoving(null); } finally { setBusy(false); }
  };

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
            <PersonCard key={p.id} name={p.full_name} muted={!p.is_active} userId={p.id} avatarVersion={p.has_avatar ? p.avatar_version : null}
              subtitle={p.email}
              badge={<>{!role && <StatusPill value={p.role} />}{!p.is_active && <span className="rounded-full bg-red-100 px-2.5 py-1 text-xs font-bold text-red-700">Cannot log in</span>}</>}
              facts={[...p.details, ...(p.phone ? [["Phone", p.phone]] : []), ["Last login", timeAgo(p.last_login)]]}
              actions={p.id !== me.id && (
                <div className="flex flex-wrap gap-2">
                  {p.role === "DOCTOR" && <Button variant="secondary" onClick={() => setEditing(p)} aria-label={`Edit department of ${p.full_name}`}><Pencil size={15} className="mr-1.5 inline" /> Edit</Button>}
                  <Button variant={p.is_active ? "secondary" : "soft"} onClick={() => toggle(p)}>
                    {p.is_active ? <><UserX size={15} className="mr-1.5 inline" /> Deactivate</> : <><UserCheck size={15} className="mr-1.5 inline" /> Activate</>}
                  </Button>
                  <Button variant="danger" onClick={() => askDelete(p)} aria-label={`Delete ${p.full_name}`}><Trash2 size={15} className="mr-1.5 inline" /> Delete</Button>
                </div>)} />
          ))}
          <ShowMore shown={data.length} total={total} hasMore={hasMore} loading={loadingMore} onMore={loadMore} noun="people" />
        </div>
      )}

      {editing && <EditDoctorDialog person={editing} onClose={() => setEditing(null)} onSaved={() => { toast(`${editing.full_name} was updated`); reload(); }} />}

      {removing && (
        <Modal title={`Delete ${removing.person.full_name}?`} onClose={() => setRemoving(null)}>
          {removing.check.can_delete ? (
            <>
              <p className="text-slate-700">This account has no records linked to it, so it can be deleted. <b>This cannot be undone.</b> The email <b>{removing.person.email}</b> can be registered again afterwards.</p>
              <div className="mt-5 flex justify-end gap-2"><Button variant="secondary" onClick={() => setRemoving(null)}>Keep the account</Button><Button variant="danger" disabled={busy} onClick={confirmDelete}>{busy ? "Deleting..." : "Yes, delete permanently"}</Button></div>
            </>
          ) : (
            <>
              <p className="flex items-start gap-2 rounded-xl bg-amber-50 p-3 font-semibold text-amber-900"><AlertTriangle size={20} className="mt-0.5 shrink-0" /><span>This account cannot be deleted.</span></p>
              <ul className="mt-3 list-disc space-y-1 pl-5 text-slate-700">{removing.check.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
              <div className="mt-5 flex justify-end gap-2">
                <Button variant="secondary" onClick={() => setRemoving(null)}>Close</Button>
                {removing.person.is_active && <Button onClick={() => { const p = removing.person; setRemoving(null); toggle(p); }}>Deactivate instead</Button>}
              </div>
            </>
          )}
        </Modal>
      )}
    </div>
  );
}
