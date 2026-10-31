// "My profile" for every role: profile picture, name, the details of the role, and the account information.
// What the hospital assigns (job, department, patient ID, medical details ...) is shown but cannot be edited here.
import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Camera, KeyRound, Trash2 } from "lucide-react";
import useFetch from "../../hooks/useFetch";
import { deleteAvatar, getProfile, updateProfile, uploadAvatar } from "../../services/profileApi";
import { getErrorMessage, getFieldErrors } from "../../services/api";
import { FormField } from "../../components/FormField";
import * as v from "../../utils/validators";
import { Avatar } from "../../components/DataViews";
import { Section } from "../../components/HealthCard";
import { StatusPill } from "../../components/StatusBadge";
import { ErrorBox, Hint, Loading, PageTitle } from "../../components/Feedback";
import { Button, Field, Input, Textarea, fmtDate, fmtUtc, inputClass } from "../../components/ui";
import { useToast } from "../../components/Toast";
import { useAuth } from "../../context/AuthContext";

export default function Profile() {
  const toast = useToast();
  const { refresh } = useAuth();
  const { data, loading, error, reload } = useFetch(getProfile, []);
  const picker = useRef(null);
  const [edits, setEdits] = useState({});            // changed values only
  const [name, setName] = useState(null);
  const [busy, setBusy] = useState("");
  const [problem, setProblem] = useState("");
  const [errs, setErrs] = useState({});                 // messages under the fields

  if (loading && !data) return <Loading />;
  if (error) return <ErrorBox message={error} onRetry={reload} />;
  const u = data.user;
  const changed = name !== null && name !== u.full_name || Object.keys(edits).length > 0;

  const done = async (message) => { toast(message); setEdits({}); setName(null); await reload(); await refresh(); };

  const choosePhoto = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    const wrong = v.file(file, v.AVATAR_FILE);         // type, size (2 MB) and empty file; the server looks at the real picture again
    if (wrong) { setProblem(wrong); return; }
    setBusy("photo");
    setProblem("");
    try { await uploadAvatar(file); await done("Your photo was saved"); } catch (err) { setProblem(getErrorMessage(err)); } finally { setBusy(""); }
  };
  const removePhoto = async () => {
    if (!window.confirm("Remove your profile photo?")) return;
    setBusy("photo");
    try { await deleteAvatar(); await done("Your photo was removed"); } catch (err) { setProblem(getErrorMessage(err)); } finally { setBusy(""); }
  };
  const save = async (e) => {
    e.preventDefault();
    if (busy) return;
    const found = {};
    if (name !== null && v.personName(name)) found.full_name = v.personName(name);
    for (const f of editable) if (f.key in edits) { const m = f.key === "phone" ? v.phone(edits[f.key]) : v.text(edits[f.key], { max: 300 }); if (m) found[f.key] = m; }
    setErrs(found);
    const first = Object.keys(found)[0];
    if (first) { document.getElementById(first)?.focus(); return; }
    setBusy("save");
    setProblem("");
    try {
      await updateProfile({ ...(name !== null ? { full_name: v.cleanText(name) } : {}), values: edits });
      await done("Your details were saved");
    } catch (err) { const server = getFieldErrors(err); if (Object.keys(server).length) setErrs(server); else setProblem(getErrorMessage(err)); } finally { setBusy(""); }
  };

  const valueOf = (f) => (f.key in edits ? edits[f.key] : f.value ?? "");
  const editable = data.fields.filter((f) => f.editable);
  const fixed = data.fields.filter((f) => !f.editable);

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <PageTitle title="My profile" subtitle="Your photo and your details. Keep them up to date so people can recognise and reach you." />

      <Section>
        <div className="flex flex-wrap items-center gap-6">
          <Avatar name={u.full_name} size={120} userId={u.id} version={u.avatar_version} round />
          <div className="min-w-0 flex-1">
            <p className="break-words text-2xl font-extrabold text-slate-900">{u.full_name}</p>
            <p className="mt-1 flex flex-wrap items-center gap-2 text-base text-slate-600"><StatusPill value={u.role} /> <span className="min-w-0 break-all">{u.email}</span></p>
            <div className="mt-4 flex flex-wrap gap-3">
              <input ref={picker} type="file" accept="image/jpeg,image/png" className="sr-only" aria-label="Choose a profile photo" onChange={choosePhoto} />
              <Button type="button" onClick={() => picker.current?.click()} disabled={busy === "photo"}><Camera size={20} /> {busy === "photo" ? "Saving..." : u.has_avatar ? "Change photo" : "Add a photo"}</Button>
              {u.has_avatar && <Button type="button" variant="secondary" onClick={removePhoto} disabled={busy === "photo"} className="!border-red-600 !text-red-700 hover:!bg-red-50"><Trash2 size={18} /> Remove photo</Button>}
              <p className="w-full text-xs text-slate-500">Photo: {v.AVATAR_FILE.hint}.</p>
            </div>
            <p className="mt-2 text-sm text-slate-500">A JPG, PNG or WEBP picture under 5 MB. It is cropped to a square.</p>
          </div>
        </div>
        {problem && <div className="mt-4"><ErrorBox message={problem} /></div>}
      </Section>

      <form onSubmit={save} className="space-y-5">
        <Section title="My details">
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField label="Full name" name="full_name" error={errs.full_name}>
              <Input autoComplete="name" maxLength={150} value={name ?? u.full_name} onChange={(e) => { setName(e.target.value); setErrs({ ...errs, full_name: "" }); }}
                onBlur={() => name !== null && setErrs({ ...errs, full_name: v.personName(name) })} />
            </FormField>
            {editable.map((f) => (
              <FormField key={f.key} label={f.label} name={f.key} hint={f.help} error={errs[f.key]}>
                {f.kind === "textarea"
                  ? <Textarea rows={2} maxLength={300} value={valueOf(f)} onChange={(e) => { setEdits({ ...edits, [f.key]: e.target.value }); setErrs({ ...errs, [f.key]: "" }); }} />
                  : <Input type={f.kind === "number" ? "number" : f.key === "phone" ? "tel" : "text"} inputMode={f.key === "phone" ? "tel" : undefined} min={f.kind === "number" ? 0 : undefined} max={f.kind === "number" ? 70 : undefined}
                      maxLength={f.kind === "number" ? undefined : f.key === "phone" ? 20 : 150} value={valueOf(f)} onChange={(e) => { setEdits({ ...edits, [f.key]: e.target.value }); setErrs({ ...errs, [f.key]: "" }); }}
                      onBlur={() => f.key === "phone" && setErrs({ ...errs, phone: v.phone(valueOf(f)) })} />}
              </FormField>
            ))}
          </div>
          <Button disabled={!changed || busy === "save"} className="mt-5 w-full sm:w-auto sm:min-w-64">{busy === "save" ? "Saving..." : "✓ Save my details"}</Button>
          {!changed && <p className="mt-2 text-sm text-slate-500">Change something above, then press the button to save it.</p>}
        </Section>
      </form>

      {fixed.length > 0 && (
        <Section title="Set by the hospital">
          <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
            {fixed.map((f) => (
              <div key={f.key}>
                <dt className="text-sm font-semibold text-slate-500">{f.label}</dt>
                <dd className="whitespace-pre-line text-base font-semibold text-slate-900">{f.kind === "date" && f.value ? fmtDate(f.value) : f.value || <span className="font-normal text-slate-400">Not provided</span>}</dd>
                {f.help && <dd className="text-xs text-slate-500">{f.help}</dd>}
              </div>
            ))}
          </dl>
        </Section>
      )}

      <Section title="My account">
        <dl className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
          <div><dt className="text-sm font-semibold text-slate-500">Email (used to log in)</dt><dd className="text-base font-semibold text-slate-900">{u.email}</dd></div>
          <div><dt className="text-sm font-semibold text-slate-500">Role</dt><dd className="text-base font-semibold text-slate-900">{u.role_label}</dd></div>
          <div><dt className="text-sm font-semibold text-slate-500">Account created</dt><dd className="text-base font-semibold text-slate-900">{fmtUtc(u.created_at)}</dd></div>
          <div><dt className="text-sm font-semibold text-slate-500">Last login</dt><dd className="text-base font-semibold text-slate-900">{u.last_login ? fmtUtc(u.last_login) : "This is your first login"}</dd></div>
        </dl>
        <Link to="/change-password" className="mt-5 inline-flex min-h-11 items-center gap-2 rounded-xl border-2 border-brand-700 bg-white px-5 py-2.5 text-base font-bold text-brand-800 hover:bg-brand-50"><KeyRound size={18} /> Change my password</Link>
      </Section>

      <Hint title="Who sees my photo?">Hospital staff can see your photo next to your name. A patient's photo is visible only to the patient, the admin, doctors and reception.</Hint>
    </div>
  );
}
