import api from "./api";

export const listAppointments = (params = {}) => api.get("/appointments", { params }).then((r) => r.data);
export const createAppointment = (data) => api.post("/appointments", data).then((r) => r.data);
export const updateAppointment = (id, data) => api.put(`/appointments/${id}`, data).then((r) => r.data);
