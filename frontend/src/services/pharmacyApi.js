import api from "./api";

export const getPharmacyDashboard = () => api.get("/pharmacy/dashboard").then((r) => r.data);
export const searchPrescriptions = (q, statusFilter) =>
  api.get("/pharmacy/prescriptions", { params: { ...(q ? { q } : {}), ...(statusFilter ? { status_filter: statusFilter } : {}) } }).then((r) => r.data);
export const dispense = (data) => api.post("/pharmacy/dispense", data).then((r) => r.data);
export const getDispensingHistory = () => api.get("/pharmacy/history").then((r) => r.data);
export const listInventory = (q) => api.get("/pharmacy/inventory", { params: q ? { q } : {} }).then((r) => r.data);
export const addInventory = (data) => api.post("/pharmacy/inventory", data).then((r) => r.data);
export const lookupBarcode = (code) => api.get("/pharmacy/inventory/lookup", { params: { code } }).then((r) => r.data);
export const receiveStock = (data) => api.post("/pharmacy/inventory/receive", data).then((r) => r.data);
export const createSale = (data) => api.post("/pharmacy/sales", data).then((r) => r.data);
export const listSales = (q = "") => api.get("/pharmacy/sales", { params: q ? { q } : {} }).then((r) => r.data);
export const getSale = (id) => api.get(`/pharmacy/sales/${id}`).then((r) => r.data);
export const getBillPreview = (prescriptionId) => api.get(`/pharmacy/prescriptions/${prescriptionId}/bill-preview`).then((r) => r.data);
export const createPrescriptionBill = (prescriptionId, data) => api.post(`/pharmacy/prescriptions/${prescriptionId}/bill`, data).then((r) => r.data);
export const getSalesSummary = () => api.get("/pharmacy/sales/summary").then((r) => r.data);
export const updateInventory = (id, data) => api.put(`/pharmacy/inventory/${id}`, data).then((r) => r.data);
