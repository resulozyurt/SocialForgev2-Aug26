// Thin typed client for the SocialForge backend.
// Override the base URL with NEXT_PUBLIC_API_BASE_URL in .env.local if needed.

import type { Brand, BrandCreate } from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers ?? {}),
    },
    cache: "no-store",
    ...options,
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      // response had no JSON body
    }
    throw new Error(`${res.status} — ${detail}`);
  }

  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  // Brands
  listBrands: () => request<Brand[]>("/brands"),
  getBrand: (id: string) => request<Brand>(`/brands/${id}`),
  createBrand: (payload: BrandCreate) =>
    request<Brand>("/brands", { method: "POST", body: JSON.stringify(payload) }),
  deactivateBrand: (id: string) =>
    request<void>(`/brands/${id}`, { method: "DELETE" }),
};