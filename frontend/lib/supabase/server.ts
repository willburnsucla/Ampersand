/**
 * Server-side Supabase client for Route Handlers and Server Components.
 *
 * Wired to Next's cookies() so the session is read from (and written back to) the request cookies. In a Server Component the set() calls can throw because cookies are read-only there
 */
import { createServerClient } from '@supabase/ssr'
import { cookies } from 'next/headers'

export async function createClient() {
  const cookieStore = await cookies()

  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll()
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options),
            )
          } catch {
            // Called from a Server Component where cookies are read only here.
            // Safe to ignore as middleware refreshes the session cookie.
          }
        },
      },
    },
  )
}
