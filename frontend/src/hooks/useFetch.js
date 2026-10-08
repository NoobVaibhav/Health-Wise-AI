// Tiny data-loading hook: { data, loading, error, reload }.
import { useCallback, useEffect, useState } from "react";
import { getErrorMessage } from "../services/api";

export default function useFetch(fetcher, deps = []) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    return fetcher()
      .then(setData)
      .catch((e) => setError(getErrorMessage(e)))
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    load();
  }, [load]);

  return { data, loading, error, reload: load, setData };
}
