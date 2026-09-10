"use client";

// V3b — per-(brand, solution) reference library: upload (multipart), delete,
// reorder, and an editable visual note. These references seed gpt-image-1 edits at
// Phase-4 generation (V4) so a new post inherits the brand's proven style for this
// solution.

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";

import { api } from "@/lib/api";
import type { Brand, ReferenceImage, SolutionKey, VisualNotes } from "@/lib/types";
import { PageHeader, EmptyState, Loading } from "@/components/ui";

const SOLUTION_LABELS: Record<SolutionKey, string> = {
  merchandising: "Merchandising",
  field_audit: "Field Audit",
  field_sales: "Field Sales",
  home_service: "Home Service",
  ai: "AI",
  general: "General",
};

const ALL_SOLUTIONS: SolutionKey[] = [
  "merchandising",
  "field_audit",
  "field_sales",
  "home_service",
  "ai",
  "general",
];

function isSolutionKey(v: string): v is SolutionKey {
  return (ALL_SOLUTIONS as string[]).includes(v);
}

export default function SolutionReferencesPage() {
  const params = useParams<{ id: string; solution: string }>();
  const brandId = params.id;
  const solutionParam = params.solution;
  const validSolution = isSolutionKey(solutionParam);
  const solution = solutionParam as SolutionKey;

  const [brand, setBrand] = useState<Brand | null>(null);
  const [refs, setRefs] = useState<ReferenceImage[]>([]);
  const [notes, setNotes] = useState<VisualNotes | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Visual-note editor
  const [noteDraft, setNoteDraft] = useState("");
  const [noteSaving, setNoteSaving] = useState(false);
  const [noteMsg, setNoteMsg] = useState<string | null>(null);
  // AI-drafted art direction. The draft lands in the textarea unsaved, so the
  // owner still reviews and saves it — same human-in-the-loop rule as every stage.
  const [noteDrafting, setNoteDrafting] = useState(false);
  const [noteHint, setNoteHint] = useState<string | null>(null);

  // Upload / reorder / delete busy state
  const [uploading, setUploading] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [reordering, setReordering] = useState(false);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const load = useCallback(async () => {
    if (!validSolution) {
      setError(`Unknown solution: ${solutionParam}`);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [b, r, n] = await Promise.all([
        api.getBrand(brandId),
        api.listReferences(brandId, solution),
        api.getVisualNotes(brandId, solution),
      ]);
      setBrand(b);
      setRefs(r);
      setNotes(n);
      setNoteDraft(n.visual_notes ?? "");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [brandId, solution, solutionParam, validSolution]);

  useEffect(() => {
    void load();
  }, [load]);

  async function onFilesChosen(fileList: FileList | null) {
    if (!fileList || fileList.length === 0) return;
    setUploading(true);
    setError(null);
    try {
      const created = await api.uploadReferences(brandId, solution, Array.from(fileList));
      // Append the new ones, keeping display order (server assigns sort_order).
      setRefs((prev) => [...prev, ...created]);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function onDelete(id: string) {
    setBusyId(id);
    setError(null);
    try {
      await api.deleteReference(id);
      setRefs((prev) => prev.filter((r) => r.id !== id));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusyId(null);
    }
  }

  async function move(index: number, dir: -1 | 1) {
    const target = index + dir;
    if (target < 0 || target >= refs.length) return;
    const next = refs.slice();
    [next[index], next[target]] = [next[target], next[index]];
    setRefs(next); // optimistic
    setReordering(true);
    setError(null);
    try {
      const saved = await api.reorderReferences(
        brandId,
        solution,
        next.map((r) => r.id),
      );
      setRefs(saved);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
      await load(); // reconcile on failure
    } finally {
      setReordering(false);
    }
  }

  async function draftNote() {
    setNoteDrafting(true);
    setNoteMsg(null);
    setNoteHint(null);
    try {
      const res = await api.suggestVisualNotes(brandId, solution);
      setNoteDraft(res.suggestion);
      const bits: string[] = [];
      if (res.used_research) bits.push("the latest approved trend report");
      if (res.used_recent_posts) bits.push(`${res.used_recent_posts} recent post(s)`);
      if (res.used_reference_count) bits.push(`${res.used_reference_count} reference image(s)`);
      setNoteHint(
        bits.length
          ? `Drafted from ${bits.join(", ")}. Edit it, then Save note.`
          : "Drafted from the brand profile only. Edit it, then Save note."
      );
    } catch (e) {
      setNoteMsg(e instanceof Error ? e.message : "Could not draft a note.");
    } finally {
      setNoteDrafting(false);
    }
  }

  async function saveNote() {
    setNoteSaving(true);
    setNoteMsg(null);
    setError(null);
    try {
      const trimmed = noteDraft.trim();
      const saved = await api.setVisualNotes(brandId, solution, trimmed || null);
      setNotes(saved);
      setNoteDraft(saved.visual_notes ?? "");
      setNoteMsg("Saved.");
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setNoteSaving(false);
    }
  }

  if (loading) return <Loading label="Loading solution…" />;

  const label = validSolution ? SOLUTION_LABELS[solution] : solutionParam;
  const noteDirty = noteDraft.trim() !== (notes?.visual_notes ?? "").trim();
  const anyBusy = uploading || reordering || busyId !== null;

  return (
    <div>
      <Link
        href={`/brands/${brandId}`}
        className="ui-btn ui-btn-subtle ui-btn-sm"
        style={{ marginBottom: 16, display: "inline-flex" }}
      >
        ← Back to brand
      </Link>

      <PageHeader
        eyebrow={brand ? brand.display_name : "Brand"}
        title={`${label} · Reference library`}
        subtitle="Example posts that steer this solution's generated visuals. The image model reuses their style, so keep them on-brand and consistent."
      />

      {error && (
        <div className="sf-test is-err" style={{ marginBottom: 16 }}>
          {error}
        </div>
      )}

      {/* Editable visual note */}
      <section className="sf-section" style={{ marginBottom: 20 }}>
        <h2 className="sf-section-title">Visual note</h2>
        <p className="sf-note" style={{ marginTop: 0 }}>
          The art direction for this solution. Image generation treats it as the
          authoritative setting — it overrides whatever location the copy step
          invented — so describe the scene: who is in frame, where, doing what, in
          what light. Leave it empty to fall back to the built-in scene family.
        </p>
        <textarea
          className="sf-input"
          rows={3}
          value={noteDraft}
          onChange={(e) => setNoteDraft(e.target.value)}
          placeholder="e.g. Keep generous negative space top-left for the logo; muted product-in-context photography; avoid busy backgrounds."
          style={{ width: "100%", resize: "vertical" }}
          disabled={!validSolution || noteSaving}
        />
        <div className="sf-form-actions" style={{ marginTop: 10 }}>
          <button
            className="sf-btn sf-btn-accent"
            onClick={saveNote}
            disabled={!validSolution || noteSaving || !noteDirty}
          >
            {noteSaving ? "Saving…" : "Save note"}
          </button>
          <button
            className="sf-btn"
            onClick={draftNote}
            disabled={!validSolution || noteSaving || noteDrafting}
            title="Draft an art-direction brief from the brand profile, the latest trend report and recent posts"
          >
            {noteDrafting ? "Drafting…" : "Draft with AI"}
          </button>
          {noteMsg && !noteDirty && <span className="sf-test is-ok">{noteMsg}</span>}
        </div>
        {noteHint && <p className="sf-note" style={{ marginTop: 8 }}>{noteHint}</p>}
      </section>

      {/* Reference grid + upload */}
      <section className="sf-section">
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
            flexWrap: "wrap",
          }}
        >
          <h2 className="sf-section-title" style={{ margin: 0 }}>
            Reference images{refs.length ? ` · ${refs.length}` : ""}
          </h2>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            {reordering && <span className="sf-hint">Saving order…</span>}
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              multiple
              hidden
              onChange={(e) => onFilesChosen(e.target.files)}
            />
            <button
              className="sf-btn sf-btn-accent"
              onClick={() => fileInputRef.current?.click()}
              disabled={!validSolution || uploading}
            >
              {uploading ? "Uploading…" : "Upload images"}
            </button>
          </div>
        </div>

        <p className="sf-note" style={{ marginTop: 8 }}>
          Around 8–10 proven posts works well. Images are downscaled and stored
          automatically. Use the arrows to set the order the model sees them in.
        </p>

        {refs.length === 0 ? (
          <div style={{ marginTop: 12 }}>
            <EmptyState title="No reference images yet">
              Upload your proven posts for this solution — they will appear here and
              steer generation.
            </EmptyState>
          </div>
        ) : (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))",
              gap: 14,
              marginTop: 12,
            }}
          >
            {refs.map((r, i) => (
              <figure
                key={r.id}
                style={{
                  margin: 0,
                  border: "1px solid var(--sf-border, #e2e5ea)",
                  borderRadius: 10,
                  overflow: "hidden",
                  background: "var(--sf-surface, #fff)",
                  opacity: busyId === r.id ? 0.5 : 1,
                }}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={api.referenceRawUrl(r.id)}
                  alt={r.filename ?? "reference image"}
                  loading="lazy"
                  style={{ display: "block", width: "100%", height: 150, objectFit: "cover" }}
                />
                <figcaption
                  style={{
                    padding: "8px 10px",
                    fontSize: 12,
                    lineHeight: 1.35,
                    color: "var(--sf-muted, #667085)",
                    display: "flex",
                    flexDirection: "column",
                    gap: 8,
                  }}
                >
                  <span style={{ wordBreak: "break-word" }}>
                    {r.note || r.filename || "reference"}
                  </span>
                  <span style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <button
                      className="ui-btn ui-btn-subtle ui-btn-sm"
                      title="Move earlier"
                      onClick={() => move(i, -1)}
                      disabled={i === 0 || anyBusy}
                    >
                      ◀
                    </button>
                    <button
                      className="ui-btn ui-btn-subtle ui-btn-sm"
                      title="Move later"
                      onClick={() => move(i, 1)}
                      disabled={i === refs.length - 1 || anyBusy}
                    >
                      ▶
                    </button>
                    <button
                      className="ui-btn ui-btn-subtle ui-btn-sm"
                      title="Delete"
                      onClick={() => onDelete(r.id)}
                      disabled={anyBusy}
                      style={{ marginLeft: "auto" }}
                    >
                      Delete
                    </button>
                  </span>
                </figcaption>
              </figure>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
