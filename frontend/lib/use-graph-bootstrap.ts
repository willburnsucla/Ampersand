'use client'

/**
 * useGraphBootstrap — fetches initial graph snapshot and wires SSE updates.
 *
 * On mount:
 *   1. Fetches graph snapshot → graphStore.loadGraph()
 *   2. Opens SSE subscription → graphStore.applyDelta() on each event
 *   3. On SSE reconnect → re-fetches snapshot to fill any missed events
 *
 * Uses a ref for the resync closure to avoid stale closure bugs with applyDelta.
 */

import { useEffect, useRef, useCallback } from 'react'
import { HttpApiClient } from '@/lib/api-client'
import { useGetToken } from '@/lib/auth-client'
import { sseClient } from '@/lib/sse-client'
import { useGraphStore } from '@/lib/graph-store'
import type { GraphSnapshot } from '@/lib/types'

export function useGraphBootstrap(storyId: string | null, branchId: string | null) {
  const getToken = useGetToken()
  const loadGraph = useGraphStore((s) => s.loadGraph)
  const applyDelta = useGraphStore((s) => s.applyDelta)
  const reset = useGraphStore((s) => s.reset)

  // Stable ref so the resync closure inside applyDelta doesn't capture stale values
  const ctxRef = useRef({ storyId, branchId, getToken, loadGraph })
  ctxRef.current = { storyId, branchId, getToken, loadGraph }

  const fetchSnapshot = useCallback(async () => {
    const { storyId, branchId, getToken, loadGraph } = ctxRef.current
    if (!storyId || !branchId) return
    const client = new HttpApiClient(getToken)
    const snapshot = (await client.getGraph(storyId, branchId)) as GraphSnapshot
    loadGraph(storyId, branchId, snapshot)
  }, []) // empty deps — always reads from ref

  useEffect(() => {
    if (!storyId || !branchId) return

    reset()
    fetchSnapshot()

    const sub = sseClient.subscribe(storyId, {
      onEvent: (event) => {
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
  }, [storyId, branchId, fetchSnapshot, applyDelta, reset])
}
