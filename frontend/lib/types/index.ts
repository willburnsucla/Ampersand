/**
 * Hand-authored TypeScript types mirroring backend Pydantic models.
 * Delete this file and import from /lib/types/generated/ once `make codegen` runs.
 */

import type { StoryNode, StoryEdge } from '@/lib/graph-store'

// ── v1 (legacy) ───────────────────────────────────────────────────────────────

export interface Story {
  id: string
  owner_id: string
  title: string
  active_branch_id: string | null
  created_at: string
}

export interface TurnResult {
  turn_id: string
  reply: string
  applied_delta: {
    delta: { turn_id: string; ops: unknown[] }
    affected_node_ids: string[]
    affected_edge_ids: string[]
  }
}

export interface GraphSnapshot {
  story_id: string
  branch_id: string
  nodes: StoryNode[]
  edges: StoryEdge[]
  last_applied_sequence: number
  generated_at: string
}

// ── v2 ────────────────────────────────────────────────────────────────────────

export interface Project {
  id: string
  owner_id: string
  title: string
  primary_branch_id: string | null
  created_at: string
  updated_at: string
}

export interface Branch {
  id: string
  project_id: string
  parent_branch_id: string | null
  created_from_beat_id: string | null
  name: string | null
  state: 'active' | 'dormant' | 'committed' | 'graveyard'
  declared_arc: string | null
  created_at: string
}

export interface Beat {
  id: string
  branch_id: string
  sequence_index_in_branch: number
  logline: string
  content: Record<string, unknown>
  turning_point: string | null
  valence: number | null
  arousal: number | null
  status: 'proposed' | 'committed' | 'rejected'
  created_at: string
  updated_at: string
}

export interface Character {
  id: string
  project_id: string
  name: string
  base_properties: Record<string, unknown>
  status: 'proposed' | 'committed' | 'rejected'
  created_at: string
  updated_at: string
}

export interface Theme {
  id: string
  project_id: string
  name: string
  base_properties: Record<string, unknown>
  status: 'proposed' | 'committed' | 'rejected'
  created_at: string
  updated_at: string
}

export interface Setting {
  id: string
  project_id: string
  name: string
  base_properties: Record<string, unknown>
  status: 'proposed' | 'committed' | 'rejected'
  created_at: string
  updated_at: string
}

export interface Issue {
  id: string
  branch_id: string
  type:
    | 'contradiction'
    | 'timeline_gap'
    | 'character_inconsistency'
    | 'world_rule_violation'
    | 'pacing_anomaly'
    | 'framework_misuse'
  description: string
  related_beat_ids: string[]
  related_entity_ids: string[]
  status: 'open' | 'acknowledged' | 'resolved'
  detected_at: string
  resolved_at: string | null
}

export interface ConversationTurn {
  id: string
  branch_id: string
  role: 'writer' | 'assistant'
  content: string
  created_at: string
}

export interface TurnResultV2 {
  reply: string
  beat: Beat | null
  issues: Issue[]
}
