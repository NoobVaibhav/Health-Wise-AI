// Runs a save or an action: shows the server's sentence when it fails (the typed values stay), a toast when it works. Returns the answer, or null when it failed.
import { useState } from "react";
import { getErrorMessage } from "../services/api";
import { useToast } from "../components/Toast";

export default function useSave() {
  const toast = useToast();
  const [problem, setProblem] = useState("");
  const [busy, setBusy] = useState(false);
  const run = async (fn, message) => {
    setProblem("");
    setBusy(true);
    try {
      const result = await fn();
      if (message) toast(message);
      return result ?? true;
    } catch (e) {
      setProblem(getErrorMessage(e));
      return null;
    } finally { setBusy(false); }
  };
  return { problem, busy, run, clear: () => setProblem("") };
}
