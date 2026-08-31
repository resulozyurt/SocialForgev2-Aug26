"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Brand, BrandCreate } from "@/lib/types";
import {
  Button,
  Card,
  CardFoot,
  Badge,
  Stat,
  Stats,
  Field,
  Input,
  PageHeader,
  EmptyState,
  Loading,
} from "@/components/ui";

const EMPTY_FORM: BrandCreate = {
  slug: "",
  display_name: "",
  industry: "",
  monthly_post_target: 20,
};

function IconPlus() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}

export default function BrandsPage() {
  const [brands, setBrands] = useState<Brand[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<BrandCreate>(EMPTY_FORM);
  const [submitting, setSubmitting] = useState(false);

  async function loadBrands() {
    setLoading(true);
    setError(null);
    try {
      setBrands(await api.listBrands());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load brands.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadBrands();
  }, []);

  const summary = useMemo(() => {
    const active = brands.filter((b) => b.is_active).length;
    const posts = brands.reduce((n, b) => n + (b.monthly_post_target || 0), 0);
    return { total: brands.length, active, posts };
  }, [brands]);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api.createBrand({
        slug: form.slug.trim(),
        display_name: form.display_name.trim(),
        industry: form.industry?.trim() || null,
        monthly_post_target: Number(form.monthly_post_target) || 20,
      });
      setForm(EMPTY_FORM);
      setShowForm(false);
      await loadBrands();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create brand.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <PageHeader
        eyebrow="Workspace"
        title="Brands"
        subtitle="Each brand runs its own isolated pipeline — competitors, voice, and AI config."
        actions={
          <Button variant="primary" onClick={() => setShowForm((v) => !v)}>
            {showForm ? "Cancel" : (<><IconPlus /> New brand</>)}
          </Button>
        }
      />

      {error && <div className="ui-error">{error}</div>}

      {!loading && brands.length > 0 && (
        <div style={{ marginBottom: 22 }}>
          <Stats>
            <Stat label="Brands" value={summary.total} note="workspaces" />
            <Stat label="Active" value={summary.active} note={`${summary.total - summary.active} inactive`} />
            <Stat label="Monthly posts" value={summary.posts} note="combined target" />
          </Stats>
        </div>
      )}

      {showForm && (
        <form className="ui-form" onSubmit={handleCreate}>
          <div className="ui-row">
            <Field label="Slug">
              <Input
                value={form.slug}
                onChange={(e) => setForm({ ...form, slug: e.target.value })}
                placeholder="e.g. acme"
                minLength={2}
                maxLength={64}
                required
              />
            </Field>
            <Field label="Display name">
              <Input
                value={form.display_name}
                onChange={(e) => setForm({ ...form, display_name: e.target.value })}
                placeholder="e.g. Acme Corp"
                maxLength={128}
                required
              />
            </Field>
          </div>
          <div className="ui-row">
            <Field label="Industry">
              <Input
                value={form.industry ?? ""}
                onChange={(e) => setForm({ ...form, industry: e.target.value })}
                placeholder="e.g. Field Service Management SaaS"
              />
            </Field>
            <Field label="Monthly post target">
              <Input
                type="number"
                min={1}
                max={200}
                value={form.monthly_post_target}
                onChange={(e) => setForm({ ...form, monthly_post_target: Number(e.target.value) })}
              />
            </Field>
          </div>
          <div className="ui-form-actions">
            <Button variant="primary" type="submit" disabled={submitting}>
              {submitting ? "Creating…" : "Create brand"}
            </Button>
            <Button variant="subtle" type="button" onClick={() => setShowForm(false)}>
              Cancel
            </Button>
          </div>
        </form>
      )}

      {loading ? (
        <Loading label="Loading brands…" />
      ) : brands.length === 0 ? (
        <EmptyState title="No brands yet">
          Create your first brand to start a content pipeline.
        </EmptyState>
      ) : (
        <div className="ui-grid">
          {brands.map((brand) => (
            <Card interactive key={brand.id}>
              <div className="ui-card-pad" style={{ display: "flex", flexDirection: "column", gap: 10, minHeight: 128 }}>
                <div>
                  <h2 style={{ margin: 0, fontFamily: "var(--font-display), sans-serif", fontSize: 18, fontWeight: 700, letterSpacing: "-.01em", color: "var(--text)" }}>
                    {brand.display_name}
                  </h2>
                  <p style={{ margin: "4px 0 0", fontSize: 12.5, color: "var(--muted)" }}>
                    @{brand.slug}
                    {brand.industry ? ` · ${brand.industry}` : ""}
                  </p>
                </div>
                <p style={{ margin: 0, fontSize: 13, color: "var(--text-2)" }}>
                  Target: <b style={{ fontVariantNumeric: "tabular-nums" }}>{brand.monthly_post_target}</b> posts / month
                </p>
              </div>
              <CardFoot>
                <Badge tone={brand.is_active ? "ok" : "muted"}>
                  {brand.is_active ? "Active" : "Inactive"}
                </Badge>
                <Link href={`/brands/${brand.id}`} className="ui-btn ui-btn-subtle ui-btn-sm" style={{ marginLeft: "auto" }}>
                  Open →
                </Link>
              </CardFoot>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
