// One page of a long list. The server answers with the rows and the size of the whole list in the X-Total-Count header.
import api from "./api";

export const PAGE_SIZE = 100;

export const getPage = (url, params = {}, offset = 0) =>
  api.get(url, { params: { ...params, limit: PAGE_SIZE, offset } })
    .then((r) => ({ rows: r.data, total: Number(r.headers?.["x-total-count"] ?? r.data.length) }));
