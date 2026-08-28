"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import type {
  Brand,
  ContentCalendar,
  ContentPackage,
  TrendReport,
} from "@/lib/types";

const S = (v: unknown): string =>
  v === null || v === undefined ? "" : typeof v === "string" ? v : String(v);
const A = (v: unknown): unknown[] => (Array.isArray(v) ? v : []);
const O = (v: unknown): Record<string, unknown> =>
  v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : {};
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const msg = (e: unknown) => (e instanceof Error ? e.message : "Something went wrong.");

function currentPeriod(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

type Running = { research: boolean; calendar: boolean; copy: boolean };
type LogLine = { time: string; text: string; kind: "info" | "ok" | "err" };

// A backend 404 on a by-id action means the row is already gone (deleted in
// another tab, or the on-screen list is stale). Treat it as "missing" so the UI
// can silently refresh and explain, instead of surfacing a scary error banner.
const isMissingError = (e: unknown) => msg(e).includes("404");

// ── F3: solution-first, tabbed report view ──────────────────────────────────
const SOLUTION_LABELS: Record<string, string> = {
  merchandising: "Merchandising",
  field_audit: "Field Audit",
  field_sales: "Field Sales",
  home_service: "Home Service",
  ai: "AI",
  general: "General",
};
const SOLUTION_ORDER = ["merchandising", "field_audit", "field_sales", "home_service", "ai", "general"];
const solKey = (v: unknown): string =>
  S(v).trim().toLowerCase().replace(/\s+/g, "_") || "general";
const solLabel = (key: string): string =>
  SOLUTION_LABELS[key] ?? key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

function ReportView({ report }: { report: TrendReport }) {
  const topics = A(report.trending_topics).map((t) => O(t));
  const gaps = A(report.content_gaps).map((g) => O(g));
  const pillars = A(report.recommended_pillars).map((p) => O(p));
  const src = O(report.sources);
  const search = A(src.search).map((x) => O(x));
  const rss = A(src.rss).map((x) => O(x));
  const trends = A(src.trends).map((x) => O(x));

  const present = new Set<string>();
  topics.forEach((t) => present.add(solKey(t.solution)));
  gaps.forEach((g) => present.add(solKey(g.solution)));
  search.forEach((x) => present.add(solKey(x.solution)));
  const solutions = [...present].sort(
    (a, b) => ((SOLUTION_ORDER.indexOf(a) + 1) || 99) - ((SOLUTION_ORDER.indexOf(b) + 1) || 99)
  );

  const tabs = ["overview", ...solutions];
  const [tab, setTab] = useState<string>("overview");
  const active = tabs.includes(tab) ? tab : "overview";

  const forSol = (arr: Record<string, unknown>[], key: string) =>
    arr.filter((x) => solKey(x.solution) === key);
  const count = (key: string) => forSol(topics, key).length + forSol(gaps, key).length;

  return (
    <div className="sf-report">
      <div className="sf-tabs sf-rtabs">
        {tabs.map((t) => (
          <button
            key={t}
            className={`sf-tab${active === t ? " is-active" : ""}`}
            onClick={() => setTab(t)}
          >
            {t === "overview" ? "Overview" : solLabel(t)}
          </button>
        ))}
      </div>

      {active === "overview" ? (
        <div className="sf-report-panel">
          <div className="sf-caldist">
            {solutions.map((sol) => (
              <span key={sol} className={`sf-caldist-chip${sol === "ai" ? " is-ai" : ""}`}>
                {solLabel(sol)} <b>{count(sol)}</b>
              </span>
            ))}
          </div>
          {pillars.length > 0 && (
            <>
              <h4 className="sf-h4">Recommended pillars</h4>
              <ul className="sf-list">
                {pillars.map((o, i) => (
                  <li key={i}>
                    <strong>{S(o.name)}</strong>
                    {o.percentage ? ` (${S(o.percentage)}%)` : ""} — {S(o.description)}
                  </li>
                ))}
              </ul>
            </>
          )}
          {(rss.length > 0 || trends.length > 0) && (
            <>
              <h4 className="sf-h4">Feeds &amp; trends</h4>
              {rss.length > 0 && (
                <ul className="sf-list sf-sources">
                  {rss.map((o, i) => (
                    <li key={`r${i}`}>
                      <a href={S(o.link)} target="_blank" rel="noopener noreferrer">
                        {S(o.title) || S(o.link)}
                      </a>
                      <span className="sf-src-tag">{S(o.source) || "rss"}</span>
                    </li>
                  ))}
                </ul>
              )}
              {trends.length > 0 && (
                <p className="sf-hint">
                  Trends: {trends.map((o) => S(o.title)).filter(Boolean).join(", ")}
                </p>
              )}
            </>
          )}
        </div>
      ) : (
        <div className="sf-report-panel">
          {(() => {
            const t = forSol(topics, active);
            const g = forSol(gaps, active);
            const so = forSol(search, active);
            if (!t.length && !g.length && !so.length)
              return <p className="sf-note">Nothing tagged for {solLabel(active)} in this report.</p>;
            return (
              <>
                {t.length > 0 && (
                  <>
                    <h4 className="sf-h4">Trending topics</h4>
                    <ul className="sf-list">
                      {t.map((o, i) => (
                        <li key={i}>
                          <strong>{S(o.topic)}</strong>
                          {o.signal_strength ? (
                            <span className={`sf-sig is-${S(o.signal_strength).toLowerCase()}`}>
                              {S(o.signal_strength)}
                            </span>
                          ) : null}
                          {" — "}
                          {S(o.why_it_matters)}
                        </li>
                      ))}
                    </ul>
                  </>
                )}
                {g.length > 0 && (
                  <>
                    <h4 className="sf-h4">Content gaps</h4>
                    <ul className="sf-list">
                      {g.map((o, i) => (
                        <li key={i}>
                          <strong>{S(o.gap)}</strong> → {S(o.opportunity)}
                        </li>
                      ))}
                    </ul>
                  </>
                )}
                {so.length > 0 && (
                  <>
                    <h4 className="sf-h4">Sources</h4>
                    <ul className="sf-list sf-sources">
                      {so.map((o, i) => (
                        <li key={`s${i}`}>
                          <a href={S(o.url)} target="_blank" rel="noopener noreferrer">
                            {S(o.title) || S(o.url)}
                          </a>
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </>
            );
          })()}
        </div>
      )}
    </div>
  );
}

export default function PipelinePage() {
  const params = useParams();
  const brandId = String(params.id);

  const [brand, setBrand] = useState<Brand | null>(null);
  const [reports, setReports] = useState<TrendReport[]>([]);
  const [reportBusy, setReportBusy] = useState<string | null>(null);
  const [editReportId, setEditReportId] = useState<string | null>(null);
  const [editInstruction, setEditInstruction] = useState("");
  const [calendars, setCalendars] = useState<ContentCalendar[]>([]);
  const [packages, setPackages] = useState<ContentPackage[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState<Running>({
    research: false,
    calendar: false,
    copy: false,
  });

  const [period, setPeriod] = useState(currentPeriod());
  const [copyLimit, setCopyLimit] = useState<string>("");
  const [generateTr, setGenerateTr] = useState(true);

  const [log, setLog] = useState<LogLine[]>([]);
  const logEndRef = useRef<HTMLDivElement | null>(null);

  const addLog = useCallback(
    (text: string, kind: LogLine["kind"] = "info") => {
      const time = new Date().toLocaleTimeString();
      setLog((l) => [...l, { time, text, kind }].slice(-250));
    },
    []
  );

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ block: "nearest" });
  }, [log]);

  const refreshReports = useCallback(
    () =>
      api
        .listReports(brandId)
        .then(setReports)
        .catch((e) => addLog(`Could not refresh reports: ${msg(e)}`, "err")),
    [brandId, addLog]
  );
  const refreshCalendars = useCallback(
    () =>
      api
        .listCalendars(brandId)
        .then(setCalendars)
        .catch((e) => addLog(`Could not refresh calendars: ${msg(e)}`, "err")),
    [brandId, addLog]
  );
  const refreshPackages = useCallback(
    () =>
      api
        .listPackages(brandId)
        .then(setPackages)
        .catch((e) => addLog(`Could not refresh packages: ${msg(e)}`, "err")),
    [brandId, addLog]
  );

  useEffect(() => {
    api.getBrand(brandId).then(setBrand).catch((e) => setError(msg(e)));
    refreshReports();
    refreshCalendars();
    refreshPackages();
  }, [brandId, refreshReports, refreshCalendars, refreshPackages]);

  const hasApprovedReport = reports.some((r) => r.is_approved);
  const hasApprovedCalendar = calendars.some((c) => c.is_approved);

  async function runResearch() {
    setError(null);
    setRunning((r) => ({ ...r, research: true }));
    const before = reports.length;
    addLog(`Research: requesting a trend report for ${period}…`);
    try {
      await api.runResearch(brandId, { planning_period: period, max_posts: 20 });
      addLog("Research: gathering RSS + Google Trends, then drafting with AI…");
      for (let i = 0; i < 24; i++) {
        await sleep(5000);
        addLog(`Research: waiting for the draft (check ${i + 1})…`);
        const latest = await api.listReports(brandId);
        setReports(latest);
        if (latest.length > before) {
          const topics = A(O(latest[0]).trending_topics).length;
          addLog(`Research: draft received — ${topics} trending topics. Review and approve.`, "ok");
          break;
        }
        if (i === 23) addLog("Research: still working — use Refresh in a moment.", "info");
      }
    } catch (e) {
      addLog(`Research: error — ${msg(e)}`, "err");
      setError(msg(e));
    } finally {
      setRunning((r) => ({ ...r, research: false }));
    }
  }

  async function runCalendar() {
    setError(null);
    setRunning((r) => ({ ...r, calendar: true }));
    const before = calendars.length;
    addLog("Calendar: building a monthly plan from the approved report…");
    try {
      await api.runCalendar(brandId, {});
      for (let i = 0; i < 24; i++) {
        await sleep(5000);
        const latest = await api.listCalendars(brandId);
        setCalendars(latest);
        if (latest.length > before) {
          const entries = A(O(latest[0]).entries).length;
          addLog(`Calendar: draft received — ${entries} planned posts. Review and approve.`, "ok");
          break;
        }
        // Surface a background-run failure instead of waiting the full timeout.
        const st = await api.calendarStatus(brandId).catch(() => null);
        if (st?.status === "error") {
          addLog(`Calendar: run failed — ${st.message}`, "err");
          setError(st.message);
          break;
        }
        addLog(`Calendar: waiting for the draft (check ${i + 1})…`);
        if (i === 23) addLog("Calendar: still working — use Refresh in a moment.", "info");
      }
    } catch (e) {
      addLog(`Calendar: error — ${msg(e)}`, "err");
      setError(msg(e));
    } finally {
      setRunning((r) => ({ ...r, calendar: false }));
    }
  }

  async function runCopy() {
    setError(null);
    setRunning((r) => ({ ...r, copy: true }));
    const before = packages.length;
    const limit = copyLimit.trim() ? Number(copyLimit) : undefined;
    addLog(
      `Copy: drafting ${limit ? limit + " post(s)" : "all posts"}${
        generateTr ? " (EN + TR)" : " (EN)"
      } — one AI call each…`
    );
    try {
      await api.runCopy(brandId, { limit, generate_tr: generateTr });
      for (let i = 0; i < 60; i++) {
        await sleep(5000);
        addLog(`Copy: writing content… (check ${i + 1})`);
        const latest = await api.listPackages(brandId);
        setPackages(latest);
        if (latest.length > before) {
          addLog(`Copy: ${latest.length - before} content package(s) ready. Review and approve.`, "ok");
          break;
        }
        if (i === 59) addLog("Copy: still working — use Refresh in a moment.", "info");
      }
    } catch (e) {
      addLog(`Copy: error — ${msg(e)}`, "err");
      setError(msg(e));
    } finally {
      setRunning((r) => ({ ...r, copy: false }));
    }
  }

  async function approveReport(id: string) {
    setReportBusy(id);
    try {
      await api.approveReport(id);
      addLog("Trend report approved — you can now run the calendar.", "ok");
      await refreshReports();
    } catch (e) {
      if (isMissingError(e)) {
        addLog("That report no longer exists — the list has been refreshed.", "info");
        await refreshReports();
      } else {
        addLog(`Approve report: error — ${msg(e)}`, "err");
        setError(msg(e));
      }
    } finally {
      setReportBusy(null);
    }
  }
  async function rejectReport(id: string) {
    setReportBusy(id);
    try {
      await api.rejectReport(id);
      addLog("Trend report rejected.", "info");
      await refreshReports();
    } catch (e) {
      if (isMissingError(e)) {
        addLog("That report no longer exists — the list has been refreshed.", "info");
        await refreshReports();
      } else {
        addLog(`Reject report: error — ${msg(e)}`, "err");
        setError(msg(e));
      }
    } finally {
      setReportBusy(null);
    }
  }
  async function deleteReport(id: string) {
    setReportBusy(id);
    try {
      await api.deleteReport(id);
      addLog("Trend report deleted.", "info");
      await refreshReports();
    } catch (e) {
      if (isMissingError(e)) {
        addLog("That report was already removed — the list has been refreshed.", "info");
        await refreshReports();
      } else {
        addLog(`Delete report: error — ${msg(e)}`, "err");
        setError(msg(e));
      }
    } finally {
      setReportBusy(null);
    }
  }
  async function submitAiEdit(id: string) {
    if (!editInstruction.trim()) return;
    setReportBusy(id);
    addLog("Report: AI is applying your edit…");
    try {
      await api.aiEditReport(id, editInstruction.trim());
      addLog("Report: AI edit applied — review the updated draft.", "ok");
      setEditReportId(null);
      setEditInstruction("");
      await refreshReports();
    } catch (e) {
      if (isMissingError(e)) {
        addLog("That report no longer exists — the list has been refreshed.", "info");
        setEditReportId(null);
        await refreshReports();
      } else {
        addLog(`AI edit: error — ${msg(e)}`, "err");
        setError(msg(e));
      }
    } finally {
      setReportBusy(null);
    }
  }
  async function approveCalendar(id: string) {
    try {
      await api.approveCalendar(id);
      addLog("Calendar approved — you can now run copy.", "ok");
      await refreshCalendars();
    } catch (e) {
      if (isMissingError(e)) {
        addLog("That calendar no longer exists — the list has been refreshed.", "info");
        await refreshCalendars();
      } else {
        addLog(`Approve calendar: error — ${msg(e)}`, "err");
        setError(msg(e));
      }
    }
  }
  async function approvePackage(id: string) {
    try {
      await api.approvePackage(id);
      addLog("Content package approved.", "ok");
      await refreshPackages();
    } catch (e) {
      if (isMissingError(e)) {
        addLog("That content package no longer exists — the list has been refreshed.", "info");
        await refreshPackages();
      } else {
        addLog(`Approve package: error — ${msg(e)}`, "err");
        setError(msg(e));
      }
    }
  }

  const anyRunning = running.research || running.calendar || running.copy;

  return (
    <div>
      <Link href={`/brands/${brandId}`} className="sf-back">
        ← {brand ? brand.display_name : "Brand"}
      </Link>

      <div className="sf-page-head">
        <div>
          <p className="sf-eyebrow">Content pipeline</p>
          <h1 className="sf-title">Research → Calendar → Copy</h1>
          <p className="sf-subtitle">
            Every stage drafts; you approve before the next one can run.
          </p>
        </div>
      </div>

      <div className="sf-info">
        Run each stage in order. A stage stays locked until you approve the one
        before it. Each stage needs its AI provider set on the brand page (Research,
        Calendar, Copy). Runs happen in the background — the activity log below shows
        what&rsquo;s happening in real time.
      </div>

      {error && <div className="sf-error">{error}</div>}

      {/* ── Activity log ────────────────────────────────────── */}
      <section className="sf-log-panel">
        <div className="sf-log-head">
          <span className="sf-log-title">
            Activity {anyRunning && <span className="sf-live-dot" />}
          </span>
          {log.length > 0 && (
            <button className="sf-linkbtn" onClick={() => setLog([])}>
              Clear
            </button>
          )}
        </div>
        <div className="sf-log">
          {log.length === 0 ? (
            <p className="sf-log-empty">Run a stage to see live activity here.</p>
          ) : (
            log.map((l, i) => (
              <div className={`sf-log-line is-${l.kind}`} key={i}>
                <span className="sf-log-time">{l.time}</span> {l.text}
              </div>
            ))
          )}
          <div ref={logEndRef} />
        </div>
      </section>

      {/* ── Stage 1: Research ─────────────────────────────── */}
      <section className="sf-stage">
        <div className="sf-stage-head">
          <div>
            <span className="sf-stage-num">1</span>
            <h2 className="sf-stage-title">Research — trend report</h2>
          </div>
          <div className="sf-stage-actions">
            <label className="sf-inline-field">
              <span className="sf-label">Period</span>
              <input
                className="sf-input sf-input-sm"
                value={period}
                onChange={(e) => setPeriod(e.target.value)}
                placeholder="2026-09"
              />
            </label>
            <button className="sf-btn sf-btn-accent" onClick={runResearch} disabled={running.research}>
              {running.research ? "Running…" : "Run research"}
            </button>
            <button className="sf-btn" onClick={refreshReports} disabled={running.research}>
              Refresh
            </button>
          </div>
        </div>
        <p className="sf-hint">
          Free RSS + Google Trends. Requires a Research AI provider (set it on the brand page).
        </p>

        {reports.length === 0 ? (
          <p className="sf-note">No reports yet. Run research to draft one.</p>
        ) : (
          reports.map((r) => (
            <article className="sf-item" key={r.id}>
              <div className="sf-item-head">
                <div>
                  <span className="sf-item-title">Trend report · {r.planning_period}</span>
                  <span className="sf-item-meta">
                    {A(r.trending_topics).length} topics · {A(r.recommended_pillars).length} pillars
                  </span>
                </div>
                <div className="sf-item-actions">
                  <span className={`sf-badge${r.is_approved ? " is-active" : r.is_rejected ? " is-warn" : ""}`}>
                    {r.is_approved ? "Approved" : r.is_rejected ? "Rejected" : "Draft"}
                  </span>
                  {!r.is_approved && (
                    <button className="sf-btn" onClick={() => approveReport(r.id)} disabled={reportBusy === r.id}>
                      Approve
                    </button>
                  )}
                  {!r.is_rejected && (
                    <button className="sf-btn" onClick={() => rejectReport(r.id)} disabled={reportBusy === r.id}>
                      Reject
                    </button>
                  )}
                  <button
                    className="sf-btn"
                    onClick={() => {
                      setEditReportId(editReportId === r.id ? null : r.id);
                      setEditInstruction("");
                    }}
                    disabled={reportBusy === r.id}
                  >
                    Edit with AI
                  </button>
                  <button className="sf-btn" onClick={() => deleteReport(r.id)} disabled={reportBusy === r.id}>
                    Delete
                  </button>
                </div>
              </div>
              {editReportId === r.id && (
                <div className="sf-airow">
                  <textarea
                    className="sf-input sf-textarea"
                    value={editInstruction}
                    onChange={(e) => setEditInstruction(e.target.value)}
                    placeholder="Tell the AI what to change, e.g. 'Focus the content gaps on in-store AI compliance and drop the generic ones.'"
                  />
                  <div className="sf-form-actions">
                    <button
                      className="sf-btn sf-btn-accent"
                      onClick={() => submitAiEdit(r.id)}
                      disabled={reportBusy === r.id || !editInstruction.trim()}
                    >
                      {reportBusy === r.id ? "Applying…" : "Apply AI edit"}
                    </button>
                    <button
                      className="sf-btn"
                      onClick={() => {
                        setEditReportId(null);
                        setEditInstruction("");
                      }}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              )}
              <details className="sf-details">
                <summary>View report</summary>
                <ReportView report={r} />
              </details>
            </article>
          ))
        )}
      </section>

      {/* ── Stage 2: Calendar ─────────────────────────────── */}
      <section className="sf-stage">
        <div className="sf-stage-head">
          <div>
            <span className="sf-stage-num">2</span>
            <h2 className="sf-stage-title">Calendar — monthly plan</h2>
          </div>
          <div className="sf-stage-actions">
            <button
              className="sf-btn sf-btn-accent"
              onClick={runCalendar}
              disabled={running.calendar || !hasApprovedReport}
            >
              {running.calendar ? "Running…" : "Run calendar"}
            </button>
            <button className="sf-btn" onClick={refreshCalendars} disabled={running.calendar}>
              Refresh
            </button>
          </div>
        </div>
        <p className="sf-hint">
          {hasApprovedReport
            ? "Builds from your latest approved trend report."
            : "Approve a trend report above first."}
        </p>

        {calendars.length === 0 ? (
          <p className="sf-note">No calendars yet.</p>
        ) : (
          calendars.map((c) => (
            <article className="sf-item" key={c.id}>
              <div className="sf-item-head">
                <div>
                  <span className="sf-item-title">Calendar · {c.planning_period}</span>
                  <span className="sf-item-meta">
                    {c.post_count} posts · {(c.platforms ?? []).join(", ") || "—"}
                  </span>
                </div>
                <div className="sf-item-actions">
                  <span className={`sf-badge${c.is_approved ? " is-active" : ""}`}>
                    {c.is_approved ? "Approved" : "Draft"}
                  </span>
                  {!c.is_approved && (
                    <button className="sf-btn" onClick={() => approveCalendar(c.id)}>
                      Approve
                    </button>
                  )}
                </div>
              </div>
              {c.summary && <p className="sf-prose">{c.summary}</p>}
              {(() => {
                const entries = A(c.entries);
                if (!entries.length) return null;
                const bySol: Record<string, number> = {};
                let withAi = 0;
                for (const e of entries) {
                  const o = O(e);
                  const sol = S(o.solution) || "general";
                  bySol[sol] = (bySol[sol] || 0) + 1;
                  if (S(o.ai_angle)) withAi += 1;
                }
                const dist = Object.entries(bySol).sort((a, b) => b[1] - a[1]);
                return (
                  <div className="sf-caldist">
                    {dist.map(([sol, n]) => (
                      <span className="sf-caldist-chip" key={sol}>
                        {sol} <b>{n}</b>
                      </span>
                    ))}
                    <span className="sf-caldist-chip is-ai">AI angle <b>{withAi}</b></span>
                  </div>
                );
              })()}
              <details className="sf-details">
                <summary>View {A(c.entries).length} entries</summary>
                <div className="sf-table-scroll">
                  <table className="sf-table">
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Solution</th>
                        <th>Platform</th>
                        <th>Type</th>
                        <th>Pillar</th>
                        <th>Hook</th>
                        <th>AI angle</th>
                      </tr>
                    </thead>
                    <tbody>
                      {A(c.entries).map((e, i) => {
                        const o = O(e);
                        return (
                          <tr key={i}>
                            <td>{S(o.date)}</td>
                            <td>
                              {S(o.solution) ? (
                                <span className="sf-sol-chip">{S(o.solution)}</span>
                              ) : (
                                "—"
                              )}
                            </td>
                            <td>{S(o.platform)}</td>
                            <td>{S(o.content_type)}</td>
                            <td>{S(o.pillar)}</td>
                            <td>{S(o.hook_concept)}</td>
                            <td>{S(o.ai_angle) || "—"}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </details>
            </article>
          ))
        )}
      </section>

      {/* ── Stage 3: Copy ─────────────────────────────────── */}
      <section className="sf-stage">
        <div className="sf-stage-head">
          <div>
            <span className="sf-stage-num">3</span>
            <h2 className="sf-stage-title">Copy — content packages</h2>
          </div>
          <div className="sf-stage-actions">
            <label className="sf-inline-field">
              <span className="sf-label">Limit</span>
              <input
                className="sf-input sf-input-sm"
                value={copyLimit}
                onChange={(e) => setCopyLimit(e.target.value)}
                placeholder="all"
                type="number"
                min={1}
              />
            </label>
            <label className="sf-check">
              <input
                type="checkbox"
                checked={generateTr}
                onChange={(e) => setGenerateTr(e.target.checked)}
              />
              TR
            </label>
            <button
              className="sf-btn sf-btn-accent"
              onClick={runCopy}
              disabled={running.copy || !hasApprovedCalendar}
            >
              {running.copy ? "Running…" : "Run copy"}
            </button>
            <button className="sf-btn" onClick={refreshPackages} disabled={running.copy}>
              Refresh
            </button>
          </div>
        </div>
        <p className="sf-hint">
          {hasApprovedCalendar
            ? "Limit = how many posts to draft now (leave empty for all). TR = also write the Turkish version. One AI draft per entry — a full month can take a few minutes."
            : "Approve a calendar above first."}
        </p>

        {packages.length === 0 ? (
          <p className="sf-note">No content packages yet.</p>
        ) : (
          packages.map((p) => {
            const en = O(p.copy_package_en);
            const tr = O(p.copy_package_tr);
            const vd = O(p.visual_direction);
            const hashtags = O(en.hashtags);
            const allTags = [
              ...A(hashtags.broad),
              ...A(hashtags.niche),
              ...A(hashtags.branded),
            ].map(S);
            return (
              <article className="sf-item" key={p.id}>
                <div className="sf-item-head">
                  <div>
                    <span className="sf-item-title">{p.post_id}</span>
                    <span className="sf-item-meta">
                      {p.platform} · {p.content_type}
                    </span>
                  </div>
                  <div className="sf-item-actions">
                    <span className={`sf-badge${p.status === "approved" ? " is-active" : ""}`}>
                      {p.status}
                    </span>
                    {p.status !== "approved" && (
                      <button className="sf-btn" onClick={() => approvePackage(p.id)}>
                        Approve
                      </button>
                    )}
                  </div>
                </div>
                <details className="sf-details">
                  <summary>View copy &amp; visual</summary>
                  {S(en.caption) && (
                    <>
                      <h4 className="sf-h4">Caption (EN)</h4>
                      <p className="sf-prose">{S(en.caption)}</p>
                    </>
                  )}
                  {A(en.hooks).length > 0 && (
                    <>
                      <h4 className="sf-h4">Hooks</h4>
                      <ul className="sf-list">
                        {A(en.hooks).map((h, i) => (
                          <li key={i}>{S(h)}</li>
                        ))}
                      </ul>
                    </>
                  )}
                  {S(en.cta) && (
                    <p className="sf-prose">
                      <strong>CTA:</strong> {S(en.cta)}
                    </p>
                  )}
                  {allTags.length > 0 && (
                    <div className="sf-chips">
                      {allTags.map((t, i) => (
                        <span className="sf-chip" key={i}>
                          {t.startsWith("#") ? t : `#${t}`}
                        </span>
                      ))}
                    </div>
                  )}
                  {S(tr.caption) && (
                    <>
                      <h4 className="sf-h4">Caption (TR)</h4>
                      <p className="sf-prose">{S(tr.caption)}</p>
                    </>
                  )}
                  {(S(vd.concept) || S(vd.image_prompt)) && (
                    <>
                      <h4 className="sf-h4">Visual direction</h4>
                      {S(vd.concept) && <p className="sf-prose">{S(vd.concept)}</p>}
                      {S(vd.image_prompt) && (
                        <p className="sf-prose sf-mono-sm">{S(vd.image_prompt)}</p>
                      )}
                    </>
                  )}
                </details>
              </article>
            );
          })
        )}
      </section>
    </div>
  );
}
