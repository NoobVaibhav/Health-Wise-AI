// The foot of a paged list: how many are shown, and a button for the next page.
import { Button } from "./ui";

export default function ShowMore({ shown, total, hasMore, loading, onMore, noun = "items" }) {
  if (!total) return null;
  return (
    <div className="flex flex-col items-center gap-2 py-2 text-sm text-slate-600">
      <p>Showing {shown} of {total} {noun}</p>
      {hasMore && <Button variant="secondary" onClick={onMore} disabled={loading}>{loading ? "Loading…" : "Show more"}</Button>}
    </div>
  );
}
