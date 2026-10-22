import api from "./api";

// Patient Clinical Intelligence: everything a doctor needs to understand one patient's documented history (doctors only).
const base = (id) => `/doctor/patients/${id}`;
export const getClinicalSummary = (id) => api.get(`${base(id)}/clinical-summary`).then((r) => r.data);
export const generateAiNarrative = (id) => api.post(`${base(id)}/clinical-summary/generate`).then((r) => r.data);
export const reviewSummaryItem = (id, body) => api.post(`${base(id)}/clinical-summary/review`, body).then((r) => r.data);
export const getTimeline = (id, q) => api.get(`${base(id)}/timeline`, { params: q ? { q } : {} }).then((r) => r.data);
export const getReportTrends = (id) => api.get(`${base(id)}/report-trends`).then((r) => r.data);
export const getMedicationHistory = (id) => api.get(`${base(id)}/medication-history`).then((r) => r.data);
export const getFollowUps = (id) => api.get(`${base(id)}/follow-ups`).then((r) => r.data);
export const createFollowUp = (id, body) => api.post(`${base(id)}/follow-ups`, body).then((r) => r.data);
export const updateFollowUp = (id, taskId, body) => api.patch(`${base(id)}/follow-ups/${taskId}`, body).then((r) => r.data);
export const getEmergencyHistory = (id) => api.get(`${base(id)}/emergency-history`).then((r) => r.data);
export const recordEmergency = (id, body) => api.post(`${base(id)}/emergency-events`, body).then((r) => r.data);
export const getEmergencyEvent = (eventId) => api.get(`/doctor/emergency-events/${eventId}`).then((r) => r.data);
