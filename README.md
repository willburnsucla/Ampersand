# Ampersand

A story-development IDE for writers, with natural language conversational input, and knowledge graph-based out puts. Track characters, beats, themes, world elements, and threads, all branchable like git.

> **Status:** Scaffold complete. Mock backend runs end-to-end without a database. Real backend (Postgres + Claude + Clerk) wires in over next two weeks.

---

## Stack

| Layer | Tech |
|---|---|
| Frontend | Next.js 14 (App Router), React 18, TypeScript, Tailwind, Zustand, TanStack Query, D3 |
| Backend | Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.0 (async), Alembic |
| Database | PostgreSQL 16 + pgvector |
| LLM | Anthropic Claude (`claude-haiku-4-5` default, `claude-sonnet-4-6` escalation) |
| Embeddings | Voyage AI |
| Auth | Clerk (JWT verified server-side) |
| Realtime | Server-Sent Events (one-way, server → client) |
| Deployment | Vercel (FE), Railway (BE), Neon (DB) |

---

## Repo layout

```
ampersand/
├── backend/           # FastAPI + SQLAlchemy + Alembic
│   └── app/
│       ├── core/             # config, db engine, dependency injection
│       ├── domain/           # Pydantic models, ORM, BranchStateMachine
│       ├── repos/            # Repository pattern — only place DB is touched
│       ├── services/         # Extractor (Claude), Embedder, etc.
│       ├── orchestration/    # ConversationOrchestrator (Mediator)
│       ├── broadcast/        # EventBroadcaster + SSE endpoint
│       ├── auth/             # Clerk JWT adapter
│       ├── api/              # FastAPI route handlers (thin)
│       └── migrations/       # Alembic
├── frontend/          # Next.js 14
│   ├── app/(authed)/         # conversation, inspector, visualizations, branches, export
│   └── lib/                  # api-client, sse-client, graph-store (Zustand), auth-client
├── shared/schemas/    # JSON Schema — single source of truth for domain types
└── docs/
```

---

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Python | 3.11+ | `uv python install 3.11` |
| `uv` | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node | 18+ | [nodejs.org](https://nodejs.org) |
| Docker Desktop | latest | [docker.com](https://www.docker.com/products/docker-desktop/) - (needed only for real-mode DB) |

---

## Quickstart — mock mode (no DB, ~2 min)

```bash
git clone https://github.com/willburnsucla/Ampersand.git
cd Ampersand
```

**1. Install `uv` (Python package manager) if you don't have it:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env   # load uv into your current shell session
```

**2. Install dependencies:**
```bash
make install   # runs uv sync + npm install
```

> If `npm install` fails with a peer-dep conflict, run `cd frontend && npm install --legacy-peer-deps` instead.

**3. Set up Clerk keys for the frontend (required even in mock mode):**

Create `frontend/.env.local` with the following (get free keys at [dashboard.clerk.com](https://dashboard.clerk.com)):
```
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_...
NEXT_PUBLIC_CLERK_SIGN_IN_URL=/sign-in
NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up
NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL=/conversation
NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL=/conversation
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

**4. Start the servers:**
```bash
make dev-mock        # backend on :8000, frontend on :3000
```

Visit [http://localhost:8000/docs](http://localhost:8000/docs) for the API explorer. The mock backend uses in-memory repos + a deterministic `MockExtractor`, and accepts any auth token.

Smoke test:
```bash
curl -s http://localhost:8000/api/v1/healthz
# → {"status":"ok"}

# Create a story
curl -X POST http://localhost:8000/api/v1/stories \
  -H "Content-Type: application/json" -H "Authorization: Bearer mock" \
  -d '{"title":"My Story"}'

# Send a turn (the MockExtractor recognizes "detective", "wizard", "forest", "chapter", "theme")
curl -X POST http://localhost:8000/api/v1/conversation/turn \
  -H "Content-Type: application/json" -H "Authorization: Bearer mock" \
  -d '{"story_id":"<id>","branch_id":"<id>","content":"Maya is a detective"}'
```

---

## Real mode (Postgres + Claude + Clerk)

1. Copy `.env.example` to `.env` and fill in:
   - `ANTHROPIC_API_KEY`
   - `VOYAGE_API_KEY`
   - `CLERK_SECRET_KEY`, `CLERK_PUBLISHABLE_KEY`, `CLERK_JWT_ISSUER`
   - Set `AMPERSAND_BACKEND_MODE=real`

2. Start Postgres + run migrations:
   ```bash
   make db-up        # docker compose up -d db (pgvector/pgvector:pg16)
   make migrate      # alembic upgrade head
   ```

3. Start dev servers:
   ```bash
   make dev
   ```

> Real-mode wiring (Postgres repos, Claude API, Clerk verification) is implemented in Weeks 2–3. The mock mode covers the entire API surface today.

---

## Common commands

```bash
make help             # list every target
make install          # uv sync + npm install
make dev-mock         # mock backend + Next.js (no DB needed)
make dev              # real backend + Next.js (needs .env + Docker)
make migrate          # alembic upgrade head
make migrate-new MSG="add foo"
make codegen          # regenerate Pydantic + TS types from /shared/schemas/
make test             # pytest + npm test
make lint             # ruff + eslint
make format           # ruff format + prettier
```

---

## Architectural invariants — read before opening a PR

These are the rules that will keep our app from becoming a a big ball of mud. We should should reject PRs that break them.

1. **No raw DB access outside `/backend/app/repos/`.** Every read or write goes through a Repository.
2. **Branch-scoped reads only via `GraphRepo.for_branch(branch_id)`.** The `WHERE branch_id = ANY(branch_tags)` filter is a secret of `GraphRepo` — no other module constructs it.
3. **Conversation round-trip lives only in `ConversationOrchestrator`.** Route handlers cannot call `Extractor`, `DeltaApplier`, or `EventBroadcaster` directly.
4. **Every node and edge carries a non-null `provenance_turn_id`.** Enforced at the Pydantic layer and as a DB constraint.
5. **The Anthropic SDK is imported only inside `app/services/extractor.py`.** No LLM calls anywhere else, ever, including the frontend.
6. **SSE events ship only via `EventBroadcaster.publish()`.** SSE route handlers subscribe — they never push.
7. **Mock implementations live in the same package as their real counterparts.** `InMemoryGraphRepo` next to `PostgresGraphRepo`, `MockExtractor` next to `ClaudeExtractor`. This is what makes parallel development possible.
8. **Client-side delta application is idempotent.** `add_node` is upsert-by-id, `add_edge` is upsert, `set_status`/`update_property` are overwrite. This is what makes the snapshot/SSE race resolve safely.
9. **The frontend talks to the backend only via `ApiClient`, `SseClient`, or `AuthClient`.** No raw `fetch()` in components, no `EventSource` outside `SseClient`.

---

## Domain types (spec-locked — do not drift)

```ts
NodeType    = "character" | "beat" | "theme" | "world_element" | "thread"
NodeStatus  = "proposed"  | "committed" | "rejected"
BranchState = "active"    | "dormant"   | "committed" | "graveyard"

DeltaOp kinds: add_node | add_edge | update_property | set_status | add_branch_tag
```

Branch state machine:

```
(creation) ──CREATE──→ active
active ──SWITCH_TO_DORMANT──→ dormant
dormant ──SWITCH_TO_ACTIVE──→ active
active ──COMMIT──→ committed     (terminal)
active|dormant ──ABANDON──→ graveyard
graveyard ──REVIVE──→ active
```

The single source of truth for these types is `/shared/schemas/*.schema.json`. Pydantic models and TypeScript types are generated from them via `make codegen` — never hand-edit `/backend/app/domain/generated/` or `/frontend/lib/types/generated/`.

---

## Build plan (for the TA)

Roughly 25 tasks (T-001…T-025) organized into 7 streams that build in parallel after a Week 1 foundation. The full plan is at `/Users/burns/.claude/plans/users-burns-downloads-ampersand-initial-stateful-forest.md` (or check the design doc PDF in the team Drive).

| Week | Tasks | What we will ship |
|---|---|---|
| 6 | T-001 schemas, T-002 DB, T-003 repos, T-004 mock backend, T-005 branch SM, T-013 auth, T-014 broadcaster | ** Done — `make dev-mock` works end-to-end** |
| 7 | T-006 Extractor+Embedder, T-007 ContextBuilder, T-008 DeltaApplier, T-009 Exporter, T-010 GapAnalyzer, T-011 QueryService, T-012 VizDataBuilder; T-017–T-019 frontend infra; T-021/T-023/T-024 views | All services + most views, parallel against mock |
| 8 | T-015 Orchestrator, T-016 routes, T-020 ConversationView, T-022 VisualizationsView | Real backend converges |
| 9 | T-025 e2e + deploy | Playwright tests + Vercel/Railway/Neon |

---

## Working with the codebase — pointers

- **Add a new domain type:** edit `/shared/schemas/`, then `make codegen`. Mirror it in `/backend/app/domain/models.py` and add ORM equivalent in `orm.py`.
- **Add a new endpoint:** route handler in `/backend/app/api/router.py` (≤10 lines, dispatches to a service). The service goes in `/backend/app/services/`.
- **Add a new repository method:** edit the abstract base + both `InMemory*` and `Postgres*` impls. Add a unit test that runs against both — they should pass the same suite.
- **Add a new view:** new `app/(authed)/<route>/page.tsx`. Read graph state via `useGraphStore` selectors — never call `ApiClient` for graph data inside a component.
- **Using an AI for development:** keep a log of all prompts and outputs, to be submitted with the final project. It is the policy of the course that we maintain transparency in our AI use, to maintain the integrity of this being a course focused around US designing and implementing the software. That being said, using it for working with unfamiliar syntaxes, so long as you are clearly specifying the actions that need to be taken and showing a clear understanding of what you are developing, it should be no issue. 

---

## Tests

```bash
make test-backend     # pytest — covers BranchStateMachine, repos, services
make test-frontend    # npm test — components + stores
make test             # both
```

CI runs lint → unit → integration → e2e (Playwright) on every PR.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `make migrate` errors with `connection refused` | `make db-up` first; wait for healthcheck |
| `make dev` fails with `pgvector` error | Use the `pgvector/pgvector:pg16` image (already in `docker-compose.yml`); `make db-destroy && make db-up && make migrate` to recreate |
| `make codegen` can't find `datamodel-codegen` | `cd backend && uv sync` first |
| `uv: command not found` after installing uv | Run `source $HOME/.local/bin/env` to load uv into your current shell session |
| Frontend `npm install` peer-dep conflict | Run `cd frontend && npm install --legacy-peer-deps` |
| Frontend Clerk error: `Missing publishableKey` | Create `frontend/.env.local` with your Clerk public key — required even in mock mode (see Quickstart step 3) |
| Mock backend doesn't return a node for my message | The MockExtractor matches on the keywords `detective`, `wizard`, `forest`, `chapter`, `theme`; otherwise it returns a generic Character |
| `401 Unauthorized` in mock mode | Send any value as `Authorization: Bearer <anything>` — `MockAuthGate` accepts any token but the `HTTPBearer` dep still requires the header |

---

## Team

| Role | Person |
|---|---|
| Team Member | William Burns ([@willburnsucla](https://github.com/willburnsucla)) |
| Team Member | Gabriel Sanchez _(fill in ur Github :) )_ |
| Team Member | Thomas McConnell _(fill in ur Github :))_ |
| Team Member | Lam Luong _(fill in ur Github :))_ |
| Team Member | Emily Zhang _(fill in ur Github :))_ |
| Team Member | Ashley Wu _(fill in ur Github :))_ |
| Team Member | Hana Chloe Yoon  _(fill in ur Github :))_ |
| Course | CS130 |

PRs welcome. Read the architectural invariants first.
