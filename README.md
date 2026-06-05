# Ampersand

A story-development tool. The writer talks to it in natural language; it builds a typed **story graph** (beats, characters, themes, settings) that branches like git, and an LLM mid-layer extracts beats from prose, tracks the entities they involve, checks consistency, and analyzes narrative arc.

> **Status (pre-demo):** the typed v2 mid-layer is on `main` and runs end to end. `make dev-mock` brings up the mock backend (no database) and the Vite frontend; a writer signs in, pastes prose, and watches it become beats on a branchable story graph. Extraction runs on Gemini with a deterministic mock fallback so a turn never fails, beats dedupe so re-sent prose does not pile up, and branches fork and switch in the UI. Details below.

---

## The one idea that explains the rest

The graph IS the story. The nodes are beats, characters, themes, and settings; the edges are the beat-to-entity links and the branch/sequence lineage. It is stored as typed tables in Postgres (`orm_v2`), not a generic node/edge blob. Each character/theme/setting has base properties plus a per-branch overlay, so an alternate timeline can change a fact without forking the whole entity (base ⊕ overlay merge on read).

The LLM never sees SQL, repos, or the ORM. It sees one thing: the **query catalog**, a fixed menu of named tools (retrieval like `get_beats_in_branch`, analytical like `find_logic_error`). `project_id` and `branch_id` are baked into the catalog at construction from the authenticated request, so the model cannot name another tenant. Everything below the catalog is hidden; everything above it (orchestrator, router) never builds SQL.

---

## Architecture

```
router_v2.py                 thin HTTP handlers, one per endpoint  (POST /api/v2/conversation/turn)
   │ Depends()
ConversationOrchestrator     the mediator: handle_turn() sequences the services, owns nothing else
   ├── ContextBuilder        gather branch + project state into LlmContextV2
   ├── Extractor (Mock/Gemini) prose -> proposed beats + named entities
   ├── DeltaApplier          write the proposed beat, resolve/create/link its entities
   ├── ConsistencyChecker    inline + deep-scan -> Issues
   └── SocraticPrompter       decide when to ask a clarifying question
   │
query_catalog.py             the LLM's only tool surface; tenancy baked in at construction
FrameworkRegistry            .get("vonnegut") / .get("papalampidi")  -> arc + anomaly analysis over narrative.py
   │
Repos (ABC + Sql impl)       Project · Branch · Beat · Character · Theme · Setting · Issue · Conversation  (on orm_v2)
   │ SQLAlchemy 2.0 async
Supabase Postgres (orm_v2 schema)
```

The `docs/mid-layer-architecture.md` doc has the full version: the layer map, the one-turn sequence, the GoF pattern table, and the Parnas change-impact matrix.

---

## What is built, and what is left

**Built:**
- the typed domain (`models_v2.py`, `orm_v2.py`) and all eight repos with base ⊕ overlay merge, branch-scoped reads, and the 3-fork cap, each with an InMemory impl so `/api/v2` runs in `make dev-mock` with no database
- `GeminiExtractorV2`: real beat extraction over Gemini (native `google-genai`), a whole passage to several ordered beats. it is curatorial, not advisory: it organizes the beats the writer's prose already contains and never invents, embellishes, suggests, or judges. transient errors retry, and any failure falls back to the deterministic `MockExtractorV2`, so a turn always produces beats
- beat dedup: the extractor is shown the beats already in the story and asked for only new ones, with a logline match in the applier as a backstop, so re-sent or overlapping prose does not duplicate beats
- story branching in the UI: `POST /branches/fork` forks an alternate that inherits the story up to a chosen beat, and the graph has a switcher to move between branches
- the turn services (`ContextBuilder`, `DeltaApplier`, `ConsistencyChecker`, `SocraticPrompter`), `ConversationOrchestrator`, and `router_v2.py`; a turn round-trips over HTTP in both mock and real mode
- `query_catalog.py` (the Facade the LLM sees, tenancy baked in), `frameworks/` (Vonnegut arcs + Papalampidi turning points), the branch state machine, and the prompt-security layer on the turn endpoint
- Supabase auth: the `ez_frontend_clean` frontend signs in with Supabase; the backend verifies the JWT in real mode and accepts any token in mock mode
- 350 backend tests green

**Left to do:**
- an LLM-backed `ConsistencyChecker` for the semantic checks (contradiction, character drift, world-rule violations); the heuristic checker stands in today
- Supabase Realtime in place of the custom SSE broadcaster
- retire the Week-1 node/edge code (`models.py` graph types, `graph_repo.py`, the `/api/v1` turn endpoint) now that the app is on `/v2`

---

## Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 async, Alembic |
| Database | PostgreSQL 16 + pgvector (Supabase); no vector store yet, pgvector slots in behind the catalog later |
| LLM | Google Gemini (`gemini-2.5-flash`), native `google-genai`, with a deterministic mock fallback |
| Auth | Supabase JWT, verified server-side in `app/auth/supabase_gate.py` (ES256 with an HS256 fallback) |
| Realtime | Supabase Realtime (planned), replacing the Week-1 custom SSE broadcaster |
| Frontend | `ez_frontend_clean/`: Vite + React, the demo UI (chat, story graph, branch switcher, Supabase sign-in). `frontend/` is the older Next.js app |

---

## Quickstart (mock mode, no DB)

```bash
git clone https://github.com/willburnsucla/Ampersand.git
cd Ampersand
make dev-mock       # mock backend on :8000 + the Vite frontend on :5173
```

`make dev-mock` sets `AMPERSAND_BACKEND_MODE=mock`: in-memory repos (no Postgres) and a `MockAuthGate` that accepts any bearer token. It installs the frontend and starts both servers, so the whole `/api/v2` app, story graph and all, runs with no database. The mode defaults to `real` when unset, so a misconfigured deploy fails closed (auth on); `make dev-mock` and the test suite set mock explicitly.

For real extraction, drop a Gemini key into `backend/.env` (a free key from [aistudio.google.com](https://aistudio.google.com) works):

```
AMPERSAND_BACKEND_MODE=mock
EXTRACTOR_BACKEND=gemini
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.5-flash
```

Leave `EXTRACTOR_BACKEND=mock` to skip Gemini entirely (deterministic beats, no key). Sign-in needs `VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY` in `ez_frontend_clean/.env`; the mock backend accepts the resulting token.

---

## Real mode (Postgres + Gemini + Supabase)

```bash
# backend/.env: AMPERSAND_BACKEND_MODE=real, GEMINI_API_KEY, the Supabase Postgres
# DATABASE_URL (asyncpg) + SYNC_DATABASE_URL, SUPABASE_URL, SUPABASE_JWT_SECRET
make db-up               # docker compose up -d db (pgvector/pgvector:pg16), or point at Supabase
make migrate             # alembic upgrade head
make dev                 # real backend + frontend
```

Real mode verifies the Supabase JWT server-side and persists to Postgres; it refuses to boot without `SUPABASE_JWT_SECRET`.

---

## Common commands

```bash
make help            # list every target
make install         # uv sync + npm install
make dev-mock        # mock backend + frontend (no DB)
make dev             # real backend + frontend (needs .env + Docker)
make migrate         # alembic upgrade head
make test            # pytest + npm test
make lint            # ruff + eslint
make format          # ruff format + prettier
```

---

## Architectural invariants (read before opening a PR)

1. **No raw DB access outside `app/repos/`.** Every read and write goes through a repo. Each repo owns its aggregate's ORM, including its beat-entity link table.
2. **The LLM sees only the query catalog.** No SQL, no repos, no ORM rows reach the model. `project_id` and `branch_id` are baked into the catalog at construction, never a tool argument, so the model cannot reach another tenant.
3. **The conversation turn lives only in `ConversationOrchestrator`.** Route handlers do not call `Extractor`, `DeltaApplier`, or the checker directly.
4. **The LLM SDK (`google-genai`) is imported only inside the extractor.** No model call anywhere else, including the frontend.
5. **Every read and write is tenant-scoped.** Reads and writes filter by `owner_id` / `project_id` / `branch_id`; a foreign id returns nothing or raises, it never leaks.
6. **Mock and real implementations live in the same package.** `MockAuthGate` next to `SupabaseAuthGate`, the InMemory repo next to the Sql repo. This is what lets the team build against mocks in parallel.
7. **Beat affect is atomic.** `valence` and `arousal` are scored together or not at all, enforced at the model and as a DB constraint.

---

## Domain model

```
Project ──< Branch ──< Beat            (Beat.sequence_index_in_branch orders beats within a branch)
Project ──< Character / Theme / Setting (base properties + per-branch overlay)
Branch  ──< Branch                      (forks, <= 3 alternates per beat)
Beat    >──< Character / Theme / Setting (link tables = the graph edges)
Branch  ──< Issue                       (bot-detected, lifecycle: open -> acknowledged -> resolved)
Branch  ──< ConversationTurn            (append-only writer/assistant log)
```

Branch states: `active`, `dormant`, `committed` (terminal), `graveyard` (revivable). Narrative analysis is Vonnegut's 7 arcs plus Papalampidi's 5 turning points plus valence/arousal affect; more frameworks slot in behind the `Framework` interface.

The full design lives in `~/.claude/plans/...ampersand-initial-stateful-forest.md` (the Week-7 mid-layer plan) and `docs/mid-layer-architecture.md`.

---

## Tests

```bash
make test-backend     # pytest (350 green): repos, services, the catalog, the orchestrator, the turn over HTTP
make test-frontend    # npm test
```

Backend tests run against a throwaway Postgres via testcontainers, so Docker must be running for `make test-backend`.

---

## Team

| Person | GitHub |
|---|---|
| William Burns | [@willburnsucla](https://github.com/willburnsucla) |
| Gabriel Sanchez | [@GSANC10](https://github.com/GSANC10) |
| Thomas McConnell | [@thomasmcconnell33](https://github.com/thomasmcconnell33) |
| Lam Luong | [@lamluongg](https://github.com/lamluongg) |
| Emily Zhang | [@emilyzhang625](https://github.com/emilyzhang625) |
| Ashley Wu | [@ashleyjwu](https://github.com/ashleyjwu) |
| Hana Chloe Yoon | [@cloyooni](https://github.com/cloyooni) |

CS130. PRs welcome; read the invariants first.
