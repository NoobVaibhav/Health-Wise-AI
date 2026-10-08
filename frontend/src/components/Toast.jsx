// Small pop-up messages ("Note saved") so users always know that an action worked.
import { createContext, useCallback, useContext, useState } from "react";
import { CheckCircle2, XCircle } from "lucide-react";

const ToastContext = createContext(() => {});
export const useToast = () => useContext(ToastContext);

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const toast = useCallback((message, type = "success") => {
    const id = Math.random().toString(36).slice(2);
    setToasts((t) => [...t, { id, message, type }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 4000);
  }, []);
  return (
    <ToastContext.Provider value={toast}>
      {children}
      <div className="pointer-events-none fixed bottom-5 right-5 z-[60] flex flex-col gap-2">
        {toasts.map((t) => (
          <div key={t.id} className={`toast-in pointer-events-auto flex items-center gap-2 rounded-2xl px-4 py-3 text-sm font-semibold text-white shadow-xl ${t.type === "error" ? "bg-red-600" : "bg-emerald-600"}`}>
            {t.type === "error" ? <XCircle size={18} /> : <CheckCircle2 size={18} />}
            {t.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
