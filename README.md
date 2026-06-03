# Ampersand

A story-development tool. The writer talks to it in natural language; it builds a typed **story graph** (beats, characters, themes, settings) that branches like git, and an LLM mid-layer extracts beats from prose, tracks the entities they involve, checks consistency, and analyzes narrative arc.

> **Status:** The Week-1 scaffold and the query-catalog retrieval wave (#53) are on `main`; `make dev-mock` runs the node/edge backend end to end. The rest of the **mid-layer** (the typed beat/entity graph plus the LLM orchestration over it) is in review as PR #54. Remaining work is wiring the frontend to it, swapping SSE for Supabase Realtime, and dropping in the real Claude calls. Details below.

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
   ├── Extractor (Mock/Claude) prose -> proposed beat + named entities
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

**Built (in review on PRs #53 / #54 / #56):**
- the typed domain (`models_v2.py`, `orm_v2.py`) and all eight repos with base ⊕ overlay merge, branch-scoped reads, and the 3-fork cap
- `query_catalog.py`: the Facade the LLM sees, 14 tools (10 retrieval + `find_logic_error`, `scan_branch`, `classify_arc`, `framework_anomalies`), Pydantic-derived tool schemas, validating dispatch
- `frameworks/`: Vonnegut (7 arcs) and Papalampidi (5 turning points) over `narrative.py`, behind a registry
- `ConsistencyChecker` (heuristic impl today), and the turn services: `ContextBuilder`, `DeltaApplier`, `SocraticPrompter`, and a deterministic `MockExtractorV2`
- `ConversationOrchestrator` and `router_v2.py` with the v2 DI wiring; a turn round-trips over HTTP against real Postgres
- Supabase auth gate (mock gate for local dev), branch state machine, the prompt-security module
- 197 backend tests green

**Left to do:**
- InMemory v2 repos so `/api/v2` runs in `make dev-mock` with no database (today the v2 path needs Postgres)
- point a frontend at `/api/v2` (tracked in issue #55)
- replace the custom SSE broadcaster with Supabase Realtime (subscribe the client to Postgres row changes, gated by RLS)
- `ClaudeExtractorV2`: the real extraction behind the `Extractor` ABC (the mock stands in)
- an LLM-backed `ConsistencyChecker` for the semantic checks (contradiction, character drift, world-rule violations)
- fold `extractor_v2.py` / `dependencies_v2.py` back into `extractor.py` / `dependencies.py` (the plan calls for EXTEND, not separate files)
- retire the Week-1 node/edge code (`models.py` graph types, `graph_repo.py`, the original `/api/v1` turn endpoint, the SSE broadcaster) once the frontend is on `/v2`

---

## Stack

| Layer | Tech |
|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.0 async, Alembic |
| Database | PostgreSQL 16 + pgvector (Supabase); no vector store yet, pgvector slots in behind the catalog later |
| LLM | Anthropic Claude (`claude-haiku-4-5` default, `claude-sonnet-4-6` escalation) |
| Auth | Supabase JWT, verified server-side in `app/auth/supabase_gate.py` (ES256 with an HS256 fallback) |
| Realtime | Supabase Realtime (planned), replacing the Week-1 custom SSE broadcaster |
| Frontend | Next.js 14 in `frontend/` (Zustand graph store, TanStack Query, d3); `ez_frontend_clean/` is a separate Vite mockup currently wired to the mock backend |

---

## Quickstart (mock mode, no DB)

```bash
git clone https://github.com/willburnsucla/Ampersand.git
cd Ampersand
make install        # uv sync + npm install
make dev-mock       # mock backend on :8000, Next.js on :3000
```

`make dev-mock` sets `AMPERSAND_BACKEND_MODE=mock`, which uses in-memory repos and a `MockAuthGate` that accepts any bearer token. Note: mock mode runs the Week-1 node/edge backend today; the v2 path needs Postgres until the InMemory v2 repos land.

The backend mode now defaults to `real` when the env var is unset, so a misconfigured deploy fails closed (auth on) instead of open. `make dev-mock` and `make dev` both set the mode explicitly, and the test suite pins mock.

Smoke test the Week-1 backend:

```bash
curl -s http://localhost:8000/api/v1/healthz                    # {"status":"ok"}
curl -X POST http://localhost:8000/api/v1/stories \
  -H "Content-Type: application/json" -H "Authorization: Bearer mock" \
  -d '{"title":"My Story"}'
```

---

## Real mode (Postgres + Claude + Supabase)

```bash
cp .env.example .env     # fill ANTHROPIC_API_KEY, SUPABASE_JWT_SECRET, set AMPERSAND_BACKEND_MODE=real
make db-up               # docker compose up -d db (pgvector/pgvector:pg16)
make migrate             # alembic upgrade head
make dev                 # real backend + frontend
```

Real mode requires a non-empty `SUPABASE_JWT_SECRET`; the app refuses to boot without one.

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
4. **The Anthropic SDK is imported only inside the extractor.** No LLM call anywhere else, including the frontend.
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
make test-backend     # pytest (197 green): repos, services, the catalog, the orchestrator, the turn over HTTP
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
