/**
 * AuthClient — thin wrapper over Clerk's useAuth hook.
 *
 * Architectural invariant #7: Components import getToken from here,
 * not from @clerk/nextjs directly. Makes it easy to swap auth providers.
 */
'use client'

import { useAuth } from '@clerk/nextjs'

export function useGetToken() {
  const { getToken } = useAuth()
  return getToken
}

export function useUserId(): string | null | undefined {
  const { userId } = useAuth()
  return userId
}
