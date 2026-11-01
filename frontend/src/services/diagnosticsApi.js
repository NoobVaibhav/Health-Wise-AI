import api from "./api";

// Laboratory results: the technician enters values, the pathologist approves, the doctor marks the result as seen (then the patient sees it).
export const getLabTest = (id) => api.get(`/lab/tests/${id}`).then((r) => r.data);
export const saveLabResults = (id, results, submit) => api.post(`/lab/tests/${id}/results`, { results, submit }).then((r) => r.data);
export const listPendingApproval = () => api.get("/lab/pending-approval").then((r) => r.data);
export const approveLabResult = (id, note) => api.post(`/lab/tests/${id}/approve`, { note: note || null }).then((r) => r.data);
export const returnLabResult = (id, comment) => api.post(`/lab/tests/${id}/return`, { comment }).then((r) => r.data);
export const markLabSeen = (id) => api.post(`/lab/tests/${id}/seen`).then((r) => r.data);

// Radiology
export const getRadiologyDashboard = () => api.get("/radiology/dashboard").then((r) => r.data);
export const getRadiologyWorklist = (params = {}) => api.get("/radiology/worklist", { params }).then((r) => r.data);
export const getRadiologyOrder = (id) => api.get(`/radiology/orders/${id}`).then((r) => r.data);
export const scheduleStudy = (id, scheduled_at) => api.post(`/radiology/orders/${id}/schedule`, { scheduled_at }).then((r) => r.data);
export const startStudy = (id) => api.post(`/radiology/orders/${id}/start`).then((r) => r.data);
export const addStudyFile = (id, file) => { const form = new FormData(); form.append("file", file); return api.post(`/radiology/orders/${id}/files`, form).then((r) => r.data); };
export const reportStudy = (id, body) => api.post(`/radiology/orders/${id}/report`, body).then((r) => r.data);
export const approveStudy = (id) => api.post(`/radiology/orders/${id}/approve`).then((r) => r.data);
export const markStudySeen = (id) => api.post(`/radiology/orders/${id}/seen`).then((r) => r.data);
export const getMyStudies = () => api.get("/radiology/my-studies").then((r) => r.data);
export const getPatientStudies = (patientId) => api.get(`/radiology/patient/${patientId}/studies`).then((r) => r.data);
/** Open a scan file in a new tab (the request carries the sign-in token, so it is fetched as a blob). */
export const openStudyFile = async (fileId) => {
  const res = await api.get(`/radiology/files/${fileId}`, { responseType: "blob" });
  window.open(URL.createObjectURL(res.data), "_blank", "noopener");
};
