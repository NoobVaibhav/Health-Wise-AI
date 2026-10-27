import { ShieldCheck } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import ChangePasswordForm from "./ChangePasswordForm";

// Shown over the app right after someone logs in with the system-generated (starting) password. It cannot be closed: nothing else works until a new password is saved.
export default function ChangePasswordDialog() {
  const { user, logout } = useAuth();
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center overflow-y-auto bg-slate-900/60 p-4 backdrop-blur-sm">
      <div role="dialog" aria-modal="true" aria-labelledby="first-login-title" className="page-enter w-full max-w-md rounded-3xl bg-white p-6 shadow-2xl">
        <div className="mb-4 flex items-center gap-3">
          <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-brand-100 text-brand-700"><ShieldCheck size={26} /></span>
          <div>
            <h2 id="first-login-title" className="text-xl font-extrabold text-slate-900">Choose your own password</h2>
            <p className="text-sm text-slate-500">Welcome, <b className="text-slate-700">{user.full_name}</b></p>
          </div>
        </div>
        <p className="mb-4 rounded-2xl bg-amber-50 p-3 text-sm text-amber-900">You logged in with the starting password the hospital gave you. Please set a password that only you know. It takes a few seconds.</p>
        <ChangePasswordForm first />
        <button type="button" onClick={logout} className="mt-3 w-full text-center text-sm font-semibold text-slate-500 hover:text-slate-800">Log out instead</button>
      </div>
    </div>
  );
}
