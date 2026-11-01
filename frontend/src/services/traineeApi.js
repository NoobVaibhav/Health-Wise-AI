import api from "./api";

// Trainee (intern / PG student) workspace
export const getTraineeDashboard = () => api.get("/trainee/dashboard").then((r) => r.data);
export const listTraineePatients = (q) => api.get("/trainee/patients", { params: q ? { q } : {} }).then((r) => r.data);
export const startTraineeHistory = (patient_id) => api.post("/trainee/histories", { patient_id }).then((r) => r.data);
export const getTraineeHistory = (id) => api.get(`/trainee/histories/${id}`).then((r) => r.data);
export const saveTraineeHistory = (id, data) => api.put(`/trainee/histories/${id}`, { data }).then((r) => r.data);
export const completeTraineeHistory = (id) => api.post(`/trainee/histories/${id}/complete`).then((r) => r.data);
export const getDoctorSuggestion = (id) => api.get(`/trainee/histories/${id}/suggestion`).then((r) => r.data);
export const listDepartmentDoctors = (departmentId) => api.get(`/trainee/departments/${departmentId}/doctors`).then((r) => r.data);
export const createReferral = (data) => api.post("/trainee/referrals", data).then((r) => r.data);
export const listMyReferrals = () => api.get("/trainee/referrals").then((r) => r.data);

// The doctor's side
export const listReferrals = () => api.get("/referrals").then((r) => r.data);
export const getReferral = (id) => api.get(`/referrals/${id}`).then((r) => r.data);
export const markReferralSeen = (id) => api.post(`/referrals/${id}/seen`).then((r) => r.data);
export const markReferralCompleted = (id) => api.post(`/referrals/${id}/complete`).then((r) => r.data);
export const reviewReferral = (id, data) => api.post(`/referrals/${id}/review`, data).then((r) => r.data);
export const verifyTraineeHistory = (id) => api.post(`/referrals/histories/${id}/verify`).then((r) => r.data);
export const editTraineeHistory = (id, data) => api.put(`/referrals/histories/${id}`, data).then((r) => r.data);
export const listPatientTraineeHistories = (patientId) => api.get(`/referrals/patient/${patientId}`).then((r) => r.data);

// Countersign: what a junior doctor prepared, waiting for the supervising consultant
export const listAwaiting = (state = "PENDING") => api.get("/countersign/awaiting", { params: { state } }).then((r) => r.data);
export const listMySubmissions = () => api.get("/countersign/mine").then((r) => r.data);
export const getCountersign = (id) => api.get(`/countersign/${id}`).then((r) => r.data);
export const approveCountersign = (id, data = {}) => api.post(`/countersign/${id}/approve`, data).then((r) => r.data);
export const returnCountersign = (id, comment) => api.post(`/countersign/${id}/return`, { comment }).then((r) => r.data);
