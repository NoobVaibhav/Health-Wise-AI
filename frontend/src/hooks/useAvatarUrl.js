// Profile pictures are private: the browser cannot load them with a plain <img src>, because that sends no login.
// This asks the API (with the login) and turns the answer into a local picture address. Each picture is fetched
// once per version; when someone changes their photo its version changes and the new one is fetched.
import { useEffect, useState } from "react";
import api from "../services/api";

const cache = new Map();   // "userId:version" -> Promise<string | null>

export function loadAvatar(userId, version) {
  const key = `${userId}:${version}`;
  if (!cache.has(key)) {
    cache.set(key, api.get(`/profile/avatar/${userId}`, { responseType: "blob" })
      .then((r) => URL.createObjectURL(r.data))
      .catch(() => { cache.delete(key); return null; }));
  }
  return cache.get(key);
}

export default function useAvatarUrl(userId, version) {
  const [url, setUrl] = useState(null);
  useEffect(() => {
    let alive = true;
    if (!userId || !version) { setUrl(null); return undefined; }
    loadAvatar(userId, version).then((u) => { if (alive) setUrl(u); });
    return () => { alive = false; };
  }, [userId, version]);
  return url;
}
