/**
 * SseClient — T-018 (stub).
 *
 * Wraps EventSource. Full implementation (reconnection, sequence tracking) in Week 2.
 * The `onReconnected` callback triggers GraphStore.resync() (T-019).
 *
 * Architectural invariant #7: The only way to receive SSE events in the frontend.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000'

export interface GraphDeltaEvent {
  schema_version: 1
  story_id: string
  branch_id: string
  turn_id: string
  sequence_number: number
  applied_ops: unknown[]
  timestamp: string
}

export interface Subscription {
  unsubscribe(): void
}

export interface SseClient {
  subscribe(
    storyId: string,
    handlers: {
      onEvent: (e: GraphDeltaEvent) => void
      onReconnected?: () => void
      onError?: (err: Error) => void
    },
  ): Subscription
}

// ── EventSourceSseClient ──────────────────────────────────────────────────────

export class EventSourceSseClient implements SseClient {
  subscribe(
    storyId: string,
    handlers: {
      onEvent: (e: GraphDeltaEvent) => void
      onReconnected?: () => void
      onError?: (err: Error) => void
    },
  ): Subscription {
    const url = `${API_BASE}/api/v1/stories/${storyId}/events`
    const source = new EventSource(url)

    source.addEventListener('graph_delta', (raw: MessageEvent) => {
      try {
        const event = JSON.parse(raw.data) as GraphDeltaEvent
        handlers.onEvent(event)
      } catch (err) {
        handlers.onError?.(new Error(`Failed to parse SSE event: ${err}`))
      }
    })

    source.onerror = () => {
      handlers.onError?.(new Error('SSE connection error'))
      // EventSource auto-reconnects; fire onReconnected when it succeeds
      source.onopen = () => handlers.onReconnected?.()
    }

    return {
      unsubscribe() {
        source.close()
      },
    }
  }
}

// Default singleton — import this in components
export const sseClient: SseClient = new EventSourceSseClient()
