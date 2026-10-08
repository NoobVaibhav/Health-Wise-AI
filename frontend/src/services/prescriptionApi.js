import api from "./api";

export const listPrescriptions = (params = {}) => api.get("/prescriptions", { params }).then((r) => r.data);
export const getPrescription = (id) => api.get(`/prescriptions/${id}`).then((r) => r.data);
export const createPrescription = (data) => api.post("/prescriptions", data).then((r) => r.data);
export const cancelPrescription = (id) => api.put(`/prescriptions/${id}/cancel`).then((r) => r.data);
