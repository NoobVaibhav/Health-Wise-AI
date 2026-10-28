import { createContext, useContext, useEffect, useState } from "react";
import * as authApi from "../services/authApi";
import { clearSavedPatientData, tokenStore } from "../services/api";

const AuthContext = createContext(null);

// Where each role lands after login.
export const ROLE_HOME = { ADMIN: "/admin", DOCTOR: "/doctor", EMPLOYEE: "/employee", PATIENT: "/patient", PHARMACY: "/pharmacy", LAB: "/lab" };

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // On first load: if a token is saved, ask the backend who we are (and which role).
  useEffect(() => {
    if (!tokenStore.get()) {
      setLoading(false);
      return;
    }
    authApi
      .getMe()
      .then(setUser)
      .catch(() => tokenStore.clear())
      .finally(() => setLoading(false));
  }, []);

  // Logging out (or logging in as someone else) in another tab ends this tab's session at once, instead of showing the old person's pages.
  useEffect(() => {
    const onStorage = (e) => {
      if (e.key !== "healthwise_token") return;
      if (!e.newValue) setUser(null);
      else if (e.newValue !== e.oldValue) authApi.getMe().then(setUser).catch(() => setUser(null));
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const value = {
    user,
    loading,
    login: async (email, password) => {
      const data = await authApi.login({ email, password });
      tokenStore.set(data.access_token);
      setUser(data.user);
      return data.user;
    },
    registerFirstAdmin: async (form) => {
      const data = await authApi.registerFirstAdmin(form);
      tokenStore.set(data.access_token);
      setUser(data.user);
      return data.user;
    },
    logout: () => {
      tokenStore.clear();
      clearSavedPatientData();
      setUser(null);
    },
    refresh: () => authApi.getMe().then(setUser),
  };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
