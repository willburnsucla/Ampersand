'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { useSignIn, useSignUp } from '@/lib/auth-client'

type Mode = 'signin' | 'signup'

export default function SignInPage() {
  const router = useRouter()
  const signIn = useSignIn()
  const signUp = useSignUp()

  const [mode, setMode] = useState<Mode>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)
    setLoading(true)

    const fn = mode === 'signin' ? signIn : signUp
    const { error } = await fn(email, password)

    setLoading(false)
    if (error) {
      setError(error)
    } else {
      router.push('/')
    }
  }

  return (
    <main className="flex h-screen items-center justify-center bg-background">
      <div className="w-full max-w-sm space-y-6 px-6">
        <h1 className="text-2xl font-semibold tracking-tight text-center">Ampersand</h1>

        {/* Mode toggle */}
        <div className="flex border border-border rounded-md overflow-hidden text-sm">
          {(['signin', 'signup'] as Mode[]).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => { setMode(m); setError(null) }}
              className={`flex-1 py-2 font-medium transition-colors ${
                mode === m
                  ? 'bg-foreground text-background'
                  : 'text-foreground/60 hover:text-foreground/90'
              }`}
            >
              {m === 'signin' ? 'Sign in' : 'Create account'}
            </button>
          ))}
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <input
            type="email"
            required
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm
                       placeholder:text-foreground/40 focus:outline-none focus:ring-1 focus:ring-foreground/20"
          />
          <input
            type="password"
            required
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm
                       placeholder:text-foreground/40 focus:outline-none focus:ring-1 focus:ring-foreground/20"
          />
          {error && (
            <p className="text-sm text-red-500">{error}</p>
          )}
          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-md bg-foreground text-background py-2 text-sm font-medium
                       hover:bg-foreground/90 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? 'Please wait…' : mode === 'signin' ? 'Sign in' : 'Create account'}
          </button>
        </form>
      </div>
    </main>
  )
}
