import api from "./api";

// the patient's own health history (read-only: only doctors change it)
export const getMyHistory = () => api.get("/health-history/me").then((r) => r.data);

// a doctor reading or adding to the history of one of their patients
export const getPatientHistoryForm = (patientId) => api.get(`/health-history/patient/${patientId}`).then((r) => r.data);
export const savePatientHistoryForm = (patientId, data) => api.put(`/health-history/patient/${patientId}`, data).then((r) => r.data);
export const previewPoints = (patientId, data) => api.post(`/health-history/patient/${patientId}/preview`, data).then((r) => r.data);
export const addAssessment = (patientId, data) => api.post(`/health-history/patient/${patientId}/assessments`, data).then((r) => r.data);
