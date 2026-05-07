'use client'

import { RedirectToSignIn } from '@clerk/nextjs'
import { useAuth } from '@clerk/nextjs'

export default function AuthedLayout({ children }: { children: React.ReactNode }) {
  const { isSignedIn, isLoaded } = useAuth()

  if (!isLoaded) return null
  if (!isSignedIn) return <RedirectToSignIn />
  return <>{children}</>
}
