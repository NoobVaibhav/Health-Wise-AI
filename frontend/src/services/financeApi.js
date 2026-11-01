import api from "./api";

const get = (url, params) => api.get(url, { params }).then((r) => r.data);
const post = (url, body) => api.post(url, body ?? {}).then((r) => r.data);

export const findBillingPatients = (q) => get("/finance/patients", { q });
export const getPatientBilling = (id) => get(`/finance/patients/${id}/overview`);
export const collectCharges = (id) => post(`/finance/patients/${id}/collect-charges`);
export const getInvoices = (params) => get("/finance/invoices", params);
export const getInvoice = (id) => get(`/finance/invoices/${id}`);
export const makeInvoice = (body) => post("/finance/invoices", body);
export const addInvoiceLines = (id, body) => post(`/finance/invoices/${id}/lines`, body);
export const removeInvoiceLine = (id, lineId) => api.delete(`/finance/invoices/${id}/lines/${lineId}`).then((r) => r.data);
export const setDiscount = (id, amount, reason) => post(`/finance/invoices/${id}/discount`, { amount, reason: reason || null });
export const approveDiscount = (id) => post(`/finance/invoices/${id}/discount/approve`);
export const finaliseInvoice = (id) => post(`/finance/invoices/${id}/finalise`);
export const cancelInvoice = (id, reason) => post(`/finance/invoices/${id}/cancel`, { reason });
export const payInvoice = (id, body) => post(`/finance/invoices/${id}/pay`, body);
export const getReceipt = (paymentId) => get(`/finance/payments/${paymentId}/receipt`);
export const takeDeposit = (body) => post("/finance/deposits", body);
export const requestRefund = (body) => post("/finance/refunds", body);
export const getRefunds = (params) => get("/finance/refunds", params);
export const decideRefund = (id, approve, note) => post(`/finance/refunds/${id}/decide`, { approve, note: note || null });
export const getPackages = () => get("/finance/packages");
export const getMyInvoices = () => get("/finance/my-invoices");
export const getDailyCash = (day) => get("/finance/reports/daily-cash", day ? { day } : undefined);
export const getOutstanding = () => get("/finance/reports/outstanding");
export const getRevenue = (from_day, to_day) => get("/finance/reports/revenue", { from_day, to_day });
export const listServices = (category) => get("/hospital/services", category ? { category } : undefined);

export const getClaims = (params) => get("/claims", params);
export const getClaimSummary = () => get("/claims/summary");
export const makeClaim = (invoice_id, patient_insurance_id) => post("/claims", { invoice_id, patient_insurance_id });
export const claimAction = (id, action, body) => post(`/claims/${id}/${action}`, body);
export const markClaimDocument = (id, docId, received) => post(`/claims/${id}/documents/${docId}`, { received });
