import api from "./api";

// Pick-lists for the doctor: medicines and tests used in the hospital.
export const getMedicineOptions = () => api.get("/catalog/medicines").then((r) => r.data);
export const getTestOptions = () => api.get("/catalog/tests").then((r) => r.data);

// Departments and specializations. The department list is loaded once and kept (it rarely changes); the admin screens call clearCatalogCache() after a change.
let departmentsOnce = null;
export const clearCatalogCache = () => { departmentsOnce = null; };
export const getDepartments = () => {
  if (!departmentsOnce) departmentsOnce = api.get("/catalog/departments").then((r) => r.data).catch((err) => { departmentsOnce = null; throw err; });
  return departmentsOnce;
};
export const getSpecializations = (departmentId) => api.get("/catalog/specializations", { params: { department_id: departmentId } }).then((r) => r.data);

// admin management (the lists include the inactive ones, with how many doctors use each)
export const adminDepartments = () => api.get("/catalog/departments", { params: { include_inactive: true } }).then((r) => r.data);
export const adminSpecializations = (departmentId) => api.get("/catalog/specializations", { params: { include_inactive: true, department_id: departmentId } }).then((r) => r.data);
const changed = (request) => request.then((r) => { clearCatalogCache(); return r.data; });
export const addDepartment = (name) => changed(api.post("/catalog/departments", { name }));
export const renameDepartment = (id, name) => changed(api.put(`/catalog/departments/${id}`, { name }));
export const setDepartmentActive = (id, is_active) => changed(api.patch(`/catalog/departments/${id}`, { is_active }));
export const addSpecialization = (department_id, name) => changed(api.post("/catalog/specializations", { department_id, name }));
export const renameSpecialization = (id, name) => changed(api.put(`/catalog/specializations/${id}`, { name }));
export const setSpecializationActive = (id, is_active) => changed(api.patch(`/catalog/specializations/${id}`, { is_active }));
