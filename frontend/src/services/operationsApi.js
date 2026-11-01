import api from "./api";

const get = (url, params) => api.get(url, { params }).then((r) => r.data);
const post = (url, body) => api.post(url, body ?? {}).then((r) => r.data);

// ---- stock control (pharmacy)
export const getStockAlerts = () => get("/stock/alerts");
export const getMovements = (params) => get("/stock/movements", params);
export const recallBatch = (id, reason) => post(`/stock/batches/${id}/recall`, { reason });
export const writeOffBatch = (id, reason) => post(`/stock/batches/${id}/write-off`, { reason });
export const getSuppliers = () => get("/stock/suppliers");
export const addSupplier = (body) => post("/stock/suppliers", body);
export const getMedicineRequests = (params) => get("/stock/requests", params);
export const issueRequest = (id, issues, note) => post(`/stock/requests/${id}/issue`, { issues, note: note || null });
export const rejectRequest = (id, reason) => post(`/stock/requests/${id}/reject`, { reason });
export const createMedicineRequest = (body) => post("/stock/requests", body);

// ---- procurement
export const getItems = (q) => get("/procurement/items", q ? { q } : undefined);
export const addItem = (body) => post("/procurement/items", body);
export const getRequisitions = () => get("/procurement/requisitions");
export const addRequisition = (body) => post("/procurement/requisitions", body);
export const decideRequisition = (id, approve, note) => post(`/procurement/requisitions/${id}/decide`, { approve, note: note || null });
export const getOrders = () => get("/procurement/orders");
export const addOrder = (body) => post("/procurement/orders", body);
export const approveOrder = (id) => post(`/procurement/orders/${id}/approve`);
export const receiveOrder = (id, body) => post(`/procurement/orders/${id}/receive`, body);
export const getCounts = () => get("/procurement/counts");
export const addCount = (body) => post("/procurement/counts", body);
export const decideCount = (id, approve) => post(`/procurement/counts/${id}/decide`, { approve });
export const getConsumption = (days = 30) => get("/procurement/consumption", { days });
export const getPharmacyBatches = () => get("/pharmacy/inventory");

// ---- operation theatre
export const getTheatres = () => get("/ot/theatres");
export const getSurgeries = (params) => get("/ot/surgeries", params);
export const getSurgery = (id) => get(`/ot/surgeries/${id}`);
export const bookSurgery = (body) => post("/ot/surgeries", body);
export const cancelSurgery = (id, reason) => post(`/ot/surgeries/${id}/cancel`, { reason });
export const otAction = (id, action, body) => post(`/ot/surgeries/${id}/${action}`, body);

// ---- blood bank
export const getBloodStock = () => get("/bloodbank/stock");
export const getBloodRules = () => get("/bloodbank/rules");
export const getDonors = (q) => get("/bloodbank/donors", q ? { q } : undefined);
export const addDonor = (body) => post("/bloodbank/donors", body);
export const collectBlood = (donorId, body) => post(`/bloodbank/donors/${donorId}/donations`, body);
export const getDonations = (pendingOnly) => get("/bloodbank/donations", pendingOnly ? { pending_only: true } : undefined);
export const screenDonation = (id, result, note) => post(`/bloodbank/donations/${id}/screening`, { result, note: note || null });
export const getBloodUnits = (params) => get("/bloodbank/units", params);
export const discardUnit = (id, reason) => post(`/bloodbank/units/${id}/discard`, { reason });
export const getBloodRequests = (params) => get("/bloodbank/requests", params);
export const requestBlood = (body) => post("/bloodbank/requests", body);
export const cancelBloodRequest = (id) => post(`/bloodbank/requests/${id}/cancel`);
export const rejectBloodRequest = (id, reason) => post(`/bloodbank/requests/${id}/reject`, { reason });
export const getCandidates = (id) => get(`/bloodbank/requests/${id}/candidates`);
export const crossmatch = (id, unit_id, result) => post(`/bloodbank/requests/${id}/crossmatch`, { unit_id, result });
export const issueBlood = (id, unit_id) => post(`/bloodbank/requests/${id}/issue`, { unit_id });
export const verifyIssue = (id) => post(`/bloodbank/issues/${id}/verify`);
export const returnBlood = (id, reason, cold_chain_ok) => post(`/bloodbank/issues/${id}/return`, { reason, cold_chain_ok });
export const getReadyUnits = () => get("/bloodbank/ready");
export const getActiveTransfusions = () => get("/bloodbank/transfusions");
export const startTransfusion = (issueId, body) => post(`/bloodbank/issues/${issueId}/transfusion`, body);
export const verifyTransfusion = (id) => post(`/bloodbank/transfusions/${id}/verify`);
export const endTransfusion = (id, body) => post(`/bloodbank/transfusions/${id}/end`, body);
export const getPatientTransfusions = (patientId) => get(`/bloodbank/patient/${patientId}/transfusions`);
