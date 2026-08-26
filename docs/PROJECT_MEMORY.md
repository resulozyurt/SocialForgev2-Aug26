# SocialForge AI — Project Memory

> Persistent context for the project. Update at the end of every phase. If you
> open a fresh chat, read this file first to resume without losing the thread.

Last updated: 2026-08-26 — end of **Phase A** (stabilization & deploy foundation).

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

## 5. Brand Profiles (target — full modeling lands in Phase B)

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

---

## 6. Phase Status

| Phase | Scope | Status |
|-------|-------|--------|
| 1 Research | Competitor/trend intel -> TrendReportCard | DONE (Apify; RSS/Trends pending) |
| 2 Calendar | Approved report -> monthly calendar | DONE |
| 3 Copy | Approved calendar -> ContentPackage (EN+TR) + visual brief | DONE |
| Approval gates | report / calendar / package | DONE (API); UI pending |
| **A Foundation** | deps fix, Alembic, auth, Railway prep, DB URL norm | **DONE (this commit)** |
| B Brand+Solution | rich brand profiles, solution taxonomy, seed FieldPie/Evatro | TODO (next) |
| C Review UI + free research | 3 approval screens, RSS/Trends, Google Drive | TODO |
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

---

## 8. Known Issues / Tech Debt

- `json_repair` was used but missing from requirements — FIXED in Phase A.
- Redis/APScheduler are declared but unused (intended for Phase 5).
- No automated tests yet — add pytest coverage from Phase B onward.
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

---

## 10. How to Resume

Phase A is committed. Next up is **Phase B** (rich brand profiles + solution
taxonomy + seed FieldPie/Evatro), pending Resul's approval. Each phase = one
reviewed commit; do not skip ahead without approval.
