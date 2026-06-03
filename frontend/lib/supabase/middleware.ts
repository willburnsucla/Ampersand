/**
 * updateSession — runs in Next middleware on every request.
 *
 * Two jobs:
 *  1. Refresh the Supabase session cookie (access token expires  roughly hourly; the refresh token is traded for a fresh one and written back via Set-Cookie).
 *  2. Return the validated `user` so the caller can gate page navigation.
 *
 * Gating uses getUser() (server-validated), NOT getSession() (reads the cookie without revalidating).
 */
import { createServerClient } from '@supabase/ssr'
import { NextResponse, type NextRequest } from 'next/server'

export async function updateSession(request: NextRequest) {
  let response = NextResponse.next({ request })

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll()
        },
        setAll(cookiesToSet) {
          // Write onto both the request (for downstream reads) and the
          // response (so the browser stores the refreshed cookie).
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value),
          )
          response = NextResponse.next({ request })
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options),
          )
        },
      },
    },
  )

  const {
    data: { user },
  } = await supabase.auth.getUser()

  return { response, user }
}
