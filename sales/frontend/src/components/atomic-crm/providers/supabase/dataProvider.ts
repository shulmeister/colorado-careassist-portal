import type {
  DataProvider,
  GetListParams,
  Identifier,
  RaRecord,
} from "ra-core";

const apiUrl = "/sales/admin";

type HttpResult<T> = { json: T; headers: Headers };

const httpClient = async <T>(url: string, options: RequestInit = {}): Promise<HttpResult<T>> => {
  const res = await fetch(url, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  const json = (await res.json()) as T;
  if (!res.ok) {
    const message = (json as any)?.detail || res.statusText;
    throw new Error(message);
  }
  return { json, headers: res.headers };
};

const parseTotal = (headers: Headers, fallback: number) => {
  const total = headers.get("X-Total-Count");
  return total ? parseInt(total, 10) : fallback;
};

const buildRangeHeader = (params?: GetListParams) => {
  const page = params?.pagination?.page ?? 1;
  const perPage = params?.pagination?.perPage ?? 25;
  const start = (page - 1) * perPage;
  const end = start + perPage - 1;
  return `items=${start}-${end}`;
};

const buildQuery = (params: any) => {
  const search = new URLSearchParams();
  if (params?.sort?.field) {
    search.set("sort", params.sort.field);
    search.set("order", params.sort.order ?? "ASC");
  }
  if (params?.filter) {
    Object.entries(params.filter).forEach(([key, value]) => {
      if (value === undefined || value === "") return;
      // Special case: "@is" suffix with null value means filter for SQL NULL
      // e.g. "done_date@is": null -> send done_date@is=null
      if (value === null) {
        if (key.endsWith("@is")) {
          search.append(key, "null");
        }
        return;
      }
      search.append(key, String(value));
    });
  }
  return search.toString();
};

const extractList = <T extends RaRecord>(result: any) => {
  if (Array.isArray(result)) return result as T[];
  if (Array.isArray(result?.data)) return result.data as T[];
  return [];
};

const dataProvider: DataProvider = {
  getList: async (resource, params) => {
    const query = buildQuery(params);
    const rangeHeader = buildRangeHeader(params);
    const { json, headers } = await httpClient<any>(
      `${apiUrl}/${resource}${query ? `?${query}` : ""}`,
      { headers: { Range: rangeHeader } },
    );
    const data = extractList<RaRecord>(json);
    const total = parseTotal(headers, json?.total ?? data.length);
    return { data, total };
  },

  getOne: async (resource, params) => {
    const { json } = await httpClient<any>(`${apiUrl}/${resource}/${params.id}`);
    return { data: json.data ?? json };
  },

  getMany: async (resource, params) => {
    const items = await Promise.all(
      params.ids.map((id) => dataProvider.getOne(resource, { id })),
    );
    return { data: items.map((i) => i.data) };
  },

  getManyReference: async (resource, params) => {
    const query = buildQuery({
      filter: { [params.target]: params.id, ...(params.filter ?? {}) },
      sort: params.sort,
      pagination: params.pagination,
    });
    const rangeHeader = buildRangeHeader(params);
    const { json, headers } = await httpClient<any>(
      `${apiUrl}/${resource}${query ? `?${query}` : ""}`,
      { headers: { Range: rangeHeader } },
    );
    const data = extractList<RaRecord>(json);
    const total = parseTotal(headers, json?.total ?? data.length);
    return { data, total };
  },

  update: async (resource, params) => {
    const { json } = await httpClient<any>(`${apiUrl}/${resource}/${params.id}`, {
      method: "PUT",
      body: JSON.stringify(params.data),
    });
    return { data: json.data ?? json };
  },

  updateMany: async (resource, params) => {
    const results = await Promise.all(
      params.ids.map((id) => dataProvider.update(resource, { id, data: params.data })),
    );
    return { data: results.map((r) => r.data.id as Identifier) };
  },

  create: async (resource, params) => {
    const { json } = await httpClient<any>(`${apiUrl}/${resource}`, {
      method: "POST",
      body: JSON.stringify(params.data),
    });
    const data = json.data ?? json;
    return { data: { ...params.data, ...data } };
  },

  delete: async (resource, params) => {
    const { json } = await httpClient<any>(`${apiUrl}/${resource}/${params.id}`, {
      method: "DELETE",
    });
    return { data: json.data ?? params.previousData ?? { id: params.id } };
  },

  deleteMany: async (resource, params) => {
    const results = await Promise.all(
      params.ids.map((id) => dataProvider.delete(resource, { id })),
    );
    return { data: results.map((r) => (r.data as any)?.id ?? null).filter(Boolean) };
  },
  
  // Custom method for activity log
  getActivityLog: async (companyId?: any, contactId?: any, dealId?: any) => {
    const params = new URLSearchParams();
    if (companyId) params.append('company_id', String(companyId));
    if (contactId) params.append('contact_id', String(contactId));
    if (dealId) params.append('deal_id', String(dealId));
    
    const url = params.toString()
      ? `api/activity-logs?${params.toString()}`
      : `api/activity-logs`;
    const { json } = await httpClient<any>(url);
    // API returns {success, logs, count} - extract just the logs array
    return json.logs || [];
  },
};

export type CrmDataProvider = typeof dataProvider;
export { dataProvider };
