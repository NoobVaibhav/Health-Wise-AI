import api from "./api";

// the patient's own health history (read-only: only doctors change it)
export const getMyHistory = () => api.get("/health-history/me").then((r) => r.data);

// a doctor reading or adding to the history of one of their patients
export const getPatientHistoryForm = (patientId) => api.get(`/health-history/patient/${patientId}`).then((r) => r.data);
export const savePatientHistoryForm = (patientId, data) => api.put(`/health-history/patient/${patientId}`, data).then((r) => r.data);
export const previewPoints = (patientId, data) => api.post(`/health-history/patient/${patientId}/preview`, data).then((r) => r.data);
export const addAssessment = (patientId, data) => api.post(`/health-history/patient/${patientId}/assessments`, data).then((r) => r.data);

// the detailed past history (illnesses, regular medicines, hospital admissions, operations): only doctors write; every call returns { past }
const base = (id) => `/health-history/patient/${id}`;
export const getPast = (id) => api.get(`${base(id)}/past`).then((r) => r.data.past);
export const getHistoryRevisions = (id) => api.get(`${base(id)}/revisions`).then((r) => r.data.revisions);
const save = (kind) => (id, body, recordId) => (recordId ? api.put(`${base(id)}/${kind}/${recordId}`, body) : api.post(`${base(id)}/${kind}`, body)).then((r) => r.data.past);
const remove = (kind) => (id, recordId) => api.delete(`${base(id)}/${kind}/${recordId}`).then((r) => r.data.past);
export const saveCondition = save("conditions");
export const removeCondition = remove("conditions");
export const saveMedicine = save("medicines");
export const removeMedicine = remove("medicines");
export const saveAdmission = save("admissions");
export const removeAdmission = remove("admissions");
export const saveSurgery = save("surgeries");
export const removeSurgery = remove("surgeries");
export const verifyRecord = (id, entity, recordId) => api.post(`${base(id)}/verify/${entity}/${recordId}`).then((r) => r.data.past);
