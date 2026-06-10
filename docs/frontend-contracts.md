# Frontend API Contract

What the frontend team builds against. All endpoints below are live in `router_v2.py` on `/api/v2`. Build against the real backend with `make dev-mock` (no DB needed) or swap in mocks of the shapes below during parallel frontend development.

## Setup

**Base URL:** the API base from your env, plus `/api/v2` (FastAPI). Defaults to `http://localhost:8000/api/v2` in dev.

**Auth:** every request carries `Authorization: Bearer <supabase_jwt>`. Get the JWT from the Supabase JS client.

**Errors:** every non-2xx response has the shape `{ "detail": "human readable message", "code": "snake_case_id" }`. The `code` is optional but stable when present, so you can switch on it for specific error UI (e.g. `fork_cap_exceeded`).

**Realtime:** subscribe via the Supabase JS client directly, not through FastAPI. RLS scopes everything the writer can see.

## Principle: where state changes show up

The backend has two channels for delivering state to the frontend. Knowing which is which avoids duplication and weird race conditions.

1. **DB state changes flow through Realtime.** New beats, new issues, primary branch promotion, anything that lives in a table. The frontend subscribes once to the relevant channels and reacts.
2. **The HTTP response carries only the bot's reply plus session-level UI hints.** Things Realtime can't deliver because they're not DB records, like "the bot wants you to switch your URL to a different branch."

The practical consequence: the conversation turn response is intentionally thin. The bot's side effects (new beats, issues, etc.) arrive via Realtime, not in the response body. The response itself only carries the reply text and any UI nudges the bot wants the frontend to act on.

## TypeScript types

Drop these into your types directory. When codegen lands they get replaced. Until then, keep them in sync with `backend/app/domain/models_v2.py`.

```typescript
type UUID = string;
type ISODateTime = string;

type EntityStatus = "proposed" | "committed" | "rejected";
type BranchState = "active" | "dormant" | "committed" | "graveyard";
type TurnRole = "writer" | "assistant";

type VonnegutArc =
  | "rags_to_riches" | "riches_to_rags"
  | "man_in_hole"    | "double_man_in_hole"
  | "icarus"         | "cinderella" | "oedipus";

type TurningPoint = "tp1" | "tp2" | "tp3" | "tp4" | "tp5";

type IssueType =
  | "contradiction" | "timeline_gap" | "character_inconsistency"
  | "world_rule_violation" | "pacing_anomaly" | "framework_misuse";
type IssueStatus = "open" | "acknowledged" | "resolved";

interface Project {
  id: UUID;
  owner_id: string;
  title: string;
  primary_branch_id: UUID | null;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

interface Branch {
  id: UUID;
  project_id: UUID;
  parent_branch_id: UUID | null;
  created_from_beat_id: UUID | null;
  name: string | null;
  state: BranchState;
  declared_arc: VonnegutArc | null;
  created_at: ISODateTime;
}

interface Beat {
  id: UUID;
  branch_id: UUID;
  sequence_index_in_branch: number;
  logline: string;
  content: Record<string, unknown>;
  turning_point: TurningPoint | null;
  valence: number | null;   // 0-1
  arousal: number | null;   // 0-1
  status: EntityStatus;
  created_at: ISODateTime;
  updated_at: ISODateTime;
}

// CharacterView / ThemeView / SettingView are read-only projections
// with base + branch-overlay already merged. The frontend never sees
// the raw base record or overlay record, only the merged view.
interface EntityView {
  id: UUID;
  name: string;
  properties: Record<string, unknown>;
  resolved_in_branch: UUID;
}
type CharacterView = EntityView;
type ThemeView = EntityView;
type SettingView = EntityView;

interface Issue {
  id: UUID;
  branch_id: UUID;
  type: IssueType;
  description: string;
  related_beat_ids: UUID[];
  related_entity_ids: UUID[];
  status: IssueStatus;
  detected_at: ISODateTime;
  resolved_at: ISODateTime | null;
}

interface ConversationTurn {
  id: UUID;
  branch_id: UUID;
  role: TurnRole;
  content: string;
  created_at: ISODateTime;
}

// Suggested actions: how the bot tells the frontend it wants UI state
// to change without that change being a DB write. Open shape, more
// action types added over time. See the conversation turn section.
type SuggestedAction =
  | { type: "switch_branch"; branch_id: UUID; label: string };
```

## Endpoints by page

### Project picker

The entry point when the URL doesn't tell you which project to open. Could be rendered as a Claude-style sidebar stack of projects, a card grid, whatever feels right. Same endpoints either way.

```
GET   /projects                 -> Project[]
POST  /projects {title}         -> Project
GET   /projects/{id}            -> Project
```

When the URL has a project id (`/p/<project_id>/...`) the frontend can skip the picker and load the project directly.

### Story graph page

The main canvas. Shows the primary branch's beats in sequence with alternate branches forking off where they were created.

```
GET   /projects/{id}/branches
        -> Branch[]
        (all branches in the project, build the tree from parent_branch_id)

GET   /projects/{id}/graph?branch_id=X
        -> {
             branch: Branch,
             beats: Beat[],              // ordered by sequence_index_in_branch
             characters: CharacterView[],// all chars touching any beat in this branch
             themes: ThemeView[],
             settings: SettingView[],
           }

GET   /beats/{id}
        -> {
             beat: Beat,
             characters: CharacterView[],
             themes: ThemeView[],
             settings: SettingView[],
           }

POST  /branches/fork
        body { parent_branch_id, from_beat_id, name }
        -> Branch

POST  /branches/{id}/promote    -> Project   // updates primary_branch_id
POST  /branches/{id}/transition
        body { event }
        -> Branch
        (event: "switch_to_dormant" | "switch_to_active" | "commit" | "abandon" | "revive")
```

The 3-fork cap is enforced in `POST /branches/fork`. If a beat already has 3 alternate branches, it returns `409 Conflict` with `code: "fork_cap_exceeded"`.

### World page (characters, themes, settings)

Could be one page with tabs or three pages. Backend serves them the same way.

```
GET   /projects/{id}/characters?branch_id=X   -> CharacterView[]
GET   /projects/{id}/themes?branch_id=X       -> ThemeView[]
GET   /projects/{id}/settings?branch_id=X     -> SettingView[]

GET   /characters/{id}?branch_id=X
        -> { view: CharacterView, beats: Beat[] }
GET   /themes/{id}?branch_id=X                -> { view, beats }
GET   /settings/{id}?branch_id=X              -> { view, beats }
```

All views are branch-scoped (base + overlay merged for that branch). When the active branch changes, refetch. The same character's properties can differ across branches.

### Conversation (NLI)

```
POST  /conversation/turn
        body { branch_id, content }
        -> { turn_id, reply, suggested_actions? }
```

The response is intentionally thin. The bot's side effects (new beats, new issues, primary promotion) land in the DB and arrive over Realtime, not in this response body. The only thing the response carries beyond the reply itself is `suggested_actions`, which is how the bot nudges the frontend to do UI-state changes Realtime can't deliver.

Right now there's one action type:

```typescript
{ type: "switch_branch", branch_id: UUID, label: string }
```

The frontend can either auto-apply it (update URL to the new branch) or render it as a clickable confirmation in the chat. Frontend's call. Most turns return an empty array or omit the field.

**Latency:** the POST is synchronous and waits for extraction and delta apply, roughly 2 to 6 seconds with Gemini. Show the user's message optimistically, render a thinking indicator, then drop the bot reply when the response arrives.

**Dedup:** any beat the bot proposed during this turn also arrives via the Realtime `beats` channel. Dedupe by `beat.id` so it doesn't appear twice.

```
GET   /branches/{id}/conversation
        -> { turns: ConversationTurn[], has_more: boolean, next_cursor: string | null }
```

Pagination is optional. Defaults return the most recent 50 turns (newest first, reverse for chat display). To load older turns when the user scrolls to the top, pass `?before=<next_cursor>`. If the frontend never paginates, the writer just sees their most recent 50 turns. Same pattern Claude / ChatGPT use.

| Param  | Default | Use                                          |
|--------|---------|----------------------------------------------|
| limit  | 50      | how many turns to return (max 200)           |
| before | none    | ISO timestamp, only return turns older than this |

### Visualization pages

Three graphs, one per discourse level in Tian et al. 2024.

```
GET   /branches/{id}/viz/arc-curve
        -> {
             points: ArcPoint[],
             detected_arc: VonnegutArc | null,   // null if classify_arc cant tell yet
             declared_arc: VonnegutArc | null,   // what the writer said theyre aiming for
           }

// ArcPoint = {
//   beat_id, sequence_index, beat_logline,
//   valence: number | null,    // 0-1
//   arousal: number | null,    // 0-1
//   turning_point: TurningPoint | null,
// }

GET   /branches/{id}/viz/turning-points
        -> {
             tps: TurningPointMarker[],
             expected_positions: { tp1: 0.10, tp2: 0.30, tp3: 0.55, tp4: 0.75, tp5: 0.90 },
           }

// TurningPointMarker = {
//   kind: TurningPoint, beat_id, sequence_index, position_ratio: number,  // 0-1
// }

GET   /branches/{id}/viz/character-depth
        -> { characters: CharacterDepth[] }

// CharacterDepth = {
//   character_id, name,
//   beat_count, first_beat_sequence_index, last_beat_sequence_index,
//   beat_ids: UUID[],
// }

GET   /branches/{id}/viz/thematic-strength
        -> { themes: ThemeDensity[] }

// ThemeDensity = { theme_id, name, beat_count, beat_ids: UUID[] }
```

These are derived on each request, no caching yet. If they get slow at scale we'll memoize on the backend.

### Issues

Where to surface these is a frontend UX call (sidebar counter, inline beat badges, a "diagnostics" panel). Backend gives them the same way regardless.

```
GET   /branches/{id}/issues?status=open    -> Issue[]
        (omit the status param to get all statuses)

POST  /issues/{id}/acknowledge             -> Issue   // status -> "acknowledged"
POST  /issues/{id}/resolve                 -> Issue   // status -> "resolved"
```

The bot may auto-resolve issues when it detects the underlying contradiction is fixed. Frontend should rely on Realtime to pick those up.

## Realtime subscriptions

Use the Supabase JS client directly. RLS scopes everything to the writer's projects.

```typescript
// New beats appearing on a branch (proposed or committed by the bot)
supabase
  .channel(`beats:${branchId}`)
  .on('postgres_changes', {
    event: '*',
    schema: 'public',
    table: 'beats',
    filter: `branch_id=eq.${branchId}`,
  }, (payload) => { /* upsert into your beats store */ })
  .subscribe();

// New issues the bot flagged
supabase
  .channel(`issues:${branchId}`)
  .on('postgres_changes', {
    event: 'INSERT',
    schema: 'public',
    table: 'issues',
    filter: `branch_id=eq.${branchId}`,
  }, (payload) => { /* surface in the issues UI */ })
  .subscribe();

// Conversation turns (for multi-device sync or background turns)
supabase
  .channel(`turns:${branchId}`)
  .on('postgres_changes', {
    event: 'INSERT',
    schema: 'public',
    table: 'conversation_turns',
    filter: `branch_id=eq.${branchId}`,
  }, (payload) => { /* append to chat */ })
  .subscribe();

// Project changes (primary branch promotion, title rename)
supabase
  .channel(`project:${projectId}`)
  .on('postgres_changes', {
    event: 'UPDATE',
    schema: 'public',
    table: 'projects',
    filter: `id=eq.${projectId}`,
  }, (payload) => { /* refresh the project state */ })
  .subscribe();
```

Resubscribe whenever the active branch or active project changes. Tear down on unmount.

## Things the frontend decides

Backend stays neutral on these. Pick whatever serves the UX best.

- **Active project and active branch state.** URL params (`/p/<project_id>/b/<branch_id>/...`) are the recommended default since they're bookmarkable and multi-tab safe, but cookie or localstorage works if there's a reason. Backend just needs `branch_id` in the relevant query params.
- **Loading, empty, error states.** Every list endpoint can return an empty array, every detail endpoint can 404, every request can fail with the error shape above.
- **Optimistic updates on the chat.** Show the user's message immediately on send. Render the bot reply when the POST returns.
- **Beat dedup between the turn response and Realtime.** The same proposed beat arrives twice. Dedupe by `beat.id`.
- **Whether character/theme/setting lists show all project entities or only those referenced in the current branch.** Default endpoints return everything project-scoped. Add `?only_referenced=true` if you want to filter to entities that appear in at least one beat of the active branch.
- **How to render `suggested_actions`.** Auto-apply (e.g. just switch the URL when the bot says to), or show as clickable chips in the chat for the writer to confirm. Both are valid.

## Status

All endpoints above are live. Run `make dev-mock` to bring up the full stack (no DB required) — it uses `MockExtractorV2` in `backend/app/services/extractor_v2.py` for deterministic bot replies. Set `EXTRACTOR_BACKEND=gemini` in `backend/.env` to switch to live Gemini extraction without changing anything else.
