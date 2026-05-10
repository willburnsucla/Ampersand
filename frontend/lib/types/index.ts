/**
 * Hand-authored TypeScript types mirroring backend Pydantic models.
 * Delete this file and import from /lib/types/generated/ once `make codegen` runs.
 */

import type { StoryNode, StoryEdge } from '@/lib/graph-store'

export interface Story {
  id: string
  owner_id: string
  title: string
  active_branch_id: string | null
  created_at: string
}

export interface Branch {
  id: string
  story_id: string
  parent_branch_id: string | null
  state: 'active' | 'dormant' | 'committed' | 'graveyard'
  name: string | null
  created_from_beat_id: string | null
  created_at: string
}

export interface TurnResult {
  turn_id: string
  reply: string  // NOTE: field is `reply`, not `reply_text`
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
