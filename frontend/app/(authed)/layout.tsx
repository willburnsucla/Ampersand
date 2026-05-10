'use client'

import { RedirectToSignIn, useAuth } from '@clerk/nextjs'
import { StoryProvider } from '@/lib/story-context'
import { Sidebar } from '@/components/nav/sidebar'

export default function AuthedLayout({ children }: { children: React.ReactNode }) {
  const { isSignedIn, isLoaded } = useAuth()

  if (!isLoaded) return null
  if (!isSignedIn) return <RedirectToSignIn />

  return (
    <StoryProvider>
      <div className="flex h-screen overflow-hidden bg-background">
        <Sidebar />
        <main className="flex-1 overflow-auto">
          {children}
        </main>
      </div>
    </StoryProvider>
  )
}
