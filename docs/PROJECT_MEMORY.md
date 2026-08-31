# SocialForge AI — Project Memory

> Persistent context for the project. Update at the end of every phase. If you
> open a fresh chat, read this file first to resume without losing the thread.

Last updated: 2026-08-31 — **RV5** (solutions/competitors nested tabs). Owner review #1–#8 ALL DONE.

---

## 0. Working Agreement & Collaboration Rules (READ FIRST)

**Language.** Converse with the owner (Resul) in **Turkish**. ALL development output
— code, comments, README, this PROJECT_MEMORY.md, commit messages, and UI strings —
is **native American English**. Content exception: **Evatro** generated content is
Turkish; **FieldPie** generated content is English.

**Cadence & approval.** Every step advances **only with the owner's approval**; do
not jump to the next phase/step unattended. Break big work into **small,
independently deployable sub-steps** (e.g. D2a/D2b, RV2a/RV2b). Explain steps simply
and always end with a separate **"Senin yapman gerekenler"** heading listing the
owner's actions step by step.

**End of every step.** Edit the files, update this PROJECT_MEMORY.md, and hand the
owner **ONE copyable commit** (native American English message). The **owner does all
commit/push** — Claude must **NOT run git** (no git via device_bash); Claude only
edits files.

**Editing.** Work in place via `device_bash` (repo mounted under `$HOME/mnt/socialforge-ai`).
Use anchored Python read-modify-write for edits; write new files via heredoc. Prefer
targeted commands (a broad `find` is slow on the device).

**Verification (Claude runs these).** Backend: `python -m py_compile <files>`.
Frontend: `./node_modules/.bin/tsc --noEmit` from `frontend/` (the direct binary, NOT
npx; it can take ~45s on the device). Anything needing live keys/DB (AI calls, image
generation, migrations against the live DB, seeds) is run by the **owner** — say so
explicitly.

**Locked decisions.**
1. API keys come from the **in-app Settings page** (`app_settings`, Fernet-encrypted),
   never from code or env.
2. Image provider was OpenAI `gpt-image-1`, **but the whole visual-generation step is
   being redesigned by the owner** — do **NOT** build the old D2 (Pillow overlay) or D3
   (Drive); wait for the owner's new architecture spec.
3. Auth: admin panel HTTP Basic; frontend `/api` proxy is same-origin; Railway backend
   `replicas=1` (in-memory job/status state depends on this).
4. **Human-in-the-loop is non-negotiable**: the system drafts; a human approves at the
   checkpoints (research / calendar / copy / visual). No fully autonomous publishing.

**Infra.** Live on Railway: `SocialForge-Backend` (root `backend`), `SocialForge-Front`
(root `frontend`), managed `Postgres`. Alembic **migration head = 0009**; deploy runs
`alembic upgrade head` automatically. Repo is private.

---

## 1. Mission

Automate 70–80% of the social content chain for two brands — **FieldPie** (US /
global, English) and **Evatro** (Turkey, Turkish) — down to a human-reviewable
draft. Chain: research/trends → monthly calendar → headline + copy → branded
visual. **Human-in-the-loop is non-negotiable**: the system drafts, a human
approves at three checkpoints. No fully autonomous publishing.

Solution areas: merchandising, field audit, field sales, home service, AI, general.

---

## 2. Architecture Snapshot

```
Sources (RSS / Google Trends / optional Apify)
  -> Phase 1 Research (AIProvider) -> TrendReportCard
     ★ APPROVAL 1 (human)
  -> Phase 2 Calendar (AIProvider) -> ContentCalendar
     ★ APPROVAL 2 (human)
  -> Phase 3 Copy (AIProvider, EN+TR) -> ContentPackage (draft) + visual_direction
  -> Phase 4 Visual (image gen + brand profile) -> asset -> Google Drive   [NOT BUILT]
     ★ APPROVAL 3 (human, copy + visual)
  -> publish-ready draft (manual/assisted publish)

Brand Profile store feeds every phase. AI config is per brand x per phase.
Storage: PostgreSQL (records) + Google Drive (assets, planned).
Hosting: Railway (backend + managed Postgres); frontend on Railway/Vercel.
Access: admin panel behind HTTP Basic auth.
Secrets: .env (bootstrap) + Fernet-encrypted provider keys in DB.
```

---

## 3. Tech Stack

- **Backend:** FastAPI, async SQLAlchemy 2.0 + asyncpg (PostgreSQL), Pydantic v2,
  Alembic (migrations), cryptography/Fernet, tenacity, httpx, structlog.
  Declared but not yet used: redis, apscheduler (reserved for Phase 5 scheduling).
- **AI:** single `core/ai_provider.py` abstraction over Anthropic / OpenAI /
  Google / Groq. No other module calls an AI SDK directly.
- **Frontend:** Next.js 16 (App Router), React 19, Tailwind 4, TypeScript.
- **Deploy:** Railway (Nixpacks). `backend/railway.json` runs
  `alembic upgrade head` then uvicorn on `$PORT`.

---

## 4. Secrets / Env (names only — values live in .env, never committed)

Backend: `APP_ENV`, `APP_SECRET_KEY`, `DEBUG`, `FERNET_KEY`, `DATABASE_URL`
(scheme auto-normalized to asyncpg), `REDIS_URL`, `ADMIN_USERNAME`,
`ADMIN_PASSWORD`, `CORS_ORIGINS`, `BOOTSTRAP_ANTHROPIC_KEY`,
`BOOTSTRAP_OPENAI_KEY`, `BOOTSTRAP_APIFY_KEY`.
Frontend (server-side only): `BACKEND_URL`, `ADMIN_USERNAME`, `ADMIN_PASSWORD`.

`.env` has never been committed (verified 2026-08-26). Repo should be **private**.

---

## 5. Brand Profiles (modeled in Phase B)

- **FieldPie** — English (native US). All six solutions. Teal/petrol accent +
  dark slate headers + white ground; accent words in teal pill. Clean modern
  SaaS look; logo top-left; half-circle "pie" motif bottom-left. Voice: clear,
  reassuring, problem->solution, short punchy headlines.
- **Evatro** — Turkish (natural, local). Focus: merchandising, audit, AI. Red
  accent + dark navy/black block + white ground; accent words in red pill. Navy
  corner block top-left; "EVATRO" logo bottom-left; magnifier, device mockups,
  shelf photos, red accent lines. Voice: sharp, assertive, "not enough -> this
  is what's needed".

The two identities must never mix.

**Schema (Phase B).** `Brand` now carries `language` (enum `brandlanguageenum`:
EN/TR), plus two JSONB specs: `visual_identity` (`ground_color`, `block_color`,
`pill{bg_color,text_color,shape}`, `logo{url,position}`, `motifs[]`,
`style_keywords[]`, `reference_images[]`) and `voice_profile` (`tone_keywords[]`,
`narrative_structure`, `example_headlines[]`, `avoid[]`). Solution focus lives in
the `brand_solutions` link table (`solution`, `is_focus`, `priority`,
`concept_notes`), taxonomy = `SolutionEnum` {merchandising, field_audit,
field_sales, home_service, ai, general}. FieldPie seeds all six; Evatro focuses
merchandising / field_audit / ai. Content pillars stay a separate concept.

---

## 6. Phase Status

| Phase | Scope | Status |
|-------|-------|--------|
| 1 Research | Competitor/trend intel -> TrendReportCard | DONE (Apify; RSS/Trends pending) |
| 2 Calendar | Approved report -> monthly calendar | DONE |
| 3 Copy | Approved calendar -> ContentPackage (EN+TR) + visual brief | DONE |
| Approval gates | report / calendar / package | DONE (API + UI) |
| A Foundation | deps fix, Alembic, auth, Railway prep, DB URL norm | DONE |
| **B Brand+Solution** | rich brand profiles, solution taxonomy, seed FieldPie/Evatro | **DONE (this commit)** |
| C Review UI + free research | 3 approval screens, RSS/Trends, Google Drive | DONE (C1+C2+C3; Drive->D) |
| D Visual | Phase 4 branded image generation | IN PROGRESS (D1 backend + D4 UI done via U3b; D2 overlay / D3 Drive next) |
| U UI Rebuild | Studio design system + app shell + per-page rebuild | **DONE (U1–U5)** |
| E Schedule/Publish/Metrics | Phase 5/6 (assisted, not autonomous) | LATER |
| R Research Depth | pluggable search, source traceability, taxonomy/cadence, competitors, social | IN PROGRESS (R1 + R2a done) |

---

## 7. Decisions Log (ADR-style)

- **2026-08-26 — Research source:** RSS + Google Trends is the primary, free
  path (built in Phase C). Apify (paid IG/LinkedIn scraping) stays optional,
  behind a flag. Rationale: honor "no extra paid services" and the brief's
  legitimate-sources requirement.
- **2026-08-26 — Image provider:** Dropped Replicate (removed
  `BOOTSTRAP_REPLICATE_KEY`). Phase 4 will use OpenAI/Gemini image generation
  and/or Canva Pro — decided at Phase D. Rationale: avoid an extra paid service.
- **2026-08-26 — Auth:** HTTP Basic (single admin credential) on all `/api/v1`
  routes; `/health` stays public. Frontend proxies through a Next.js route
  handler so the password stays server-side. Upgrade to per-user auth later.
- **2026-08-26 — Migrations:** Adopt Alembic. Baseline revision `0001` builds
  the schema from ORM metadata (no hand-transcription drift); later revisions use
  autogenerate. `scripts/create_tables.py` kept only as a local quick-start.
- **2026-08-26 (Phase B) — Solution taxonomy:** `SolutionEnum` (6 fixed areas) +
  a `brand_solutions` link table (per-brand `is_focus`, `priority`,
  `concept_notes`). Chosen over a JSONB list for query-ability and integrity;
  matches the enum-heavy model style.
- **2026-08-26 (Phase B) — Profile storage:** hybrid. Queryable identity stays in
  columns (`language`, colors); the fast-evolving design/voice spec lives in JSONB
  (`visual_identity`, `voice_profile`) to avoid migration churn.
- **2026-08-26 (Phase B) — Migration idempotency:** `0002` is hand-written and
  inspector-guarded (adds only what is missing). Required because the `0001`
  baseline uses `create_all` off live metadata, so a fresh DB already has the new
  objects; the guards make fresh-DB and existing-DB paths converge. Enum labels use
  member NAMES (EN, MERCHANDISING, ...) to match what SQLAlchemy `create_all` emits
  (verified against the ORM).
- **2026-08-26 (Phase B) — Profile wiring:** the Phase 3 copy prompt now receives
  the brand's primary-language directive, real hex palette (so the model stops
  inventing brand colors in `visual_direction.color_palette`), and visual language.
  Deeper visual-motif use stays for Phase D.
- **2026-08-26 (Phase C) — Split & scope:** Phase C ships as C1 (brand detail
  page + per-phase AI provider config UI), C2 (free RSS + Google Trends research
  path, Apify optional/flagged), C3 (the three approval screens). Google Drive
  deferred to Phase D (nothing to store until visual generation exists). Each
  sub-phase = its own reviewed commit.
- **2026-08-26 (Phase C1) — Shipped:** frontend `/brands/[id]` detail page
  (identity, voice, solutions, competitors) + an AI provider config panel driven
  by the existing `/settings/providers` endpoints, including a live 'Test key'
  button. `src/lib/types.ts` and `src/lib/api.ts` extended accordingly. Verified
  with `tsc --noEmit` (clean); the Next build on Railway is the final gate.
- **2026-08-26 (Phase C2) — Free research path:** Phase 1 now gathers RSS feeds +
  Google Trends daily trending searches (region derived from brand language) via
  `feedparser` (new dep) — deliberately no pytrends/pandas. Apify competitor
  scraping became opt-in per brand (`research_sources.use_apify`); the research
  endpoint no longer requires an Apify key. New `brands.research_sources` JSONB
  (migration `0003`, inspector-guarded); Phase 1 falls back to language-based
  default feeds when it is unset. `ANALYSIS_PROMPT` generalized to Trends + RSS +
  optional competitor inputs; the output JSON schema is unchanged so calendar and
  copy are unaffected.
- **2026-08-26 (Phase C3) — Approval screens shipped:** `/brands/[id]/pipeline`
  drives the full human-in-the-loop flow — Research -> Calendar -> Copy — each
  stage with a Run button, background-run auto-refresh (polls the list until the
  draft lands), an expandable review, and an Approve gate that unlocks the next
  stage. A 'Content pipeline' link was added to the brand detail page. Phase C is
  complete.
- **2026-08-26 (C-polish) — Admin UX pass:** brand detail is now tabbed (Identity
  / Voice / Solutions / AI Providers) so nothing is buried in a long scroll. The AI
  provider model is chosen from a dropdown populated by a new `POST /settings/models`
  endpoint that lists the models a given provider + key can use (live via the
  provider SDK, curated `FALLBACK_MODELS` on failure) — no manual model typing.
  Added inline help ('info') callouts across the UI, and a live activity log on the
  pipeline page so a run's progress is visible step by step. All admin UI is native
  American English; only Evatro's generated content is Turkish.
- **2026-08-27 (Phase R1) — Research depth, part 1:** research is now grounded in
  real, targeted web search + auditable sources. A **pluggable search layer**
  (`integrations/web_search.py`: serper / brave / google_cse / tavily) replaces the
  single-vendor assumption — the provider + key are chosen on a new in-app
  **Settings page** (`/settings`), stored Fernet-encrypted in a new `app_settings`
  table (migration `0005`); no keys in code or server env. Brave turned out to be
  paid, so **serper (Google SERP, free credits)** is the default; google_cse
  (100/day free) is the free-truly option. Per-brand areas of interest are set on a
  new brand **Sources** tab (search keywords + RSS feeds + trends region, stored in
  `research_sources`). Every report now stores the actual gathered inputs in
  `trend_report_cards.sources` (migration `0004`) and the pipeline shows them as
  **real, clickable source links** — so a report is verifiably real, not
  AI-guessed. Apify (competitor social) key also moved to the Settings page. R2
  (taxonomy/cadence), R3 (competitor discovery), R4 (Apify social monitoring) are
  next.
- **2026-08-27 (Phase R2a) — Solution-aware calendar:** Phase 2 now plans against
  the brand's **solution taxonomy** (`brand_solutions`), not just content pillars.
  A deterministic quota is computed in Python (`_allocate_solutions`) so posts are
  **balanced across the brand's focus solutions** — the LLM is handed exact
  per-solution counts that sum to `monthly_post_target`, rather than being trusted
  to balance them. **AI is treated as a cross-cutting theme, not a silo:** it gets
  no quota bucket; instead ~45% of posts carry a concrete `ai_angle` (e.g. "AI
  within merchandising"). Each calendar entry gains `solution` + `ai_angle`;
  `solution` is normalized against `SolutionEnum` (unknown -> `general`). No
  migration — `ContentCalendar.entries` is JSONB. Brands with no modeled solutions
  fall back to the old pillar-only behavior. `general` reserves ~15% when the brand
  covers it. FieldPie's seed `monthly_post_target` raised 20 -> 30 (daily cadence);
  Evatro stays 12. Verified example quotas: FieldPie 30 -> merch 7 / audit 7 /
  sales 6 / home_service 6 / general 4 (ai_angle 14); Evatro 12 -> merch 5 / audit
  5 / general 2 (ai_angle 5). Next: R2b surfaces solution chips + AI angle +
   distribution in the calendar review UI.
- **2026-08-27 (E0) — Calendar run fix:** the calendar run was returning nothing
  because the Phase-2 output overflowed the 4096-token default and truncated the
  JSON (30 posts + new `solution`/`ai_angle` fields), so parsing failed inside a
  background task that swallowed the error. Fix: (a) scale `max_tokens` to the plan
  size — `min(max(config, post_count*200+1200), 8000)`; (b) a tolerant parser that
  strips code fences and **salvages complete entries from truncated JSON**
  (`_salvage_entries`, brace-balanced scan); (c) background-run errors are now
  captured in an in-memory per-brand registry and exposed at
  `GET /calendar/{brand_id}/status`, and the pipeline UI surfaces the real message
  instead of a silent empty list. No migration.
- **2026-08-27 (E1) — Identity & Voice editable:** the brand detail `Identity` and
  `Voice` tabs are now full edit forms saving through the existing
  `PATCH /brands/{id}` (no backend change, no migration). Identity edits
  display_name, industry, language, **monthly_post_target** (the field that was
  read-only), the three brand colors, logo, and the `visual_identity` JSON
  (ground/block/pill colors, style keywords, motifs). Voice edits
  `voice_guide_text` and the `voice_profile` JSON (tone keywords, narrative,
  example headlines, avoid). Forms rebuild from the saved brand after each save;
  list fields are one-per-line textareas. Verified `tsc --noEmit` clean.
- **2026-08-27 (E2) — Solutions management + importance-weighted split:** each
  `brand_solutions` row gains an `importance` intensity (1-5, default 3) via
  **migration 0006** (inspector-guarded; `server_default "3"` so existing rows and
  the create_all baseline converge). Phase 2's `_allocate_solutions` now splits the
  month **by importance weight** (largest-remainder; ties by priority) instead of
  evenly — equal importance reproduces the old balanced split, so it is backward
  compatible. AI stays cross-cutting (no bucket; ~45% ai_angle). New
  `DELETE /brands/{id}/solutions/{solution}` hard-removes one focus; `PUT` upsert now
  carries importance. The brand **Solutions tab is fully editable**: include/exclude
  each of the six areas, toggle focus, set importance + priority + concept notes, with
  a **live monthly-split preview** (bars, per-solution counts, AI-angle target) that
  mirrors the backend allocator. Verified: FieldPie 30 with merch=5/audit=4/sales=2/
  home=1 -> 11/9/4/2 + general 4; equal importance -> 7/7/6/6 + 4. `tsc` + `py_compile`
  clean. Importance is not seeded (defaults to 3 = balanced) and tuned in the UI;
  re-seed preserves it (upsert does not touch importance).
- **2026-08-27 (E3) — Competitors CRUD + solution grouping:** `Competitor` gains a
  nullable `solution` (reuses the existing `solutionenum`, `create_type=False`) and a
  `notes` field via **migration 0007** (guarded). Competitor endpoints went from
  GET+POST to full CRUD: added `PATCH` and `DELETE
  /brands/{id}/competitors/{competitor_id}`; Create/Response/Update schemas carry
  solution + notes. The Solutions tab's competitor area is now **fully editable**: an
  add form (name, solution, IG/LI/X handles, aspirational, notes) plus a list
  **grouped by solution** (a "General / untagged" bucket for null), each row with
  inline Edit (name/handles/notes/solution/aspirational) and Delete. `tsc` +
  `py_compile` clean.
- **2026-08-27 (E4a) — Report controls (reject/delete/AI-edit):** reports were
  approve-only. Added `is_rejected` + `rejected_at` to `trend_report_cards`
  (**migration 0008**, guarded) and three endpoints: `PATCH /research/reports/{id}/reject`
  (keeps the record, marks dismissed), `DELETE /research/reports/{id}` (hard delete),
  and `POST /research/reports/{id}/ai-edit` {instruction} — sends the current report
  JSON + a human instruction to the brand's **Research** AIProviderConfig and rewrites
  the report in place as a fresh unapproved draft (whole report or a section, driven by
  the instruction text; sources are left untouched as the audit trail). Approve now also
  clears rejection and stamps `approved_at`. Pipeline report cards gained Reject / Delete /
  **Edit with AI** (inline instruction box) plus a Rejected badge. `tsc` + `py_compile`
  clean.
- **2026-08-27 (E4b) — Per-solution research:** Phase 1 now runs a **separate search
  per focus solution** using that solution's own keywords (from a new
  `research_sources.solution_keywords` map, `{solution: [kw]}`), plus a general bucket
  from the brand-wide `search_keywords`. Results are deduped by URL across solutions and
  each carries a `solution` tag. `ANALYSIS_PROMPT` gained the brand's focus-solution list
  and now asks the model to spread trending_topics + content_gaps across solutions and tag
  each with its `solution` (or "general"); sources are tagged per solution. No migration
  (all in the `research_sources` JSONB). Backward compatible: with no per-solution keywords
  set, it falls back to brand-wide keywords (old behavior). Frontend: the brand **Sources**
  tab gained a per-focus-solution keyword textarea each, and the pipeline report view shows
  the solution tag on every topic, gap, and source. `tsc` + `py_compile` clean. **E4 (a+b)
  complete.**
- **2026-08-27 (E5 / R2b) — Calendar review UI:** the pipeline calendar view now
  surfaces the solution model built in R2a/E2. Each calendar entry table gained a
  **Solution** chip column and an **AI angle** column, and each calendar shows a
  **distribution summary** (per-solution post counts + how many carry an AI angle) above
  the entries. Frontend-only; no backend/migration. `tsc` clean. **The Editability &
  Solution-First roadmap (E0–E5) is complete.** Next: resume the original chain — Phase D
  (branded visual generation + Google Drive), then Copy polish.

- **2026-08-28 (F1) — Pipeline stale-state fix (root cause of the "404 — Report
  not found" storm):** the backend was sound the whole time (verified live: a
  freshly listed report id returns 200 on approve). The real defect was in the
  pipeline UI: the three list refreshers swallowed every error
  (`.catch(() => {})`), so after a row was deleted the page kept showing stale
  cards; clicking one hit a by-id route for a row that no longer existed → 404
  (and, on delete, an occasional bare 500). Fix (`/brands/[id]/pipeline`): the
  refreshers now surface failures to the activity log instead of hiding them;
  every by-id action (approve / reject / delete / ai-edit for reports, approve
  for calendars + packages) detects a 404 via a shared `isMissingError` helper
  and responds by auto-refreshing the list and logging "no longer exists —
  refreshed" instead of a scary error; `approveReport` now sets `reportBusy` like
  its siblings so its button disables while in flight. Frontend-only, no
  migration. Verified `tsc --noEmit` clean.
- **2026-08-28 (F2) — Delete report hardening:** `DELETE /research/reports/{id}`
  is now idempotent and no longer emits a bare 500. Deleting an already-removed
  report returns success (204) so a stale UI never sees a 404; a genuine delete
  failure is wrapped and surfaced as a clear `409 Could not delete report: …`
  instead of an empty 500. Backend-only, no migration. `py_compile` clean. The
  diagnosis was confirmed live before any code changed (single Postgres, single
  replica, stable list — the multi-instance hypothesis was ruled out).
- **2026-08-28 (F2b) — The actual DELETE-500 root cause (Next.js proxy):** after
  F1/F2, DELETE still returned 500 to the browser even though the row was removed
  (visible after a manual refresh). The backend was fine — it returns `204`. The
  bug was in the frontend proxy (`app/api/[...path]/route.ts`): it wrapped every
  upstream response as `new NextResponse(text, {status})`, but `204/205/304` are
  "null body" statuses and the Fetch spec forbids a body on them, so building that
  response threw a `TypeError` that surfaced as a spurious 500. Only DELETE hit it
  (the sole 204 endpoint). Fix: the proxy now returns `new NextResponse(null,
  {status})` for 204/205/304 and only attaches a body/content-type otherwise.
  Frontend-only, no migration. `tsc --noEmit` clean. Lesson: any 204 route would
  have broken; the fix is at the proxy, not per-endpoint.
- **2026-08-28 (F3) — Solution-first tabbed report view:** the trend report review
  was one long flat wall of lists — topics, gaps, pillars and dozens of source links
  with tiny inline solution tags — so it was impossible to see which content and which
  link belonged to which solution. Replaced it with a `ReportView` component
  (`/brands/[id]/pipeline`) that is tabbed by solution: an **Overview** tab (per-solution
  topic+gap counts, the recommended pillars, and the cross-cutting RSS feeds + trends),
  then **one tab per focus solution actually present** (Merchandising / Field Audit / AI /
  …) showing that solution's trending topics, content gaps and search sources grouped
  together. Data drives the tabs (each topic/gap/source already carries a `solution` tag
  from E4b); solutions are ordered by the canonical `SOLUTION_ORDER`, unknown tags fall to
  `general`, and signal strength renders as a small high/medium/low pill (`.sf-sig`).
  Reuses existing `.sf-tabs`/`.sf-caldist`/`.sf-sources` styles; frontend-only, no
  migration. `tsc --noEmit` clean.
- **2026-08-28 (G1) — Per-solution research sources always populated:** the report's
  solution tabs were empty of sources because Phase 1 only ran a per-solution search
  when the brand had entered explicit `research_sources.solution_keywords` for that
  solution; otherwise everything fell into the untagged "general" bucket (so all links
  showed under General). Fix (`phases/phase1_research.py`): each focus solution now runs
  its OWN tagged search using explicit keywords when set, else a baseline
  `_SOLUTION_KEYWORDS` map (merchandising / field_audit / field_sales / home_service /
  ai; unknown solutions derive `"<label> <industry>"`). The general bucket now runs only
  when the brand set explicit brand-wide `search_keywords`, or when the brand has no focus
  solutions at all. Result: every focus solution's report tab shows real, solution-specific
  source links. Topics/gaps were already solution-tagged by the LLM. RSS feeds stay
  brand-wide (shown under the Overview tab). Backend-only, no migration; `py_compile` clean.
  To see it: re-run research for the brand after deploy.
- **2026-08-28 (G2) — Real month-grid calendar + field glossary:** the calendar review
  was a wide horizontal table where the on-image-relevant fields were hard to read.
  Replaced it with a `CalendarView` component (`/brands/[id]/pipeline`): a real Mon–Sun
  month grid (month derived from `planning_period`), each day cell showing its posts as
  compact chips colored by solution and labeled by platform (IG/LI/X/…). Clicking a chip
  opens a detail panel with every field — pillar, **hook concept**, AI angle, objective,
  and the rationale. Posts whose date falls outside the month show under an "Other dates"
  row so nothing is hidden. Clarified the field meanings for the human reviewer: **pillar**
  = editorial theme (not on-image); **hook concept** = the scroll-stopping idea, which
  becomes the actual on-image headline only later in the Copy stage
  (`visual_direction.text_overlay.primary` + `hooks[0]`); **ai_angle** = how AI is woven
  into the post (guidance, not necessarily on-image). Renamed the "Hook" label to "Hook
  concept" and added dt tooltips. Solution chip colors added to `globals.css` via
  `data-sol` attribute selectors. Frontend-only, no migration; `tsc --noEmit` clean.
  Note for Phase D: the branded visual's headline text should be sourced from the Copy
  stage `text_overlay.primary`, not the calendar hook concept.
- **2026-08-28 (Phase D provider decision):** image provider = **OpenAI (gpt-image-1)**,
  with the brand pill / logo / exact headline **composited by us** (Pillow, Phase D2)
  rather than rendered by the model, because image models render text unreliably and both
  brands need pixel-exact headlines and identity. Gemini/Imagen is a drop-in alternative
  (same architecture); Canva Pro deferred. Key comes from the Settings page.
- **2026-08-28 (D1) — Branded visual generation, backend:** new pluggable
  `integrations/image_gen.py` (OpenAI gpt-image-1 via httpx, returns PNG bytes, raises
  `ImageGenError` on failure); new `phases/phase4_visual.py` builds a **text-free scene
  prompt** from the package's `visual_direction` (image_prompt/mood/composition) + the
  brand's `visual_identity` (style keywords, motifs, ground tone) and explicitly tells the
  model to leave negative space for the overlay; new `api/routes/visuals.py` exposes
  `POST /visuals/{package_id}/generate` (background, requires the package's copy to be
  APPROVED), `GET /visuals/{package_id}` (+ `/status`), and `PATCH .../approve|reject`
  (Approval 3). Two new Settings keys (`image_provider`, `image_api_key`). The generated
  image is stored as a base64 data URI in the existing `ContentPackage.asset_urls` JSONB
  with `visual_status` (draft/approved/rejected) — **no migration**. `py_compile` clean.
  D2 replaces the raw scene with a brand-composited image (pill + logo + exact headline);
  D3 uploads the final asset to Google Drive and drops the heavy base64; D4 adds the Stage-4
  pipeline UI. To test D1 live: Settings → set image_provider=openai + paste an OpenAI key,
  approve a content package, then POST generate and GET the visual.
- **2026-08-28 (H1) — Research relevance:** research was surfacing off-topic noise
  (unrelated platform/affiliate/viral stories) because two inputs are inherently
  brand-agnostic. Fixes: (a) **Google Trends daily-trending is now opt-in** per brand
  (`research_sources.use_trends`, default off) instead of always mixed in — it is
  region-wide viral noise; targeted per-solution search (G1) is the primary signal now.
  (b) Dropped the **Social Media Today** default RSS feed (platform-news noise); default
  EN feeds are retail-ops only (Retail Dive, Modern Retail). (c) `ANALYSIS_PROMPT` gained
  a hard **RELEVANCE** rule: use only inputs clearly tied to the brand's industry + focus
  solutions, silently discard off-topic items, prefer fewer sharper signals. Backend-only,
  no migration; `py_compile` clean. Part of a research/calendar quality pass (H1–H5 all done).
- **2026-08-28 (H3) — On-image headline field:** calendar entries only had a
  `hook_concept` (the idea), so the reviewer never saw the actual words that will go
  on the visual. Phase 2 now produces a distinct **`headline`** per entry — the exact,
  short, brand-voiced on-image hook (e.g. "Photos Don't Fix Shelves. Actions Do.") —
  added to the prompt rules + example, and `_normalize_entries` guarantees it (falls
  back to `hook_concept` when the model omits it). Phase 4 visuals / Copy should source
  the on-image text from here. Backend-only, no migration (entries are JSONB); `py_compile`
  clean.
- **2026-08-28 (H4) — Calendar rebuilt as a rich card board:** the month-grid + click-to-
  expand (G2) was clunky (everything behind a click). Replaced `CalendarView` with a
  **week-grouped card board**: every post is a full card showing date, solution color chip,
  platform · type, the **headline** (prominent), pillar, hook concept, and AI angle — all
  visible, no clicking. Entries with no valid date fall under an "Unscheduled" group.
  Frontend-only (`sf-cal2-*` styles), no migration; `tsc --noEmit` clean. Supersedes G2's
  grid; old `.sf-cal-*` grid styles are now unused but left in place.
- **2026-08-28 (H2) — Readable, quality trend report:** the report was a terse wall of
  lists that a non-expert could not follow. `ANALYSIS_PROMPT` now adds a WRITING QUALITY
  rule (plain English, no buzzwords, grounded + specific) and enriches `algorithm_notes`
  into a **narrative container**: `executive_summary` (3-5 plain sentences) + `solution_briefs`
  (per focus solution: `whats_happening` / `why_it_matters` / `content_ideas[]`) + `platform`
  notes — stored in the existing `algorithm_notes` JSONB, so **no migration**. The analysis
  `max_tokens` is bumped to `max(config, 8000)` so the richer report never truncates.
  Frontend `ReportView`: the Overview tab shows the executive summary as a highlighted
  callout; each solution tab leads with that solution's brief (what's happening / why it
  matters / what to create) above its topics, gaps and sources. `tsc` + `py_compile` clean.
  Re-run research to populate the new narrative (old reports simply omit it).
- **2026-08-28 (H5) — Per-stage, meaningful activity logs:** the pipeline had one shared
  activity box full of fake "waiting (check 18)" spam. Now each stage (Research / Calendar /
  Copy) has its **own** activity box inside its section, fed by the backend's **real steps**.
  New `core/job_status.py` (in-memory {status,message,log[]} keyed `<stage>:<brand_id>`);
  `phase1_research.run` and `phase3_copy.run` take a `progress` callback and emit real
  milestones (e.g. "Searched merchandising: 8 new source(s)", "Collected N sources; running
  AI analysis…", "Report saved — N topics"; "Writing post 3/12 — merchandising · instagram…");
  research/calendar/copy routes wrap their background task with start/finish/fail and expose
  `GET /{stage}/{brand_id}/status`. The frontend polls the stage's status and streams new
  steps into that stage's box (idempotent by index) instead of faking progress; the old top
  Activity panel was removed. Native American English throughout. Backend + frontend, no
  migration; `py_compile` + `tsc --noEmit` clean.
- **2026-08-28 (FieldPie profile seed) — comprehensive brand fill:** researched FieldPie
  from fieldpie.com + public sources (all-in-one AI field-ops platform; solutions =
  merchandising / retail execution, field audit, field sales, home service, image
  recognition + AI route optimization; audience = CPG brands, retail-execution agencies,
  F&B, multi-location retailers, and home-service trades; 27 countries, 10M+ jobs/yr,
  clients incl. Coca-Cola, Danone, Mercedes-Benz; proof metrics 32% productivity / 64%
  less paper / 12% profitability). New `scripts/seed_fieldpie_profile.py` (stdlib-only,
  idempotent, live-API) fills FieldPie end-to-end: identity (teal #0EA5A4 / slate,
  monthly_post_target 30), enriched voice_guide + voice_profile (problem->solution->proof),
  visual_identity, solution focuses with **importance** (merch 5 / audit 4 / ai 4 / sales 3 /
  home 3; general non-focus), **per-solution research keywords** (research_sources.
  solution_keywords) + brand-wide keywords + retail-ops RSS + use_trends off, and real
  competitors mapped by solution (YOOBIC, Repsly, Wiser, GoSpotCheck/FORM, SimplyDepo,
  SalesRabbit, ServiceTitan, Connecteam; social handles left blank, not fabricated).
  Run: `python scripts/seed_fieldpie_profile.py` from backend/ (asks for admin user/pass;
  BACKEND_URL overridable). Idempotent — PATCH + upsert, adds only missing competitors.

---

- **2026-08-31 (U1) — Studio design system + app shell (UI rebuild, part 1):** the
  old admin UI was the AI-default cream/terracotta + serif look and the manager
  disliked it. After an approved interactive mockup, we picked the **"Studio"**
  direction (clean modern SaaS, airy, per-brand accent: FieldPie teal / Evatro
  red). U1 is **frontend-only, backend/API untouched.** `globals.css` `:root` was
  rewritten to the Studio palette **keeping the old token names** (`--paper`,
  `--surface`, `--ink`, `--muted`, `--line`, `--accent`, `--accent-soft`, `--ok`
  …) so **every existing `.sf-*` page re-skins automatically** — plus new tokens
  (`--text-2`, `--border-strong`, `--accent-2`, `--ring`, semantic warn/bad/info,
  six `--sol-*` solution hues, `--radius-*`, `--shadow-lg`). Fonts switched via
  next/font from Fraunces/Hanken to **Plus Jakarta Sans (display) + Inter (body) +
  JetBrains Mono**, which de-serifs all headings instantly. Dark theme + per-brand
  accent are appended at the end of `globals.css` (they remap the same token
  names, so old pages get dark mode for free), guarded so an explicit
  `data-theme="light"` beats a dark OS. New **`components/AppShell.tsx`** (client)
  replaces the old top-header `layout.tsx`: left **sidebar** (logo, brand-accent
  switcher, Workspace/Configure nav with a contextual Pipeline link + "soon" items,
  admin footer) + **topbar** (breadcrumb, brand chip, light/dark toggle). Theme +
  brand persist in `localStorage` (`sf-theme` / `sf-brand`); a no-flash inline
  script in `layout.tsx` applies them before first paint. All existing pages render
  unchanged inside the new shell. Verified `tsc --noEmit` clean. **Note:** the
  brand switcher only re-themes the accent for now (does not navigate); it will be
  wired to real brand context in U3. Not-yet-rebuilt page internals may show minor
  dark-mode contrast quirks (a few hardcoded companion colors in `.sf-*`) until
  each page's U-step. Next: **U2** (primitives: Button/Card/Tabs/Chip/Stat/Stepper,
  applied to the Brands home page).

- **2026-08-31 (U2) — Studio primitives + Brands page rebuilt:** added a small
  reusable component library under **`src/components/ui/`** (barrel `index.ts`):
  `Button` (primary/ghost/subtle/danger, sm/md), `Card` + `CardHead/CardBody/CardFoot`,
  `Badge` (ok/warn/bad/accent/muted), `SolutionChip` (data-sol colored), `Stat`+`Stats`,
  `Field`+`Input`, `PageHeader`, `EmptyState`. All are thin wrappers over new **`.ui-*`
  CSS** appended to `globals.css` (token-driven, so they follow theme + brand accent).
  Rebuilt the **Brands home page** (`app/page.tsx`) on these primitives: a `PageHeader`,
  a small summary stat strip (brands / active / combined monthly target), the create
  form using `Field`/`Input`, and brand `Card`s with a footer `Badge` + Open link.
  Functionality is unchanged (list / create / loading / error / empty). **Tabs and
  Stepper were intentionally deferred to U3**, where the pipeline is their real
  consumer (no speculative components). Verified `tsc --noEmit` clean. Frontend-only,
  no backend/migration. Next: **U3** — rebuild the pipeline page (`/brands/[id]/pipeline`)
  on the primitives, adding Tabs + Stepper; likely split U3a (research + calendar) /
  U3b (copy + visual).

- **2026-08-31 (U3a) — Pipeline rebuilt: stepper + research/calendar stages:**
  reworked the presentation of `/brands/[id]/pipeline` onto the Studio primitives
  **without touching any logic** (all state, effects, polling, and approval
  handlers are byte-for-byte unchanged — the rebuild was a surgical splice of three
  presentational spans). Added two primitives to `src/components/ui/`: **`Tabs`**
  (controlled) and **`Stepper`** (done/active/todo states, optional click-to-scroll).
  New CSS block "STUDIO PIPELINE (U3)" in `globals.css` (tabs, stepper, executive
  callout, solution-brief boxes, source cards with favicon + signal pill, the
  distribution bar, and the week-grouped card board). The page now opens with a
  `PageHeader` + a **4-stage Stepper** (Research/Calendar/Copy/Visual) that reflects
  the real gate state (approved report → calendar unlocks, etc.) and scroll-jumps to
  each stage. `ReportView` rebuilt with `Tabs` + solution chips + source cards;
  `CalendarView` rebuilt as the `.ui-post` card board (top-border colored by
  solution) with a distribution bar. Stages 1 (Research) and 2 (Calendar) are now
  `Card`s with `CardHead` action rows (Run/Refresh, Period input) and `.ui-item`
  report/calendar rows using `Button`/`Badge`. **Stage 3 (Copy) intentionally left on
  the old `.sf-*` markup** (re-skinned by U1 tokens) — it is rebuilt in **U3b** along
  with the Visual stage. Verified `tsc --noEmit` clean. Frontend-only, no
  backend/migration. Next: **U3b** — rebuild the Copy stage (per-post cards, EN/TR
  toggle, hashtags, visual prompt) + add the Visual (Phase-4) stage placeholder.

- **2026-08-31 (U3b) — Copy stage rebuilt + Visual (Phase 4) stage wired (also
  completes D4's UI):** rebuilt Stage 3 (Copy) of `/brands/[id]/pipeline` on the
  Studio primitives — per-post `.ui-copycard`s showing the on-image headline
  (`visual_direction.text_overlay.primary`), caption, hashtag pills, and the visual
  prompt, with a global **EN/TR** language toggle (`.ui-langsw`) over the whole grid,
  plus per-card status `Badge` + Approve. Added a real **Stage 4 (Visual)** wired to
  the existing D1 backend endpoints — new `api.ts` methods (`generateVisual`,
  `visualStatus`, `getVisual`, `approveVisual`, `rejectVisual`) + `VisualStatus`/
  `VisualResponse` types. The stage lists **approved** packages as `.ui-vcard`s; each
  can Generate (background POST + 3s status poll, up to ~3 min), shows the returned
  image (base64 data URI from D1) in a square canvas with a status badge, streams a
  per-card progress message, and offers **Approve / Regenerate / Reject** (Approval
  3). A load-time effect preloads any already-generated visuals for approved
  packages. **This is effectively D4 (the Phase-4 pipeline UI), delivered inside the
  UI rebuild.** All new pipeline logic is additive; the Research/Calendar/Copy run +
  approval logic from before is untouched. Note: the image is still the **raw D1
  scene** (the pill/logo/exact-headline overlay is D2, not yet built) — the UI says
  so. `StageLog` (the shared activity box) intentionally kept on its U1-reskinned
  `.sf-*` classes. Verified `tsc --noEmit` clean. Frontend-only, no backend/migration.
  **Phase U pipeline rebuild (U3a+U3b) is complete.** Next options: **U4** (rebuild
  brand detail + settings pages), or resume **D2** (Pillow brand overlay) so the
  Visual stage renders true branded images, or the small **copy-run hardening** fix.

- **2026-08-31 (U4a) — Settings rebuilt + brand-detail chrome:** rebuilt the whole
  **Settings page** (`app/settings/page.tsx`) on the Studio primitives — each app
  setting is now a `Card` (label + status `Badge`, description, an `Input`/select row
  with Save/Clear and an inline saved-note). Same logic (`listAppSettings` /
  `updateAppSetting`, secret masking, choices dropdown) unchanged. On the **brand
  detail page** (`app/brands/[id]/page.tsx`) the header + tab bar were swapped to
  `PageHeader` (with brand badges + a Content-pipeline button in the actions slot) +
  the `Tabs` primitive + a back link. **The five tab section contents (identity /
  voice / solutions / providers / sources forms + competitors CRUD) still use the
  U1-reskinned `.sf-*` markup — that is U4b.** Verified `tsc --noEmit` clean.
  Frontend-only, no backend/migration. Next: **U4b** — rebuild the five brand-detail
  sections on primitives (`Field`/`Input`, `Button`, `Badge`, `SolutionChip`), then
  **U5** polish.

- **2026-08-31 — Visual generation on hold (owner directive):** the owner (Resul)
  has a **different architecture idea for the whole visual-generation step** and will
  describe it when the UI rebuild reaches the visual stage. **Do NOT build the old D2
  (Pillow pill/logo/headline overlay) or D3 (Drive) as previously planned** — wait for
  the new design. The current Visual stage (U3b) still works against D1 (raw scene) as
  a placeholder. Ping the owner once the UI rebuild (U4/U5) is done so they can explain
  the new visual approach.

- **2026-08-31 (U4b) — Brand-detail sections unified with the Studio system:** the
  five brand-detail tabs (identity / voice / solutions / providers / sources) + the
  competitors CRUD are heavily form-driven (~1200 lines of stable TSX using
  high-frequency `.sf-*` classes: `sf-input` ×45, `sf-label` ×38, `sf-field` ×38,
  `sf-btn`, `sf-section`, `sf-info`, `sf-textarea`…). Rather than rewrite that TSX,
  U4b appends a **"STUDIO BRIDGE" CSS block** to `globals.css` that redefines those
  `.sf-*` form/section classes to match the Studio primitives exactly (sf-section →
  Card, sf-input/sf-textarea → the ui-input shape + focus ring, sf-btn/sf-btn-accent →
  ghost/primary buttons, sf-label/sf-field/sf-row, sf-badge tones, sf-info/sf-error
  callouts, plus light polish on the provider table / competitor / distribution /
  swatch blocks). Appended last so it wins over the originals. Result: all five tabs
  read as one system with **zero TSX change and near-zero risk**; the pipeline
  `StageLog`'s `.sf-log*` classes are deliberately left untouched. Verified `tsc
  --noEmit` clean (no TSX changed). Frontend-only, no backend/migration. **Phase U4
  (brand + settings) complete.** Next: **U5** polish (empty/loading states, focus,
  responsive, micro-interactions) — then the UI rebuild is done and the owner will
  describe the new visual-generation architecture (see the on-hold note above).

- **2026-08-31 (U5) — Polish pass; Phase U (UI rebuild) COMPLETE:** added a
  `Spinner` + `Loading` primitive and wired it into the three loading states
  (Brands, Settings, brand detail). Added a system-wide "STUDIO POLISH" CSS block:
  keyboard `:focus-visible` rings on all interactive elements, smooth scroll (for the
  stepper jumps), accent `::selection`, custom thin scrollbars, a subtle reveal
  animation on open `<details>`, active-nav icon accent, and a global
  `prefers-reduced-motion` guard. Verified `tsc --noEmit` clean. Frontend-only, no
  backend/migration. **The Studio UI rebuild is done end to end** — app shell +
  primitives + full pipeline (research/calendar/copy/visual) + brands + brand detail
  + settings, all light/dark + per-brand accent. **Next up is the visual-generation
  step, which the owner is redesigning from scratch (see the on-hold note) — wait for
  that spec before writing any Phase D visual code.**

- **2026-08-31 (RV1) — Pipeline view: 3-col calendar + fully tabbed nav (owner
  review #1, #3):** the calendar card board is now a fixed **3 columns** (2 / 1 on
  narrower screens) with roomier cards. The pipeline no longer stacks all stages and
  scroll-jumps between them — it is now **fully tabbed**: only the selected stage
  renders, driven by a `view` state; the Stepper selects the stage (no more
  scroll-into-view), and a **Back / Next** bar at the bottom steps through
  research → calendar → copy → visual. Free navigation (any stage viewable
  regardless of gate). Frontend-only, no backend/migration. `tsc --noEmit` clean.
  Owner review queue (from the U-complete screenshot): #1 done (RV1), #3 done (RV1);
  remaining — #2 delete/reject/ai-edit on calendar+copy (RV2, needs backend),
  #4/#5/#6 sidebar+brand-switch nav (RV3), #7 identity colors+layout (RV4),
  #8 solutions/competitors nested tabs (RV5). Owner chose: remove Calendar/Assets
  sidebar items; full parity (delete+reject+ai-edit) for RV2.

- **2026-08-31 (RV2a) — Delete + Reject on calendar & copy (owner review #2, part
  1):** mirrored the report management flow onto the calendar and copy stages.
  Backend: added `is_rejected` + `rejected_at` to **ContentCalendar** (ORM) —
  ContentPackage already had them — plus **migration `0009_calendar_package_rejected`**
  (guarded/idempotent, adds the two columns to `content_calendars` and, as a no-op
  safety, `content_packages`). New endpoints: `PATCH /calendar/{id}/reject`,
  `DELETE /calendar/{id}` (204, idempotent), `PATCH /copy/{id}/reject` (reverts an
  approved package to DRAFT), `DELETE /copy/{id}` (204, idempotent). Approve now also
  clears rejection; `CalendarResponse`/`ContentPackageResponse` gained `is_rejected`.
  Frontend: `api.ts` rejectCalendar/deleteCalendar/rejectPackage/deletePackage;
  `is_rejected` on the calendar + package types; pipeline calendar items and copy
  cards gained **Reject / Delete** buttons + a Rejected badge, all using the shared
  `isMissingError` refresh-on-404 pattern. `py_compile` + `tsc --noEmit` clean.
  **To apply live: deploy runs `alembic upgrade head` (0009) automatically.** Next:
  **RV2b** — AI-edit on calendar & copy (per-stage ai-edit endpoints + UI), to finish
  full research parity.

- **2026-08-31 (RV2b) — AI-edit on calendar & copy; owner review #2 COMPLETE:**
  added `POST /calendar/{id}/ai-edit` and `POST /copy/{id}/ai-edit` (both {instruction}),
  mirroring the report ai-edit. Each sends the current record JSON + the human
  instruction to that brand's stage AIProviderConfig (PhaseEnum.CALENDAR /
  PhaseEnum.COPY), rewrites it in place, and resets it to an unapproved draft
  (calendar → is_approved/is_rejected false; package → status DRAFT, is_rejected
  false). Calendar ai-edit best-effort-normalizes entries via
  `Phase2Calendar._normalize_entries`; JSON parsed with `core.json_utils.parse_ai_json`.
  Frontend: `api.ts` aiEditCalendar/aiEditPackage; pipeline calendar items and copy
  cards gained an **Edit with AI** button + inline instruction box (Apply/Cancel),
  matching the report flow, with per-item busy state and isMissingError handling.
  `py_compile` + `tsc --noEmit` clean. **No migration.** Owner review #2 (delete +
  reject + ai-edit on all stages) is fully done. Next: **RV3** — #4/#5/#6 sidebar +
  smart brand switcher (navigate to the same screen for the other brand) + brand-context
  menu + Dashboard link + remove empty Calendar/Assets items.

- **2026-08-31 (RV3) — Smart brand switcher + brand-context sidebar (owner review
  #4/#5/#6):** reworked `components/AppShell.tsx`. It now fetches the brand list
  (`api.listBrands`) and the sidebar brand pills are **real brands that navigate**:
  clicking a brand keeps you on the same screen for that brand — e.g. on
  `/brands/A/pipeline`, clicking brand B goes to `/brands/B/pipeline` (path suffix
  preserved; off a brand route it goes to `/brands/B`). The **accent now follows the
  brand you are viewing** (derived from the route's brand via `accentOf`: slug
  contains "evatro" → red, else teal), not a manual toggle; it falls back to the
  last-used accent on non-brand pages. Sidebar nav restructured (#6): a **Dashboard**
  link at the top (→ "/"), and when inside a brand it shows that brand's items —
  **{Brand name}** (overview → /brands/{id}) and **Content Pipeline** — all real,
  active links. The empty **Calendar / Assets** "soon" items were removed (#5, owner
  chose remove). Topbar breadcrumb + brand chip now reflect the current brand. The
  logo links to the dashboard. `tsc --noEmit` clean. Frontend-only, no
  backend/migration. Next: **RV4** — #7 identity tab: real color pickers + fix the
  cramped layout / Save-button overlap. Then **RV5** — #8 solutions/competitors nested
  tabs.

- **2026-08-31 (RV4) — Identity color pickers + layout fix (owner review #7):** the
  brand Identity tab's seven color fields (primary / secondary / accent / ground /
  block / pill bg / pill text) were plain hex text inputs, so colors felt
  unchangeable and the form was cramped with the Save button crowding the swatches.
  Added a **`ColorField`** primitive (native `<input type="color">` swatch + a hex
  text input, both bound to the same value; the picker falls back to #000000 when the
  stored value is not a #rgb/#rrggbb hex) and swapped all seven fields to it — colors
  are now editable by picker or by typing. Layout: `.sf-section` is now a flex column
  with a 16px gap and the swatches row / Save actions get their own spacing, so
  nothing overlaps. Saving is unchanged (saveIdentity already persisted these colors).
  `tsc --noEmit` clean. Frontend-only, no backend/migration. Next: **RV5** (last in
  the review queue) — #8 solutions tab restructure: split Solutions vs Competitors
  with nested tabs so entering competitors no longer scrambles the solution data.

- **2026-08-31 (RV5) — Solutions tab split into nested tabs (owner review #8;
  review round COMPLETE):** the brand **Solutions** tab crammed solution editing +
  the monthly-split preview + the full competitors CRUD into one long section, so
  adding a competitor visually scrambled the solution data. Split it with a nested
  `Tabs` (the same primitive): **Solutions** sub-tab (the six-area include/focus/
  importance/priority/notes editor + Save + the live monthly-split preview) and
  **Competitors** sub-tab (the grouped-by-solution competitor add form + list). New
  `solTab` state drives it; each sub-tab is its own `.sf-section` card. Frontend-only,
  no backend/migration. `tsc --noEmit` clean. **All eight owner-review items are now
  done: #1 3-col calendar, #2 delete/reject/ai-edit on all stages, #3 fully tabbed
  pipeline, #4 smart brand switcher, #5 removed empty nav items, #6 brand-context
  sidebar + Dashboard, #7 identity color pickers + layout, #8 solutions/competitors
  nested tabs.** Next: the owner will describe the new visual-generation architecture
  (see the on-hold note); do not build old D2/D3 until then.

## 8. Known Issues / Tech Debt

- `json_repair` was used but missing from requirements — FIXED in Phase A.
- Redis/APScheduler are declared but unused (intended for Phase 5).
- No automated tests yet — add pytest coverage from Phase C onward (Phase B was
  verified via py_compile + a live ORM `configure_mappers()` check, not pytest).
- Phase B added `PATCH /brands/{id}` (partial profile edit) and
  `GET`/`PUT /brands/{id}/solutions` (upsert-only, non-destructive). A review UI
  for these is Phase C.
- Phase 1 free RSS + Google Trends path shipped (C2); Apify is now optional
  (opt-in per brand via `research_sources.use_apify`).
- Pipeline list refreshers used to swallow errors silently (`.catch(() => {})`),
  which hid backend failures and left stale cards on screen — FIXED in F1. Apply
  the same "surface errors + refresh on 404" pattern to any new list UI.

---

## 9. Deploy Notes (Railway)

1. Provision a **PostgreSQL** plugin; it exposes `DATABASE_URL` (scheme is
   normalized to asyncpg automatically).
2. **Backend service:** root directory = `backend`. Set env: `APP_ENV=production`,
   `DEBUG=false`, `FERNET_KEY`, `APP_SECRET_KEY`, `ADMIN_USERNAME`,
   `ADMIN_PASSWORD`, `CORS_ORIGINS`, bootstrap keys. Start command (from
   `railway.json`) runs `alembic upgrade head` then uvicorn.
3. **Frontend service:** root directory = `frontend`. Set env: `BACKEND_URL`
   (internal backend URL), `ADMIN_USERNAME`, `ADMIN_PASSWORD`.
4. Verify `/health` returns `{"status":"ok"}`.

Local dev: `docker compose up -d` (Postgres+Redis), then in `backend/`:
`alembic upgrade head` and `uvicorn main:app --reload`.

**Live (2026-08-26).** Deployed on Railway project "SocialForge - v2": services
`SocialForge-Backend` (root `backend`), `SocialForge-Front` (root `frontend`),
and a managed `Postgres`. Backend URL:
https://socialforgev2-aug26-production.up.railway.app (`/health` -> ok). The
frontend proxies to the backend via `BACKEND_URL` (must include `https://`) and
shares `ADMIN_USERNAME`/`ADMIN_PASSWORD` with it. Phase B migration `0002` ran
automatically on deploy; the two brands were seeded into the live DB. Keep the
Postgres **Public Access OFF** — turn it on only for a one-off seed, then off
again. Seeding options: `scripts/seed_brands.py` (needs a DB URL, seeds pillars
too) or `scripts/seed_via_api.py` (talks to the live API, no DB access, no
pillars).

---

## 10. How to Resume

**Where we are (2026-08-31).** The full app is live and working end to end:
research -> calendar -> copy -> (raw) visual, with human approval at each gate.
The **Studio UI rebuild (Phase U, U1-U5) is complete** and the owner's post-rebuild
**review round (RV1-RV5, items #1-#8) is complete** — see the decision log for each.
Alembic head is **0009** (auto-applied on deploy).

**Immediate next work: visual generation — NEW architecture (owner-driven).** The
owner has a different design for the whole visual-generation step and will describe
it. **Do NOT build the old D2 (Pillow pill/logo/headline overlay) or D3 (Google
Drive).** The current Stage-4 Visual UI works against D1 (OpenAI raw scene) as a
placeholder. When the owner gives the spec: first do a gap analysis + a sub-stepped
plan (no code yet), get approval, then build.

**Other open items (not started):**
- Copy-run hardening: the copy poll window (~6 min) can end before a 30-post batch
  finishes; surface "N generated / M failed" and let a partial run resume.
- Research depth R3 (competitor discovery) + R4 (Apify social monitoring, optional/paid).
- Phase E — assisted Schedule / Publish / Metrics (APScheduler already a dep; NOT autonomous).
- No automated tests yet (pytest from here on).

**To verify locally:** backend `python -m py_compile`, frontend `./node_modules/.bin/tsc
--noEmit`. To exercise live: open a brand, set its Research/Calendar/Copy AI providers
under AI Providers, set the search + image keys on Settings, then run the pipeline and
approve each stage.


## 11. Editability & Solution-First Roadmap (approved 2026-08-27)

Driven by live feedback after the manager demo: every piece of brand data must be
editable, everything organizes around solution areas, and human-in-the-loop stays.
Shareable one-pager artifact:
https://claude.ai/code/artifact/38ea41ec-302d-4692-928a-2f99f8575272

| Epic | Scope | Status |
|------|-------|--------|
| E0 Calendar fix | surface run errors + max_tokens headroom + salvage parser | **DONE (this commit)** |
| E1 Identity/Voice editable | edit forms over existing `PATCH /brands` (incl. monthly_post_target) | **DONE** |
| E2 Solutions + importance | add `importance` to brand_solutions (mig 0006); weighted auto-split; add/remove UI + live preview | **DONE** |
| E3 Competitors CRUD | competitor PATCH/DELETE + solution tag (migration); grouped-by-solution UI | **DONE** |
| E4a Report controls | reject/delete/AI-edit report endpoints + UI (migration 0008) | **DONE** |
| E4b Per-solution research | per-solution search + solution-tagged topics/gaps/sources | **DONE** |
| E5 Back to Calendar | R2b review UI (solution chips + ai_angle + distribution) | **DONE** |

Notes: backend already has `PATCH /brands` (so post-limit is writable — E1 is UI
only) and `GET/POST` competitors (E3 adds PATCH/DELETE + solution tag). E2 upgrades
R2a's even split to an importance-weighted split. Each epic ships as its own
reviewed, deployable commit; migrations stay idempotent + inspector-guarded.
