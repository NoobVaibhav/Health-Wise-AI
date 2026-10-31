import api from "./api";

// Hospital profile, branches, settings, price list
export const getHospitalProfile = () => api.get("/hospital/profile").then((r) => r.data);
export const saveHospitalProfile = (data) => api.put("/hospital/profile", data).then((r) => r.data);
export const listBranches = () => api.get("/hospital/branches").then((r) => r.data);
export const addBranch = (data) => api.post("/hospital/branches", data).then((r) => r.data);
export const updateBranch = (id, data) => api.put(`/hospital/branches/${id}`, data).then((r) => r.data);
export const listSettings = () => api.get("/hospital/settings").then((r) => r.data);
export const saveSetting = (key, value) => api.put("/hospital/settings", { key, value }).then((r) => r.data);
export const listServices = (includeInactive = false) => api.get("/hospital/services", { params: includeInactive ? { include_inactive: true } : {} }).then((r) => r.data);
export const addService = (data) => api.post("/hospital/services", data).then((r) => r.data);
export const updateService = (id, data) => api.put(`/hospital/services/${id}`, data).then((r) => r.data);

// Roles, permissions, emergency access
export const getMyAccess = () => api.get("/access/me").then((r) => r.data);
export const listRoles = () => api.get("/access/roles").then((r) => r.data);
export const listPermissions = () => api.get("/access/permissions").then((r) => r.data);
export const saveRolePermissions = (id, permissions) => api.put(`/access/roles/${id}/permissions`, { permissions }).then((r) => r.data);
export const lookupForBreakGlass = (uhid) => api.get("/access/break-glass/lookup", { params: { uhid } }).then((r) => r.data);
export const openBreakGlass = (patient_id, reason) => api.post("/access/break-glass", { patient_id, reason }).then((r) => r.data);
export const listBreakGlass = (onlyUnreviewed = false) => api.get("/access/break-glass", { params: onlyUnreviewed ? { only_unreviewed: true } : {} }).then((r) => r.data);
export const reviewBreakGlass = (id, note) => api.post(`/access/break-glass/${id}/review`, { note: note || null }).then((r) => r.data);

// Patient registry
export const findDuplicates = (params) => api.get("/patient-registry/duplicates", { params }).then((r) => r.data);
export const getRegistry = (id) => api.get(`/patient-registry/${id}`).then((r) => r.data);
export const addConsent = (id, data) => api.post(`/patient-registry/${id}/consents`, data).then((r) => r.data);
export const withdrawConsent = (id, consentId) => api.post(`/patient-registry/${id}/consents/${consentId}/withdraw`).then((r) => r.data);
export const saveAbha = (id, abha_id) => api.put(`/patient-registry/${id}/abha`, { abha_id: abha_id || null }).then((r) => r.data);
export const addInsurance = (id, data) => api.post(`/patient-registry/${id}/insurance`, data).then((r) => r.data);
export const deactivateInsurance = (id, insuranceId) => api.post(`/patient-registry/${id}/insurance/${insuranceId}/deactivate`).then((r) => r.data);
export const mergePatients = (data) => api.post("/patient-registry/merge", data).then((r) => r.data);
export const listMerges = () => api.get("/patient-registry/merges").then((r) => r.data);
