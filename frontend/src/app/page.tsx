"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import type { Brand, BrandCreate } from "@/lib/types";

const EMPTY_FORM: BrandCreate = {
  slug: "",
  display_name: "",
  industry: "",
  monthly_post_target: 20,
};

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
      <div className="sf-page-head">
        <div>
          <p className="sf-eyebrow">Workspace</p>
          <h1 className="sf-title">Brands</h1>
          <p className="sf-subtitle">
            Each brand runs its own isolated pipeline — competitors, voice, and AI config.
          </p>
        </div>
        <button
          className="sf-btn sf-btn-accent"
          onClick={() => setShowForm((v) => !v)}
        >
          {showForm ? "Cancel" : "New brand"}
        </button>
      </div>

      {error && <div className="sf-error">{error}</div>}

      {showForm && (
        <form className="sf-form" onSubmit={handleCreate}>
          <div className="sf-row">
            <div className="sf-field">
              <label className="sf-label">Slug</label>
              <input
                className="sf-input"
                value={form.slug}
                onChange={(e) => setForm({ ...form, slug: e.target.value })}
                placeholder="e.g. acme"
                minLength={2}
                maxLength={64}
                required
              />
            </div>
            <div className="sf-field">
              <label className="sf-label">Display name</label>
              <input
                className="sf-input"
                value={form.display_name}
                onChange={(e) => setForm({ ...form, display_name: e.target.value })}
                placeholder="e.g. Acme Corp"
                maxLength={128}
                required
              />
            </div>
          </div>
          <div className="sf-row">
            <div className="sf-field">
              <label className="sf-label">Industry</label>
              <input
                className="sf-input"
                value={form.industry ?? ""}
                onChange={(e) => setForm({ ...form, industry: e.target.value })}
                placeholder="e.g. Field Service Management SaaS"
              />
            </div>
            <div className="sf-field">
              <label className="sf-label">Monthly post target</label>
              <input
                className="sf-input"
                type="number"
                min={1}
                max={200}
                value={form.monthly_post_target}
                onChange={(e) =>
                  setForm({ ...form, monthly_post_target: Number(e.target.value) })
                }
              />
            </div>
          </div>
          <div className="sf-form-actions">
            <button className="sf-btn sf-btn-accent" type="submit" disabled={submitting}>
              {submitting ? "Creating…" : "Create brand"}
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <p className="sf-note">Loading brands…</p>
      ) : brands.length === 0 ? (
        <div className="sf-empty">No brands yet. Create your first one above.</div>
      ) : (
        <div className="sf-grid">
          {brands.map((brand) => (
            <div className="sf-card" key={brand.id}>
              <div>
                <h2 className="sf-card-name">{brand.display_name}</h2>
                <p className="sf-card-meta">
                  @{brand.slug}
                  {brand.industry ? ` · ${brand.industry}` : ""}
                </p>
              </div>
              <p className="sf-card-meta">
                Target: {brand.monthly_post_target} posts / month
              </p>
              <div className="sf-card-foot">
                <span className={`sf-badge${brand.is_active ? " is-active" : ""}`}>
                  {brand.is_active ? "Active" : "Inactive"}
                </span>
                <Link href={`/brands/${brand.id}`} className="sf-link">
                  Open →
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}