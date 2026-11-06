import api from "./api";
import { getPage } from "./paged";

export const getAdminDashboard = () => api.get("/admin/dashboard").then((r) => r.data);
export const listPeoplePage = (role, q, offset = 0) => getPage("/admin/people", { ...(role ? { role } : {}), ...(q ? { q } : {}) }, offset);
export const listPeople = (role, q) => api.get("/admin/people", { params: { ...(role ? { role } : {}), ...(q ? { q } : {}) } }).then((r) => r.data);
export const listUsers = (role) => api.get("/admin/users", { params: role ? { role } : {} }).then((r) => r.data);
export const createStaff = (kind, data) => api.post(`/admin/${kind}`, data).then((r) => r.data); // doctors | employees | pharmacy-staff | lab-staff
export const updateUser = (id, data) => api.put(`/admin/users/${id}`, data).then((r) => r.data);
export const checkDeleteUser = (id) => api.get(`/admin/users/${id}/delete-check`).then((r) => r.data);
export const deleteUser = (id) => api.delete(`/admin/users/${id}`).then((r) => r.data);
export const listDepartments = () => api.get("/admin/departments").then((r) => r.data);
export const createDepartment = (name) => api.post("/admin/departments", { name }).then((r) => r.data);
export const getAuditLogs = (action) => api.get("/admin/audit-logs", { params: action ? { action } : {} }).then((r) => r.data);
export const getEmployeeDashboard = () => api.get("/employee/dashboard").then((r) => r.data);
