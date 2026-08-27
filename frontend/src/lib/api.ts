// Thin typed client for the SocialForge backend.
// Override the base URL with NEXT_PUBLIC_API_BASE_URL in .env.local if needed.

import type {
  Brand,
  BrandCreate,
  BrandSolution,
  CalendarRunRequest,
  Competitor,
  ContentCalendar,
  ContentPackage,
  CopyRunRequest,
  PhaseKey,
  ProviderConfig,
  ProviderConfigCreate,
  ProviderTestResult,
  ResearchRunRequest,
  TrendReport,
} from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api";

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
      if (body?.detail)
        detail =
          typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
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
  updateBrand: (id: string, payload: Record<string, unknown>) =>
    request<Brand>(`/brands/${id}`, { method: "PATCH", body: JSON.stringify(payload) }),

  // Solutions
  listSolutions: (id: string) => request<BrandSolution[]>(`/brands/${id}/solutions`),
  setSolutions: (id: string, items: import("./types").SolutionInput[]) =>
    request<BrandSolution[]>(`/brands/${id}/solutions`, {
      method: "PUT",
      body: JSON.stringify(items),
    }),
  deleteSolution: (id: string, solution: string) =>
    request<void>(`/brands/${id}/solutions/${solution}`, { method: "DELETE" }),

  // Competitors
  listCompetitors: (id: string) => request<Competitor[]>(`/brands/${id}/competitors`),

  // AI provider configs
  listProviders: (id: string) => request<ProviderConfig[]>(`/settings/providers/${id}`),
  upsertProvider: (id: string, payload: ProviderConfigCreate) =>
    request<ProviderConfig>(`/settings/providers/${id}`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  testProvider: (id: string, phase: PhaseKey) =>
    request<ProviderTestResult>(`/settings/providers/${id}/test?phase=${phase}`, {
      method: "POST",
    }),
  listModels: (provider: string, apiKey: string) =>
    request<{ models: string[]; source: string }>("/settings/models", {
      method: "POST",
      body: JSON.stringify({ provider, api_key: apiKey }),
    }),

  // Platform settings (Brave/Apify/search keys)
  listAppSettings: () => request<import("./types").AppSetting[]>("/settings/app"),
  updateAppSetting: (key: string, value: string) =>
    request<{ message: string; is_set: boolean }>(`/settings/app/${key}`, {
      method: "PUT",
      body: JSON.stringify({ value }),
    }),

  // Phase 1 — research
  runResearch: (id: string, body: ResearchRunRequest) =>
    request<{ message: string }>(`/research/${id}/run`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listReports: (id: string) => request<TrendReport[]>(`/research/${id}/reports`),
  approveReport: (reportId: string) =>
    request<unknown>(`/research/reports/${reportId}/approve`, { method: "PATCH" }),

  // Phase 2 — calendar
  runCalendar: (id: string, body: CalendarRunRequest) =>
    request<{ message: string }>(`/calendar/${id}/run`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listCalendars: (id: string) => request<ContentCalendar[]>(`/calendar/${id}`),
  approveCalendar: (calendarId: string) =>
    request<unknown>(`/calendar/${calendarId}/approve`, { method: "PATCH" }),
  calendarStatus: (id: string) =>
    request<{ status: string; message: string }>(`/calendar/${id}/status`),

  // Phase 3 — copy
  runCopy: (id: string, body: CopyRunRequest) =>
    request<{ message: string }>(`/copy/${id}/run`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listPackages: (id: string) => request<ContentPackage[]>(`/copy/${id}`),
  approvePackage: (packageId: string) =>
    request<unknown>(`/copy/${packageId}/approve`, { method: "PATCH" }),
};
