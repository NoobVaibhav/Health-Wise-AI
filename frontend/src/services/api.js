// One shared Axios instance: adds the JWT to every request and turns errors into friendly messages.
import axios from "axios";

const TOKEN_KEY = "healthwise_token";

/** Patient details saved in this browser (the unsaved history drafts). They are removed when the person logs out, so the next person at a shared computer cannot read them. */
export function clearSavedPatientData() {
  try {
    for (const key of Object.keys(localStorage)) if (key.startsWith("hw_history_draft_")) localStorage.removeItem(key);
  } catch { /* storage may be blocked: nothing was saved */ }
}

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (t) => localStorage.setItem(TOKEN_KEY, t),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

const api = axios.create({
  baseURL: (import.meta.env.VITE_API_URL || "") + "/api",
  timeout: 120000, // OCR of a multi-page scan can take a while
});

api.interceptors.request.use((config) => {
  const token = tokenStore.get();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Expired / invalid token on a protected call -> go back to the login page.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const url = error.config?.url || "";
    if (error.response?.status === 401 && !url.includes("/auth/login") && !url.includes("/auth/register")) {
      tokenStore.clear();
      if (window.location.pathname !== "/login") window.location.href = "/login";
    }
    return Promise.reject(error);
  }
);

/** { field: message } from a 422 answer of the server, to show each message under its own field. */
export function getFieldErrors(error) {
  const rows = error?.response?.data?.errors;
  if (!Array.isArray(rows)) return {};
  const out = {};
  for (const r of rows) if (r.field && !out[r.field]) out[r.field] = r.message;
  return out;
}

/** Never show a bare "Failed to fetch" / "Network Error": always return a useful sentence. */
export function getErrorMessage(error) {
  if (error.response) {
    const detail = error.response.data?.detail;
    // FastAPI's own "Not Found" means the URL does not exist on the running server: it is older than the app.
    if (error.response.status === 404 && detail === "Not Found") {
      return "The server does not know this feature yet. The backend was probably started before the latest update. Please stop it and start it again (uvicorn app.main:app --reload).";
    }
    if (typeof detail === "string") return detail;                                    // the server writes one readable sentence for invalid input (422)
    if (Array.isArray(detail)) return [...new Set(detail.map((d) => String(d.msg || "").replace(/^Value error, /, "")))].join(" ");
    return "Something went wrong while processing your request. Please try again.";
  }
  if (error.code === "ECONNABORTED") {
    return "The server took too long to respond. The report may be large; please try again.";
  }
  return "HealthWise AI server is currently unavailable. Please start the backend or try again.";
}

export default api;
