import { ArrowLeft } from "lucide-react";
import useLayoutMode from "../hooks/useLayoutMode";

// Master-detail. From 1024 px wide the list stays on the left and the detail opens on the right, each scrolling on its own. Below that only one of them
// shows at a time: the list, or the detail with a Back button. `hasSelection` says whether something is open.
export default function SplitView({ list, detail, hasSelection, onBack, emptyDetail = null, listLabel = "List", detailLabel = "Details", listWidth = "minmax(18rem, 24rem)" }) {
  const { split } = useLayoutMode();
  if (!split) {
    return hasSelection ? (
      <section aria-label={detailLabel} className="space-y-3">
        {onBack && <button type="button" onClick={onBack} className="inline-flex min-h-11 items-center gap-1.5 rounded-xl border-2 border-brand-700 bg-white px-4 font-bold text-brand-800"><ArrowLeft size={16} aria-hidden="true" /> Back to the list</button>}
        {detail}
      </section>
    ) : <section aria-label={listLabel}>{list}</section>;
  }
  return (
    <div className="grid items-start gap-4" style={{ gridTemplateColumns: `${listWidth} minmax(0, 1fr)` }} data-split>
      <section aria-label={listLabel} className="max-h-[calc(100dvh-9rem)] overflow-y-auto overscroll-contain pr-1">{list}</section>
      <section aria-label={detailLabel} className="max-h-[calc(100dvh-9rem)] min-w-0 overflow-y-auto overscroll-contain">{hasSelection ? detail : emptyDetail}</section>
    </div>
  );
}
