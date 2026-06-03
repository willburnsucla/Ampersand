/**
 * AuthClient — thin wrapper over Supabase auth.
 *
 * Architectural invariant #7: Components import getToken/userId from here, not from @supabase/* directly. Makes it easy to swap auth providers —> the exported signatures below are the contract the rest of the app depends on.
 *
 * For the frontend team building the sign-in/sign-up form: call useSignIn() and useSignUp()
 */
'use client'

import { useEffect, useState } from 'react'
import { createClient } from '@/lib/supabase/client'

/**
 * useGetToken returns a function that yields the current access token (JWT), or null if signed out. Always reads via getSession() so it picks up the token the middleware keeps fresh; never caches it.
 */
export function useGetToken() {
  const supabase = createClient()
  return async (): Promise<string | null> => {
    const {
      data: { session },
    } = await supabase.auth.getSession()
    return session?.access_token ?? null
  }
}

/**
 * useUserId with three states:
 *   undefined means we are still loading (don't redirect yet)
 *   null      means signed out
 *   string   means the Supabase user UUID (the JWT `sub`, == backend owner_id)
 */
export function useUserId(): string | null | undefined {
  const [userId, setUserId] = useState<string | null | undefined>(undefined)

  useEffect(() => {
    const supabase = createClient()

    supabase.auth.getSession().then(({ data: { session } }) => {
      setUserId(session?.user?.id ?? null)
    })

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setUserId(session?.user?.id ?? null)
    })

    return () => subscription.unsubscribe()
  }, [])

  return userId
}

/**
 * useSignIn for the future sign-in form. Email + password.
 * Returns { error } -> null on success, a message string on failure.
 */
export function useSignIn() {
  const supabase = createClient()
  return async (
    email: string,
    password: string,
  ): Promise<{ error: string | null }> => {
    const { error } = await supabase.auth.signInWithPassword({ email, password })
    return { error: error?.message ?? null }
  }
}

/**
 * useSignUp for the future create-account form. Email + password.
 * Returns { error } —> null on success, a message string on failure.
 * (Email confirmation is OFF in the Supabase dashboard, so signup is instant.)
 */
export function useSignUp() {
  const supabase = createClient()
  return async (
    email: string,
    password: string,
  ): Promise<{ error: string | null }> => {
    const { error } = await supabase.auth.signUp({ email, password })
    return { error: error?.message ?? null }
  }
}
