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

export default function PipelinePage() {
  const params = useParams();
  const brandId = String(params.id);

  const [brand, setBrand] = useState<Brand | null>(null);
  const [reports, setReports] = useState<TrendReport[]>([]);
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
    () => api.listReports(brandId).then(setReports).catch(() => {}),
    [brandId]
  );
  const refreshCalendars = useCallback(
    () => api.listCalendars(brandId).then(setCalendars).catch(() => {}),
    [brandId]
  );
  const refreshPackages = useCallback(
    () => api.listPackages(brandId).then(setPackages).catch(() => {}),
    [brandId]
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
        addLog(`Calendar: waiting for the draft (check ${i + 1})…`);
        const latest = await api.listCalendars(brandId);
        setCalendars(latest);
        if (latest.length > before) {
          const entries = A(O(latest[0]).entries).length;
          addLog(`Calendar: draft received — ${entries} planned posts. Review and approve.`, "ok");
          break;
        }
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
    try {
      await api.approveReport(id);
      addLog("Trend report approved — you can now run the calendar.", "ok");
      await refreshReports();
    } catch (e) {
      addLog(`Approve report: error — ${msg(e)}`, "err");
      setError(msg(e));
    }
  }
  async function approveCalendar(id: string) {
    try {
      await api.approveCalendar(id);
      addLog("Calendar approved — you can now run copy.", "ok");
      await refreshCalendars();
    } catch (e) {
      addLog(`Approve calendar: error — ${msg(e)}`, "err");
      setError(msg(e));
    }
  }
  async function approvePackage(id: string) {
    try {
      await api.approvePackage(id);
      addLog("Content package approved.", "ok");
      await refreshPackages();
    } catch (e) {
      addLog(`Approve package: error — ${msg(e)}`, "err");
      setError(msg(e));
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
                  <span className={`sf-badge${r.is_approved ? " is-active" : ""}`}>
                    {r.is_approved ? "Approved" : "Draft"}
                  </span>
                  {!r.is_approved && (
                    <button className="sf-btn" onClick={() => approveReport(r.id)}>
                      Approve
                    </button>
                  )}
                </div>
              </div>
              <details className="sf-details">
                <summary>View report</summary>
                {A(r.trending_topics).length > 0 && (
                  <>
                    <h4 className="sf-h4">Trending topics</h4>
                    <ul className="sf-list">
                      {A(r.trending_topics).map((t, i) => {
                        const o = O(t);
                        return (
                          <li key={i}>
                            <strong>{S(o.topic)}</strong>
                            {o.signal_strength ? ` [${S(o.signal_strength)}]` : ""} — {S(o.why_it_matters)}
                          </li>
                        );
                      })}
                    </ul>
                  </>
                )}
                {A(r.content_gaps).length > 0 && (
                  <>
                    <h4 className="sf-h4">Content gaps</h4>
                    <ul className="sf-list">
                      {A(r.content_gaps).map((g, i) => {
                        const o = O(g);
                        return (
                          <li key={i}>
                            <strong>{S(o.gap)}</strong> → {S(o.opportunity)}
                          </li>
                        );
                      })}
                    </ul>
                  </>
                )}
                {A(r.recommended_pillars).length > 0 && (
                  <>
                    <h4 className="sf-h4">Recommended pillars</h4>
                    <ul className="sf-list">
                      {A(r.recommended_pillars).map((p, i) => {
                        const o = O(p);
                        return (
                          <li key={i}>
                            <strong>{S(o.name)}</strong>
                            {o.percentage ? ` (${S(o.percentage)}%)` : ""} — {S(o.description)}
                          </li>
                        );
                      })}
                    </ul>
                  </>
                )}
              {(() => {
                  const src = O(r.sources);
                  const search = A(src.search);
                  const rss = A(src.rss);
                  const trends = A(src.trends);
                  if (!search.length && !rss.length && !trends.length) return null;
                  return (
                    <>
                      <h4 className="sf-h4">Sources used (real, auditable)</h4>
                      {search.length > 0 && (
                        <ul className="sf-list sf-sources">
                          {search.map((x, i) => {
                            const o = O(x);
                            return (
                              <li key={`s${i}`}>
                                <a href={S(o.url)} target="_blank" rel="noopener noreferrer">
                                  {S(o.title) || S(o.url)}
                                </a>
                                <span className="sf-src-tag">search</span>
                              </li>
                            );
                          })}
                        </ul>
                      )}
                      {rss.length > 0 && (
                        <ul className="sf-list sf-sources">
                          {rss.map((x, i) => {
                            const o = O(x);
                            return (
                              <li key={`r${i}`}>
                                <a href={S(o.link)} target="_blank" rel="noopener noreferrer">
                                  {S(o.title) || S(o.link)}
                                </a>
                                <span className="sf-src-tag">{S(o.source) || "rss"}</span>
                              </li>
                            );
                          })}
                        </ul>
                      )}
                      {trends.length > 0 && (
                        <p className="sf-hint">
                          Trends: {trends.map((x) => S(O(x).title)).filter(Boolean).join(", ")}
                        </p>
                      )}
                    </>
                  );
                })()}
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
              <details className="sf-details">
                <summary>View {A(c.entries).length} entries</summary>
                <div className="sf-table-scroll">
                  <table className="sf-table">
                    <thead>
                      <tr>
                        <th>Date</th>
                        <th>Platform</th>
                        <th>Type</th>
                        <th>Pillar</th>
                        <th>Hook</th>
                      </tr>
                    </thead>
                    <tbody>
                      {A(c.entries).map((e, i) => {
                        const o = O(e);
                        return (
                          <tr key={i}>
                            <td>{S(o.date)}</td>
                            <td>{S(o.platform)}</td>
                            <td>{S(o.content_type)}</td>
                            <td>{S(o.pillar)}</td>
                            <td>{S(o.hook_concept)}</td>
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
