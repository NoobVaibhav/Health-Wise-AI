// Like useFetch for a long list: the first page loads at once, `loadMore` adds the next one.
// { data (rows so far), total, loading, loadingMore, error, reload, loadMore, hasMore }
import { useCallback, useEffect, useRef, useState } from "react";
import { getErrorMessage } from "../services/api";

export default function usePagedFetch(fetchPage, deps = []) {
  const [data, setData] = useState(null);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState("");
  const latest = useRef(0);                      // an answer to an older search must not replace the newer one

  const load = useCallback(() => {
    const mine = ++latest.current;
    setLoading(true);
    setError("");
    return fetchPage(0)
      .then(({ rows, total: all }) => { if (mine === latest.current) { setData(rows); setTotal(all); } })
      .catch((e) => { if (mine === latest.current) setError(getErrorMessage(e)); })
      .finally(() => { if (mine === latest.current) setLoading(false); });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => { load(); }, [load]);

  const loadMore = useCallback(() => {
    const mine = latest.current;
    setLoadingMore(true);
    return fetchPage(data?.length || 0)
      .then(({ rows, total: all }) => { if (mine === latest.current) { setData((old) => [...(old || []), ...rows]); setTotal(all); } })
      .catch((e) => { if (mine === latest.current) setError(getErrorMessage(e)); })
      .finally(() => setLoadingMore(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data, ...deps]);

  return { data, total, loading, loadingMore, error, reload: load, loadMore, hasMore: !!data && data.length < total };
}
