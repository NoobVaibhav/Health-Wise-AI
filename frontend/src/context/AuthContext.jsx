import { createContext, useContext, useEffect, useState } from "react";
import * as authApi from "../services/authApi";
import { tokenStore } from "../services/api";

const AuthContext = createContext(null);

// Where each role lands after login.
export const ROLE_HOME = { ADMIN: "/admin", DOCTOR: "/doctor", EMPLOYEE: "/employee", PATIENT: "/patient", PHARMACY: "/pharmacy" };

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
      setUser(null);
    },
    refresh: () => authApi.getMe().then(setUser),
  };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
