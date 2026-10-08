import api from "./api";

export const getSetupStatus = () => api.get("/auth/setup-status").then((r) => r.data);
export const registerFirstAdmin = (data) => api.post("/auth/register", data).then((r) => r.data);
export const login = (data) => api.post("/auth/login", data).then((r) => r.data);
export const getHealth = () => api.get("/health").then((r) => r.data);
export const getMe = () => api.get("/auth/me").then((r) => r.data);
export const changePassword = (data) => api.post("/auth/change-password", data).then((r) => r.data);
