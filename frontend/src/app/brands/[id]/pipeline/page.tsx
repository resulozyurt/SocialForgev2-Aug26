"use client";

// F0b — Content Pipeline landing: the month-board list.
// Each board is one (brand, planning_period). Starting a month opens a board;
// the whole research -> calendar -> copy -> visual flow then runs *inside* that
// board's period (the runner now lives at /pipeline/[period]).

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import { api } from "@/lib/api";
import type { Brand, MonthBoard } from "@/lib/types";
import { PageHeader, Loading, EmptyState, Button, Card, CardBody, Badge } from "@/components/ui";

function nextMonth(): string {
  const d = new Date();
  d.setDate(1);
  d.setMonth(d.getMonth() + 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

const PERIOD_RE = /^\d{4}-\d{2}$/;
const msg = (e: unknown) => (e instanceof Error ? e.message : "Something went wrong.");

const MONTHS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];

function periodLabel(period: string): string {
  const m = PERIOD_RE.exec(period);
  if (!m) return period;
  const [y, mm] = period.split("-");
  const idx = Number(mm) - 1;
  return `${MONTHS[idx] ?? mm} ${y}`;
}

type StatusMeta = { tone: "accent" | "ok" | "muted"; label: string };
function statusMeta(status: string): StatusMeta {
  if (status === "ready") return { tone: "ok", label: "Ready" };
  if (status === "archived") return { tone: "muted", label: "Archived" };
  return { tone: "accent", label: "In progress" };
}

type Pill = { tone: "ok" | "warn" | "muted" | "neutral"; label: string };
function gatePill(total: number, approved: number): Pill {
  if (approved > 0) return { tone: "ok", label: "Approved" };
  if (total > 0) return { tone: "warn", label: "Draft" };
  return { tone: "muted", label: "—" };
}

function StageRow({ label, pill, hint }: { label: string; pill: Pill; hint?: string }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: 8,
        padding: "6px 0",
        borderTop: "1px solid var(--ui-line, rgba(120,120,120,0.15))",
      }}
    >
      <span style={{ fontSize: 13, color: "var(--ui-muted, #6b7280)" }}>{label}</span>
      <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
        {hint && <span style={{ fontSize: 12, color: "var(--ui-muted, #6b7280)" }}>{hint}</span>}
        <Badge tone={pill.tone}>{pill.label}</Badge>
      </span>
    </div>
  );
}

export default function PipelineBoardsPage() {
  const params = useParams();
  const brandId = String(params.id);

  const [brand, setBrand] = useState<Brand | null>(null);
  const [boards, setBoards] = useState<MonthBoard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [newPeriod, setNewPeriod] = useState(nextMonth());
  const [newTitle, setNewTitle] = useState("");
  const [creating, setCreating] = useState(false);
  const [confirmRemove, setConfirmRemove] = useState<string | null>(null);
  const [removingId, setRemovingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [b, list] = await Promise.all([api.getBrand(brandId), api.listBoards(brandId)]);
      setBrand(b);
      setBoards(list);
    } catch (e) {
      setError(msg(e));
    } finally {
      setLoading(false);
    }
  }, [brandId]);

  useEffect(() => {
    load();
  }, [load]);

  async function createBoard() {
    const period = newPeriod.trim();
    if (!PERIOD_RE.test(period)) {
      setError("Month must be in YYYY-MM format (e.g. 2026-11).");
      return;
    }
    setCreating(true);
    setError(null);
    try {
      await api.createBoard(brandId, { planning_period: period, title: newTitle.trim() || null });
      setNewTitle("");
      await load();
    } catch (e) {
      setError(msg(e));
    } finally {
      setCreating(false);
    }
  }

  async function removeBoard(id: string) {
    setRemovingId(id);
    setError(null);
    try {
      await api.deleteBoard(id);
      setConfirmRemove(null);
      await load();
    } catch (e) {
      setError(msg(e));
    } finally {
      setRemovingId(null);
    }
  }

  if (loading) return <Loading label="Loading boards…" />;

  return (
    <div>
      <Link
        href={`/brands/${brandId}`}
        className="ui-btn ui-btn-subtle ui-btn-sm"
        style={{ marginBottom: 16, display: "inline-flex" }}
      >
        ← {brand ? brand.display_name : "Brand"}
      </Link>

      <PageHeader
        eyebrow={brand ? brand.display_name : "Brand"}
        title="Content Pipeline"
        subtitle="Each month is its own board. Start a month, then run research → calendar → copy → visual inside it — everything stays scoped to that month."
      />

      {error && (
        <div className="sf-test is-err" style={{ marginBottom: 16 }}>
          {error}
        </div>
      )}

      {/* Start a month */}
      <section className="sf-section" style={{ marginBottom: 24 }}>
        <h2 className="sf-section-title" style={{ marginTop: 0 }}>Start a month</h2>
        <p className="sf-note" style={{ marginTop: 0 }}>
          Opens a board for that month. If a board already exists for it, you land on the existing one.
        </p>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "flex-end" }}>
          <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12 }}>
            <span style={{ color: "var(--ui-muted, #6b7280)" }}>Month (YYYY-MM)</span>
            <input
              className="sf-input"
              value={newPeriod}
              onChange={(e) => setNewPeriod(e.target.value)}
              placeholder="2026-11"
              style={{ width: 140 }}
              disabled={creating}
            />
          </label>
          <label style={{ display: "flex", flexDirection: "column", gap: 4, fontSize: 12, flex: "1 1 240px" }}>
            <span style={{ color: "var(--ui-muted, #6b7280)" }}>Title (optional)</span>
            <input
              className="sf-input"
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              placeholder="e.g. November — Perfect Store push"
              disabled={creating}
            />
          </label>
          <Button variant="primary" onClick={createBoard} disabled={creating}>
            {creating ? "Starting…" : "Start month"}
          </Button>
        </div>
      </section>

      {/* Board list */}
      {boards.length === 0 ? (
        <EmptyState title="No month boards yet">
          Start your first month above to begin the pipeline.
        </EmptyState>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
            gap: 16,
          }}
        >
          {boards.map((b) => {
            const st = statusMeta(b.status);
            const s = b.stats;
            const copyHint = `${s.copy_approved}/${s.copy_total || 0} approved`;
            const visualHint = s.visual_posts > 0 ? `${s.visual_posts} with image` : undefined;
            return (
              <Card key={b.id}>
                <CardBody>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "flex-start",
                      justifyContent: "space-between",
                      gap: 8,
                    }}
                  >
                    <div>
                      <div style={{ fontSize: 18, fontWeight: 700 }}>{periodLabel(b.planning_period)}</div>
                      <div style={{ fontSize: 12, color: "var(--ui-muted, #6b7280)" }}>
                        {b.planning_period}
                        {b.title ? ` · ${b.title}` : ""}
                      </div>
                    </div>
                    <Badge tone={st.tone}>{st.label}</Badge>
                  </div>

                  <div style={{ marginTop: 12 }}>
                    <StageRow label="Research" pill={gatePill(s.report_total, s.report_approved)} />
                    <StageRow label="Calendar" pill={gatePill(s.calendar_total, s.calendar_approved)} />
                    <StageRow
                      label="Copy"
                      hint={copyHint}
                      pill={
                        s.copy_approved > 0
                          ? { tone: "ok", label: `${s.copy_approved}` }
                          : s.copy_total > 0
                            ? { tone: "warn", label: "Draft" }
                            : { tone: "muted", label: "—" }
                      }
                    />
                    <StageRow
                      label="Visual"
                      hint={visualHint}
                      pill={
                        s.visual_posts > 0
                          ? { tone: "ok", label: `${s.visual_posts}` }
                          : { tone: "muted", label: "—" }
                      }
                    />
                  </div>

                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: 8,
                      marginTop: 14,
                    }}
                  >
                    <Link
                      href={`/brands/${brandId}/pipeline/${b.planning_period}`}
                      className="ui-btn ui-btn-primary ui-btn-sm"
                    >
                      Open →
                    </Link>
                    {confirmRemove === b.id ? (
                      <span style={{ display: "inline-flex", gap: 6 }}>
                        <Button
                          variant="danger"
                          size="sm"
                          onClick={() => removeBoard(b.id)}
                          disabled={removingId === b.id}
                        >
                          {removingId === b.id ? "Removing…" : "Confirm"}
                        </Button>
                        <Button size="sm" onClick={() => setConfirmRemove(null)} disabled={removingId === b.id}>
                          Cancel
                        </Button>
                      </span>
                    ) : (
                      <Button variant="subtle" size="sm" onClick={() => setConfirmRemove(b.id)}>
                        Remove
                      </Button>
                    )}
                  </div>
                </CardBody>
              </Card>
            );
          })}
        </div>
      )}

      <p className="sf-note" style={{ marginTop: 20 }}>
        Removing a board only clears the board entry — the month&apos;s reports, calendars and posts stay intact.
      </p>
    </div>
  );
}
