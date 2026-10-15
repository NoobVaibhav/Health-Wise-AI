import api from "./api";

// Pick-lists for the doctor: medicines and tests used in the hospital.
export const getMedicineOptions = () => api.get("/catalog/medicines").then((r) => r.data);
export const getTestOptions = () => api.get("/catalog/tests").then((r) => r.data);
