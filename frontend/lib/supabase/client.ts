/**
 * Browser side Supabase client.
 * Used by client components/the auth client hooks. Reads the session from cookies that the middleware keeps fresh.
 */
import { createBrowserClient } from '@supabase/ssr'

export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  )
}
