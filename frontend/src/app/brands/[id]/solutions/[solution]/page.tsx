"use client";

// V3a — per-(brand, solution) page shell + reference-image list.
// The owner uploads ~8-10 proven example posts here; at Phase-4 generation (V4)
// they seed gpt-image-1 edits so a new post inherits the brand's proven style for
// this solution. V3a is read-only display + empty states; upload / delete /
// reorder and the editable visual note arrive in V3b.

import { useCallback, useEffect, useState } from "react";
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
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [brandId, solution, solutionParam, validSolution]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading) return <Loading label="Loading solution…" />;

  const label = validSolution ? SOLUTION_LABELS[solution] : solutionParam;

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

      {/* Visual note (read-only in V3a; editable in V3b) */}
      <section className="sf-section" style={{ marginBottom: 20 }}>
        <h2 className="sf-section-title">Visual note</h2>
        <p className="sf-note" style={{ marginTop: 0 }}>
          A short style instruction added to the image prompt for this solution
          (e.g. layout, motifs, what to avoid). Editing arrives next (V3b).
        </p>
        {notes?.visual_notes ? (
          <p style={{ whiteSpace: "pre-wrap", marginTop: 8 }}>{notes.visual_notes}</p>
        ) : (
          <p className="sf-hint" style={{ marginTop: 8 }}>
            No visual note yet.
          </p>
        )}
      </section>

      {/* Reference grid */}
      <section className="sf-section">
        <h2 className="sf-section-title">
          Reference images{refs.length ? ` · ${refs.length}` : ""}
        </h2>

        {refs.length === 0 ? (
          <EmptyState title="No reference images yet">
            Uploading is added in the next step (V3b). Once you add your ~8-10 proven
            posts for this solution, they will appear here and steer generation.
          </EmptyState>
        ) : (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))",
              gap: 14,
              marginTop: 12,
            }}
          >
            {refs.map((r) => (
              <figure
                key={r.id}
                style={{
                  margin: 0,
                  border: "1px solid var(--sf-border, #e2e5ea)",
                  borderRadius: 10,
                  overflow: "hidden",
                  background: "var(--sf-surface, #fff)",
                }}
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={api.referenceRawUrl(r.id)}
                  alt={r.filename ?? "reference image"}
                  loading="lazy"
                  style={{ display: "block", width: "100%", height: 150, objectFit: "cover" }}
                />
                {(r.filename || r.note) && (
                  <figcaption
                    style={{
                      padding: "8px 10px",
                      fontSize: 12,
                      lineHeight: 1.35,
                      color: "var(--sf-muted, #667085)",
                      wordBreak: "break-word",
                    }}
                  >
                    {r.note || r.filename}
                  </figcaption>
                )}
              </figure>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
