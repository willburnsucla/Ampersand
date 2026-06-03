# Auth — frontend contract
Supabase, email + password. The plumbing is wired. The sign-in / create-account form is the frontend team's to build; this is the contract for it.

## Helpers
From `@/lib/auth-client`:
const signIn = useSignIn() 
const signUp = useSignUp()

`error === null` is success; the session cookie is set for you, so route to a
protected page (e.g. `router.push('/conversation')`). A string `error` is the
failure message to surface on the form.

Build the form at `app/sign-in/page.tsx` (currently a placeholder).

## useUserId — tri-state
```ts
const userId = useUserId()
// Either string, null, undefined
```
- `undefined` — loading; render nothing.
- `null` — signed out; the middleware already redirects to `/sign-in`.
- `string` — the user's UUID (the JWT `sub`, == backend `owner_id`).

## How it fits together
- The token lives in a cookie after sign-in -> we what never read it directly.
- `middleware.ts` gates page navigation and refreshes the cookie.
- `api-client` attaches the token as `Authorization: Bearer` on every backend call -> no token wiring needed in components.
- Protected routes live under `app/(authed)/`; unauthenticated users are redirected to `/sign-in`.

Architectural invariant #7: components reach auth only through
`@/lib/auth-client`, never `@supabase/*` directly. Don't cache the token.

## One-time setup
`.env.local`:
NEXT_PUBLIC_SUPABASE_URL=...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000

