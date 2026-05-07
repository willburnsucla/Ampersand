/**
 * GraphStore — T-019 (stub).
 *
 * Zustand store — single source of truth for the story graph on the client.
 * Full implementation (sequence tracking, gap detection, resync) in Week 2.
 *
 * Idempotency invariant (#8): applying the same DeltaOp twice must produce
 * the same result as applying it once. add_node/add_edge = upsert by id.
 *
 * Architectural invariant #7: Components import from graph-store, not from
 * Zustand directly. The store is the only client-side mutation point for graph state.
 */
import { create } from 'zustand'

export type NodeType = 'character' | 'beat' | 'theme' | 'world_element' | 'thread'
export type NodeStatus = 'proposed' | 'committed' | 'rejected'

export interface StoryNode {
  id: string
  story_id: string
  type: NodeType
  status: NodeStatus
  branch_tags: string[]
  provenance_turn_id: string
  properties: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface StoryEdge {
  id: string
  source_id: string
  target_id: string
  relation: string
  branch_tags: string[]
  provenance_turn_id: string
}

interface GraphStoreState {
  // Normalized graph
  nodes: Record<string, StoryNode>
  edges: Record<string, StoryEdge>

  // Index by type for fast lookup
  byType: Record<NodeType, string[]>

  // Active context
  loadedFor: { storyId: string; branchId: string } | null
  lastAppliedSequence: number
  resyncInFlight: boolean

  // Actions
  loadGraph: (storyId: string, branchId: string, snapshot: {
    nodes: StoryNode[]
    edges: StoryEdge[]
    last_applied_sequence: number
  }) => void
  applyDelta: (event: {
    story_id: string
    branch_id: string
    sequence_number: number
    applied_ops: unknown[]
  }, resync: () => Promise<void>) => void
  reset: () => void
}

function buildByType(nodes: Record<string, StoryNode>): Record<NodeType, string[]> {
  const result: Record<NodeType, string[]> = {
    character: [], beat: [], theme: [], world_element: [], thread: [],
  }
  for (const node of Object.values(nodes)) {
    result[node.type]?.push(node.id)
  }
  return result
}

export const useGraphStore = create<GraphStoreState>((set, get) => ({
  nodes: {},
  edges: {},
  byType: { character: [], beat: [], theme: [], world_element: [], thread: [] },
  loadedFor: null,
  lastAppliedSequence: 0,
  resyncInFlight: false,

  loadGraph(storyId, branchId, snapshot) {
    const nodes: Record<string, StoryNode> = {}
    for (const n of snapshot.nodes) nodes[n.id] = n
    const edges: Record<string, StoryEdge> = {}
    for (const e of snapshot.edges) edges[e.id] = e

    set({
      nodes,
      edges,
      byType: buildByType(nodes),
      loadedFor: { storyId, branchId },
      lastAppliedSequence: snapshot.last_applied_sequence,
      resyncInFlight: false,
    })
  },

  applyDelta(event, resync) {
    const state = get()

    // 1. Ignore events for wrong story/branch
    if (
      !state.loadedFor ||
      state.loadedFor.storyId !== event.story_id ||
      state.loadedFor.branchId !== event.branch_id
    ) return

    // 2. Duplicate — drop silently
    if (event.sequence_number <= state.lastAppliedSequence) return

    // 3. Gap detected — trigger resync, drop event
    if (event.sequence_number > state.lastAppliedSequence + 1) {
      if (!state.resyncInFlight) {
        set({ resyncInFlight: true })
        resync().finally(() => set({ resyncInFlight: false }))
      }
      return
    }

    // 4. In-order — apply ops (idempotent upsert)
    const nodes = { ...state.nodes }
    const edges = { ...state.edges }

    for (const op of event.applied_ops as Array<{ kind: string; node?: StoryNode; edge?: StoryEdge; node_id?: string; key?: string; value?: unknown; status?: NodeStatus }>) {
      if (op.kind === 'add_node' && op.node) {
        nodes[op.node.id] = op.node  // upsert
      } else if (op.kind === 'add_edge' && op.edge) {
        edges[op.edge.id] = op.edge  // upsert
      } else if (op.kind === 'update_property' && op.node_id && op.key !== undefined) {
        if (nodes[op.node_id]) {
          nodes[op.node_id] = {
            ...nodes[op.node_id],
            properties: { ...nodes[op.node_id].properties, [op.key]: op.value },
          }
        }
      } else if (op.kind === 'set_status' && op.node_id && op.status) {
        if (nodes[op.node_id]) {
          nodes[op.node_id] = { ...nodes[op.node_id], status: op.status }
        }
      } else if (op.kind === 'add_branch_tag') {
        // set-add — handled by server; client reflects updated branch_tags on next snapshot
      }
    }

    set({
      nodes,
      edges,
      byType: buildByType(nodes),
      lastAppliedSequence: event.sequence_number,
    })
  },

  reset() {
    set({
      nodes: {},
      edges: {},
      byType: { character: [], beat: [], theme: [], world_element: [], thread: [] },
      loadedFor: null,
      lastAppliedSequence: 0,
      resyncInFlight: false,
    })
  },
}))

// ── Selector hooks ────────────────────────────────────────────────────────────

export function useNode(id: string): StoryNode | undefined {
  return useGraphStore((s) => s.nodes[id])
}

export function useNodesByType(type: NodeType): StoryNode[] {
  return useGraphStore((s) => {
    const ids = s.byType[type] ?? []
    return ids.map((id) => s.nodes[id]).filter(Boolean) as StoryNode[]
  })
}

export function useGraphReady(): boolean {
  return useGraphStore((s) => s.loadedFor !== null)
}
