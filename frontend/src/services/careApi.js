import api from "./api";

const get = (url, params) => api.get(url, { params }).then((r) => r.data);
const post = (url, body) => api.post(url, body ?? {}).then((r) => r.data);
const put = (url, body) => api.put(url, body).then((r) => r.data);

// OPD
export const opdQueue = (doctorId) => get("/opd/queue", doctorId ? { doctor_id: doctorId } : undefined);
export const checkIn = (appointment_id, urgent = false) => post("/opd/check-in", { appointment_id, urgent });
export const walkIn = (data) => post("/opd/walk-in", data);
export const callNext = () => post("/opd/queue/next");
export const callToken = (id) => post(`/opd/queue/${id}/call`);
export const closeToken = (id, outcome) => post(`/opd/queue/${id}/${outcome}`);

// consultation workspace
export const getWorkspace = (encounterId) => get(`/opd/encounters/${encounterId}`);
export const saveConsultation = (encounterId, data) => put(`/opd/encounters/${encounterId}/consultation`, data);
export const signConsultation = (encounterId) => post(`/opd/encounters/${encounterId}/sign`);
export const addAddendum = (consultationId, text) => post(`/opd/consultations/${consultationId}/addenda`, { text });
export const addVitals = (encounterId, data) => post(`/opd/encounters/${encounterId}/vitals`, data);
export const addDiagnosis = (encounterId, data) => post(`/opd/encounters/${encounterId}/diagnoses`, data);
export const withdrawDiagnosis = (id) => post(`/opd/diagnoses/${id}/withdraw`);
export const addOrder = (encounterId, data) => post(`/opd/encounters/${encounterId}/orders`, data);
export const setOrderStatus = (id, status) => post(`/opd/orders/${id}/status`, { status });
export const listTemplates = () => get("/opd/templates");
export const saveTemplate = (id, data) => (id ? put(`/opd/templates/${id}`, data) : post("/opd/templates", data));

// emergency
export const edBoard = () => get("/emergency/board");
export const edVisit = (id) => get(`/emergency/visits/${id}`);
export const edRegister = (data) => post("/emergency/visits", data);
export const edTriage = (id, data) => post(`/emergency/visits/${id}/triage`, data);
export const edAssign = (id, doctor_id) => post(`/emergency/visits/${id}/assign`, { doctor_id });
export const edTimeline = (id, data) => post(`/emergency/visits/${id}/timeline`, data);
export const edOrder = (id, data) => post(`/emergency/visits/${id}/orders`, data);
export const edDisposition = (id, data) => post(`/emergency/visits/${id}/disposition`, data);

// wards, beds, admissions
export const listWards = () => get("/ipd/wards");
export const addWard = (data) => post("/ipd/wards", data);
export const addBed = (wardId, code) => post(`/ipd/wards/${wardId}/beds`, { code });
export const setBedStatus = (id, status) => post(`/ipd/beds/${id}/status`, { status });
export const listAdmissions = (state = "ADMITTED") => get("/ipd/admissions", { state });
export const getAdmission = (id) => get(`/ipd/admissions/${id}`);
export const admit = (data) => post("/ipd/admissions", data);
export const moveBed = (admissionId, bed_id, reason) => post(`/ipd/admissions/${admissionId}/bed`, { bed_id, reason: reason || null });
export const staffOptions = (kind) => get("/ipd/staff-options", { kind });
export const assignStaff = (admissionId, user_id, kind) => post(`/ipd/admissions/${admissionId}/staff`, { user_id, kind });
export const addProgressNote = (admissionId, note) => post(`/ipd/admissions/${admissionId}/notes`, { note });
export const addMedicationOrder = (admissionId, data) => post(`/ipd/admissions/${admissionId}/medication-orders`, data);
export const stopMedication = (id) => post(`/ipd/medication-orders/${id}/stop`);
export const addAdmissionOrder = (admissionId, data) => post(`/ipd/admissions/${admissionId}/orders`, data);
export const saveDischargeSummary = (admissionId, data) => put(`/ipd/admissions/${admissionId}/discharge-summary`, data);
export const approveDischargeSummary = (admissionId) => post(`/ipd/admissions/${admissionId}/discharge-summary/approve`);
export const dischargePatient = (admissionId, discharge_type = "NORMAL") => post(`/ipd/admissions/${admissionId}/discharge`, { discharge_type });

// nursing
export const nurseDashboard = () => get("/nursing/dashboard");
export const getChart = (admissionId) => get(`/nursing/admissions/${admissionId}/chart`);
export const chartVitals = (admissionId, data) => post(`/nursing/admissions/${admissionId}/vitals`, data);
export const chartNote = (admissionId, data) => post(`/nursing/admissions/${admissionId}/notes`, data);
export const chartIntakeOutput = (admissionId, data) => post(`/nursing/admissions/${admissionId}/intake-output`, data);
export const actOnDose = (entryId, status, note) => post(`/nursing/mar/${entryId}/act`, { status, note: note || null });
export const listAlerts = () => get("/nursing/alerts");
export const ackAlert = (id, note) => post(`/nursing/alerts/${id}/ack`, { note: note || null });
export const listRules = () => get("/nursing/escalation-rules");
export const saveRule = (id, data) => (id ? put(`/nursing/escalation-rules/${id}`, data) : post("/nursing/escalation-rules", data));

// referral requests between departments
export const referralBox = (box) => get("/referral-requests", { box });
export const referralDetail = (id) => get(`/referral-requests/${id}`);
export const askReferral = (data) => post("/referral-requests", data);
export const acceptReferral = (id) => post(`/referral-requests/${id}/accept`);
export const declineReferral = (id, note) => post(`/referral-requests/${id}/decline`, { note });
export const completeReferral = (id, note) => post(`/referral-requests/${id}/complete`, { note: note || null });
