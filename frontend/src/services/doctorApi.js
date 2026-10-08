import api from "./api";

export const listDoctors = () => api.get("/doctors").then((r) => r.data);
export const getDoctorDashboard = () => api.get("/doctor/dashboard").then((r) => r.data);
export const getMyPatients = (q) => api.get("/doctor/patients", { params: q ? { q } : {} }).then((r) => r.data);
export const getPatientHistory = (id, q) =>
  api.get(`/doctor/patients/${id}/history`, { params: q ? { q } : {} }).then((r) => r.data);
export const reviewReport = (id, data) => api.put(`/doctor/reports/${id}/review`, data).then((r) => r.data);
export const addNote = (data) => api.post("/doctor/notes", data).then((r) => r.data);
export const getDoctorNotes = () => api.get("/doctor/notes").then((r) => r.data);
export const addRecommendation = (data) => api.post("/doctor/recommendations", data).then((r) => r.data);
export const getDoctorRecommendations = () => api.get("/doctor/recommendations").then((r) => r.data);
export const addHistoryEntry = (data) => api.post("/doctor/history-entries", data).then((r) => r.data);
