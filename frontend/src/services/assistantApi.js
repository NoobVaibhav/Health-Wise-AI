import api from "./api";

// Patient assistant (chat and voice). The server knows the patient from the login; no patient id is ever sent.
export const getAssistantInfo = (lang) => api.get("/patient-assistant/info", { params: { lang } }).then((r) => r.data);
export const getSuggestions = (lang) => api.get("/patient-assistant/suggestions", { params: { lang } }).then((r) => r.data.suggestions);
export const sendChat = (body) => api.post("/patient-assistant/chat", body, { timeout: 60000 }).then((r) => r.data);
export const getConversations = () => api.get("/patient-assistant/conversations").then((r) => r.data);
export const getConversation = (id) => api.get(`/patient-assistant/conversations/${id}`).then((r) => r.data);
export const deleteConversation = (id) => api.delete(`/patient-assistant/conversations/${id}`);
