import api from "./api";

// Tests advised by doctors (laboratory staff and hospital employees only).
export const getTestOrders = (q = "") => api.get("/lab/test-orders", { params: q ? { q } : {} }).then((r) => r.data);

// Laboratory work: follow each advised test from order to result.
export const getLabDashboard = () => api.get("/lab/dashboard").then((r) => r.data);
export const getWorklist = (params = {}) => api.get("/lab/worklist", { params }).then((r) => r.data);
export const setTestStatus = (id, body) => api.post(`/lab/tests/${id}/status`, body).then((r) => r.data);
export const setTestUrgent = (id, urgent) => api.post(`/lab/tests/${id}/urgent`, { urgent }).then((r) => r.data);
export const uploadTestResult = (id, file, confirmMismatch = false) => {
  const form = new FormData();
  form.append("file", file);
  if (confirmMismatch) form.append("confirm_mismatch", "true");
  return api.post(`/lab/tests/${id}/result`, form).then((r) => r.data);
};
// progress of a patient's tests: the patient's own, or a doctor's patient
export const getMyTests = () => api.get("/lab/my-tests").then((r) => r.data);
export const getPatientTests = (patientId) => api.get(`/lab/patient/${patientId}/tests`).then((r) => r.data);
