"use client";

// B1 — post detail page. Click a post -> one page with EVERYTHING for it (on-visual
// headline, caption, hooks, CTA, hashtags, alt text, carousel/thread, visual
// direction) plus inline visual generation + candidate selection. This is the
// post-centric view that replaces hopping across pipeline stages.

import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";

import { api } from "@/lib/api";
import type { ContentPackage, VisualResponse } from "@/lib/types";
import { PageHeader, Badge, Loading, Button } from "@/components/ui";

function O(v: unknown): Record<string, unknown> {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : {};
}
function S(v: unknown): string {
  return typeof v === "string" ? v : "";
}
function A(v: unknown): unknown[] {
  return Array.isArray(v) ? v : [];
}
function msg(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="sf-section" style={{ marginBottom: 16 }}>
      <h2 className="sf-section-title">{title}</h2>
      {children}
    </section>
  );
}

export default function PostDetailPage() {
  const params = useParams<{ id: string; packageId: string }>();
  const brandId = params.id;
  const packageId = params.packageId;

  const [pkg, setPkg] = useState<ContentPackage | null>(null);
  const [visual, setVisual] = useState<VisualResponse | null>(null);
  const [lang, setLang] = useState<"en" | "tr">("en");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [vmsg, setVmsg] = useState("");
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [p, v] = await Promise.all([
        api.getPackage(packageId),
        api.getVisual(packageId).catch(() => null),
      ]);
      setPkg(p);
      setVisual(v);
    } catch (e) {
      setError(msg(e));
    } finally {
      setLoading(false);
    }
  }, [packageId]);

  useEffect(() => {
    void load();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [load]);

  async function approveCopy() {
    try {
      await api.approvePackage(packageId);
      await load();
    } catch (e) {
      setError(msg(e));
    }
  }
  async function rejectCopy() {
    try {
      await api.rejectPackage(packageId);
      await load();
    } catch (e) {
      setError(msg(e));
    }
  }

  async function generate() {
    setBusy(true);
    setVmsg("Generating candidates…");
    try {
      await api.generateVisual(packageId);
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = setInterval(async () => {
        const st = await api.visualStatus(packageId).catch(() => null);
        if (st) setVmsg(st.message || st.status);
        if (st && st.status === "done") {
          if (pollRef.current) clearInterval(pollRef.current);
          const v = await api.getVisual(packageId);
          setVisual(v);
          setBusy(false);
          setVmsg("Candidates ready — pick one.");
        } else if (st && st.status === "error") {
          if (pollRef.current) clearInterval(pollRef.current);
          setBusy(false);
          setVmsg(st.message);
        }
      }, 2500);
    } catch (e) {
      setBusy(false);
      setVmsg(msg(e));
    }
  }
  async function selectCandidate(generationId: string) {
    setVisual((v) => (v ? { ...v, selected_generation_id: generationId } : v));
    try {
      await api.selectVisualGeneration(packageId, generationId);
    } catch (e) {
      setVmsg(msg(e));
      const v = await api.getVisual(packageId).catch(() => null);
      if (v) setVisual(v);
    }
  }
  async function approveVisual() {
    try {
      await api.approveVisual(packageId);
      const v = await api.getVisual(packageId).catch(() => null);
      if (v) setVisual(v);
      setVmsg("Visual approved.");
    } catch (e) {
      setVmsg(msg(e));
    }
  }
  async function rejectVisual() {
    try {
      await api.rejectVisual(packageId);
      const v = await api.getVisual(packageId).catch(() => null);
      if (v) setVisual(v);
      setVmsg("Visual rejected — you can regenerate.");
    } catch (e) {
      setVmsg(msg(e));
    }
  }
  function download() {
    const sel = visual?.selected_generation_id ?? visual?.generations?.[0]?.id;
    if (!sel) return;
    const a = document.createElement("a");
    a.href = api.visualGenerationRawUrl(sel);
    a.download = `${pkg?.post_id ?? packageId}.png`;
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  if (loading) return <Loading label="Loading post…" />;
  if (!pkg) return <div className="sf-test is-err">{error ?? "Post not found."}</div>;

  const copy = O(lang === "tr" ? pkg.copy_package_tr : pkg.copy_package_en);
  const en = O(pkg.copy_package_en);
  const vd = O(pkg.visual_direction);
  const overlay = O(vd.text_overlay);
  const headline = S(overlay.primary);
  const hooks = A(copy.hooks).map(S).filter(Boolean);
  const caption = S(copy.caption) || S(en.caption);
  const cta = S(copy.cta);
  const hashtags = O(copy.hashtags);
  const tags = [...A(hashtags.broad), ...A(hashtags.niche), ...A(hashtags.branded)].map(S);
  const slides = A(copy.carousel_slides).map(S).filter(Boolean);
  const thread = A(copy.thread).map(S).filter(Boolean);
  const altText = S(copy.alt_text);
  const approved = pkg.status === "approved";
  const status = visual?.visual_status ?? undefined;
  const selGen = visual?.selected_generation_id ?? visual?.generations?.[0]?.id;
  const selUrl = selGen ? api.visualGenerationRawUrl(selGen) : "";

  return (
    <div>
      <Link
        href={
          pkg.planning_period
            ? `/brands/${brandId}/pipeline/${pkg.planning_period}`
            : `/brands/${brandId}/pipeline`
        }
        className="ui-btn ui-btn-subtle ui-btn-sm"
        style={{ marginBottom: 16, display: "inline-flex" }}
      >
        ← Back to {pkg.planning_period ? `${pkg.planning_period} board` : "pipeline"}
      </Link>

      <PageHeader
        eyebrow={`${pkg.platform} · ${pkg.content_type}${pkg.solution ? ` · ${pkg.solution}` : ""}${
          pkg.planning_period ? ` · ${pkg.planning_period}` : ""
        }`}
        title={headline || pkg.post_id}
        subtitle={pkg.post_id}
        actions={
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <Badge tone={approved ? "ok" : pkg.is_rejected ? "warn" : "neutral"}>
              {pkg.is_rejected ? "rejected" : pkg.status}
            </Badge>
            <div className="ui-langsw" role="group" aria-label="Copy language">
              <button className={lang === "en" ? "active" : ""} onClick={() => setLang("en")}>
                EN
              </button>
              <button className={lang === "tr" ? "active" : ""} onClick={() => setLang("tr")}>
                TR
              </button>
            </div>
          </div>
        }
      />

      {error && <div className="sf-test is-err" style={{ marginBottom: 16 }}>{error}</div>}

      <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) minmax(0, 360px)", gap: 18, alignItems: "start" }}>
        {/* LEFT — all copy details */}
        <div>
          {headline ? (
            <Section title="On-visual headline">
              <p style={{ fontSize: 20, fontWeight: 700, margin: 0 }}>{headline}</p>
              {S(overlay.secondary) ? <p className="sf-note" style={{ marginTop: 6 }}>{S(overlay.secondary)}</p> : null}
            </Section>
          ) : null}

          {hooks.length > 0 ? (
            <Section title="Hooks">
              <ul style={{ margin: 0, paddingLeft: 18 }}>
                {hooks.map((h, i) => <li key={i} style={{ marginBottom: 4 }}>{h}</li>)}
              </ul>
            </Section>
          ) : null}

          {caption ? (
            <Section title="Caption">
              <p style={{ whiteSpace: "pre-wrap", margin: 0 }}>{caption}</p>
            </Section>
          ) : null}

          {cta ? (
            <Section title="Call to action"><p style={{ margin: 0 }}>{cta}</p></Section>
          ) : null}

          {tags.length > 0 ? (
            <Section title="Hashtags">
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {tags.map((t, i) => (
                  <span key={i} className="sf-badge">{t.startsWith("#") ? t : `#${t}`}</span>
                ))}
              </div>
            </Section>
          ) : null}

          {slides.length > 0 ? (
            <Section title="Carousel slides">
              <ol style={{ margin: 0, paddingLeft: 18 }}>
                {slides.map((sl, i) => <li key={i} style={{ marginBottom: 4 }}>{sl}</li>)}
              </ol>
            </Section>
          ) : null}

          {thread.length > 0 ? (
            <Section title="Thread">
              <ol style={{ margin: 0, paddingLeft: 18 }}>
                {thread.map((tw, i) => <li key={i} style={{ marginBottom: 4 }}>{tw}</li>)}
              </ol>
            </Section>
          ) : null}

          {altText ? (
            <Section title="Alt text"><p className="sf-note" style={{ margin: 0 }}>{altText}</p></Section>
          ) : null}

          {(S(pkg.strategic_rationale) || S(pkg.target_audience) || S(pkg.trend_signal)) ? (
            <Section title="Strategy">
              {S(pkg.target_audience) ? <p style={{ margin: "0 0 6px" }}><b>Audience: </b>{S(pkg.target_audience)}</p> : null}
              {S(pkg.strategic_rationale) ? <p style={{ margin: "0 0 6px" }}><b>Rationale: </b>{S(pkg.strategic_rationale)}</p> : null}
              {S(pkg.trend_signal) ? <p style={{ margin: 0 }}><b>Trend signal: </b>{S(pkg.trend_signal)}</p> : null}
            </Section>
          ) : null}

          {(S(vd.image_prompt) || S(vd.concept) || S(vd.mood) || S(vd.composition)) ? (
            <Section title="Visual direction">
              {S(vd.concept) ? <p style={{ margin: "0 0 6px" }}><b>Concept: </b>{S(vd.concept)}</p> : null}
              {S(vd.mood) ? <p style={{ margin: "0 0 6px" }}><b>Mood: </b>{S(vd.mood)}</p> : null}
              {S(vd.composition) ? <p style={{ margin: "0 0 6px" }}><b>Composition: </b>{S(vd.composition)}</p> : null}
              {S(vd.image_prompt) ? (
                <div className="ui-promptbox" style={{ marginTop: 6 }}><b>Image prompt · </b>{S(vd.image_prompt)}</div>
              ) : null}
            </Section>
          ) : null}
        </div>

        {/* RIGHT — visual generation */}
        <div style={{ position: "sticky", top: 12 }}>
          <Section title="Visual">
            {!approved ? (
              <div>
                <p className="sf-note" style={{ marginTop: 0 }}>
                  Approve the copy first, then generate the visual (Approval 3 is copy + visual).
                </p>
                <Button size="sm" variant="primary" onClick={approveCopy}>Approve copy</Button>
                {!pkg.is_rejected ? (
                  <Button size="sm" variant="subtle" onClick={rejectCopy} style={{ marginLeft: 8 }}>Reject</Button>
                ) : null}
              </div>
            ) : (
              <div>
                <div
                  style={{
                    aspectRatio: "1 / 1",
                    border: "1px solid var(--sf-border, #e2e5ea)",
                    borderRadius: 10,
                    overflow: "hidden",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    background: "var(--sf-surface, #fafafa)",
                    marginBottom: 10,
                  }}
                >
                  {selUrl ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={selUrl} alt={headline || pkg.post_id} style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                  ) : (
                    <span className="sf-hint">{busy ? "Generating…" : "No visual yet"}</span>
                  )}
                </div>

                {visual?.generations && visual.generations.length > 1 ? (
                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
                    {visual.generations.map((g, ci) => {
                      const sel = selGen === g.id;
                      return (
                        <button
                          key={g.id}
                          type="button"
                          title={`Version ${visual.generations.length - ci}`}
                          onClick={() => selectCandidate(g.id)}
                          style={{
                            padding: 0,
                            border: sel ? "2px solid var(--sf-accent, #0ea5a4)" : "2px solid transparent",
                            borderRadius: 8,
                            overflow: "hidden",
                            cursor: "pointer",
                            lineHeight: 0,
                            background: "none",
                          }}
                        >
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img src={api.visualGenerationRawUrl(g.id)} alt={`version ${ci + 1}`} style={{ width: 56, height: 56, objectFit: "cover", display: "block" }} />
                        </button>
                      );
                    })}
                  </div>
                ) : null}

                {selUrl && visual?.used_references === false ? (
                  <p className="sf-note" style={{ fontSize: 12, marginTop: 0 }}>
                    No references for this solution — generated from text only. Add references on the solution page.
                  </p>
                ) : null}
                {selUrl && visual?.used_references ? (
                  <p className="sf-note" style={{ fontSize: 12, marginTop: 0 }}>
                    Generated from {visual.reference_count ?? 0} reference image{(visual.reference_count ?? 0) === 1 ? "" : "s"}.
                  </p>
                ) : null}

                {status ? <div style={{ marginBottom: 8 }}><Badge tone={status === "approved" ? "ok" : "neutral"}>{status}</Badge></div> : null}
                {vmsg ? <p className="sf-note" style={{ fontSize: 12, marginTop: 0 }}>{vmsg}</p> : null}

                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  <Button size="sm" variant="primary" onClick={generate} disabled={busy}>
                    {busy ? "Generating…" : selUrl ? "Regenerate" : "Generate"}
                  </Button>
                  {selUrl && status !== "approved" ? (
                    <Button size="sm" onClick={approveVisual} disabled={busy}>Approve</Button>
                  ) : null}
                  {selUrl ? (
                    <Button size="sm" variant="subtle" onClick={download} disabled={busy}>Download</Button>
                  ) : null}
                  {selUrl ? (
                    <Button size="sm" variant="subtle" onClick={rejectVisual} disabled={busy}>Reject</Button>
                  ) : null}
                </div>
              </div>
            )}
          </Section>
        </div>
      </div>
    </div>
  );
}
