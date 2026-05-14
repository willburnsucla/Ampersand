'use client'

/**
 * useGraphBootstrap — fetches initial graph snapshot and wires SSE updates
 * for the given (storyId, branchId).
 *
 * On mount / context change:
 *   1. Reset graph store (clears stale data from previous context)
 *   2. Fetch snapshot → graphStore.loadGraph()
 *   3. Open SSE subscription → graphStore.applyDelta() per event
 *   4. On SSE reconnect → re-fetch snapshot to fill missed events
 *
 * Race protection: each effect run gets a unique `requestToken`. In-flight
 * fetches that complete after a context change are discarded — prevents
 * stale snapshots from overwriting fresh ones during rapid branch switches.
 */

import { useEffect, useRef, useCallback } from 'react'
import { useApiClient } from '@/lib/use-api-client'
import { sseClient } from '@/lib/sse-client'
import { useGraphStore } from '@/lib/graph-store'
import type { GraphSnapshot } from '@/lib/types'

export function useGraphBootstrap(storyId: string | null, branchId: string | null) {
  const apiClient = useApiClient()
  const loadGraph = useGraphStore((s) => s.loadGraph)
  const applyDelta = useGraphStore((s) => s.applyDelta)
  const reset = useGraphStore((s) => s.reset)

  // Monotonic request token — incremented per effect run.
  // Closures capture their own token and bail if it's stale.
  const requestTokenRef = useRef(0)

  // Stable ref so the resync closure inside applyDelta always sees the
  // latest context, not a captured-at-mount snapshot
  const ctxRef = useRef({ storyId, branchId, apiClient, loadGraph })
  ctxRef.current = { storyId, branchId, apiClient, loadGraph }

  // resync used by applyDelta on sequence gaps; must be stable + always-fresh
  const fetchSnapshot = useCallback(async () => {
    const { storyId, branchId, apiClient, loadGraph } = ctxRef.current
    if (!storyId || !branchId) return
    const myToken = requestTokenRef.current
    const snapshot = (await apiClient.getGraph(storyId, branchId)) as GraphSnapshot
    // Discard if context changed mid-flight
    if (myToken !== requestTokenRef.current) return
    loadGraph(storyId, branchId, snapshot)
  }, [])

  useEffect(() => {
    if (!storyId || !branchId) return

    // New context — bump token so any in-flight fetches from previous run are discarded
    requestTokenRef.current += 1
    const myToken = requestTokenRef.current

    reset()

    // Initial snapshot
    void (async () => {
      try {
        const snapshot = (await apiClient.getGraph(storyId, branchId)) as GraphSnapshot
        if (myToken !== requestTokenRef.current) return
        loadGraph(storyId, branchId, snapshot)
      } catch (err) {
        console.warn('[useGraphBootstrap] snapshot fetch failed:', err)
      }
    })()

    // SSE subscription
    const sub = sseClient.subscribe(storyId, {
      onEvent: (event) => {
        // Drop events for the wrong branch (graph store also guards this,
        // but skipping early avoids unnecessary work)
        if (event.branch_id !== branchId) return
        applyDelta(event, fetchSnapshot)
      },
      onReconnected: fetchSnapshot,
      onError: (err) => {
        console.warn('[SSE] error:', err.message)
      },
    })

    return () => {
      sub.unsubscribe()
    }
  }, [storyId, branchId, apiClient, fetchSnapshot, applyDelta, loadGraph, reset])
}
