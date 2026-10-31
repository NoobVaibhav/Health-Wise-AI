import { useCallback, useState } from "react";
import { getFieldErrors } from "../services/api";

/** Field errors for a form. `rules` is { field: (value, allValues) => message }.
 *  check(name, values): validate one field (use it on blur); validateAll(values): validate everything, put the cursor in the first wrong field and
 *  return true when the form may be sent; fromServer(error): show the messages the server sent under their fields; the typed values are never cleared. */
export default function useValidation(rules) {
  const [errors, setErrors] = useState({});

  const check = useCallback((name, values) => {
    const message = rules[name]?.(values[name], values) || "";
    setErrors((e) => (e[name] === message ? e : { ...e, [name]: message }));
    return message;
  }, [rules]);

  const clear = useCallback((name) => setErrors((e) => (e[name] ? { ...e, [name]: "" } : e)), []);

  const validateAll = useCallback((values) => {
    const next = {};
    for (const [name, rule] of Object.entries(rules)) next[name] = rule(values[name], values) || "";
    setErrors(next);
    const first = Object.keys(next).find((k) => next[k]);
    if (first) document.getElementById(first)?.focus();
    return !first;
  }, [rules]);

  /** Returns true when at least one server message belonged to a field of this form (the caller then needs no separate banner). */
  const fromServer = useCallback((error) => {
    const byField = getFieldErrors(error);
    const known = Object.keys(byField).filter((f) => f in rules);
    if (!known.length) return false;
    setErrors((e) => ({ ...e, ...Object.fromEntries(known.map((f) => [f, byField[f]])) }));
    document.getElementById(known[0])?.focus();
    return true;
  }, [rules]);

  return { errors, check, clear, validateAll, fromServer, setErrors };
}
