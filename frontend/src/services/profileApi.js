import api from "./api";

export const getProfile = () => api.get("/profile").then((r) => r.data);
export const updateProfile = (data) => api.put("/profile", data).then((r) => r.data);
export const uploadAvatar = (file) => {
  const form = new FormData();
  form.append("file", file);
  return api.post("/profile/avatar", form).then((r) => r.data);
};
export const deleteAvatar = () => api.delete("/profile/avatar").then((r) => r.data);
