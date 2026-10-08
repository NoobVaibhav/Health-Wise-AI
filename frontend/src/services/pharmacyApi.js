import api from "./api";

export const getPharmacyDashboard = () => api.get("/pharmacy/dashboard").then((r) => r.data);
export const searchPrescriptions = (q, statusFilter) =>
  api.get("/pharmacy/prescriptions", { params: { ...(q ? { q } : {}), ...(statusFilter ? { status_filter: statusFilter } : {}) } }).then((r) => r.data);
export const dispense = (data) => api.post("/pharmacy/dispense", data).then((r) => r.data);
export const getDispensingHistory = () => api.get("/pharmacy/history").then((r) => r.data);
export const listInventory = (q) => api.get("/pharmacy/inventory", { params: q ? { q } : {} }).then((r) => r.data);
export const addInventory = (data) => api.post("/pharmacy/inventory", data).then((r) => r.data);
export const updateInventory = (id, data) => api.put(`/pharmacy/inventory/${id}`, data).then((r) => r.data);
