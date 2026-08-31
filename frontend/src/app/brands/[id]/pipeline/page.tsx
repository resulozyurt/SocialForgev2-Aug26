"use client";

import { useCallback, useEffect, useState } from "react";
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
type Stage = "research" | "calendar" | "copy";

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
  const notes = O(report.algorithm_notes);
  const execSummary = S(notes.executive_summary);
  const briefs = A(notes.solution_briefs).map((b) => O(b));
  const briefFor = (key: string) => briefs.find((b) => solKey(b.solution) === key);

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
          {execSummary ? (
            <div className="sf-report-exec">
              <span className="sf-report-exec-label">Executive summary</span>
              <p>{execSummary}</p>
            </div>
          ) : null}
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
            const brief = briefFor(active);
            if (!t.length && !g.length && !so.length && !brief)
              return <p className="sf-note">Nothing tagged for {solLabel(active)} in this report.</p>;
            return (
              <>
                {brief ? (
                  <div className="sf-brief">
                    {S(brief.whats_happening) ? (
                      <>
                        <h4 className="sf-h4">What&rsquo;s happening</h4>
                        <p>{S(brief.whats_happening)}</p>
                      </>
                    ) : null}
                    {S(brief.why_it_matters) ? (
                      <>
                        <h4 className="sf-h4">Why it matters</h4>
                        <p>{S(brief.why_it_matters)}</p>
                      </>
                    ) : null}
                    {A(brief.content_ideas).length > 0 ? (
                      <>
                        <h4 className="sf-h4">What to create</h4>
                        <ul className="sf-list">
                          {A(brief.content_ideas).map((c, i) => (
                            <li key={`ci${i}`}>{S(c)}</li>
                          ))}
                        </ul>
                      </>
                    ) : null}
                  </div>
                ) : null}
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

// ── H4: rich card board calendar (week-grouped, all info visible, no clicking) ──
const CAL_MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const fmtCalDate = (iso: string): string => {
  const m = iso.match(/^(\d{4})-(\d{2})-(\d{2})/);
  return m ? `${CAL_MONTHS[Number(m[2]) - 1]} ${Number(m[3])}` : iso;
};

function CalendarView({ calendar }: { calendar: ContentCalendar }) {
  const entries = A(calendar.entries).map((e) => O(e));
  const rows = entries.map((o, i) => {
    const iso = S(o.date);
    const d = /^\d{4}-\d{2}-\d{2}/.test(iso) ? new Date(`${iso}T00:00:00Z`) : null;
    return { o, i, t: d && !Number.isNaN(d.getTime()) ? d.getTime() : null };
  });
  const scheduled = rows
    .filter((r) => r.t != null)
    .sort((a, b) => (a.t as number) - (b.t as number));
  const unscheduled = rows.filter((r) => r.t == null);

  const byWeek = new Map<string, typeof rows>();
  for (const r of scheduled) {
    const dow = (new Date(r.t as number).getUTCDay() + 6) % 7;
    const monKey = new Date((r.t as number) - dow * 86400000).toISOString().slice(0, 10);
    if (!byWeek.has(monKey)) byWeek.set(monKey, []);
    byWeek.get(monKey)!.push(r);
  }
  const weeks = [...byWeek.keys()].sort().map((k) => byWeek.get(k)!);

  const card = (r: { o: Record<string, unknown>; i: number }) => {
    const o = r.o;
    const sol = solKey(o.solution);
    const headline = S(o.headline) || S(o.hook_concept);
    const hook = S(o.hook_concept);
    return (
      <article className="sf-cal2-card" key={r.i}>
        <div className="sf-cal2-top">
          <span className="sf-cal2-date">{fmtCalDate(S(o.date)) || "—"}</span>
          <span className="sf-cal-soltag" data-sol={sol}>{solLabel(sol)}</span>
          <span className="sf-src-tag">
            {S(o.platform)} · {S(o.content_type)}
          </span>
        </div>
        {headline ? <p className="sf-cal2-headline">{headline}</p> : null}
        <dl className="sf-cal2-meta">
          {S(o.pillar) ? (
            <>
              <dt>Pillar</dt>
              <dd>{S(o.pillar)}</dd>
            </>
          ) : null}
          {hook && hook !== headline ? (
            <>
              <dt>Hook</dt>
              <dd>{hook}</dd>
            </>
          ) : null}
          {S(o.ai_angle) ? (
            <>
              <dt>AI angle</dt>
              <dd>{S(o.ai_angle)}</dd>
            </>
          ) : null}
        </dl>
      </article>
    );
  };

  return (
    <div className="sf-cal2">
      {weeks.map((items, wi) => (
        <section className="sf-cal2-week" key={wi}>
          <h4 className="sf-cal2-wk">
            Week {wi + 1} · {fmtCalDate(S(items[0].o.date))} – {fmtCalDate(S(items[items.length - 1].o.date))}
          </h4>
          <div className="sf-cal2-cards">{items.map((r) => card(r))}</div>
        </section>
      ))}
      {unscheduled.length > 0 && (
        <section className="sf-cal2-week">
          <h4 className="sf-cal2-wk">Unscheduled</h4>
          <div className="sf-cal2-cards">{unscheduled.map((r) => card(r))}</div>
        </section>
      )}
    </div>
  );
}

function StageLog({
  lines,
  live,
  onClear,
}: {
  lines: LogLine[];
  live: boolean;
  onClear: () => void;
}) {
  if (lines.length === 0 && !live) return null;
  return (
    <div className="sf-stagelog">
      <div className="sf-log-head">
        <span className="sf-log-title">
          Activity {live && <span className="sf-live-dot" />}
        </span>
        {lines.length > 0 && (
          <button className="sf-linkbtn" onClick={onClear}>
            Clear
          </button>
        )}
      </div>
      <div className="sf-log">
        {lines.length === 0 ? (
          <p className="sf-log-empty">Working…</p>
        ) : (
          lines.map((l, i) => (
            <div className={`sf-log-line is-${l.kind}`} key={i}>
              <span className="sf-log-time">{l.time}</span> {l.text}
            </div>
          ))
        )}
      </div>
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

  const [logs, setLogs] = useState<Record<Stage, LogLine[]>>({
    research: [],
    calendar: [],
    copy: [],
  });

  const addLog = useCallback(
    (stage: Stage, text: string, kind: LogLine["kind"] = "info") => {
      const time = new Date().toLocaleTimeString();
      setLogs((prev) => ({
        ...prev,
        [stage]: [...prev[stage], { time, text, kind }].slice(-120),
      }));
    },
    []
  );
  const clearLog = useCallback(
    (stage: Stage) => setLogs((prev) => ({ ...prev, [stage]: [] })),
    []
  );
  // Merge the backend's real step log into a stage box (idempotent by index).
  const mergeSteps = useCallback(
    (stage: Stage, steps: { text: string }[] | undefined, seen: number): number => {
      if (!steps) return seen;
      for (let i = seen; i < steps.length; i++) addLog(stage, String(steps[i].text), "info");
      return steps.length;
    },
    [addLog]
  );

  const refreshReports = useCallback(
    () =>
      api
        .listReports(brandId)
        .then(setReports)
        .catch((e) => addLog("research", `Could not refresh reports: ${msg(e)}`, "err")),
    [brandId, addLog]
  );
  const refreshCalendars = useCallback(
    () =>
      api
        .listCalendars(brandId)
        .then(setCalendars)
        .catch((e) => addLog("calendar", `Could not refresh calendars: ${msg(e)}`, "err")),
    [brandId, addLog]
  );
  const refreshPackages = useCallback(
    () =>
      api
        .listPackages(brandId)
        .then(setPackages)
        .catch((e) => addLog("copy", `Could not refresh packages: ${msg(e)}`, "err")),
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
    clearLog("research");
    setRunning((r) => ({ ...r, research: true }));
    addLog("research", `Requesting a trend report for ${period}…`);
    try {
      await api.runResearch(brandId, { planning_period: period, max_posts: 20 });
      let seen = 0;
      for (let i = 0; i < 80; i++) {
        await sleep(3000);
        const st = await api.researchStatus(brandId).catch(() => null);
        if (st) seen = mergeSteps("research", st.log, seen);
        if (st?.status === "done") {
          await refreshReports();
          addLog("research", "Draft ready — review and approve below.", "ok");
          break;
        }
        if (st?.status === "error") {
          addLog("research", `Run failed — ${st.message}`, "err");
          setError(st.message);
          break;
        }
        if (i === 79) addLog("research", "Still working — use Refresh in a moment.", "info");
      }
    } catch (e) {
      addLog("research", `Error — ${msg(e)}`, "err");
      setError(msg(e));
    } finally {
      setRunning((r) => ({ ...r, research: false }));
    }
  }

  async function runCalendar() {
    setError(null);
    clearLog("calendar");
    setRunning((r) => ({ ...r, calendar: true }));
    addLog("calendar", "Building a monthly plan from the approved report…");
    try {
      await api.runCalendar(brandId, {});
      let seen = 0;
      for (let i = 0; i < 80; i++) {
        await sleep(3000);
        const st = await api.calendarStatus(brandId).catch(() => null);
        if (st) seen = mergeSteps("calendar", st.log, seen);
        if (st?.status === "done") {
          await refreshCalendars();
          addLog("calendar", "Draft ready — review and approve below.", "ok");
          break;
        }
        if (st?.status === "error") {
          addLog("calendar", `Run failed — ${st.message}`, "err");
          setError(st.message);
          break;
        }
        if (i === 79) addLog("calendar", "Still working — use Refresh in a moment.", "info");
      }
    } catch (e) {
      addLog("calendar", `Error — ${msg(e)}`, "err");
      setError(msg(e));
    } finally {
      setRunning((r) => ({ ...r, calendar: false }));
    }
  }

  async function runCopy() {
    setError(null);
    clearLog("copy");
    setRunning((r) => ({ ...r, copy: true }));
    const limit = copyLimit.trim() ? Number(copyLimit) : undefined;
    addLog(
      "copy",
      `Drafting ${limit ? limit + " post(s)" : "all posts"}${
        generateTr ? " (EN + TR)" : " (EN)"
      } — one AI call each…`
    );
    try {
      await api.runCopy(brandId, { limit, generate_tr: generateTr });
      let seen = 0;
      for (let i = 0; i < 120; i++) {
        await sleep(3000);
        const st = await api.copyStatus(brandId).catch(() => null);
        if (st) seen = mergeSteps("copy", st.log, seen);
        if (st?.status === "done") {
          await refreshPackages();
          addLog("copy", "Packages ready — review and approve below.", "ok");
          break;
        }
        if (st?.status === "error") {
          addLog("copy", `Run failed — ${st.message}`, "err");
          setError(st.message);
          break;
        }
        if (i === 119) addLog("copy", "Still working — use Refresh in a moment.", "info");
      }
    } catch (e) {
      addLog("copy", `Error — ${msg(e)}`, "err");
      setError(msg(e));
    } finally {
      setRunning((r) => ({ ...r, copy: false }));
    }
  }

  async function approveReport(id: string) {
    setReportBusy(id);
    try {
      await api.approveReport(id);
      addLog("research", "Trend report approved — you can now run the calendar.", "ok");
      await refreshReports();
    } catch (e) {
      if (isMissingError(e)) {
        addLog("research", "That report no longer exists — the list has been refreshed.", "info");
        await refreshReports();
      } else {
        addLog("research", `Approve report: error — ${msg(e)}`, "err");
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
      addLog("research", "Trend report rejected.", "info");
      await refreshReports();
    } catch (e) {
      if (isMissingError(e)) {
        addLog("research", "That report no longer exists — the list has been refreshed.", "info");
        await refreshReports();
      } else {
        addLog("research", `Reject report: error — ${msg(e)}`, "err");
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
      addLog("research", "Trend report deleted.", "info");
      await refreshReports();
    } catch (e) {
      if (isMissingError(e)) {
        addLog("research", "That report was already removed — the list has been refreshed.", "info");
        await refreshReports();
      } else {
        addLog("research", `Delete report: error — ${msg(e)}`, "err");
        setError(msg(e));
      }
    } finally {
      setReportBusy(null);
    }
  }
  async function submitAiEdit(id: string) {
    if (!editInstruction.trim()) return;
    setReportBusy(id);
    addLog("research", "Report: AI is applying your edit…");
    try {
      await api.aiEditReport(id, editInstruction.trim());
      addLog("research", "Report: AI edit applied — review the updated draft.", "ok");
      setEditReportId(null);
      setEditInstruction("");
      await refreshReports();
    } catch (e) {
      if (isMissingError(e)) {
        addLog("research", "That report no longer exists — the list has been refreshed.", "info");
        setEditReportId(null);
        await refreshReports();
      } else {
        addLog("research", `AI edit: error — ${msg(e)}`, "err");
        setError(msg(e));
      }
    } finally {
      setReportBusy(null);
    }
  }
  async function approveCalendar(id: string) {
    try {
      await api.approveCalendar(id);
      addLog("calendar", "Calendar approved — you can now run copy.", "ok");
      await refreshCalendars();
    } catch (e) {
      if (isMissingError(e)) {
        addLog("calendar", "That calendar no longer exists — the list has been refreshed.", "info");
        await refreshCalendars();
      } else {
        addLog("calendar", `Approve calendar: error — ${msg(e)}`, "err");
        setError(msg(e));
      }
    }
  }
  async function approvePackage(id: string) {
    try {
      await api.approvePackage(id);
      addLog("copy", "Content package approved.", "ok");
      await refreshPackages();
    } catch (e) {
      if (isMissingError(e)) {
        addLog("copy", "That content package no longer exists — the list has been refreshed.", "info");
        await refreshPackages();
      } else {
        addLog("copy", `Approve package: error — ${msg(e)}`, "err");
        setError(msg(e));
      }
    }
  }


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

        <StageLog lines={logs.research} live={running.research} onClear={() => clearLog("research")} />

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

        <StageLog lines={logs.calendar} live={running.calendar} onClear={() => clearLog("calendar")} />

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
                <CalendarView calendar={c} />
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

        <StageLog lines={logs.copy} live={running.copy} onClear={() => clearLog("copy")} />

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
