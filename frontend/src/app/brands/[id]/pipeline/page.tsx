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
  VisualResponse,
} from "@/lib/types";
import {
  Button,
  Card,
  CardHead,
  CardBody,
  Badge,
  SolutionChip,
  Input,
  PageHeader,
  EmptyState,
  Tabs,
  Stepper,
} from "@/components/ui";

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
const SOL_VAR: Record<string, string> = {
  merchandising: "var(--sol-merch)",
  field_audit: "var(--sol-audit)",
  field_sales: "var(--sol-sales)",
  home_service: "var(--sol-home)",
  ai: "var(--sol-ai)",
  general: "var(--sol-general)",
};

const STAGE_SEQ = ["research", "calendar", "copy", "visual"] as const;
type StageView = (typeof STAGE_SEQ)[number];
const STAGE_TITLE: Record<StageView, string> = {
  research: "Research",
  calendar: "Calendar",
  copy: "Copy",
  visual: "Visual",
};
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

  const tabList = ["overview", ...solutions];
  const [tab, setTab] = useState<string>("overview");
  const active = tabList.includes(tab) ? tab : "overview";

  const forSol = (arr: Record<string, unknown>[], key: string) =>
    arr.filter((x) => solKey(x.solution) === key);
  const count = (key: string) => forSol(topics, key).length + forSol(gaps, key).length;

  const tabItems = tabList.map((t) => ({
    key: t,
    label: t === "overview" ? "Overview" : solLabel(t),
    count: t === "overview" ? undefined : count(t),
  }));

  const favOf = (s: string) => (s.replace(/^https?:\/\/(www\.)?/, "")[0] || "•");

  return (
    <div>
      <Tabs items={tabItems} active={active} onChange={setTab} />

      {active === "overview" ? (
        <div>
          {execSummary ? (
            <div className="ui-exec">
              <div className="k">Executive summary</div>
              <p>{execSummary}</p>
            </div>
          ) : null}
          <div className="ui-caldist">
            {solutions.map((sol) => (
              <SolutionChip key={sol} solution={sol} label={`${solLabel(sol)} · ${count(sol)}`} />
            ))}
          </div>
          {pillars.length > 0 && (
            <>
              <div className="ui-h4">Recommended pillars</div>
              <ul className="ui-list2">
                {pillars.map((o, i) => (
                  <li key={i}>
                    <span>
                      <strong>{S(o.name)}</strong>
                      {o.percentage ? ` (${S(o.percentage)}%)` : ""} — {S(o.description)}
                    </span>
                  </li>
                ))}
              </ul>
            </>
          )}
          {(rss.length > 0 || trends.length > 0) && (
            <>
              <div className="ui-h4">Feeds &amp; trends</div>
              {rss.length > 0 && (
                <div className="ui-srcs">
                  {rss.map((o, i) => (
                    <a
                      className="ui-src"
                      key={`r${i}`}
                      href={S(o.link)}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      <span className="fav">{favOf(S(o.source) || S(o.link))}</span>
                      <span className="t">{S(o.title) || S(o.link)}</span>
                      <span className="u">{S(o.source) || "rss"}</span>
                    </a>
                  ))}
                </div>
              )}
              {trends.length > 0 && (
                <p className="ui-note" style={{ marginTop: 10 }}>
                  Trends: {trends.map((o) => S(o.title)).filter(Boolean).join(", ")}
                </p>
              )}
            </>
          )}
        </div>
      ) : (
        <div>
          {(() => {
            const t = forSol(topics, active);
            const g = forSol(gaps, active);
            const so = forSol(search, active);
            const brief = briefFor(active);
            if (!t.length && !g.length && !so.length && !brief)
              return <p className="ui-note">Nothing tagged for {solLabel(active)} in this report.</p>;
            return (
              <>
                {brief ? (
                  <div className="ui-brief">
                    {S(brief.whats_happening) ? (
                      <div className="box">
                        <h5>What&rsquo;s happening</h5>
                        <p>{S(brief.whats_happening)}</p>
                      </div>
                    ) : null}
                    {S(brief.why_it_matters) ? (
                      <div className="box">
                        <h5>Why it matters</h5>
                        <p>{S(brief.why_it_matters)}</p>
                      </div>
                    ) : null}
                    {A(brief.content_ideas).length > 0 ? (
                      <div className="box wide">
                        <h5>What to create</h5>
                        <ul className="ui-list2">
                          {A(brief.content_ideas).map((c, i) => (
                            <li key={`ci${i}`}>
                              <span>{S(c)}</span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                  </div>
                ) : null}
                {t.length > 0 && (
                  <>
                    <div className="ui-h4">Trending topics</div>
                    <ul className="ui-list2">
                      {t.map((o, i) => (
                        <li key={i}>
                          <span>
                            <strong>{S(o.topic)}</strong>
                            {o.signal_strength ? (
                              <span
                                className={`ui-sig ${S(o.signal_strength).toLowerCase()}`}
                                style={{ marginLeft: 8 }}
                              >
                                {S(o.signal_strength)}
                              </span>
                            ) : null}
                            {" — "}
                            {S(o.why_it_matters)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </>
                )}
                {g.length > 0 && (
                  <>
                    <div className="ui-h4">Content gaps</div>
                    <ul className="ui-list2">
                      {g.map((o, i) => (
                        <li key={i}>
                          <span>
                            <strong>{S(o.gap)}</strong> → {S(o.opportunity)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </>
                )}
                {so.length > 0 && (
                  <>
                    <div className="ui-h4">Sources</div>
                    <div className="ui-srcs">
                      {so.map((o, i) => (
                        <a
                          className="ui-src"
                          key={`s${i}`}
                          href={S(o.url)}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          <span className="fav">{favOf(S(o.url))}</span>
                          <span className="t">{S(o.title) || S(o.url)}</span>
                        </a>
                      ))}
                    </div>
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
      <article className="ui-post" data-sol={sol} key={r.i}>
        <div className="meta">
          <span className="day">{fmtCalDate(S(o.date)) || "—"}</span>
          <SolutionChip solution={sol} />
          <span className="plat">
            {S(o.platform)} · {S(o.content_type)}
          </span>
        </div>
        {headline ? <h4>{headline}</h4> : null}
        {hook && hook !== headline ? <div className="hook">{hook}</div> : null}
        <dl>
          {S(o.pillar) ? (
            <>
              <dt>Pillar</dt>
              <dd>{S(o.pillar)}</dd>
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
    <div>
      {weeks.map((items, wi) => (
        <section className="ui-calweek" key={wi}>
          <h4 className="wk">
            Week {wi + 1} · {fmtCalDate(S(items[0].o.date))} – {fmtCalDate(S(items[items.length - 1].o.date))}
          </h4>
          <div className="ui-calgrid">{items.map((r) => card(r))}</div>
        </section>
      ))}
      {unscheduled.length > 0 && (
        <section className="ui-calweek">
          <h4 className="wk">Unscheduled</h4>
          <div className="ui-calgrid">{unscheduled.map((r) => card(r))}</div>
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
  const [view, setView] = useState<StageView>("research");
  const [viewLang, setViewLang] = useState<"en" | "tr">("en");
  const [visuals, setVisuals] = useState<Record<string, VisualResponse>>({});
  const [visualBusy, setVisualBusy] = useState<Record<string, boolean>>({});
  const [visualMsg, setVisualMsg] = useState<Record<string, string>>({});
  const approvedPackages = packages.filter((p) => p.status === "approved");
  const approvedPkgIds = approvedPackages.map((p) => p.id).join(",");

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

  // Preload any visuals already generated for approved packages.
  useEffect(() => {
    const ids = approvedPkgIds ? approvedPkgIds.split(",") : [];
    if (!ids.length) return;
    let cancelled = false;
    (async () => {
      for (const id of ids) {
        try {
          const v = await api.getVisual(id);
          if (!cancelled && v && v.image) setVisuals((prev) => ({ ...prev, [id]: v }));
        } catch {
          /* no visual yet — ignore */
        }
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [approvedPkgIds]);

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

  async function generateVisual(pkgId: string) {
    setVisualBusy((b) => ({ ...b, [pkgId]: true }));
    setVisualMsg((m) => ({ ...m, [pkgId]: "Generating the branded visual…" }));
    try {
      await api.generateVisual(pkgId);
      for (let i = 0; i < 60; i++) {
        await sleep(3000);
        const st = await api.visualStatus(pkgId).catch(() => null);
        if (st) setVisualMsg((m) => ({ ...m, [pkgId]: st.message || st.status }));
        if (st?.status === "done") {
          const v = await api.getVisual(pkgId);
          setVisuals((prev) => ({ ...prev, [pkgId]: v }));
          setVisualMsg((m) => ({ ...m, [pkgId]: "Visual ready — review below." }));
          break;
        }
        if (st?.status === "error") {
          setVisualMsg((m) => ({ ...m, [pkgId]: st.message }));
          break;
        }
      }
    } catch (e) {
      setVisualMsg((m) => ({ ...m, [pkgId]: msg(e) }));
    } finally {
      setVisualBusy((b) => ({ ...b, [pkgId]: false }));
    }
  }
  async function approveVisual(pkgId: string) {
    try {
      await api.approveVisual(pkgId);
      const v = await api.getVisual(pkgId).catch(() => null);
      if (v) setVisuals((prev) => ({ ...prev, [pkgId]: v }));
      setVisualMsg((m) => ({ ...m, [pkgId]: "Visual approved." }));
    } catch (e) {
      setVisualMsg((m) => ({ ...m, [pkgId]: msg(e) }));
    }
  }
  async function rejectVisual(pkgId: string) {
    try {
      await api.rejectVisual(pkgId);
      const v = await api.getVisual(pkgId).catch(() => null);
      if (v) setVisuals((prev) => ({ ...prev, [pkgId]: v }));
      setVisualMsg((m) => ({ ...m, [pkgId]: "Visual rejected — you can regenerate." }));
    } catch (e) {
      setVisualMsg((m) => ({ ...m, [pkgId]: msg(e) }));
    }
  }


  return (
    <div>
      <Link
        href={`/brands/${brandId}`}
        className="ui-btn ui-btn-subtle ui-btn-sm"
        style={{ marginBottom: 16 }}
      >
        ← {brand ? brand.display_name : "Brand"}
      </Link>

      <PageHeader
        eyebrow="Content pipeline"
        title="Research → Calendar → Copy"
        subtitle="Every stage drafts; you approve before the next one can run."
      />

      <Stepper
        current={view}
        onSelect={(k) => setView(k as StageView)}
        items={[
          {
            key: "research",
            label: "Research",
            sub: hasApprovedReport
              ? "Report approved"
              : reports.length
              ? "Draft ready to review"
              : "Not started yet",
            state: hasApprovedReport ? "done" : "active",
          },
          {
            key: "calendar",
            label: "Calendar",
            sub: hasApprovedCalendar
              ? "Plan approved"
              : hasApprovedReport
              ? "Ready to run"
              : "Locked",
            state: hasApprovedCalendar ? "done" : hasApprovedReport ? "active" : "todo",
          },
          {
            key: "copy",
            label: "Copy",
            sub: packages.length
              ? `${packages.length} package(s)`
              : hasApprovedCalendar
              ? "Ready to run"
              : "Locked",
            state: hasApprovedCalendar ? "active" : "todo",
          },
          { key: "visual", label: "Visual", sub: "Coming in Phase D", state: "todo" },
        ]}
      />

      <div className="ui-note" style={{ marginBottom: 18 }}>
        Move between stages with the steps above or Next / Back. Each stage drafts a version you review
        and approve; the next stage builds on the approved one. Set each stage&rsquo;s AI provider on the
        brand page; runs happen in the background.
      </div>

      {error && <div className="ui-error">{error}</div>}

      {/* ── Stage 1: Research ─────────────────────────────── */}
      {view === "research" && (
      <Card id="stage-research" style={{ marginBottom: 20 }}>
        <CardHead
          title={
            <>
              <span className="ui-stage-num">1</span>Research — trend report
            </>
          }
          right={
            <>
              <span className="ui-inline-field">
                <span className="ui-label">Period</span>
                <Input
                  className="ui-input-sm"
                  value={period}
                  onChange={(e) => setPeriod(e.target.value)}
                  placeholder="2026-09"
                />
              </span>
              <Button variant="primary" size="sm" onClick={runResearch} disabled={running.research}>
                {running.research ? "Running…" : "Run research"}
              </Button>
              <Button variant="ghost" size="sm" onClick={refreshReports} disabled={running.research}>
                Refresh
              </Button>
            </>
          }
        />
        <CardBody>
          <p className="ui-note" style={{ marginTop: -4, marginBottom: 12 }}>
            Free RSS + Google Trends. Requires a Research AI provider (set it on the brand page).
          </p>

          <StageLog lines={logs.research} live={running.research} onClear={() => clearLog("research")} />

          {reports.length === 0 ? (
            <EmptyState title="No reports yet">Run research to draft your first trend report.</EmptyState>
          ) : (
            reports.map((r) => (
              <div className="ui-item" key={r.id}>
                <div className="ui-item-head">
                  <div>
                    <div className="ui-item-title">Trend report · {r.planning_period}</div>
                    <div className="ui-item-meta">
                      {A(r.trending_topics).length} topics · {A(r.recommended_pillars).length} pillars
                    </div>
                  </div>
                  <div className="ui-item-actions">
                    <Badge tone={r.is_approved ? "ok" : r.is_rejected ? "warn" : "neutral"}>
                      {r.is_approved ? "Approved" : r.is_rejected ? "Rejected" : "Draft"}
                    </Badge>
                    {!r.is_approved && (
                      <Button size="sm" onClick={() => approveReport(r.id)} disabled={reportBusy === r.id}>
                        Approve
                      </Button>
                    )}
                    {!r.is_rejected && (
                      <Button
                        size="sm"
                        variant="subtle"
                        onClick={() => rejectReport(r.id)}
                        disabled={reportBusy === r.id}
                      >
                        Reject
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="subtle"
                      onClick={() => {
                        setEditReportId(editReportId === r.id ? null : r.id);
                        setEditInstruction("");
                      }}
                      disabled={reportBusy === r.id}
                    >
                      Edit with AI
                    </Button>
                    <Button
                      size="sm"
                      variant="danger"
                      onClick={() => deleteReport(r.id)}
                      disabled={reportBusy === r.id}
                    >
                      Delete
                    </Button>
                  </div>
                </div>
                {editReportId === r.id && (
                  <div className="ui-airow">
                    <textarea
                      className="ui-textarea"
                      value={editInstruction}
                      onChange={(e) => setEditInstruction(e.target.value)}
                      placeholder="Tell the AI what to change, e.g. 'Focus the content gaps on in-store AI compliance and drop the generic ones.'"
                    />
                    <div className="ui-form-actions">
                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => submitAiEdit(r.id)}
                        disabled={reportBusy === r.id || !editInstruction.trim()}
                      >
                        {reportBusy === r.id ? "Applying…" : "Apply AI edit"}
                      </Button>
                      <Button
                        size="sm"
                        variant="subtle"
                        onClick={() => {
                          setEditReportId(null);
                          setEditInstruction("");
                        }}
                      >
                        Cancel
                      </Button>
                    </div>
                  </div>
                )}
                <details className="ui-details">
                  <summary>View report</summary>
                  <ReportView report={r} />
                </details>
              </div>
            ))
          )}
        </CardBody>
      </Card>
      )}

      {/* ── Stage 2: Calendar ─────────────────────────────── */}
      {view === "calendar" && (
      <Card id="stage-calendar" style={{ marginBottom: 20 }}>
        <CardHead
          title={
            <>
              <span className="ui-stage-num">2</span>Calendar — monthly plan
            </>
          }
          right={
            <>
              <Button
                variant="primary"
                size="sm"
                onClick={runCalendar}
                disabled={running.calendar || !hasApprovedReport}
              >
                {running.calendar ? "Running…" : "Run calendar"}
              </Button>
              <Button variant="ghost" size="sm" onClick={refreshCalendars} disabled={running.calendar}>
                Refresh
              </Button>
            </>
          }
        />
        <CardBody>
          <p className="ui-note" style={{ marginTop: -4, marginBottom: 12 }}>
            {hasApprovedReport
              ? "Builds from your latest approved trend report."
              : "Approve a trend report above first."}
          </p>

          <StageLog lines={logs.calendar} live={running.calendar} onClear={() => clearLog("calendar")} />

          {calendars.length === 0 ? (
            <EmptyState title="No calendars yet">Approve a report, then run the calendar.</EmptyState>
          ) : (
            calendars.map((c) => (
              <div className="ui-item" key={c.id}>
                <div className="ui-item-head">
                  <div>
                    <div className="ui-item-title">Calendar · {c.planning_period}</div>
                    <div className="ui-item-meta">
                      {c.post_count} posts · {(c.platforms ?? []).join(", ") || "—"}
                    </div>
                  </div>
                  <div className="ui-item-actions">
                    <Badge tone={c.is_approved ? "ok" : "neutral"}>
                      {c.is_approved ? "Approved" : "Draft"}
                    </Badge>
                    {!c.is_approved && (
                      <Button size="sm" onClick={() => approveCalendar(c.id)}>
                        Approve
                      </Button>
                    )}
                  </div>
                </div>
                {c.summary && (
                  <p className="ui-note" style={{ marginTop: 10 }}>
                    {c.summary}
                  </p>
                )}
                {(() => {
                  const entries = A(c.entries);
                  if (!entries.length) return null;
                  const bySol: Record<string, number> = {};
                  let withAi = 0;
                  for (const e of entries) {
                    const o = O(e);
                    const sol = solKey(o.solution);
                    bySol[sol] = (bySol[sol] || 0) + 1;
                    if (S(o.ai_angle)) withAi += 1;
                  }
                  const dist = Object.entries(bySol).sort((a, b) => b[1] - a[1]);
                  const total = entries.length;
                  return (
                    <div className="ui-caldist">
                      <div className="ui-distbar">
                        {dist.map(([sol, n]) => (
                          <span
                            key={sol}
                            style={{
                              width: `${(n / total) * 100}%`,
                              background: SOL_VAR[sol] || "var(--sol-general)",
                            }}
                          />
                        ))}
                      </div>
                      {dist.map(([sol, n]) => (
                        <SolutionChip key={sol} solution={sol} label={`${solLabel(sol)} · ${n}`} />
                      ))}
                      <span className="ui-aiangle">AI angle · {withAi}</span>
                    </div>
                  );
                })()}
                <details className="ui-details">
                  <summary>View {A(c.entries).length} entries</summary>
                  <CalendarView calendar={c} />
                </details>
              </div>
            ))
          )}
        </CardBody>
      </Card>
      )}

      {/* ── Stage 3: Copy ─────────────────────────────────── */}
      {view === "copy" && (
      <Card id="stage-copy" style={{ marginBottom: 20 }}>
        <CardHead
          title={
            <>
              <span className="ui-stage-num">3</span>Copy — content packages
            </>
          }
          right={
            <>
              <span className="ui-inline-field">
                <span className="ui-label">Limit</span>
                <Input
                  className="ui-input-sm"
                  style={{ width: 84 }}
                  value={copyLimit}
                  onChange={(e) => setCopyLimit(e.target.value)}
                  placeholder="all"
                  type="number"
                  min={1}
                />
              </span>
              <label className="ui-check">
                <input
                  type="checkbox"
                  checked={generateTr}
                  onChange={(e) => setGenerateTr(e.target.checked)}
                />
                TR
              </label>
              <Button
                variant="primary"
                size="sm"
                onClick={runCopy}
                disabled={running.copy || !hasApprovedCalendar}
              >
                {running.copy ? "Running…" : "Run copy"}
              </Button>
              <Button variant="ghost" size="sm" onClick={refreshPackages} disabled={running.copy}>
                Refresh
              </Button>
            </>
          }
        />
        <CardBody>
          <div
            style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 12, flexWrap: "wrap" }}
          >
            <p className="ui-note" style={{ margin: 0, flex: 1, minWidth: 200 }}>
              {hasApprovedCalendar
                ? "One AI draft per calendar entry — a full month can take a few minutes. Leave Limit empty for all posts."
                : "Approve a calendar above first."}
            </p>
            {packages.length > 0 && (
              <div className="ui-langsw" role="group" aria-label="Copy language">
                <button
                  className={viewLang === "en" ? "active" : ""}
                  aria-pressed={viewLang === "en"}
                  onClick={() => setViewLang("en")}
                >
                  EN
                </button>
                <button
                  className={viewLang === "tr" ? "active" : ""}
                  aria-pressed={viewLang === "tr"}
                  onClick={() => setViewLang("tr")}
                >
                  TR
                </button>
              </div>
            )}
          </div>

          <StageLog lines={logs.copy} live={running.copy} onClear={() => clearLog("copy")} />

          {packages.length === 0 ? (
            <EmptyState title="No content packages yet">Approve a calendar, then run copy.</EmptyState>
          ) : (
            <div className="ui-copygrid">
              {packages.map((p) => {
                const src = viewLang === "tr" ? O(p.copy_package_tr) : O(p.copy_package_en);
                const en = O(p.copy_package_en);
                const vd = O(p.visual_direction);
                const overlay = O(vd.text_overlay);
                const headline = S(overlay.primary);
                const hashtags = O(src.hashtags);
                const allTags = [
                  ...A(hashtags.broad),
                  ...A(hashtags.niche),
                  ...A(hashtags.branded),
                ].map(S);
                const caption = S(src.caption) || S(en.caption);
                return (
                  <div className="ui-copycard" key={p.id}>
                    <div className="ch">
                      <span className="ui-item-meta" style={{ fontWeight: 600 }}>
                        {p.platform} · {p.content_type}
                      </span>
                      <span className="pid">{p.post_id}</span>
                    </div>
                    <div className="cb">
                      {headline ? <div className="hl">{headline}</div> : null}
                      {caption ? <div className="cap">{caption}</div> : null}
                      {allTags.length > 0 && (
                        <div className="tagrow">
                          {allTags.map((t, i) => (
                            <span className="tag" key={i}>
                              {t.startsWith("#") ? t : `#${t}`}
                            </span>
                          ))}
                        </div>
                      )}
                      {S(vd.image_prompt) ? (
                        <div className="ui-promptbox">
                          <b>Visual prompt · </b>
                          {S(vd.image_prompt)}
                        </div>
                      ) : null}
                    </div>
                    <div className="cf">
                      <Badge tone={p.status === "approved" ? "ok" : "neutral"}>{p.status}</Badge>
                      {p.status !== "approved" && (
                        <Button
                          size="sm"
                          onClick={() => approvePackage(p.id)}
                          style={{ marginLeft: "auto" }}
                        >
                          Approve
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardBody>
      </Card>
      )}

      {/* ── Stage 4: Visual ───────────────────────────────── */}
      {view === "visual" && (
      <Card id="stage-visual" style={{ marginBottom: 20 }}>
        <CardHead
          title={
            <>
              <span className="ui-stage-num">4</span>Visual — branded image
            </>
          }
          right={<span className="ui-item-meta">Approval 3 · OpenAI + brand overlay</span>}
        />
        <CardBody>
          <p className="ui-note" style={{ marginTop: -4, marginBottom: 12 }}>
            Generate a branded visual for each approved post, then approve the copy + visual together
            (Approval 3). Set the image provider + key on the Settings page first. The pill, logo and exact
            headline are composited by us (Phase D2) — until then the model returns a clean scene.
          </p>
          {approvedPackages.length === 0 ? (
            <EmptyState title="No approved posts yet">
              Approve a content package above to generate its visual.
            </EmptyState>
          ) : (
            <div className="ui-copygrid">
              {approvedPackages.map((p) => {
                const v = visuals[p.id];
                const vd = O(p.visual_direction);
                const overlay = O(vd.text_overlay);
                const headline = S(overlay.primary);
                const busy = !!visualBusy[p.id];
                const status = v?.visual_status ?? undefined;
                return (
                  <div className="ui-vcard" key={p.id}>
                    <div className="ui-canvas2">
                      {v?.image ? (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={v.image} alt={headline || p.post_id} />
                      ) : (
                        <div className="ui-canvas-empty">{busy ? "Generating…" : "No visual yet"}</div>
                      )}
                      {status ? <span className="ui-canvas-badge">{status}</span> : null}
                    </div>
                    <div className="cb">
                      <div className="ui-item-meta" style={{ fontWeight: 600 }}>
                        {p.post_id}
                      </div>
                      {headline ? (
                        <div className="hl" style={{ fontSize: 15 }}>
                          {headline}
                        </div>
                      ) : null}
                      {visualMsg[p.id] ? (
                        <div className="ui-note" style={{ fontSize: 12 }}>
                          {visualMsg[p.id]}
                        </div>
                      ) : null}
                    </div>
                    <div className="cf">
                      <Button
                        size="sm"
                        variant="primary"
                        onClick={() => generateVisual(p.id)}
                        disabled={busy}
                      >
                        {busy ? "Generating…" : v?.image ? "Regenerate" : "Generate"}
                      </Button>
                      {v?.image && status !== "approved" && (
                        <Button size="sm" onClick={() => approveVisual(p.id)} disabled={busy}>
                          Approve
                        </Button>
                      )}
                      {v?.image && (
                        <Button
                          size="sm"
                          variant="subtle"
                          onClick={() => rejectVisual(p.id)}
                          disabled={busy}
                          style={{ marginLeft: "auto" }}
                        >
                          Reject
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardBody>
      </Card>
      )}

      <div className="ui-stepnav">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            const i = STAGE_SEQ.indexOf(view);
            if (i > 0) setView(STAGE_SEQ[i - 1]);
          }}
          disabled={view === "research"}
        >
          ← Back
        </Button>
        <span className="ui-stepnav-label">{STAGE_TITLE[view]} stage</span>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            const i = STAGE_SEQ.indexOf(view);
            if (i < STAGE_SEQ.length - 1) setView(STAGE_SEQ[i + 1]);
          }}
          disabled={view === "visual"}
        >
          Next →
        </Button>
      </div>

    </div>
  );
}
