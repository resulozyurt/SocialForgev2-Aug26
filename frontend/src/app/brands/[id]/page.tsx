"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import type {
  Brand,
  BrandSolution,
  Competitor,
  CompetitorInput,
  PhaseKey,
  ProviderConfig,
  ProviderConfigCreate,
  ProviderKey,
  ProviderTestResult,
  SolutionKey,
} from "@/lib/types";

const TABS = ["identity", "voice", "solutions", "providers", "sources"] as const;
type Tab = (typeof TABS)[number];
const TAB_LABELS: Record<Tab, string> = {
  identity: "Identity",
  voice: "Voice",
  solutions: "Solutions",
  providers: "AI Providers",
  sources: "Sources",
};

const PHASES: { key: PhaseKey; label: string }[] = [
  { key: "phase1_research", label: "Research" },
  { key: "phase2_calendar", label: "Calendar" },
  { key: "phase3_copy", label: "Copy" },
];
const PROVIDERS: ProviderKey[] = ["anthropic", "openai", "google", "groq"];

const SOLUTION_LABELS: Record<SolutionKey, string> = {
  merchandising: "Merchandising",
  field_audit: "Field Audit",
  field_sales: "Field Sales",
  home_service: "Home Service",
  ai: "AI",
  general: "General",
};
const PHASE_LABELS: Record<string, string> = {
  phase1_research: "Research",
  phase2_calendar: "Calendar",
  phase3_copy: "Copy",
};

function asRecord(v: unknown): Record<string, unknown> {
  return v && typeof v === "object" && !Array.isArray(v)
    ? (v as Record<string, unknown>)
    : {};
}
function asStr(v: unknown): string | null {
  return typeof v === "string" && v.trim() ? v : null;
}
function asStrList(v: unknown): string[] {
  return Array.isArray(v) ? v.filter((x) => typeof x === "string") : [];
}
const msg = (e: unknown) => (e instanceof Error ? e.message : "Something went wrong.");

function buildIdentityForm(b: Brand): Record<string, string> {
  const vi = asRecord(b.visual_identity);
  const pill = asRecord(vi.pill);
  return {
    display_name: b.display_name ?? "",
    industry: b.industry ?? "",
    language: b.language ?? "en",
    monthly_post_target: String(b.monthly_post_target ?? 20),
    primary_color: b.primary_color ?? "",
    secondary_color: b.secondary_color ?? "",
    accent_color: b.accent_color ?? "",
    logo_url: b.logo_url ?? "",
    ground_color: asStr(vi.ground_color) ?? "",
    block_color: asStr(vi.block_color) ?? "",
    pill_bg: asStr(pill.bg_color) ?? "",
    pill_text: asStr(pill.text_color) ?? "",
    style_keywords: asStrList(vi.style_keywords).join("\n"),
    motifs: asStrList(vi.motifs).join("\n"),
  };
}
function buildVoiceForm(b: Brand): Record<string, string> {
  const vp = asRecord(b.voice_profile);
  return {
    voice_guide_text: b.voice_guide_text ?? "",
    tone_keywords: asStrList(vp.tone_keywords).join("\n"),
    narrative_structure: asStr(vp.narrative_structure) ?? "",
    example_headlines: asStrList(vp.example_headlines).join("\n"),
    avoid: asStrList(vp.avoid).join("\n"),
  };
}

const ALL_SOLUTIONS: SolutionKey[] = [
  "merchandising", "field_audit", "field_sales", "home_service", "ai", "general",
];

interface SolRow {
  included: boolean;
  is_focus: boolean;
  importance: number;
  priority: number;
  concept_notes: string;
}

function buildSolRows(list: BrandSolution[]): Record<SolutionKey, SolRow> {
  const out = {} as Record<SolutionKey, SolRow>;
  for (const k of ALL_SOLUTIONS) {
    const f = list.find((s) => s.solution === k);
    out[k] = f
      ? { included: true, is_focus: f.is_focus, importance: f.importance ?? 3, priority: f.priority, concept_notes: f.concept_notes ?? "" }
      : { included: false, is_focus: true, importance: 3, priority: 100, concept_notes: "" };
  }
  return out;
}

function previewDistribution(rows: Record<SolutionKey, SolRow>, postCount: number) {
  const NON: SolutionKey[] = ["ai", "general"];
  const included = ALL_SOLUTIONS.filter((k) => rows[k].included);
  const hasAi = included.includes("ai");
  const hasGeneral = included.includes("general");
  const aiAngle = hasAi ? Math.round(0.45 * postCount) : 0;
  const primaryFocus = included.filter((k) => !NON.includes(k) && rows[k].is_focus);
  const fp = primaryFocus.length ? primaryFocus : included.filter((k) => !NON.includes(k));
  const quota: Partial<Record<SolutionKey, number>> = {};
  if (!fp.length) {
    const b: SolutionKey = hasGeneral ? "general" : hasAi ? "ai" : "general";
    quota[b] = postCount;
    return { quota, aiAngle };
  }
  let gc = hasGeneral ? Math.round(0.15 * postCount) : 0;
  gc = Math.max(0, Math.min(gc, postCount - fp.length));
  const rem = postCount - gc;
  const weights = fp.map((k) => Math.max(1, rows[k].importance || 3));
  const tw = weights.reduce((a, b) => a + b, 0) || fp.length;
  const exact = weights.map((w) => (rem * w) / tw);
  const base = exact.map((x) => Math.floor(x));
  const lo = rem - base.reduce((a, b) => a + b, 0);
  const ord = fp
    .map((_, i) => i)
    .sort((a, b) => (exact[b] - base[b] - (exact[a] - base[a])) || (rows[fp[a]].priority - rows[fp[b]].priority));
  for (let k = 0; k < lo; k++) base[ord[k]] += 1;
  fp.forEach((k, i) => (quota[k] = base[i]));
  if (gc) quota.general = (quota.general ?? 0) + gc;
  return { quota, aiAngle };
}

const EMPTY_PROVIDER: ProviderConfigCreate = {
  phase: "phase1_research",
  provider: "anthropic",
  model: "",
  api_key: "",
  temperature: 0.7,
  max_tokens: 4096,
};

const EMPTY_COMP: CompetitorInput = {
  name: "",
  solution: null,
  is_aspirational: false,
  instagram_handle: "",
  linkedin_handle: "",
  x_handle: "",
  notes: "",
};

export default function BrandDetailPage() {
  const params = useParams();
  const brandId = String(params.id);

  const [tab, setTab] = useState<Tab>("identity");
  const [brand, setBrand] = useState<Brand | null>(null);
  const [solutions, setSolutions] = useState<BrandSolution[]>([]);
  const [competitors, setCompetitors] = useState<Competitor[]>([]);
  const [providers, setProviders] = useState<ProviderConfig[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [form, setForm] = useState<ProviderConfigCreate>(EMPTY_PROVIDER);
  const [saving, setSaving] = useState(false);
  const [saveMsg, setSaveMsg] = useState<string | null>(null);
  const [testing, setTesting] = useState<PhaseKey | null>(null);
  const [testResults, setTestResults] = useState<
    Partial<Record<PhaseKey, ProviderTestResult>>
  >({});

  const [modelOptions, setModelOptions] = useState<string[]>([]);
  const [modelSource, setModelSource] = useState<string | null>(null);
  const [loadingModels, setLoadingModels] = useState(false);
  const [customModel, setCustomModel] = useState(false);

  const [srcFeeds, setSrcFeeds] = useState("");
  const [srcKeywords, setSrcKeywords] = useState("");
  const [srcGeo, setSrcGeo] = useState("");
  const [srcSaving, setSrcSaving] = useState(false);
  const [srcMsg, setSrcMsg] = useState<string | null>(null);

  const [idForm, setIdForm] = useState<Record<string, string>>({});
  const [idSaving, setIdSaving] = useState(false);
  const [idMsg, setIdMsg] = useState<string | null>(null);
  const [vForm, setVForm] = useState<Record<string, string>>({});
  const [vSaving, setVSaving] = useState(false);
  const [vMsg, setVMsg] = useState<string | null>(null);
  const [solRows, setSolRows] = useState<Record<SolutionKey, SolRow>>(() => buildSolRows([]));
  const [solSaving, setSolSaving] = useState(false);
  const [solMsg, setSolMsg] = useState<string | null>(null);
  const [newComp, setNewComp] = useState<CompetitorInput>(EMPTY_COMP);
  const [editingComp, setEditingComp] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<CompetitorInput>(EMPTY_COMP);
  const [compBusy, setCompBusy] = useState(false);
  const [compMsg, setCompMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [b, sol, comp, prov] = await Promise.all([
        api.getBrand(brandId),
        api.listSolutions(brandId).catch(() => []),
        api.listCompetitors(brandId).catch(() => []),
        api.listProviders(brandId).catch(() => []),
      ]);
      setBrand(b);
      setSolutions(sol);
      setCompetitors(comp);
      setProviders(prov);
      const rs = (b.research_sources ?? {}) as Record<string, unknown>;
      setSrcFeeds((Array.isArray(rs.rss_feeds) ? (rs.rss_feeds as string[]) : []).join("\n"));
      setSrcKeywords((Array.isArray(rs.search_keywords) ? (rs.search_keywords as string[]) : []).join("\n"));
      setSrcGeo(typeof rs.trends_geo === "string" ? rs.trends_geo : "");
      setIdForm(buildIdentityForm(b));
      setVForm(buildVoiceForm(b));
      setSolRows(buildSolRows(sol));
    } catch (err) {
      setError(msg(err));
    } finally {
      setLoading(false);
    }
  }, [brandId]);

  useEffect(() => {
    load();
  }, [load]);

  async function loadModels() {
    if (form.api_key.trim().length < 8) {
      setError("Enter your API key first (at least 8 characters) to load models.");
      return;
    }
    setLoadingModels(true);
    setError(null);
    try {
      const res = await api.listModels(form.provider, form.api_key.trim());
      setModelOptions(res.models);
      setModelSource(res.source);
      setCustomModel(false);
      if (res.models.length && !res.models.includes(form.model)) {
        setForm((f) => ({ ...f, model: res.models[0] }));
      }
    } catch (err) {
      setError(msg(err));
    } finally {
      setLoadingModels(false);
    }
  }

  async function handleSaveProvider(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setSaveMsg(null);
    setError(null);
    try {
      await api.upsertProvider(brandId, {
        ...form,
        model: form.model.trim(),
        api_key: form.api_key.trim(),
        temperature: Number(form.temperature),
        max_tokens: Number(form.max_tokens),
      });
      setSaveMsg(`Saved ${PHASE_LABELS[form.phase]} provider.`);
      setForm({ ...EMPTY_PROVIDER, phase: form.phase, provider: form.provider });
      setModelOptions([]);
      setModelSource(null);
      setCustomModel(false);
      setProviders(await api.listProviders(brandId).catch(() => []));
    } catch (err) {
      setError(msg(err));
    } finally {
      setSaving(false);
    }
  }

  async function handleTest(phase: PhaseKey) {
    setTesting(phase);
    setTestResults((r) => ({ ...r, [phase]: undefined }));
    try {
      const result = await api.testProvider(brandId, phase);
      setTestResults((r) => ({ ...r, [phase]: result }));
    } catch (err) {
      setTestResults((r) => ({
        ...r,
        [phase]: { success: false, provider: "", model: "", latency_ms: null, error: msg(err) },
      }));
    } finally {
      setTesting(null);
    }
  }

  async function saveSources() {
    setSrcSaving(true);
    setSrcMsg(null);
    setError(null);
    try {
      const rs = (brand?.research_sources ?? {}) as Record<string, unknown>;
      const lines = (t: string) => t.split("\n").map((x) => x.trim()).filter(Boolean);
      const updated = await api.updateBrand(brandId, {
        research_sources: {
          ...rs,
          rss_feeds: lines(srcFeeds),
          search_keywords: lines(srcKeywords),
          trends_geo: srcGeo.trim() || null,
        },
      });
      setBrand(updated);
      setSrcMsg("Saved.");
    } catch (err) {
      setError(msg(err));
    } finally {
      setSrcSaving(false);
    }
  }

  async function saveIdentity() {
    setIdSaving(true);
    setIdMsg(null);
    setError(null);
    try {
      const lines = (t: string) => t.split("\n").map((x) => x.trim()).filter(Boolean);
      const vi = asRecord(brand?.visual_identity);
      const pill = asRecord(vi.pill);
      const target = Math.min(200, Math.max(1, Math.round(Number(idForm.monthly_post_target) || 20)));
      const updated = await api.updateBrand(brandId, {
        display_name: (idForm.display_name ?? "").trim() || brand!.display_name,
        industry: (idForm.industry ?? "").trim() || null,
        language: idForm.language ?? "en",
        monthly_post_target: target,
        primary_color: (idForm.primary_color ?? "").trim() || null,
        secondary_color: (idForm.secondary_color ?? "").trim() || null,
        accent_color: (idForm.accent_color ?? "").trim() || null,
        logo_url: (idForm.logo_url ?? "").trim() || null,
        visual_identity: {
          ...vi,
          ground_color: (idForm.ground_color ?? "").trim() || null,
          block_color: (idForm.block_color ?? "").trim() || null,
          pill: {
            ...pill,
            bg_color: (idForm.pill_bg ?? "").trim() || null,
            text_color: (idForm.pill_text ?? "").trim() || null,
          },
          style_keywords: lines(idForm.style_keywords ?? ""),
          motifs: lines(idForm.motifs ?? ""),
        },
      });
      setBrand(updated);
      setIdForm(buildIdentityForm(updated));
      setIdMsg("Saved.");
    } catch (err) {
      setError(msg(err));
    } finally {
      setIdSaving(false);
    }
  }

  async function saveVoice() {
    setVSaving(true);
    setVMsg(null);
    setError(null);
    try {
      const lines = (t: string) => t.split("\n").map((x) => x.trim()).filter(Boolean);
      const vp = asRecord(brand?.voice_profile);
      const updated = await api.updateBrand(brandId, {
        voice_guide_text: (vForm.voice_guide_text ?? "").trim() || null,
        voice_profile: {
          ...vp,
          tone_keywords: lines(vForm.tone_keywords ?? ""),
          narrative_structure: (vForm.narrative_structure ?? "").trim() || null,
          example_headlines: lines(vForm.example_headlines ?? ""),
          avoid: lines(vForm.avoid ?? ""),
        },
      });
      setBrand(updated);
      setVForm(buildVoiceForm(updated));
      setVMsg("Saved.");
    } catch (err) {
      setError(msg(err));
    } finally {
      setVSaving(false);
    }
  }

  async function saveSolutions() {
    setSolSaving(true);
    setSolMsg(null);
    setError(null);
    try {
      const items = ALL_SOLUTIONS.filter((k) => solRows[k].included).map((k) => ({
        solution: k,
        is_focus: solRows[k].is_focus,
        priority: Number(solRows[k].priority) || 100,
        importance: Number(solRows[k].importance) || 3,
        concept_notes: solRows[k].concept_notes.trim() || null,
      }));
      await api.setSolutions(brandId, items);
      const before = new Set(solutions.map((s) => s.solution));
      const removed = ALL_SOLUTIONS.filter((k) => before.has(k) && !solRows[k].included);
      for (const k of removed) await api.deleteSolution(brandId, k);
      const fresh = await api.listSolutions(brandId);
      setSolutions(fresh);
      setSolRows(buildSolRows(fresh));
      setSolMsg("Saved.");
    } catch (err) {
      setError(msg(err));
    } finally {
      setSolSaving(false);
    }
  }

  async function refreshCompetitors() {
    setCompetitors(await api.listCompetitors(brandId).catch(() => []));
  }
  function cleanComp(c: CompetitorInput): CompetitorInput {
    const t = (v: string | null) => (v && v.trim() ? v.trim() : null);
    return {
      name: c.name.trim(),
      solution: c.solution,
      is_aspirational: c.is_aspirational,
      instagram_handle: t(c.instagram_handle),
      linkedin_handle: t(c.linkedin_handle),
      x_handle: t(c.x_handle),
      notes: t(c.notes),
    };
  }
  async function addCompetitor() {
    if (!newComp.name.trim()) return;
    setCompBusy(true);
    setCompMsg(null);
    setError(null);
    try {
      await api.createCompetitor(brandId, cleanComp(newComp));
      await refreshCompetitors();
      setNewComp(EMPTY_COMP);
      setCompMsg("Added.");
    } catch (err) {
      setError(msg(err));
    } finally {
      setCompBusy(false);
    }
  }
  function startEditCompetitor(c: Competitor) {
    setEditingComp(c.id);
    setEditDraft({
      name: c.name,
      solution: c.solution,
      is_aspirational: c.is_aspirational,
      instagram_handle: c.instagram_handle ?? "",
      linkedin_handle: c.linkedin_handle ?? "",
      x_handle: c.x_handle ?? "",
      notes: c.notes ?? "",
    });
  }
  async function saveEditCompetitor() {
    if (!editingComp) return;
    setCompBusy(true);
    setError(null);
    try {
      await api.updateCompetitor(brandId, editingComp, cleanComp(editDraft));
      await refreshCompetitors();
      setEditingComp(null);
    } catch (err) {
      setError(msg(err));
    } finally {
      setCompBusy(false);
    }
  }
  async function removeCompetitor(id: string) {
    setCompBusy(true);
    setError(null);
    try {
      await api.deleteCompetitor(brandId, id);
      await refreshCompetitors();
    } catch (err) {
      setError(msg(err));
    } finally {
      setCompBusy(false);
    }
  }

  if (loading) return <p className="sf-note">Loading brand…</p>;
  if (error && !brand) return <div className="sf-error">{error}</div>;
  if (!brand) return <div className="sf-error">Brand not found.</div>;

  const vi = asRecord(brand.visual_identity);
  const pill = asRecord(vi.pill);
  const swatches = [
    { label: "Primary", hex: brand.primary_color },
    { label: "Secondary", hex: brand.secondary_color },
    { label: "Accent", hex: brand.accent_color },
    { label: "Ground", hex: asStr(vi.ground_color) },
    { label: "Block", hex: asStr(vi.block_color) },
    { label: "Pill", hex: asStr(pill.bg_color) },
  ].filter((s) => s.hex);

  return (
    <div>
      <Link href="/" className="sf-back">
        ← All brands
      </Link>

      <div className="sf-page-head">
        <div>
          <p className="sf-eyebrow">Brand</p>
          <h1 className="sf-title">{brand.display_name}</h1>
          <p className="sf-subtitle">
            @{brand.slug}
            {brand.industry ? ` · ${brand.industry}` : ""}
          </p>
        </div>
        <div className="sf-head-side">
          <div className="sf-head-badges">
            <span className="sf-badge">{brand.language.toUpperCase()}</span>
            <span className="sf-badge">{brand.monthly_post_target} posts/mo</span>
            <span className={`sf-badge${brand.is_active ? " is-active" : ""}`}>
              {brand.is_active ? "Active" : "Inactive"}
            </span>
          </div>
          <Link href={`/brands/${brandId}/pipeline`} className="sf-btn sf-btn-accent">
            Content pipeline →
          </Link>
        </div>
      </div>

      {error && <div className="sf-error">{error}</div>}

      {/* ── Tab bar ─────────────────────────────────────────── */}
      <div className="sf-tabs">
        {TABS.map((t) => (
          <button
            key={t}
            className={`sf-tab${tab === t ? " is-active" : ""}`}
            onClick={() => setTab(t)}
          >
            {TAB_LABELS[t]}
          </button>
        ))}
      </div>

      {/* ── Identity ────────────────────────────────────────── */}
      {tab === "identity" && (
        <section className="sf-section">
          <div className="sf-info">
            Edit the brand&rsquo;s identity. <strong>Monthly post target</strong> sets how
            many posts the calendar plans, and is the base the per-solution split divides.
            Colors and visual identity feed Phase 3 copy and Phase 4 visuals.
          </div>
          <div className="sf-row">
            <div className="sf-field">
              <label className="sf-label">Display name</label>
              <input className="sf-input" value={idForm.display_name ?? ""}
                onChange={(e) => setIdForm({ ...idForm, display_name: e.target.value })} />
            </div>
            <div className="sf-field">
              <label className="sf-label">Industry</label>
              <input className="sf-input" value={idForm.industry ?? ""}
                onChange={(e) => setIdForm({ ...idForm, industry: e.target.value })}
                placeholder="B2B SaaS" />
            </div>
          </div>
          <div className="sf-row">
            <div className="sf-field">
              <label className="sf-label">Language</label>
              <select className="sf-input" value={idForm.language ?? "en"}
                onChange={(e) => setIdForm({ ...idForm, language: e.target.value })}>
                <option value="en">English (FieldPie)</option>
                <option value="tr">Turkce (Evatro)</option>
              </select>
            </div>
            <div className="sf-field">
              <label className="sf-label">Monthly post target</label>
              <input className="sf-input" type="number" min={1} max={200}
                value={idForm.monthly_post_target ?? "20"}
                onChange={(e) => setIdForm({ ...idForm, monthly_post_target: e.target.value })} />
            </div>
          </div>
          <div className="sf-row">
            <div className="sf-field">
              <label className="sf-label">Primary color</label>
              <input className="sf-input" value={idForm.primary_color ?? ""}
                onChange={(e) => setIdForm({ ...idForm, primary_color: e.target.value })}
                placeholder="#0E7C7B" />
            </div>
            <div className="sf-field">
              <label className="sf-label">Secondary color</label>
              <input className="sf-input" value={idForm.secondary_color ?? ""}
                onChange={(e) => setIdForm({ ...idForm, secondary_color: e.target.value })}
                placeholder="#1F2933" />
            </div>
            <div className="sf-field">
              <label className="sf-label">Accent color</label>
              <input className="sf-input" value={idForm.accent_color ?? ""}
                onChange={(e) => setIdForm({ ...idForm, accent_color: e.target.value })}
                placeholder="#12A3A0" />
            </div>
          </div>
          <div className="sf-row">
            <div className="sf-field">
              <label className="sf-label">Ground color</label>
              <input className="sf-input" value={idForm.ground_color ?? ""}
                onChange={(e) => setIdForm({ ...idForm, ground_color: e.target.value })}
                placeholder="#FFFFFF" />
            </div>
            <div className="sf-field">
              <label className="sf-label">Block color</label>
              <input className="sf-input" value={idForm.block_color ?? ""}
                onChange={(e) => setIdForm({ ...idForm, block_color: e.target.value })}
                placeholder="#0B1E3B" />
            </div>
          </div>
          <div className="sf-row">
            <div className="sf-field">
              <label className="sf-label">Pill background</label>
              <input className="sf-input" value={idForm.pill_bg ?? ""}
                onChange={(e) => setIdForm({ ...idForm, pill_bg: e.target.value })}
                placeholder="#E4002B" />
            </div>
            <div className="sf-field">
              <label className="sf-label">Pill text</label>
              <input className="sf-input" value={idForm.pill_text ?? ""}
                onChange={(e) => setIdForm({ ...idForm, pill_text: e.target.value })}
                placeholder="#FFFFFF" />
            </div>
          </div>
          <div className="sf-field">
            <label className="sf-label">Logo URL</label>
            <input className="sf-input" value={idForm.logo_url ?? ""}
              onChange={(e) => setIdForm({ ...idForm, logo_url: e.target.value })}
              placeholder="https://..." />
          </div>
          <div className="sf-field">
            <label className="sf-label">Style keywords (one per line)</label>
            <textarea className="sf-input sf-textarea" value={idForm.style_keywords ?? ""}
              onChange={(e) => setIdForm({ ...idForm, style_keywords: e.target.value })}
              placeholder="clean, modern SaaS, white space" />
          </div>
          <div className="sf-field">
            <label className="sf-label">Visual motifs (one per line)</label>
            <textarea className="sf-input sf-textarea" value={idForm.motifs ?? ""}
              onChange={(e) => setIdForm({ ...idForm, motifs: e.target.value })}
              placeholder={"half-circle pie graphic bottom-left"} />
          </div>
          {swatches.length > 0 && (
            <div className="sf-swatches">
              {swatches.map((sw) => (
                <div className="sf-swatch" key={sw.label}>
                  <span className="sf-swatch-chip" style={{ background: sw.hex ?? "transparent" }} />
                  <span className="sf-swatch-label">
                    {sw.label}
                    <br />
                    <code>{sw.hex}</code>
                  </span>
                </div>
              ))}
            </div>
          )}
          <div className="sf-form-actions">
            <button className="sf-btn sf-btn-accent" onClick={saveIdentity} disabled={idSaving}>
              {idSaving ? "Saving..." : "Save identity"}
            </button>
            {idMsg && <span className="sf-test is-ok">{idMsg}</span>}
          </div>
        </section>
      )}

      {/* Voice */}
      {tab === "voice" && (
        <section className="sf-section">
          <div className="sf-info">
            This voice profile steers how the AI writes captions and headlines for this
            brand &mdash; its tone, story structure, example headlines, and phrasings to avoid.
          </div>
          <div className="sf-field">
            <label className="sf-label">Voice guide (free text)</label>
            <textarea className="sf-input sf-textarea" value={vForm.voice_guide_text ?? ""}
              onChange={(e) => setVForm({ ...vForm, voice_guide_text: e.target.value })}
              placeholder="Clear, reassuring, problem to solution. Short, punchy headlines." />
          </div>
          <div className="sf-field">
            <label className="sf-label">Tone keywords (one per line)</label>
            <textarea className="sf-input sf-textarea" value={vForm.tone_keywords ?? ""}
              onChange={(e) => setVForm({ ...vForm, tone_keywords: e.target.value })}
              placeholder="clear, reassuring, confident" />
          </div>
          <div className="sf-field">
            <label className="sf-label">Narrative structure</label>
            <input className="sf-input" value={vForm.narrative_structure ?? ""}
              onChange={(e) => setVForm({ ...vForm, narrative_structure: e.target.value })}
              placeholder="problem to solution" />
          </div>
          <div className="sf-field">
            <label className="sf-label">Example headlines (one per line)</label>
            <textarea className="sf-input sf-textarea" value={vForm.example_headlines ?? ""}
              onChange={(e) => setVForm({ ...vForm, example_headlines: e.target.value })}
              placeholder={"Photos Don't Fix Shelves. Actions Do."} />
          </div>
          <div className="sf-field">
            <label className="sf-label">Avoid (one per line)</label>
            <textarea className="sf-input sf-textarea" value={vForm.avoid ?? ""}
              onChange={(e) => setVForm({ ...vForm, avoid: e.target.value })}
              placeholder="translated phrasing, corporate fluff" />
          </div>
          <div className="sf-form-actions">
            <button className="sf-btn sf-btn-accent" onClick={saveVoice} disabled={vSaving}>
              {vSaving ? "Saving..." : "Save voice"}
            </button>
            {vMsg && <span className="sf-test is-ok">{vMsg}</span>}
          </div>
        </section>
      )}

      {/* Solutions */}
      {tab === "solutions" && (
        <section className="sf-section">
          <div className="sf-info">
            Pick which product areas this brand builds content around and how much
            weight each carries. <strong>Importance (1-5)</strong> drives how the monthly
            plan is split across solutions. <strong>AI</strong> is a cross-cutting theme,
            not a separate share. Lower priority number = higher priority (breaks ties).
          </div>

          <div className="sf-solutions-edit">
            {ALL_SOLUTIONS.map((k) => {
              const r = solRows[k];
              return (
                <div className={`sf-solrow${r.included ? " is-on" : ""}`} key={k}>
                  <label className="sf-solrow-head">
                    <input
                      type="checkbox"
                      checked={r.included}
                      onChange={(e) => setSolRows({ ...solRows, [k]: { ...r, included: e.target.checked } })}
                    />
                    <span className="sf-solution-name">{SOLUTION_LABELS[k]}</span>
                    {k === "ai" && <span className="sf-badge">cross-cutting</span>}
                  </label>
                  {r.included && (
                    <div className="sf-solrow-body">
                      <label className="sf-inline-check">
                        <input
                          type="checkbox"
                          checked={r.is_focus}
                          onChange={(e) => setSolRows({ ...solRows, [k]: { ...r, is_focus: e.target.checked } })}
                        />
                        Focus
                      </label>
                      <div className="sf-field sf-field-sm">
                        <label className="sf-label">Importance</label>
                        <select
                          className="sf-input"
                          value={r.importance}
                          onChange={(e) => setSolRows({ ...solRows, [k]: { ...r, importance: Number(e.target.value) } })}
                        >
                          {[1, 2, 3, 4, 5].map((n) => (
                            <option key={n} value={n}>{n}</option>
                          ))}
                        </select>
                      </div>
                      <div className="sf-field sf-field-sm">
                        <label className="sf-label">Priority</label>
                        <input
                          className="sf-input"
                          type="number"
                          min={0}
                          value={r.priority}
                          onChange={(e) => setSolRows({ ...solRows, [k]: { ...r, priority: Number(e.target.value) } })}
                        />
                      </div>
                      <div className="sf-field sf-field-grow">
                        <label className="sf-label">Concept notes</label>
                        <input
                          className="sf-input"
                          value={r.concept_notes}
                          onChange={(e) => setSolRows({ ...solRows, [k]: { ...r, concept_notes: e.target.value } })}
                          placeholder="How this solution is positioned for this brand"
                        />
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <div className="sf-form-actions">
            <button className="sf-btn sf-btn-accent" onClick={saveSolutions} disabled={solSaving}>
              {solSaving ? "Saving..." : "Save solutions"}
            </button>
            {solMsg && <span className="sf-test is-ok">{solMsg}</span>}
          </div>

          <h2 className="sf-section-title" style={{ marginTop: 22 }}>
            Monthly split preview · {brand.monthly_post_target} posts
          </h2>
          {(() => {
            const { quota, aiAngle } = previewDistribution(solRows, brand.monthly_post_target);
            const rowsOut = ALL_SOLUTIONS.filter((k) => (quota[k] ?? 0) > 0).map(
              (k) => [k, quota[k] as number] as const,
            );
            if (!rowsOut.length)
              return <p className="sf-note">Include at least one solution to see the split.</p>;
            const maxN = Math.max(1, ...rowsOut.map(([, n]) => n));
            return (
              <div className="sf-dist">
                {rowsOut.map(([k, n]) => (
                  <div className="sf-dist-row" key={k}>
                    <span className="sf-dist-label">{SOLUTION_LABELS[k]}</span>
                    <span className="sf-dist-bar">
                      <span style={{ width: `${(n / maxN) * 100}%` }} />
                    </span>
                    <span className="sf-dist-num">{n}</span>
                  </div>
                ))}
                <p className="sf-hint">
                  AI angle target: {aiAngle} posts carry a cross-cutting AI angle.
                </p>
              </div>
            );
          })()}

          <h2 className="sf-section-title" style={{ marginTop: 22 }}>Competitors by solution</h2>
          <div className="sf-info">
            Track competitors under the solution area they compete in. Research and future
            social monitoring read these per solution. Leave the solution as General if it
            spans all areas.
          </div>

          <div className="sf-comp-add">
            <div className="sf-row">
              <div className="sf-field sf-field-grow">
                <label className="sf-label">Name</label>
                <input className="sf-input" value={newComp.name}
                  onChange={(e) => setNewComp({ ...newComp, name: e.target.value })}
                  placeholder="Competitor name" />
              </div>
              <div className="sf-field sf-field-sm2">
                <label className="sf-label">Solution</label>
                <select className="sf-input" value={newComp.solution ?? ""}
                  onChange={(e) => setNewComp({ ...newComp, solution: (e.target.value || null) as SolutionKey | null })}>
                  <option value="">General</option>
                  {ALL_SOLUTIONS.map((k) => <option key={k} value={k}>{SOLUTION_LABELS[k]}</option>)}
                </select>
              </div>
            </div>
            <div className="sf-row">
              <div className="sf-field">
                <label className="sf-label">Instagram</label>
                <input className="sf-input" value={newComp.instagram_handle ?? ""}
                  onChange={(e) => setNewComp({ ...newComp, instagram_handle: e.target.value })} placeholder="@handle" />
              </div>
              <div className="sf-field">
                <label className="sf-label">LinkedIn</label>
                <input className="sf-input" value={newComp.linkedin_handle ?? ""}
                  onChange={(e) => setNewComp({ ...newComp, linkedin_handle: e.target.value })} placeholder="company/name" />
              </div>
              <div className="sf-field">
                <label className="sf-label">X</label>
                <input className="sf-input" value={newComp.x_handle ?? ""}
                  onChange={(e) => setNewComp({ ...newComp, x_handle: e.target.value })} placeholder="@handle" />
              </div>
            </div>
            <div className="sf-field">
              <label className="sf-label">Notes</label>
              <input className="sf-input" value={newComp.notes ?? ""}
                onChange={(e) => setNewComp({ ...newComp, notes: e.target.value })} placeholder="Why we track them" />
            </div>
            <div className="sf-form-actions">
              <label className="sf-inline-check">
                <input type="checkbox" checked={newComp.is_aspirational}
                  onChange={(e) => setNewComp({ ...newComp, is_aspirational: e.target.checked })} />
                Aspirational
              </label>
              <button className="sf-btn sf-btn-accent" onClick={addCompetitor}
                disabled={compBusy || !newComp.name.trim()}>
                {compBusy ? "Saving..." : "Add competitor"}
              </button>
              {compMsg && <span className="sf-test is-ok">{compMsg}</span>}
            </div>
          </div>

          {competitors.length === 0 ? (
            <p className="sf-note">No competitors yet.</p>
          ) : (
            [...ALL_SOLUTIONS, null].map((grp) => {
              const items = competitors.filter((c) => (c.solution ?? null) === grp);
              if (!items.length) return null;
              const label = grp ? SOLUTION_LABELS[grp] : "General / untagged";
              return (
                <div className="sf-comp-group" key={grp ?? "general"}>
                  <h3 className="sf-comp-grouptitle">
                    {label} <span className="sf-hint">({items.length})</span>
                  </h3>
                  {items.map((c) => (
                    <div className="sf-comp-row" key={c.id}>
                      {editingComp === c.id ? (
                        <div className="sf-comp-edit">
                          <div className="sf-row">
                            <input className="sf-input" value={editDraft.name}
                              onChange={(e) => setEditDraft({ ...editDraft, name: e.target.value })} placeholder="Name" />
                            <select className="sf-input" value={editDraft.solution ?? ""}
                              onChange={(e) => setEditDraft({ ...editDraft, solution: (e.target.value || null) as SolutionKey | null })}>
                              <option value="">General</option>
                              {ALL_SOLUTIONS.map((k) => <option key={k} value={k}>{SOLUTION_LABELS[k]}</option>)}
                            </select>
                          </div>
                          <div className="sf-row">
                            <input className="sf-input" value={editDraft.instagram_handle ?? ""}
                              onChange={(e) => setEditDraft({ ...editDraft, instagram_handle: e.target.value })} placeholder="Instagram" />
                            <input className="sf-input" value={editDraft.linkedin_handle ?? ""}
                              onChange={(e) => setEditDraft({ ...editDraft, linkedin_handle: e.target.value })} placeholder="LinkedIn" />
                            <input className="sf-input" value={editDraft.x_handle ?? ""}
                              onChange={(e) => setEditDraft({ ...editDraft, x_handle: e.target.value })} placeholder="X" />
                          </div>
                          <input className="sf-input" value={editDraft.notes ?? ""}
                            onChange={(e) => setEditDraft({ ...editDraft, notes: e.target.value })} placeholder="Notes" />
                          <div className="sf-form-actions">
                            <label className="sf-inline-check">
                              <input type="checkbox" checked={editDraft.is_aspirational}
                                onChange={(e) => setEditDraft({ ...editDraft, is_aspirational: e.target.checked })} />
                              Aspirational
                            </label>
                            <button className="sf-btn sf-btn-accent" onClick={saveEditCompetitor} disabled={compBusy}>Save</button>
                            <button className="sf-btn" onClick={() => setEditingComp(null)}>Cancel</button>
                          </div>
                        </div>
                      ) : (
                        <>
                          <div className="sf-comp-info">
                            <span className="sf-comp-name">{c.name}{c.is_aspirational ? " ★" : ""}</span>
                            <span className="sf-comp-meta">
                              {[c.instagram_handle && `IG ${c.instagram_handle}`, c.linkedin_handle && `LI ${c.linkedin_handle}`, c.x_handle && `X ${c.x_handle}`].filter(Boolean).join(" · ") || "—"}
                            </span>
                            {c.notes && <span className="sf-comp-notes">{c.notes}</span>}
                          </div>
                          <div className="sf-comp-actions">
                            <button className="sf-btn" onClick={() => startEditCompetitor(c)}>Edit</button>
                            <button className="sf-btn" onClick={() => removeCompetitor(c.id)}>Delete</button>
                          </div>
                        </>
                      )}
                    </div>
                  ))}
                </div>
              );
            })
          )}
        </section>
      )}

      {/* ── AI providers ────────────────────────────────────── */}
      {tab === "providers" && (
        <section className="sf-section">
          <div className="sf-info">
            Each phase can use its own model. Enter your API key, click{" "}
            <strong>Load models</strong> to pick from the models that key can use,
            then <strong>Save</strong>. <strong>Temperature</strong> controls
            creativity (0 = precise, 1 = creative); <strong>Max tokens</strong> caps
            response length. Keys are stored encrypted and never shown again — use{" "}
            <strong>Test key</strong> to verify a saved phase.
          </div>

          {providers.length > 0 && (
            <div className="sf-provider-table">
              {PHASES.map(({ key, label }) => {
                const cfg = providers.find((p) => p.phase === key);
                if (!cfg) return null;
                const test = testResults[key];
                return (
                  <div className="sf-provider-row" key={key}>
                    <div className="sf-provider-cell">
                      <span className="sf-provider-phase">{label}</span>
                      <span className="sf-provider-meta">
                        {cfg.provider} · {cfg.model}
                      </span>
                      <span className="sf-provider-meta">
                        key {cfg.api_key_masked} · temp {cfg.temperature} · max {cfg.max_tokens}
                      </span>
                    </div>
                    <div className="sf-provider-action">
                      <button
                        className="sf-btn"
                        onClick={() => handleTest(key)}
                        disabled={testing === key}
                      >
                        {testing === key ? "Testing…" : "Test key"}
                      </button>
                      {test && (
                        <span className={`sf-test${test.success ? " is-ok" : " is-bad"}`}>
                          {test.success ? `OK · ${test.latency_ms}ms` : `Failed: ${test.error ?? "error"}`}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          <form className="sf-form sf-form-tight" onSubmit={handleSaveProvider}>
            <p className="sf-form-legend">Add / update a provider</p>
            <div className="sf-row">
              <div className="sf-field">
                <label className="sf-label">Phase</label>
                <select
                  className="sf-input"
                  value={form.phase}
                  onChange={(e) => setForm({ ...form, phase: e.target.value as PhaseKey })}
                >
                  {PHASES.map((p) => (
                    <option key={p.key} value={p.key}>{p.label}</option>
                  ))}
                </select>
              </div>
              <div className="sf-field">
                <label className="sf-label">Provider</label>
                <select
                  className="sf-input"
                  value={form.provider}
                  onChange={(e) => {
                    setForm({ ...form, provider: e.target.value as ProviderKey, model: "" });
                    setModelOptions([]);
                    setModelSource(null);
                    setCustomModel(false);
                  }}
                >
                  {PROVIDERS.map((p) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
              </div>
            </div>

            <div className="sf-field">
              <label className="sf-label">API key</label>
              <div className="sf-inline-row">
                <input
                  className="sf-input"
                  type="password"
                  value={form.api_key}
                  onChange={(e) => setForm({ ...form, api_key: e.target.value })}
                  placeholder="Stored encrypted; never shown again"
                  minLength={8}
                  required
                  autoComplete="off"
                />
                <button
                  type="button"
                  className="sf-btn"
                  onClick={loadModels}
                  disabled={loadingModels}
                >
                  {loadingModels ? "Loading…" : "Load models"}
                </button>
              </div>
            </div>

            <div className="sf-field">
              <label className="sf-label">Model</label>
              {modelOptions.length > 0 && !customModel ? (
                <>
                  <select
                    className="sf-input"
                    value={form.model}
                    onChange={(e) => setForm({ ...form, model: e.target.value })}
                  >
                    {modelOptions.map((m) => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                  </select>
                  <div className="sf-field-foot">
                    <span className="sf-hint">
                      {modelOptions.length} models loaded ({modelSource}).
                    </span>
                    <button type="button" className="sf-linkbtn" onClick={() => setCustomModel(true)}>
                      Enter a model id manually
                    </button>
                  </div>
                </>
              ) : (
                <>
                  <input
                    className="sf-input"
                    value={form.model}
                    onChange={(e) => setForm({ ...form, model: e.target.value })}
                    placeholder="Click 'Load models' above, or type a model id"
                    required
                  />
                  {modelOptions.length > 0 && (
                    <div className="sf-field-foot">
                      <button type="button" className="sf-linkbtn" onClick={() => setCustomModel(false)}>
                        Pick from loaded models
                      </button>
                    </div>
                  )}
                </>
              )}
            </div>

            <div className="sf-row">
              <div className="sf-field">
                <label className="sf-label">Temperature</label>
                <input
                  className="sf-input"
                  type="number"
                  step={0.1}
                  min={0}
                  max={1}
                  value={form.temperature}
                  onChange={(e) => setForm({ ...form, temperature: Number(e.target.value) })}
                />
              </div>
              <div className="sf-field">
                <label className="sf-label">Max tokens</label>
                <input
                  className="sf-input"
                  type="number"
                  min={256}
                  max={200000}
                  value={form.max_tokens}
                  onChange={(e) => setForm({ ...form, max_tokens: Number(e.target.value) })}
                />
              </div>
            </div>

            <div className="sf-form-actions">
              <button className="sf-btn sf-btn-accent" type="submit" disabled={saving}>
                {saving ? "Saving…" : "Save provider"}
              </button>
              {saveMsg && <span className="sf-test is-ok">{saveMsg}</span>}
            </div>
          </form>
        </section>
      )}

      {/* ── Sources (research inputs) ────────────────────────── */}
      {tab === "sources" && (
        <section className="sf-section">
          <div className="sf-info">
            Define what research reads for this brand. <strong>Keywords</strong>
            {" "}drive the targeted web search (one per line).{" "}
            <strong>RSS feeds</strong> are extra article sources (one URL per line).
            {" "}<strong>Trends region</strong> is the Google Trends country (e.g. US,
            TR). Choose the search provider &amp; key on the Settings page.
          </div>
          <div className="sf-field">
            <label className="sf-label">Search keywords (one per line)</label>
            <textarea
              className="sf-input sf-textarea"
              value={srcKeywords}
              onChange={(e) => setSrcKeywords(e.target.value)}
              placeholder={"retail merchandising execution\nfield audit software\nAI in-store compliance"}
            />
          </div>
          <div className="sf-field">
            <label className="sf-label">RSS feeds (one URL per line)</label>
            <textarea
              className="sf-input sf-textarea"
              value={srcFeeds}
              onChange={(e) => setSrcFeeds(e.target.value)}
              placeholder={"https://www.retaildive.com/feeds/news/"}
            />
          </div>
          <div className="sf-field" style={{ maxWidth: 200 }}>
            <label className="sf-label">Trends region</label>
            <input
              className="sf-input"
              value={srcGeo}
              onChange={(e) => setSrcGeo(e.target.value)}
              placeholder="US"
            />
          </div>
          <div className="sf-form-actions">
            <button className="sf-btn sf-btn-accent" onClick={saveSources} disabled={srcSaving}>
              {srcSaving ? "Saving…" : "Save sources"}
            </button>
            {srcMsg && <span className="sf-test is-ok">{srcMsg}</span>}
          </div>
        </section>
      )}
    </div>
  );
}
