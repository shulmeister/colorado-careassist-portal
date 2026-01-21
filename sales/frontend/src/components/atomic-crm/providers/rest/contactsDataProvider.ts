import {
  type CreateParams,
  type GetManyReferenceParams,
  type DataProvider,
  type DeleteParams,
  type GetListParams,
  type GetOneParams,
  type UpdateParams,
} from "ra-core";

import type { Contact } from "../../types";

const jsonHeaders = { "Content-Type": "application/json" };

const normalizeContact = (contact: Contact): Contact => {
  if (!contact) return contact;
  if (!contact.first_name && !contact.last_name && contact.name) {
    const parts = contact.name.split(" ").filter(Boolean);
    contact.first_name = parts[0];
    contact.last_name = parts.slice(1).join(" ") || undefined;
  }
  return contact;
};

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

  // Normalize legacy filters from Supabase schema to REST schema
  const normalizedFilter: Record<string, any> = {};
  Object.entries(filter).forEach(([key, value]) => {
    if (key.startsWith("last_seen")) {
      const suffix = key.slice("last_seen".length); // e.g. @gte
      normalizedFilter[`last_activity${suffix}`] = value;
      return;
    }
    normalizedFilter[key] = value;
  });

  if (normalizedFilter.tags) {
    const tags = Array.isArray(normalizedFilter.tags)
      ? normalizedFilter.tags
      : [normalizedFilter.tags];
    tags
      .filter(Boolean)
      .forEach((tag: string) => searchParams.append("tags", tag));
  }

  if (normalizedFilter.status) {
    searchParams.set("status", normalizedFilter.status);
  }
  if (normalizedFilter.contact_type) {
    searchParams.set("contact_type", normalizedFilter.contact_type);
  }
  if (normalizedFilter["last_activity@gte"]) {
    searchParams.set("last_activity_gte", normalizedFilter["last_activity@gte"]);
  }
  if (normalizedFilter["last_activity@lte"]) {
    searchParams.set("last_activity_lte", normalizedFilter["last_activity@lte"]);
  }

  const query = searchParams.toString();
  return query ? `?${query}` : "";
};

export const createContactsRestDataProvider = (): Pick<
  DataProvider,
  "getList" | "getOne" | "create" | "update" | "delete" | "getManyReference"
> => ({
  async getList(_resource: string, params: GetListParams) {
    const query = buildListQuery(params);
    const { json, headers } = await httpClient(`/api/contacts${query}`);
    const data = (json.data ?? json)?.map
      ? (json.data as Contact[]).map(normalizeContact)
      : json.data ?? json;
    const total =
      json.total ??
      Number(headers.get("X-Total-Count") || data?.length || 0);
    return { data, total };
  },

  async getOne(_resource: string, params: GetOneParams<Contact>) {
    const { json } = await httpClient(`/api/contacts/${params.id}`);
    return { data: normalizeContact(json as Contact) };
  },

  async create(_resource: string, params: CreateParams<Contact>) {
    const { json } = await httpClient(`/api/contacts`, {
      method: "POST",
      headers: jsonHeaders,
      body: JSON.stringify(params.data),
    });
    return { data: normalizeContact(json as Contact) };
  },

  async update(_resource: string, params: UpdateParams<Contact>) {
    const { json } = await httpClient(`/api/contacts/${params.id}`, {
      method: "PUT",
      headers: jsonHeaders,
      body: JSON.stringify(params.data),
    });
    return { data: normalizeContact(json as Contact) };
  },

  async delete(_resource: string, params: DeleteParams<Contact>) {
    await httpClient(`/api/contacts/${params.id}`, { method: "DELETE" });
    return { data: params.previousData ?? ({ id: params.id } as Contact) };
  },
  async getManyReference(_resource: string, _params: GetManyReferenceParams) {
    throw new Error("getManyReference not implemented for contacts REST provider");
  },
});
