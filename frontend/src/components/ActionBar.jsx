// The row of buttons that belongs to a whole form (Save draft, Sign, Next). It sticks to the bottom of the screen while the form scrolls, stays above the phone's
// home indicator, and is part of the page flow, so the last field is never hidden under it.
export default function ActionBar({ children, status, className = "" }) {
  return (
    <div data-action-bar className={`sticky bottom-0 z-20 -mx-3 mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-slate-200 bg-white/95 px-3 pb-[max(0.75rem,var(--safe-bottom))] pt-3 shadow-sheet backdrop-blur-sm sm:-mx-4 sm:px-4 lg:-mx-6 lg:px-6 xl:-mx-8 xl:px-8 ${className}`}>
      {status !== undefined && <div className="min-w-0 text-sm">{status}</div>}
      <div className="ml-auto flex flex-wrap items-center justify-end gap-2">{children}</div>
    </div>
  );
}
