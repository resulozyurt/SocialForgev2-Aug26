"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import type {
  Brand,
  BrandSolution,
  Competitor,
  PhaseKey,
  ProviderConfig,
  ProviderConfigCreate,
  ProviderKey,
  ProviderTestResult,
  SolutionKey,
} from "@/lib/types";

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

// ── Safe readers for the free-form JSON profile fields ──────────────────────
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

const EMPTY_PROVIDER: ProviderConfigCreate = {
  phase: "phase1_research",
  provider: "anthropic",
  model: "",
  api_key: "",
  temperature: 0.7,
  max_tokens: 4096,
};

export default function BrandDetailPage() {
  const params = useParams();
  const brandId = String(params.id);

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
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load brand.");
    } finally {
      setLoading(false);
    }
  }, [brandId]);

  useEffect(() => {
    load();
  }, [load]);

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
      const prov = await api.listProviders(brandId).catch(() => []);
      setProviders(prov);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save provider.");
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
        [phase]: {
          success: false,
          provider: "",
          model: "",
          latency_ms: null,
          error: err instanceof Error ? err.message : "Test failed.",
        },
      }));
    } finally {
      setTesting(null);
    }
  }

  if (loading) return <p className="sf-note">Loading brand…</p>;
  if (error && !brand) return <div className="sf-error">{error}</div>;
  if (!brand) return <div className="sf-error">Brand not found.</div>;

  const vi = asRecord(brand.visual_identity);
  const vp = asRecord(brand.voice_profile);
  const pill = asRecord(vi.pill);

  const swatches = [
    { label: "Primary", hex: brand.primary_color },
    { label: "Secondary", hex: brand.secondary_color },
    { label: "Accent", hex: brand.accent_color },
    { label: "Ground", hex: asStr(vi.ground_color) },
    { label: "Block", hex: asStr(vi.block_color) },
    { label: "Pill", hex: asStr(pill.bg_color) },
  ].filter((s) => s.hex);

  const motifs = asStrList(vi.motifs);
  const styleKeywords = asStrList(vi.style_keywords);
  const toneKeywords = asStrList(vp.tone_keywords);
  const exampleHeadlines = asStrList(vp.example_headlines);
  const avoid = asStrList(vp.avoid);
  const narrative = asStr(vp.narrative_structure);

  const sortedSolutions = [...solutions].sort((a, b) => a.priority - b.priority);

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
        <div className="sf-head-badges">
          <span className="sf-badge">{brand.language.toUpperCase()}</span>
          <span className="sf-badge">{brand.monthly_post_target} posts/mo</span>
          <span className={`sf-badge${brand.is_active ? " is-active" : ""}`}>
            {brand.is_active ? "Active" : "Inactive"}
          </span>
        </div>
      </div>

      {error && <div className="sf-error">{error}</div>}

      {/* ── Visual identity ─────────────────────────────────── */}
      <section className="sf-section">
        <h2 className="sf-section-title">Visual identity</h2>
        {swatches.length > 0 && (
          <div className="sf-swatches">
            {swatches.map((s) => (
              <div className="sf-swatch" key={s.label}>
                <span
                  className="sf-swatch-chip"
                  style={{ background: s.hex ?? "transparent" }}
                />
                <span className="sf-swatch-label">
                  {s.label}
                  <br />
                  <code>{s.hex}</code>
                </span>
              </div>
            ))}
          </div>
        )}
        {styleKeywords.length > 0 && (
          <div className="sf-kv">
            <span className="sf-kv-key">Style</span>
            <div className="sf-chips">
              {styleKeywords.map((k) => (
                <span className="sf-chip" key={k}>
                  {k}
                </span>
              ))}
            </div>
          </div>
        )}
        {motifs.length > 0 && (
          <div className="sf-kv">
            <span className="sf-kv-key">Motifs</span>
            <ul className="sf-list">
              {motifs.map((m) => (
                <li key={m}>{m}</li>
              ))}
            </ul>
          </div>
        )}
      </section>

      {/* ── Voice ───────────────────────────────────────────── */}
      <section className="sf-section">
        <h2 className="sf-section-title">Voice &amp; tone</h2>
        {brand.voice_guide_text && (
          <p className="sf-prose">{brand.voice_guide_text}</p>
        )}
        {toneKeywords.length > 0 && (
          <div className="sf-kv">
            <span className="sf-kv-key">Tone</span>
            <div className="sf-chips">
              {toneKeywords.map((k) => (
                <span className="sf-chip" key={k}>
                  {k}
                </span>
              ))}
            </div>
          </div>
        )}
        {narrative && (
          <div className="sf-kv">
            <span className="sf-kv-key">Narrative</span>
            <span className="sf-kv-val">{narrative}</span>
          </div>
        )}
        {exampleHeadlines.length > 0 && (
          <div className="sf-kv">
            <span className="sf-kv-key">Examples</span>
            <ul className="sf-list">
              {exampleHeadlines.map((h) => (
                <li key={h}>&ldquo;{h}&rdquo;</li>
              ))}
            </ul>
          </div>
        )}
        {avoid.length > 0 && (
          <div className="sf-kv">
            <span className="sf-kv-key">Avoid</span>
            <div className="sf-chips">
              {avoid.map((k) => (
                <span className="sf-chip is-warn" key={k}>
                  {k}
                </span>
              ))}
            </div>
          </div>
        )}
      </section>

      {/* ── Solutions ───────────────────────────────────────── */}
      <section className="sf-section">
        <h2 className="sf-section-title">Solution focus</h2>
        {sortedSolutions.length === 0 ? (
          <p className="sf-note">No solutions configured.</p>
        ) : (
          <div className="sf-solutions">
            {sortedSolutions.map((s) => (
              <div className="sf-solution" key={s.id}>
                <div className="sf-solution-head">
                  <span className="sf-solution-name">
                    {SOLUTION_LABELS[s.solution] ?? s.solution}
                  </span>
                  <span
                    className={`sf-badge${s.is_focus ? " is-active" : ""}`}
                  >
                    {s.is_focus ? "Focus" : "Off"}
                  </span>
                </div>
                {s.concept_notes && (
                  <p className="sf-solution-notes">{s.concept_notes}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* ── Competitors ─────────────────────────────────────── */}
      {competitors.length > 0 && (
        <section className="sf-section">
          <h2 className="sf-section-title">Competitors</h2>
          <div className="sf-chips">
            {competitors.map((c) => (
              <span className="sf-chip" key={c.id}>
                {c.name}
                {c.is_aspirational ? " ★" : ""}
              </span>
            ))}
          </div>
        </section>
      )}

      {/* ── AI providers ────────────────────────────────────── */}
      <section className="sf-section">
        <h2 className="sf-section-title">AI providers</h2>
        <p className="sf-hint">
          Configure which AI model and API key each phase uses. A phase can only
          run once its provider is set.
        </p>

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
                      key {cfg.api_key_masked} · temp {cfg.temperature} · max{" "}
                      {cfg.max_tokens}
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
                      <span
                        className={`sf-test${test.success ? " is-ok" : " is-bad"}`}
                      >
                        {test.success
                          ? `OK · ${test.latency_ms}ms`
                          : `Failed: ${test.error ?? "error"}`}
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
                onChange={(e) =>
                  setForm({ ...form, phase: e.target.value as PhaseKey })
                }
              >
                {PHASES.map((p) => (
                  <option key={p.key} value={p.key}>
                    {p.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="sf-field">
              <label className="sf-label">Provider</label>
              <select
                className="sf-input"
                value={form.provider}
                onChange={(e) =>
                  setForm({ ...form, provider: e.target.value as ProviderKey })
                }
              >
                {PROVIDERS.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="sf-field">
            <label className="sf-label">Model</label>
            <input
              className="sf-input"
              value={form.model}
              onChange={(e) => setForm({ ...form, model: e.target.value })}
              placeholder="e.g. claude-sonnet-4-5 / gpt-4o / gemini-1.5-pro"
              required
            />
          </div>
          <div className="sf-field">
            <label className="sf-label">API key</label>
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
                onChange={(e) =>
                  setForm({ ...form, temperature: Number(e.target.value) })
                }
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
                onChange={(e) =>
                  setForm({ ...form, max_tokens: Number(e.target.value) })
                }
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
    </div>
  );
}
