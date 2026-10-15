import api from "./api";

// Tests advised by doctors (laboratory staff and hospital employees only).
export const getTestOrders = (q = "") => api.get("/lab/test-orders", { params: q ? { q } : {} }).then((r) => r.data);
