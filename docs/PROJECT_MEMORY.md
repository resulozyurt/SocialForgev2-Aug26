# SocialForge AI — Project Memory

> Persistent context for the project. Update at the end of every phase. If you
> open a fresh chat, read this file first to resume without losing the thread.

Last updated: 2026-08-26 — end of **Phase B** (rich brand profiles + solution taxonomy + seed).

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
| Approval gates | report / calendar / package | DONE (API); UI pending |
| A Foundation | deps fix, Alembic, auth, Railway prep, DB URL norm | DONE |
| **B Brand+Solution** | rich brand profiles, solution taxonomy, seed FieldPie/Evatro | **DONE (this commit)** |
| C Review UI + free research | 3 approval screens, RSS/Trends, Google Drive | TODO (next) |
| D Visual | Phase 4 branded image generation | TODO |
| E Schedule/Publish/Metrics | Phase 5/6 (assisted, not autonomous) | LATER |

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

---

## 8. Known Issues / Tech Debt

- `json_repair` was used but missing from requirements — FIXED in Phase A.
- Redis/APScheduler are declared but unused (intended for Phase 5).
- No automated tests yet — add pytest coverage from Phase C onward (Phase B was
  verified via py_compile + a live ORM `configure_mappers()` check, not pytest).
- Phase B added `PATCH /brands/{id}` (partial profile edit) and
  `GET`/`PUT /brands/{id}/solutions` (upsert-only, non-destructive). A review UI
  for these is Phase C.
- Phase 1 still depends on Apify until the free RSS/Trends path lands (Phase C).

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

Phase B is committed. **Apply it after pulling** (Resul, on Windows, DB reachable):
`alembic upgrade head` (applies `0002`), then `python -m scripts.seed_brands`
(idempotent — safe to re-run). Verify with `GET /api/v1/brands` and
`GET /api/v1/brands/{id}/solutions`.

Next up is **Phase C** (three approval-review screens, the free RSS/Google Trends
research path, and Google Drive asset storage), pending Resul's approval. Each
phase = one reviewed commit; do not skip ahead without approval.
