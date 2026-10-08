import api from "./api";

export const listPatients = (q) => api.get("/patients", { params: q ? { q } : {} }).then((r) => r.data);
export const getPatient = (id) => api.get(`/patients/${id}`).then((r) => r.data);
export const registerPatient = (data) => api.post("/patients", data).then((r) => r.data);
export const updatePatient = (id, data) => api.put(`/patients/${id}`, data).then((r) => r.data);
export const getComparison = (patientId, previous, latest) =>
  api.get(`/patients/${patientId}/comparison`, { params: previous && latest ? { previous, latest } : {} }).then((r) => r.data);
export const getTrendList = (patientId) => api.get(`/patients/${patientId}/trends`).then((r) => r.data);
export const getTrend = (patientId, name) =>
  api.get(`/patients/${patientId}/trends/${encodeURIComponent(name)}`).then((r) => r.data);

// patient portal
export const getPatientDashboard = () => api.get("/patient/dashboard").then((r) => r.data);
export const getMyProfile = () => api.get("/patient/profile").then((r) => r.data);
export const getMyHistory = (q) => api.get("/patient/history", { params: q ? { q } : {} }).then((r) => r.data);
export const getMyNotes = () => api.get("/patient/notes").then((r) => r.data);
export const getMyRecommendations = () => api.get("/patient/recommendations").then((r) => r.data);
export const getMyPrescriptions = () => api.get("/patient/prescriptions").then((r) => r.data);
