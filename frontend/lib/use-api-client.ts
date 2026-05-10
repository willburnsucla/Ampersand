'use client'

/**
 * useApiClient — returns a stable HttpApiClient instance whose getToken
 * always reads the latest from Clerk via a ref.
 *
 * Why: Clerk's `getToken` returns a NEW function reference on every render.
 * Using it directly as a useMemo/useEffect dep causes infinite re-render loops.
 * This hook wraps the ref pattern in one place so callers don't have to.
 */

import { useMemo, useRef } from 'react'
import { HttpApiClient } from '@/lib/api-client'
import { useGetToken } from '@/lib/auth-client'

export function useApiClient(): HttpApiClient {
  const getToken = useGetToken()
  const getTokenRef = useRef(getToken)
  getTokenRef.current = getToken

  // Stable client across all renders — the ref always has the latest getToken
  return useMemo(
    () =>
      new HttpApiClient((...args: Parameters<typeof getTokenRef.current>) =>
        getTokenRef.current(...args),
      ),
    [],
  )
}
