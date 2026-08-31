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
  ReferenceImage,
  ResearchRunRequest,
  TrendReport,
  VisualNotes,
  VisualResponse,
  VisualStatus,
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

export type JobStatus = {
  status: "idle" | "running" | "done" | "error";
  message: string;
  log?: { t?: string; text: string }[];
};

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
  createCompetitor: (id: string, payload: import("./types").CompetitorInput) =>
    request<Competitor>(`/brands/${id}/competitors`, { method: "POST", body: JSON.stringify(payload) }),
  updateCompetitor: (id: string, competitorId: string, payload: import("./types").CompetitorInput) =>
    request<Competitor>(`/brands/${id}/competitors/${competitorId}`, { method: "PATCH", body: JSON.stringify(payload) }),
  deleteCompetitor: (id: string, competitorId: string) =>
    request<void>(`/brands/${id}/competitors/${competitorId}`, { method: "DELETE" }),

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
  rejectReport: (reportId: string) =>
    request<unknown>(`/research/reports/${reportId}/reject`, { method: "PATCH" }),
  deleteReport: (reportId: string) =>
    request<void>(`/research/reports/${reportId}`, { method: "DELETE" }),
  aiEditReport: (reportId: string, instruction: string) =>
    request<TrendReport>(`/research/reports/${reportId}/ai-edit`, {
      method: "POST",
      body: JSON.stringify({ instruction }),
    }),

  // Phase 2 — calendar
  runCalendar: (id: string, body: CalendarRunRequest) =>
    request<{ message: string }>(`/calendar/${id}/run`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listCalendars: (id: string) => request<ContentCalendar[]>(`/calendar/${id}`),
  approveCalendar: (calendarId: string) =>
    request<unknown>(`/calendar/${calendarId}/approve`, { method: "PATCH" }),
  rejectCalendar: (calendarId: string) =>
    request<unknown>(`/calendar/${calendarId}/reject`, { method: "PATCH" }),
  deleteCalendar: (calendarId: string) =>
    request<void>(`/calendar/${calendarId}`, { method: "DELETE" }),
  aiEditCalendar: (calendarId: string, instruction: string) =>
    request<ContentCalendar>(`/calendar/${calendarId}/ai-edit`, {
      method: "POST",
      body: JSON.stringify({ instruction }),
    }),
  calendarStatus: (id: string) =>
    request<JobStatus>(`/calendar/${id}/status`),
  researchStatus: (id: string) => request<JobStatus>(`/research/${id}/status`),

  // Phase 3 — copy
  runCopy: (id: string, body: CopyRunRequest) =>
    request<{ message: string }>(`/copy/${id}/run`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listPackages: (id: string) => request<ContentPackage[]>(`/copy/${id}`),
  getPackage: (packageId: string) => request<ContentPackage>(`/copy/detail/${packageId}`),
  copyStatus: (id: string) => request<JobStatus>(`/copy/${id}/status`),
  approvePackage: (packageId: string) =>
    request<unknown>(`/copy/${packageId}/approve`, { method: "PATCH" }),
  rejectPackage: (packageId: string) =>
    request<unknown>(`/copy/${packageId}/reject`, { method: "PATCH" }),
  deletePackage: (packageId: string) =>
    request<void>(`/copy/${packageId}`, { method: "DELETE" }),
  bulkDeletePackages: (
    brandId: string,
    payload: { package_ids?: string[]; planning_period?: string; calendar_id?: string },
  ) =>
    request<{ message: string; deleted: number }>(`/copy/${brandId}/bulk-delete`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  aiEditPackage: (packageId: string, instruction: string) =>
    request<ContentPackage>(`/copy/${packageId}/ai-edit`, {
      method: "POST",
      body: JSON.stringify({ instruction }),
    }),

  // Phase 4 — visual
  generateVisual: (packageId: string) =>
    request<{ message: string; package_id: string }>(`/visuals/${packageId}/generate`, {
      method: "POST",
    }),
  visualStatus: (packageId: string) => request<VisualStatus>(`/visuals/${packageId}/status`),
  getVisual: (packageId: string) => request<VisualResponse>(`/visuals/${packageId}`),
  approveVisual: (packageId: string) =>
    request<unknown>(`/visuals/${packageId}/approve`, { method: "PATCH" }),
  rejectVisual: (packageId: string) =>
    request<unknown>(`/visuals/${packageId}/reject`, { method: "PATCH" }),
  selectVisualCandidate: (packageId: string, candidateId: string) =>
    request<{ message: string; selected_id: string }>(`/visuals/${packageId}/select`, {
      method: "PATCH",
      body: JSON.stringify({ candidate_id: candidateId }),
    }),

  // Solution reference library (visual redesign V2/V3). The raw thumbnail URL is
  // proxy-relative (same-origin `/api` -> backend `/api/v1`), NOT the backend's
  // absolute `raw_url` field, which would double the `/v1` segment.
  referenceRawUrl: (refId: string) => `${API_BASE}/references/${refId}/raw`,
  listReferences: (id: string, solution: string) =>
    request<ReferenceImage[]>(`/brands/${id}/solutions/${solution}/references`),
  uploadReferences: async (id: string, solution: string, files: File[]) => {
    const form = new FormData();
    for (const f of files) form.append("files", f);
    // No JSON Content-Type here: the browser sets the multipart boundary itself.
    const res = await fetch(`${API_BASE}/brands/${id}/solutions/${solution}/references`, {
      method: "POST",
      body: form,
      cache: "no-store",
    });
    if (!res.ok) {
      let detail = res.statusText;
      try {
        const b = await res.json();
        if (b?.detail) detail = typeof b.detail === "string" ? b.detail : JSON.stringify(b.detail);
      } catch {
        // no JSON body
      }
      throw new Error(`${res.status} — ${detail}`);
    }
    return (await res.json()) as ReferenceImage[];
  },
  patchReference: (refId: string, payload: { note?: string | null; sort_order?: number }) =>
    request<ReferenceImage>(`/references/${refId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  reorderReferences: (id: string, solution: string, orderedIds: string[]) =>
    request<ReferenceImage[]>(`/brands/${id}/solutions/${solution}/references/order`, {
      method: "PUT",
      body: JSON.stringify({ ordered_ids: orderedIds }),
    }),
  deleteReference: (refId: string) =>
    request<void>(`/references/${refId}`, { method: "DELETE" }),
  getVisualNotes: (id: string, solution: string) =>
    request<VisualNotes>(`/brands/${id}/solutions/${solution}/visual-notes`),
  setVisualNotes: (id: string, solution: string, visual_notes: string | null) =>
    request<VisualNotes>(`/brands/${id}/solutions/${solution}/visual-notes`, {
      method: "PUT",
      body: JSON.stringify({ visual_notes }),
    }),
};
