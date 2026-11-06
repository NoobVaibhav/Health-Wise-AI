import api from "./api";
import { getPage } from "./paged";

/** Upload a real file for a patient. onProgress receives 0-100 for the upload part only. */
export const uploadReport = (file, patientId, doctorId, onProgress) => {
  const form = new FormData();
  form.append("file", file);
  form.append("patient_id", patientId);
  if (doctorId) form.append("doctor_id", doctorId);
  return api
    .post("/reports/upload", form, {
      onUploadProgress: (e) => e.total && onProgress?.(Math.round((e.loaded / e.total) * 100)),
    })
    .then((r) => r.data);
};

export const listReports = (patientId) =>
  api.get("/reports", { params: patientId ? { patient_id: patientId } : {} }).then((r) => r.data);
export const listReportsPage = ({ needsReview = false, q = "" } = {}, offset = 0) =>
  getPage("/reports", { ...(needsReview ? { needs_review: true } : {}), ...(q.trim() ? { q: q.trim() } : {}) }, offset);
export const getReport = (id) => api.get(`/reports/${id}`).then((r) => r.data);
export const refreshInsights = (id) => api.post(`/reports/${id}/insights/refresh`).then((r) => r.data);
export const deleteReport = (id) => api.delete(`/reports/${id}`).then((r) => r.data);
export const reportFileUrl = (id) => `/api/reports/${id}/file`;

/** The original file is private, so it is fetched with the login token and opened as a blob. */
export const openReportFile = async (id) => {
  const res = await api.get(`/reports/${id}/file`, { responseType: "blob" });
  window.open(URL.createObjectURL(res.data), "_blank");
};
