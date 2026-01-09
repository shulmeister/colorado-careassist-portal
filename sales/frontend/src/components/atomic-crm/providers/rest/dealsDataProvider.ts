import {
  type CreateParams,
  type DataProvider,
  type DeleteParams,
  type GetListParams,
  type GetOneParams,
  type UpdateParams,
} from "ra-core";

import type { Deal } from "../../types";

const jsonHeaders = { "Content-Type": "application/json" };

const httpClient = async (url: string, options: RequestInit = {}) => {
  const response = await fetch(url, options);
  const json = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(json?.detail || response.statusText);
  }
  return { json, headers: response.headers };
};

const buildListQuery = (params: GetListParams) => {
  const { page, perPage } = params.pagination ?? { page: 1, perPage: 25 };
  const { field, order } = params.sort ?? {
    field: "created_at",
    order: "DESC",
  };
  const searchParams = new URLSearchParams();
  const filter = params.filter ?? {};

  const start = (page - 1) * perPage;
  const end = start + perPage - 1;
  searchParams.set("range", `${start},${end}`);
  searchParams.set("sort", field);
  searchParams.set("order", order);

  if (filter.stage) {
    searchParams.set("stage", filter.stage);
  }
  if (filter["created_at@gte"]) {
    searchParams.set("created_at_gte", filter["created_at@gte"]);
  }
  if (filter["created_at@lte"]) {
    searchParams.set("created_at_lte", filter["created_at@lte"]);
  }

  const query = searchParams.toString();
  return query ? `?${query}` : "";
};

export const createDealsRestDataProvider = (): Pick<
  DataProvider,
  "getList" | "getOne" | "create" | "update" | "delete"
> => ({
  async getList(_resource: string, params: GetListParams) {
    const query = buildListQuery(params);
    const { json, headers } = await httpClient(`/api/deals${query}`);
    const data = json.data ?? json;
    const total =
      json.total ??
      Number(headers.get("X-Total-Count") || (data?.length ?? 0));
    return { data, total };
  },

  async getOne(_resource: string, params: GetOneParams<Deal>) {
    const { json } = await httpClient(`/api/deals/${params.id}`);
    return { data: json };
  },

  async create(_resource: string, params: CreateParams<Deal>) {
    const { json } = await httpClient(`/api/deals`, {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify(params.data),
    });
    return { data: json };
  },

  async update(_resource: string, params: UpdateParams<Deal>) {
    const { json } = await httpClient(`/api/deals/${params.id}`, {
      method: "PUT",
      headers: jsonHeaders,
      body: JSON.stringify(params.data),
    });
    return { data: json };
  },

  async delete(_resource: string, params: DeleteParams<Deal>) {
    await httpClient(`/api/deals/${params.id}`, { method: "DELETE" });
    return { data: params.previousData ?? ({ id: params.id } as Deal) };
  },
});
