import { Link } from "react-router-dom";
import { AlertCircle, Inbox, Info } from "lucide-react";

// A calm placeholder in the shape of a page (a heading and two cards), so nothing jumps when the real page arrives.
export const Loading = ({ text = "Loading..." }) => (
  <div role="status" aria-live="polite" className="space-y-3 py-2">
    <span className="sr-only">{text}</span>
    <div className="skeleton h-7 w-2/5" aria-hidden="true" />
    <div className="skeleton h-24 w-full" aria-hidden="true" />
    <div className="skeleton h-24 w-full" aria-hidden="true" />
  </div>
);

export const ErrorBox = ({ message, onRetry }) => (
  <div className="flex gap-3 rounded-2xl border border-red-200 bg-red-50 p-4 text-red-700">
    <AlertCircle className="mt-0.5 shrink-0" size={20} />
    <div>
      <p>{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="mt-2 text-sm font-semibold underline">
          Try again
        </button>
      )}
    </div>
  </div>
);

// Friendly empty state: says what is missing and what to do next.
export const EmptyState = ({ message, hint, actionTo, actionText, icon: Icon = Inbox }) => (
  <div className="rounded-3xl border-2 border-dashed border-slate-200 bg-white/70 p-10 text-center">
    <span className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-50 text-brand-600">
      <Icon size={28} />
    </span>
    <p className="text-lg font-semibold text-slate-700">{message}</p>
    {hint && <p className="mx-auto mt-1 max-w-md text-sm text-slate-500">{hint}</p>}
    {actionTo && (
      <Link to={actionTo} className="mt-4 inline-block rounded-xl bg-brand-600 px-5 py-2.5 text-sm font-semibold text-white shadow-sm hover:bg-brand-700">
        {actionText}
      </Link>
    )}
  </div>
);

export const PageTitle = ({ title, subtitle, icon: Icon }) => (
  <div className="mb-3 flex items-start gap-3 md:mb-5">
    {Icon && (
      <span className="mt-1 flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-brand-500 to-brand-700 text-white shadow">
        <Icon size={22} />
      </span>
    )}
    <div className="min-w-0">
      <h1 className="text-xl font-extrabold tracking-tight text-slate-900 md:text-3xl">{title}</h1>
      {subtitle && <p className="mt-0.5 line-clamp-2 text-sm text-slate-600 sm:line-clamp-none sm:text-base sm:text-slate-500">{subtitle}</p>}
    </div>
  </div>
);

// "In simple words" explanation box for non-technical users.
export const Hint = ({ title = "In simple words", children }) => (
  <div className="flex gap-3 rounded-2xl border border-sky-200 bg-sky-50 p-4 text-sm text-sky-900">
    <Info className="mt-0.5 shrink-0 text-sky-600" size={18} />
    <div>
      <p className="font-semibold">{title}</p>
      <div className="text-sky-800">{children}</div>
    </div>
  </div>
);
